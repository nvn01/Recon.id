"""
Facebook Marketplace connector for RECON scraper diagnostics.

This connector is intentionally still outside database ingestion:
- normalizes visible Marketplace listings into the Prisma-facing listing shape
- keeps run state, lock files, and logs in scraper-side local files
- supports one-shot checks and minute-level watch diagnostics
- uses Playwright because Marketplace is JS/session-driven

First-time local session setup:
    python "scraper/facebook/facebook_marketplace.py" --login

One-shot normalized JSON:
    python "scraper/facebook/facebook_marketplace.py" --once --query vga --limit 15 --format json

Minute-level diagnostic watcher:
    python "scraper/facebook/facebook_marketplace.py" --watch --interval 60 --query vga --limit 15 --details
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

try:
    from scraper.facebook.embedded import extract_marketplace_records
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scraper.facebook.embedded import extract_marketplace_records


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


PLATFORM = "FACEBOOK"
DEFAULT_LOCATION = "jakarta"
DEFAULT_CATEGORY_ID = "479353692612078"  # Facebook Marketplace Electronics category
SCRIPT_DIR = Path(__file__).resolve().parent
SCRAPER_DIR = SCRIPT_DIR.parent
DEFAULT_PROFILE_DIR = SCRIPT_DIR / ".facebook-profile"
DEFAULT_STATE_DIR = SCRAPER_DIR / ".state"
DEFAULT_LOG_DIR = SCRAPER_DIR / ".logs"
DEFAULT_STATE_FILE = DEFAULT_STATE_DIR / "facebook_marketplace.json"
DEFAULT_LOCK_FILE = DEFAULT_STATE_DIR / "facebook_marketplace.lock"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "facebook_marketplace.jsonl"
DEFAULT_TARGETS_FILE = SCRIPT_DIR / "source_targets.json"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

DEFAULT_RECON_KEYWORDS = (
    "vga",
    "gpu",
    "rtx",
    "gtx",
    "radeon",
    "geforce",
    "nvidia",
    "amd",
    "rx 580",
    "rx580",
    "pc",
    "komputer",
    "laptop",
    "monitor",
    "keyboard",
    "mouse",
    "gaming",
    "ram",
    "ssd",
    "hdd",
    "processor",
    "prosesor",
    "intel",
    "ryzen",
    "core i",
    "motherboard",
    "mainboard",
    "psu",
    "playstation",
    "ps4",
    "ps5",
    "xbox",
    "nintendo",
    "steam deck",
)

DEFAULT_BLOCKED_KEYWORDS = (
    "yamaha",
    "vega r",
    "vega zr",
    "motor vega",
    "kampas rem",
    "sparepart motor",
    "iphone",
    "ipad",
    "oppo",
    "vivo",
    "xiaomi",
    "redmi",
    "realme",
    "samsung galaxy",
    "android",
    "indihome",
    "wifi murah",
    "paket wifi",
    "mesin cuci",
    "kulkas",
    "lemari es",
    "smart tv",
    "tv led",
    "cctv",
    "kamera",
    "printer",
    "ac split",
    "remote tv",
    "kabel vga",
    "converter vga",
    "hdmi to vga",
)

SOLD_MARKERS = (
    "sold out",
    "sold",
    "terjual",
    "laku",
    "booked",
)
ASK_PRICE_MARKERS = (
    "ask price",
    "askprice",
    "tanya harga",
    "tanya admin",
    "tanyakan harga",
    "hubungi",
    "dm",
    "pm",
    "inbox",
    "chat",
)
FREE_PRICE_MARKERS = (
    "gratis",
    "free",
)
LOCATION_PREFIXES = (
    "lokasi",
    "location",
    "loc",
    "cod",
)
CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("GPU", ("gpu", "vga", "rtx", "gtx", "radeon", "geforce")),
    ("CPU", ("cpu", "processor", "prosesor", "ryzen", "core i", "intel i3", "intel i5", "intel i7", "intel i9")),
    ("RAM", ("ram", "ddr3", "ddr4", "ddr5", "sodimm", "so-dimm", "memory")),
    ("Storage", ("ssd", "hdd", "nvme", "harddisk", "hard disk", "m.2", "sata")),
    ("Motherboard", ("motherboard", "mainboard", "mobo")),
    ("Monitor", ("monitor", "lcd", "ips", "oled", "va panel", "hz")),
    ("Keyboard", ("keyboard", "keychron", "mechanical", "mecha")),
    ("Mouse", ("mouse", "logitech g", "razer viper", "deathadder")),
    ("Desktop PC", ("pc rakitan", "desktop", "mini pc", "workstation", "komputer")),
    ("Handheld PC", ("legion go", "steam deck", "rog ally", "handheld pc")),
    ("Laptop", ("laptop", "notebook", "thinkpad", "macbook", "vivobook", "zenbook", "ideapad", "legion")),
    ("Peripheral", ("headset", "earphone", "speaker", "webcam", "microphone", "mic")),
)
BRAND_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Apple", ("apple", "macbook", "imac", "mac mini")),
    ("ASUS", ("asus", "rog", "tuf")),
    ("Acer", ("acer", "predator")),
    ("Lenovo", ("lenovo", "thinkpad", "legion", "ideapad")),
    ("HP", ("hp", "hewlett packard", "omen", "victus")),
    ("Dell", ("dell", "alienware")),
    ("MSI", ("msi",)),
    ("Gigabyte", ("gigabyte", "aorus")),
    ("ASRock", ("asrock",)),
    ("Intel", ("intel",)),
    ("AMD", ("amd", "ryzen", "radeon")),
    ("NVIDIA", ("nvidia", "geforce")),
    ("Zotac", ("zotac",)),
    ("Inno3D", ("inno3d", "inno 3d")),
    ("Sapphire", ("sapphire", "saphire")),
    ("PowerColor", ("powercolor", "power color")),
    ("Palit", ("palit",)),
    ("Galax", ("galax",)),
    ("Colorful", ("colorful",)),
    ("Digital Alliance", ("digital alliance",)),
    ("Corsair", ("corsair",)),
    ("Kingston", ("kingston", "hyperx", "hyper x")),
    ("ADATA", ("adata", "xpg")),
    ("Samsung", ("samsung",)),
    ("Crucial", ("crucial",)),
    ("Western Digital", ("western digital", "wd", "wdc")),
    ("Seagate", ("seagate",)),
    ("Logitech", ("logitech",)),
    ("Razer", ("razer",)),
    ("SteelSeries", ("steelseries", "steel series")),
)


@dataclass(frozen=True)
class MarketplaceCard:
    item_id: str
    url: str
    price: str
    title: str
    location: str
    is_newly_listed: bool
    image_url: str
    image_alt: str
    raw_text: str
    price_amount: int | None = None
    seller_name: str = ""
    is_live: bool | None = None
    is_sold: bool | None = None
    is_pending: bool | None = None
    is_hidden: bool | None = None


@dataclass(frozen=True)
class MarketplaceDetail:
    posted: str = ""
    condition: str = ""
    description: str = ""
    approx_location: str = ""
    seller: str = ""
    error: str = ""


@dataclass(frozen=True)
class SourceTarget:
    id: str
    query: str
    label: str = ""
    groups: tuple[str, ...] = ()
    location: str = DEFAULT_LOCATION
    category_id: str = DEFAULT_CATEGORY_ID
    category_slug: str | None = None
    sort_by: str = "creation_time_descend"
    exact: bool = False
    radius: int | None = None
    days_since_listed: int | None = None
    delivery_method: str | None = None
    availability: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    condition: str | None = None
    cadence_seconds: int | None = None
    limit: int | None = None
    candidate_limit: int | None = None
    max_scrolls: int | None = None
    positive_keywords: tuple[str, ...] = ()
    blocked_keywords: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class MarketplaceTargetResult:
    target: SourceTarget
    url: str
    cards: list[MarketplaceCard]
    candidates_count: int
    matched_count: int
    skipped_count: int
    blocked_count: int
    matched_keywords: tuple[str, ...] = ()
    blocked_keywords: tuple[str, ...] = ()


class ConnectorBlockedError(RuntimeError):
    pass


class LoginBlockedError(ConnectorBlockedError):
    pass


class AlreadyRunningError(RuntimeError):
    pass


class FileLock(AbstractContextManager["FileLock"]):
    def __init__(self, path: Path, stale_seconds: int) -> None:
        self.path = path
        self.stale_seconds = stale_seconds
        self.fd: int | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._remove_stale_lock()
        try:
            self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise AlreadyRunningError(f"lock already exists: {self.path}") from exc

        payload = {
            "pid": os.getpid(),
            "created_at": now_utc().isoformat(),
        }
        os.write(self.fd, json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _remove_stale_lock(self) -> None:
        try:
            age = time.time() - self.path.stat().st_mtime
        except FileNotFoundError:
            return
        if age > self.stale_seconds:
            self.path.unlink(missing_ok=True)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = f"{value[:-1]}+00:00"
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def keyword_matches(text: str, keyword: str) -> bool:
    lower = text.lower()
    keyword_lower = keyword.lower().strip()
    if not keyword_lower:
        return False

    if keyword_lower in {
        "pc",
        "gpu",
        "vga",
        "rtx",
        "gtx",
        "ram",
        "ssd",
        "hdd",
        "psu",
        "oppo",
        "vivo",
        "redmi",
        "realme",
    }:
        return bool(re.search(rf"\b{re.escape(keyword_lower)}\b", lower))

    return keyword_lower in lower


def matched_keywords(card: MarketplaceCard, keywords: list[str]) -> list[str]:
    searchable_text = " ".join((card.raw_text, card.image_alt))
    return [keyword for keyword in keywords if keyword_matches(searchable_text, keyword)]


def build_search_url(target: SourceTarget) -> str:
    params: dict[str, str] = {"sortBy": target.sort_by}
    if not target.category_slug:
        params.update(
            {
                "query": target.query,
                "category_id": target.category_id,
                "exact": "true" if target.exact else "false",
            }
        )
    optional_params = {
        "radius": target.radius,
        "daysSinceListed": target.days_since_listed,
        "deliveryMethod": target.delivery_method,
        "availability": target.availability,
        "minPrice": target.min_price,
        "maxPrice": target.max_price,
        "itemCondition": target.condition,
    }
    for key, value in optional_params.items():
        if value is not None and value != "":
            params[key] = str(value)

    encoded = urllib.parse.urlencode(params)
    if target.category_slug:
        return f"https://www.facebook.com/marketplace/{target.location}/{target.category_slug}/?{encoded}"
    return f"https://www.facebook.com/marketplace/{target.location}/search?{encoded}"


def target_from_query(query: str, args: argparse.Namespace) -> SourceTarget:
    return SourceTarget(
        id=f"query-{slugify(query)}",
        label=f"Manual query: {query}",
        query=query,
        location=args.location,
        category_id=args.category_id,
    )


def load_source_targets(path: Path) -> list[SourceTarget]:
    if not path.exists():
        return []

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"failed to read source target file {path}: {exc}") from exc

    defaults = loaded.get("defaults", {}) if isinstance(loaded, dict) else {}
    records = loaded.get("targets", []) if isinstance(loaded, dict) else loaded
    if not isinstance(records, list):
        raise ValueError(f"source target file {path} must contain a list or a targets list")

    targets: list[SourceTarget] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"source target #{index} must be an object")
        merged = {**defaults, **record} if isinstance(defaults, dict) else record
        targets.append(source_target_from_record(merged, index))
    return targets


def source_target_from_record(record: dict[str, Any], index: int) -> SourceTarget:
    query = string_value(record.get("query"))
    category_slug = string_value(first_present(record, "categorySlug", "category_slug"))
    if category_slug and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", category_slug):
        raise ValueError(f"source target #{index} has invalid category slug")
    if not query and not category_slug:
        raise ValueError(f"source target #{index} is missing query or categorySlug")

    target_name = query or category_slug
    target_id = string_value(record.get("id")) or f"target-{index}-{slugify(target_name)}"
    return SourceTarget(
        id=target_id,
        label=string_value(record.get("label")),
        query=query or category_slug,
        groups=tuple(as_string_list(record.get("groups") or record.get("group"))),
        location=string_value(record.get("location")) or DEFAULT_LOCATION,
        category_id=string_value(first_present(record, "categoryId", "category_id")) or DEFAULT_CATEGORY_ID,
        category_slug=category_slug or None,
        sort_by=string_value(first_present(record, "sortBy", "sort_by")) or "creation_time_descend",
        exact=bool_value(record.get("exact"), default=False),
        radius=optional_int(record.get("radius")),
        days_since_listed=optional_int(first_present(record, "daysSinceListed", "days_since_listed")),
        delivery_method=string_value(first_present(record, "deliveryMethod", "delivery_method")) or None,
        availability=string_value(record.get("availability")) or None,
        min_price=optional_int(first_present(record, "minPrice", "min_price")),
        max_price=optional_int(first_present(record, "maxPrice", "max_price")),
        condition=string_value(first_present(record, "itemCondition", "condition")) or None,
        cadence_seconds=optional_int(first_present(record, "cadenceSeconds", "cadence_seconds")),
        limit=optional_int(record.get("limit")),
        candidate_limit=optional_int(first_present(record, "candidateLimit", "candidate_limit")),
        max_scrolls=optional_int(first_present(record, "maxScrolls", "max_scrolls")),
        positive_keywords=tuple(as_string_list(first_present(record, "positiveKeywords", "positive_keywords"))),
        blocked_keywords=tuple(as_string_list(first_present(record, "blockedKeywords", "blocked_keywords"))),
        notes=string_value(record.get("notes")),
    )


def resolve_targets(args: argparse.Namespace) -> list[SourceTarget]:
    targets: list[SourceTarget] = []
    target_file_targets: list[SourceTarget] = []
    needs_target_file = bool(args.target or args.target_group or args.list_targets)
    if needs_target_file:
        target_file_targets = load_source_targets(Path(args.targets_file))

    if args.target:
        by_id = {target.id: target for target in target_file_targets}
        missing = [target_id for target_id in args.target if target_id not in by_id]
        if missing:
            raise ValueError(f"unknown Facebook source target(s): {', '.join(missing)}")
        targets.extend(by_id[target_id] for target_id in args.target)

    if args.target_group:
        selected_ids = {target.id for target in targets}
        requested_groups = set(args.target_group)
        for target in target_file_targets:
            if target.id in selected_ids:
                continue
            if requested_groups.intersection(target.groups):
                targets.append(target)
                selected_ids.add(target.id)

    for query in args.query or []:
        targets.append(target_from_query(query, args))

    if targets:
        return dedupe_targets(targets)

    return [target_from_query("vga", args)]


def dedupe_targets(targets: Iterable[SourceTarget]) -> list[SourceTarget]:
    seen: set[str] = set()
    deduped: list[SourceTarget] = []
    for target in targets:
        key = target.id or target.query
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return deduped


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "marketplace"


def string_value(value: object) -> str:
    return str(value).strip() if value is not None else ""


def first_present(record: dict[str, Any], *keys: str) -> object:
    for key in keys:
        if key in record:
            return record[key]
    return None


def as_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def bool_value(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def compact_lines(value: str) -> list[str]:
    return [line.strip() for line in clean_text(value).splitlines() if line.strip()]


def parse_card(raw: dict[str, str]) -> MarketplaceCard:
    raw_text = clean_text(raw.get("text", ""))
    lines = compact_lines(raw_text)

    is_newly_listed = bool(lines and lines[0].lower() == "baru terdaftar")
    if is_newly_listed:
        lines = lines[1:]

    price = lines[0] if lines else ""
    title = lines[1] if len(lines) > 1 else ""
    location = " ".join(lines[2:]) if len(lines) > 2 else ""

    return MarketplaceCard(
        item_id=raw.get("itemId", ""),
        url=raw.get("href", ""),
        price=price,
        title=title,
        location=location,
        is_newly_listed=is_newly_listed,
        image_url=raw.get("image", "") or "",
        image_alt=raw.get("imageAlt", "") or "",
        raw_text=raw_text,
    )


def card_from_embedded_record(raw: dict[str, Any]) -> MarketplaceCard:
    return MarketplaceCard(
        item_id=str(raw.get("itemId") or ""),
        url=str(raw.get("href") or ""),
        price=str(raw.get("price") or ""),
        title=str(raw.get("title") or ""),
        location=str(raw.get("location") or ""),
        is_newly_listed=bool(raw.get("isNewlyListed")),
        image_url=str(raw.get("image") or ""),
        image_alt=str(raw.get("imageAlt") or raw.get("title") or ""),
        raw_text=clean_text(str(raw.get("text") or "")),
        price_amount=raw.get("priceAmount") if isinstance(raw.get("priceAmount"), int) else None,
        seller_name=str(raw.get("sellerName") or ""),
        is_live=raw.get("isLive") if isinstance(raw.get("isLive"), bool) else None,
        is_sold=raw.get("isSold") if isinstance(raw.get("isSold"), bool) else None,
        is_pending=raw.get("isPending") if isinstance(raw.get("isPending"), bool) else None,
        is_hidden=raw.get("isHidden") if isinstance(raw.get("isHidden"), bool) else None,
    )


def extract_embedded_cards(page, limit: int) -> list[MarketplaceCard]:
    script_texts = page.locator('script[type="application/json"]').all_text_contents()
    return [card_from_embedded_record(record) for record in extract_marketplace_records(script_texts, limit=limit)]


def extract_dom_cards(page, limit: int) -> list[MarketplaceCard]:
    raw_cards = page.evaluate(
        """
        (limit) => {
          const seen = new Set();
          const cards = [];

          for (const link of Array.from(document.querySelectorAll('a[href*="/marketplace/item/"]'))) {
            const match = link.href.match(/marketplace\\/item\\/(\\d+)/);
            const itemId = match ? match[1] : "";
            if (!itemId || seen.has(itemId)) continue;

            const text = (link.innerText || link.textContent || "").trim();
            if (!text) continue;

            seen.add(itemId);
            const image = link.querySelector("img[src]");
            cards.push({
              itemId,
              href: link.href,
              text,
              image: image ? image.src : "",
              imageAlt: image ? (image.alt || "") : ""
            });

            if (cards.length >= limit) break;
          }

          return cards;
        }
        """,
        limit,
    )
    return [parse_card(raw) for raw in raw_cards]


def count_marketplace_card_links(page) -> int:
    return int(
        page.evaluate(
            """
            () => {
              const ids = new Set();
              for (const link of Array.from(document.querySelectorAll('a[href*="/marketplace/item/"]'))) {
                const match = link.href.match(/marketplace\\/item\\/(\\d+)/);
                if (match) ids.add(match[1]);
              }
              return ids.size;
            }
            """
        )
    )


def load_candidate_window(page, target_limit: int, max_scrolls: int, scroll_wait_ms: int) -> None:
    if max_scrolls <= 0:
        return

    previous_count = count_marketplace_card_links(page)
    stagnant_scrolls = 0
    for _ in range(max_scrolls):
        if previous_count >= target_limit:
            return
        page.evaluate(
            """
            () => {
              const elements = [
                document.scrollingElement,
                document.documentElement,
                document.body,
                ...Array.from(document.querySelectorAll('div'))
              ].filter(Boolean);
              let target = document.scrollingElement || document.documentElement || document.body;
              let bestDelta = 0;
              for (const element of elements) {
                const delta = (element.scrollHeight || 0) - (element.clientHeight || 0);
                if (delta > bestDelta) {
                  bestDelta = delta;
                  target = element;
                }
              }
              const distance = Math.max((target.clientHeight || window.innerHeight) * 1.8, 1200);
              target.scrollBy(0, distance);
            }
            """
        )
        page.wait_for_timeout(scroll_wait_ms)
        current_count = count_marketplace_card_links(page)
        if current_count <= previous_count:
            stagnant_scrolls += 1
            if stagnant_scrolls >= 2:
                return
            continue
        stagnant_scrolls = 0
        previous_count = current_count


def extract_page_text(page, max_chars: int = 6000) -> str:
    return page.evaluate(
        """
        (maxChars) => {
          const text = document.body && document.body.innerText ? document.body.innerText : "";
          return text.replace(/\\n{3,}/g, "\\n\\n").slice(0, maxChars);
        }
        """,
        max_chars,
    )


def parse_detail_text(text: str) -> MarketplaceDetail:
    lines = compact_lines(text)
    posted = ""
    approx_location = ""

    for line in lines:
        if line.startswith("Ditawarkan ") and not posted:
            posted = line
        if "Perkiraan lokasi" in line and not approx_location:
            approx_location = line

    condition = ""
    if "Kondisi" in lines:
        condition_index = lines.index("Kondisi")
        if condition_index + 1 < len(lines):
            condition = lines[condition_index + 1]
        description_start = condition_index + 2
    elif "Detail" in lines:
        description_start = lines.index("Detail") + 1
    else:
        description_start = 0

    stop_labels = {
        "Informasi penjual",
        "Detail penjual",
        "Kirim pesan ke penjual",
        "Kirim pesan",
        "Kirim",
        "Pilihan hari ini",
    }
    description_parts: list[str] = []
    for line in lines[description_start:]:
        if line in stop_labels:
            break
        if "Perkiraan lokasi" in line:
            continue
        if line == "Lihat lebih banyak":
            continue
        description_parts.append(line)

    seller = extract_seller(lines)
    return MarketplaceDetail(
        posted=posted,
        condition=condition,
        description="\n".join(description_parts).strip(),
        approx_location=approx_location,
        seller=seller,
    )


def extract_seller(lines: list[str]) -> str:
    labels = {"Informasi penjual", "Detail penjual", "Kirim pesan ke penjual", "Kirim"}
    for label in ("Detail penjual", "Informasi penjual"):
        if label not in lines:
            continue
        index = lines.index(label)
        for candidate in lines[index + 1 : index + 5]:
            if candidate in labels:
                continue
            if candidate.startswith("Bergabung dengan Facebook"):
                continue
            return candidate[:160]
    return ""


def open_marketplace(page, url: str, wait_ms: int, timeout_ms: int) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(wait_ms)


def scrape_target(page, target: SourceTarget, args: argparse.Namespace, keywords: list[str]) -> MarketplaceTargetResult:
    url = build_search_url(target)
    target_limit = effective_limit(target, args)
    candidate_limit = effective_candidate_limit(target, args)
    print(f"Fetching Facebook Marketplace target: {target.id} ({target.query})", file=sys.stderr)
    print(f"URL: {url}", file=sys.stderr)

    open_marketplace(page, url, args.wait_ms, args.timeout * 1000)
    candidates = extract_embedded_cards(page, candidate_limit)
    if candidates:
        print(f"Parsed {len(candidates)} Marketplace listings from embedded Relay data.", file=sys.stderr)
    else:
        try:
            page.wait_for_selector('a[href*="/marketplace/item/"]', timeout=args.timeout * 1000)
        except PlaywrightTimeoutError as exc:
            page_text = extract_page_text(page, max_chars=1500)
            if looks_login_blocked(page_text):
                raise LoginBlockedError("Facebook Marketplace page is login-gated") from exc
            raise ConnectorBlockedError(f"No Marketplace item cards appeared. Page sample: {page_text[:800]}") from exc

        load_candidate_window(page, candidate_limit, effective_max_scrolls(target, args), args.scroll_wait_ms)
        candidates = extract_dom_cards(page, candidate_limit)
    result = select_target_cards(target, candidates, args, keywords, target_limit, url)
    if result.skipped_count or result.blocked_count:
        print(
            "Skipped "
            f"{result.skipped_count} non-RECON and blocked {result.blocked_count} noisy "
            f"Marketplace cards for target: {target.id}",
            file=sys.stderr,
        )
    return result


def select_target_cards(
    target: SourceTarget,
    candidates: list[MarketplaceCard],
    args: argparse.Namespace,
    keywords: list[str],
    limit: int,
    url: str,
) -> MarketplaceTargetResult:
    if args.no_relevance_filter:
        return MarketplaceTargetResult(
            target=target,
            url=url,
            cards=candidates[:limit],
            candidates_count=len(candidates),
            matched_count=min(len(candidates), limit),
            skipped_count=0,
            blocked_count=0,
        )

    positive_keywords = keywords + list(target.positive_keywords)
    blocked_keywords = list(DEFAULT_BLOCKED_KEYWORDS) + list(target.blocked_keywords)
    selected: list[MarketplaceCard] = []
    matched_count = 0
    skipped_count = 0
    blocked_count = 0
    matched_hits: list[str] = []
    blocked_hits: list[str] = []

    for card in candidates:
        block_matches = matched_keywords(card, blocked_keywords)
        if block_matches:
            blocked_count += 1
            blocked_hits.extend(block_matches)
            continue

        positive_matches = matched_keywords(card, positive_keywords)
        if positive_matches:
            matched_count += 1
            matched_hits.extend(positive_matches)
            if len(selected) < limit:
                selected.append(card)
            continue

        skipped_count += 1

    return MarketplaceTargetResult(
        target=target,
        url=url,
        cards=selected,
        candidates_count=len(candidates),
        matched_count=matched_count,
        skipped_count=skipped_count,
        blocked_count=blocked_count,
        matched_keywords=tuple(unique_prefix(matched_hits, 20)),
        blocked_keywords=tuple(unique_prefix(blocked_hits, 20)),
    )


def effective_limit(target: SourceTarget, args: argparse.Namespace) -> int:
    configured = args.limit if args.limit is not None else target.limit
    if configured is None:
        configured = 15
    return max(1, min(100, configured))


def effective_candidate_limit(target: SourceTarget, args: argparse.Namespace) -> int:
    target_limit = effective_limit(target, args)
    configured = target.candidate_limit if target.candidate_limit is not None else args.candidate_limit
    return max(target_limit, min(200, configured))


def effective_max_scrolls(target: SourceTarget, args: argparse.Namespace) -> int:
    configured = target.max_scrolls if target.max_scrolls is not None else args.max_scrolls
    return max(0, min(10, configured))


def scrape_query(page, query: str, args: argparse.Namespace, keywords: list[str]) -> list[MarketplaceCard]:
    target = target_from_query(query, args)
    return scrape_target(page, target, args, keywords).cards


def scrape_detail(page, card: MarketplaceCard, args: argparse.Namespace) -> MarketplaceDetail:
    url = canonical_marketplace_url(card)
    if not url:
        return MarketplaceDetail(error="Invalid Facebook Marketplace item URL")
    try:
        open_marketplace(page, url, args.wait_ms, args.timeout * 1000)
        return parse_detail_text(extract_page_text(page, max_chars=9000))
    except PlaywrightError as exc:
        return MarketplaceDetail(error=str(exc))


def looks_login_blocked(text: str) -> bool:
    lower = text.lower()
    return any(
        marker in lower
        for marker in (
            "masuk ke facebook",
            "log in to facebook",
            "email atau nomor telepon",
            "kata sandi",
            "create new account",
            "buat akun baru",
        )
    )


def normalize_card(
    card: MarketplaceCard,
    detail: MarketplaceDetail | None,
    fetched_at: datetime,
) -> dict[str, Any]:
    detail = detail or MarketplaceDetail()
    description = detail.description or card.raw_text
    title = normalize_listing_title(card)
    combined_text = "\n".join(
        part
        for part in (
            title,
            card.price,
            clean_card_location(card.location),
            card.raw_text,
            detail.description,
            detail.condition,
            detail.approx_location,
            card.image_alt,
        )
        if part
    )

    locations = unique_values(
        [
            clean_card_location(card.location),
            normalize_approx_location(detail.approx_location),
            *extract_locations(description),
        ],
        limit=8,
    )

    return {
        "platform": PLATFORM,
        "sourceUrl": canonical_marketplace_url(card),
        "externalId": card.item_id,
        "title": title,
        "description": description,
        "category": extract_category(combined_text),
        "brand": extract_brand(combined_text),
        "price": card.price_amount if card.price_amount is not None else extract_price(detail.description, card.price),
        "locationTexts": locations,
        "conditionText": detail.condition or extract_condition(description),
        "sellerName": detail.seller or card.seller_name or None,
        "status": structured_card_status(card, combined_text),
        "postedAt": parse_posted_at(detail.posted, fetched_at),
        "firstFetchedAt": fetched_at.isoformat(),
        "lastFetchedAt": fetched_at.isoformat(),
        "images": build_images(card),
    }


def structured_card_status(card: MarketplaceCard, fallback_text: str) -> str:
    if card.is_sold:
        return "SOLD"
    if card.is_hidden or card.is_pending or card.is_live is False:
        return "UNKNOWN"
    return extract_status(fallback_text)


def normalize_listing_title(card: MarketplaceCard) -> str:
    if not is_low_value_title(card.title):
        return card.title
    image_title = title_from_image_alt(card.image_alt)
    if image_title:
        return image_title
    return card.image_alt or "Facebook Marketplace listing"


def is_low_value_title(value: str) -> bool:
    normalized = normalize_spaces(value)
    if not normalized:
        return True
    return not bool(re.search(r"[A-Za-z0-9]", normalized))


def title_from_image_alt(value: str) -> str:
    value = normalize_spaces(value)
    if not value:
        return ""
    if " di " in value:
        return trim_value(value.rsplit(" di ", 1)[0])
    return value


def clean_card_location(value: str) -> str:
    value = normalize_spaces(value)
    if not value:
        return ""
    if re.search(r"\brp\s*[0-9]", value, flags=re.I):
        return ""
    if re.search(r"\b(jt|juta|rb|ribu)\b", value, flags=re.I) and re.search(r"\d", value):
        return ""
    return value


def canonical_marketplace_url(card: MarketplaceCard) -> str:
    if re.fullmatch(r"\d+", card.item_id):
        return f"https://www.facebook.com/marketplace/item/{card.item_id}/"
    parsed = urllib.parse.urlsplit(card.url)
    if parsed.scheme.lower() not in {"http", "https"} or (parsed.hostname or "").lower() not in {"facebook.com", "www.facebook.com", "m.facebook.com"}:
        return ""
    if not re.fullmatch(r"/marketplace/item/\d+/?", parsed.path):
        return ""
    return urllib.parse.urlunsplit(("https", "www.facebook.com", parsed.path, "", ""))


def build_images(card: MarketplaceCard) -> list[dict[str, Any]]:
    if not card.image_url:
        return []
    return [
        {
            "sourceUrl": card.image_url,
            "position": 0,
            "altText": card.image_alt or None,
        }
    ]


def extract_price(description: str, card_price: str) -> int | None:
    description_price = extract_price_from_text(description, prefer_context=True)
    if description_price is not None:
        return description_price

    card_price_lower = card_price.lower()
    if any(marker in card_price_lower for marker in FREE_PRICE_MARKERS):
        return None
    if any(marker in card_price_lower for marker in ASK_PRICE_MARKERS):
        return None

    return extract_price_from_text(card_price, prefer_context=False)


def extract_price_from_text(text: str, *, prefer_context: bool) -> int | None:
    if not text:
        return None

    candidates: list[int] = []
    for line in compact_lines(text):
        lower = line.lower()
        if prefer_context and not any(word in lower for word in ("harga", "price", "rp", "idr", "$", "nego", "nett", "net")):
            continue
        if any(marker in lower for marker in FREE_PRICE_MARKERS) and not re.search(r"\d", lower):
            continue
        if any(marker in lower for marker in ASK_PRICE_MARKERS) and not re.search(r"\d", lower):
            continue

        amount = parse_price_value(line)
        if amount is not None:
            candidates.append(amount)

    return candidates[0] if candidates else None


def parse_price_value(value: str) -> int | None:
    value = value.lower().replace("\xa0", " ")
    value = value.replace("idr", "rp")

    unit_match = re.search(r"(?:rp|\$)?\s*(\d+(?:[.,]\d+)?)\s*(jt|juta|rb|ribu|k)\b", value, flags=re.I)
    if unit_match:
        number = float(unit_match.group(1).replace(",", "."))
        unit = unit_match.group(2).lower()
        multiplier = 1_000_000 if unit in {"jt", "juta"} else 1_000
        amount = int(number * multiplier)
        return amount if 10_000 <= amount <= 200_000_000 else None

    money_match = re.search(r"(?:rp|\$)\s*([0-9][0-9.,]*)", value, flags=re.I)
    if money_match:
        amount = parse_grouped_digits(money_match.group(1))
        return amount if amount and 10_000 <= amount <= 200_000_000 else None

    grouped_match = re.search(r"\b([0-9]{1,3}(?:[.,][0-9]{3})+)\b", value)
    if grouped_match:
        amount = parse_grouped_digits(grouped_match.group(1))
        return amount if amount and 10_000 <= amount <= 200_000_000 else None

    return None


def parse_grouped_digits(value: str) -> int | None:
    separators = re.findall(r"[.,]", value)
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return None
    if not separators and len(digits) <= 3:
        return None
    return int(digits)


def extract_status(text: str) -> str:
    lower = text.lower()
    if any(re.search(rf"\b{re.escape(marker)}\b", lower) for marker in SOLD_MARKERS):
        return "SOLD"
    return "AVAILABLE"


def extract_category(text: str) -> str | None:
    lower = normalize_spaces(text).lower()
    if re.search(r"\b(legion go|steam deck|rog ally|handheld pc)\b", lower):
        return "Handheld PC"
    if re.search(r"\b(pc gaming|pc rakitan|komputer gaming|desktop|mini pc|workstation)\b", lower):
        return "Desktop PC"
    laptop_markers = (
        r"\b(laptop|notebook|thinkpad|macbook|vivobook|zenbook|ideapad|legion|katana|zephyrus|omen|victus|nitro|predator|loq)\b",
        r"\b(rog strix|asus tuf|tuf gaming|tuf a15|tuf f15|ideapad gaming|pavilion gaming)\b",
        r"\b(msi gf63|msi gf65|msi gf66|msi gf76|msi gl63|msi gl65|msi ge66|msi cyborg|msi stealth|msi raider)\b",
        r"\b(ga401|ga402|g513|g713|g14|g15|g16|fx506|fx507|fa506|fa507|gu603)[a-z0-9-]*\b",
    )
    if any(re.search(pattern, lower) for pattern in laptop_markers):
        return "Laptop"
    for category, keywords in CATEGORY_PATTERNS:
        if any(keyword_matches(lower, keyword) for keyword in keywords):
            return category
    return None


def extract_brand(text: str) -> str | None:
    lower = normalize_spaces(text).lower()
    for brand, keywords in BRAND_PATTERNS:
        if any(positive_brand_keyword_matches(lower, keyword) for keyword in keywords):
            return brand
    return None


def positive_brand_keyword_matches(text: str, keyword: str) -> bool:
    keyword_pattern = re.escape(normalize_spaces(keyword).lower()).replace(r"\ ", r"\s+")
    pattern = re.compile(rf"(?<!\w){keyword_pattern}(?!\w)")
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 24) : match.start()]
        if re.search(r"\b(?:not|no|bukan|tanpa|non)[\s/_-]*$", prefix):
            continue
        return True
    return False


def extract_condition(text: str) -> str | None:
    for line in compact_lines(text):
        lower = line.lower()
        if re.search(r"\b(kondisi|condition|bekas|second|2nd|normal|minus)\b", lower) or "like new" in lower:
            return line[:240]
    return None


def extract_locations(text: str) -> list[str]:
    locations: list[str] = []
    for line in compact_lines(text):
        stripped = trim_value(line)
        lower = stripped.lower()
        for prefix in LOCATION_PREFIXES:
            match = re.match(rf"^{re.escape(prefix)}\s*[:\\-]?\s*(.+)$", stripped, flags=re.I)
            if match:
                locations.extend(split_locations(match.group(1)))
                break
        if "perkiraan lokasi" in lower:
            locations.append(normalize_approx_location(stripped))
    return unique_values(locations, limit=8)


def split_locations(value: str) -> list[str]:
    value = trim_value(value)
    value = re.sub(r"\b(?:bisa|prefer|only|aja|dan|sekitarnya)?\s*(?:kirim|lewat|ekspedisi|paket|juga).*$", "", value, flags=re.I)
    parts = re.split(r"\s*(?:,|/|;|\||&|\+|\bdan\b|\batau\b|\bor\b)\s*", value, flags=re.I)
    return [part[:160] for part in (trim_value(part) for part in parts) if part]


def normalize_approx_location(value: str) -> str:
    value = value.replace("· Perkiraan lokasi", "")
    value = value.replace("Perkiraan lokasi", "")
    return trim_value(value)


def parse_posted_at(value: str, fallback: datetime) -> str | None:
    if not value:
        return None
    lower = value.lower()
    match = re.search(r"(\d+)\s*(menit|mnt|jam|hari|minggu|bulan)\s+lalu", lower)
    if not match:
        if "kemarin" in lower:
            return (fallback - timedelta(days=1)).isoformat()
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    if unit in {"menit", "mnt"}:
        posted_at = fallback - timedelta(minutes=amount)
    elif unit == "jam":
        posted_at = fallback - timedelta(hours=amount)
    elif unit == "hari":
        posted_at = fallback - timedelta(days=amount)
    elif unit == "minggu":
        posted_at = fallback - timedelta(weeks=amount)
    else:
        posted_at = fallback - timedelta(days=amount * 30)
    return posted_at.isoformat()


def trim_value(value: str) -> str:
    value = normalize_spaces(value)
    return value.strip(" :;,.|-")


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def unique_values(values: Iterable[str | None], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = trim_value(value or "")
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def listing_identity(listing: dict[str, Any]) -> str:
    return str(listing.get("externalId") or listing.get("sourceUrl") or "")


def card_identity(card: MarketplaceCard) -> str:
    return card.item_id or canonical_marketplace_url(card)


def should_fetch_detail(card: MarketplaceCard, state: dict[str, Any], args: argparse.Namespace) -> bool:
    if not args.details:
        return False
    if args.no_state or args.detail_scope == "all":
        return True

    seen_ids = set(str(value) for value in state.get("seen_external_ids", []) if value)
    seen_urls = set(str(value) for value in state.get("seen_source_urls", []) if value)
    source_url = canonical_marketplace_url(card)
    return not ((card.item_id and card.item_id in seen_ids) or (source_url and source_url in seen_urls))


def dedupe_cards(cards: Iterable[MarketplaceCard]) -> list[MarketplaceCard]:
    seen: set[str] = set()
    deduped: list[MarketplaceCard] = []
    for card in cards:
        identity = card_identity(card)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        deduped.append(card)
    return deduped


def dedupe_listings(listings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for listing in listings:
        identity = listing_identity(listing)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        deduped.append(listing)
    return deduped


def default_state() -> dict[str, Any]:
    return {
        "seen_external_ids": [],
        "seen_source_urls": [],
        "cooldown_until": None,
        "last_run_at": None,
        "last_success_at": None,
        "last_error": None,
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_state()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    state = default_state()
    if isinstance(loaded, dict):
        state.update(loaded)
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def filter_new_listings(listings: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    seen_ids = set(str(value) for value in state.get("seen_external_ids", []) if value)
    seen_urls = set(str(value) for value in state.get("seen_source_urls", []) if value)
    new_listings: list[dict[str, Any]] = []
    for listing in listings:
        external_id = str(listing.get("externalId") or "")
        source_url = str(listing.get("sourceUrl") or "")
        if external_id and external_id in seen_ids:
            continue
        if source_url and source_url in seen_urls:
            continue
        new_listings.append(listing)
    return new_listings


def update_seen_state(state: dict[str, Any], listings: list[dict[str, Any]], max_seen: int) -> None:
    new_ids = [str(item.get("externalId")) for item in listings if item.get("externalId")]
    new_urls = [str(item.get("sourceUrl")) for item in listings if item.get("sourceUrl")]
    state["seen_external_ids"] = unique_prefix(new_ids + list(state.get("seen_external_ids", [])), max_seen)
    state["seen_source_urls"] = unique_prefix(new_urls + list(state.get("seen_source_urls", [])), max_seen)


def unique_prefix(values: Iterable[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def cooldown_seconds_remaining(state: dict[str, Any], now: datetime | None = None) -> int:
    cooldown_until = parse_iso_datetime(str(state.get("cooldown_until") or ""))
    if not cooldown_until:
        return 0
    current = now or now_utc()
    return max(0, int((cooldown_until - current).total_seconds()))


def set_cooldown(state: dict[str, Any], seconds: int, reason: str) -> None:
    until = now_utc() + timedelta(seconds=max(1, seconds))
    state["cooldown_until"] = until.isoformat()
    state["last_error"] = reason


def clear_cooldown(state: dict[str, Any]) -> None:
    state["cooldown_until"] = None


def log_event(path: Path | None, event: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"logged_at": now_utc().isoformat(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def run_http_probe(args: argparse.Namespace) -> dict[str, Any]:
    target = resolve_targets(args)[0]
    url = build_search_url(target)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": args.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "source": "facebook",
                "status": "http_probe",
                "target_id": target.id,
                "query": target.query,
                "http_status": response.status,
                "final_url": response.url,
                "content_length": len(body),
                "has_marketplace_item": "/marketplace/item/" in body,
                "looks_login_blocked": looks_login_blocked(body),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "source": "facebook",
            "status": "http_probe_failed",
            "target_id": target.id,
            "query": target.query,
            "http_status": exc.code,
            "final_url": getattr(exc, "url", url),
            "content_length": len(body),
            "has_marketplace_item": "/marketplace/item/" in body,
            "looks_login_blocked": looks_login_blocked(body),
            "error": str(exc),
        }
    except urllib.error.URLError as exc:
        return {
            "source": "facebook",
            "status": "http_probe_failed",
            "target_id": target.id,
            "query": target.query,
            "error": str(exc),
        }


def run_login(page) -> None:
    print("Opening Facebook Marketplace login/session page.", file=sys.stderr)
    page.goto("https://www.facebook.com/marketplace/", wait_until="domcontentloaded", timeout=60_000)
    print("Log in or verify Marketplace access in the opened browser window.", file=sys.stderr)
    input("Press Enter here after the browser session is ready...")


def uses_persistent_profile(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "login", False)) or str(getattr(args, "session_mode", "ephemeral")) == "persistent"


def launch_facebook_context(playwright: Any, args: argparse.Namespace) -> tuple[Any | None, Any]:
    proxy_url = getattr(args, "proxy_url", None)
    channel = "chrome" if args.browser == "chrome" else None

    if uses_persistent_profile(args):
        profile_dir = Path(args.profile_dir).resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)
        launch_options: dict[str, Any] = {
            "user_data_dir": str(profile_dir),
            "headless": args.headless,
            "locale": "id-ID",
            "viewport": {"width": 1440, "height": 900},
        }
        if proxy_url:
            launch_options["proxy"] = {"server": proxy_url}
        if channel:
            launch_options["channel"] = channel
        return None, playwright.chromium.launch_persistent_context(**launch_options)

    launch_options = {"headless": args.headless}
    if proxy_url:
        launch_options["proxy"] = {"server": proxy_url}
    if channel:
        launch_options["channel"] = channel
    browser_instance = playwright.chromium.launch(**launch_options)
    context = browser_instance.new_context(
        locale="id-ID",
        viewport={"width": 1440, "height": 900},
    )
    return browser_instance, context


def configure_discovery_page(page: Any, args: argparse.Namespace) -> None:
    block_assets = bool(getattr(args, "block_assets", not bool(getattr(args, "load_assets", False))))
    if not block_assets or getattr(args, "login", False):
        return

    def block_heavy_assets(route: Any) -> None:
        if route.request.resource_type in {"image", "media", "font", "stylesheet"}:
            route.abort()
        else:
            route.continue_()

    page.route("**/*", block_heavy_assets)


def run_calibration(args: argparse.Namespace) -> tuple[int, list[dict[str, Any]]]:
    state_path = Path(args.state_file)
    log_path = None if args.no_state else Path(args.log_file)
    state = default_state() if args.no_state else load_state(state_path)
    state["last_run_at"] = now_utc().isoformat()

    cooldown_remaining = 0 if args.ignore_cooldown else cooldown_seconds_remaining(state)
    if cooldown_remaining > 0:
        log_event(
            log_path,
            {
                "source": "facebook",
                "status": "calibration_cooldown_skip",
                "cooldown_remaining_seconds": cooldown_remaining,
            },
        )
        print(f"Facebook connector is cooling down for {cooldown_remaining}s.", file=sys.stderr)
        return 0, []

    try:
        records = run_browser_calibration(args)
        clear_cooldown(state)
        state["last_success_at"] = now_utc().isoformat()
        state["last_error"] = None
        if not args.no_state:
            save_state(state_path, state)
        log_event(
            log_path,
            {
                "source": "facebook",
                "status": "calibration_success",
                "targets": len(records),
                "headless": bool(args.headless),
            },
        )
        return 0, records
    except LoginBlockedError as exc:
        set_cooldown(state, args.cooldown_seconds, str(exc))
        if not args.no_state:
            save_state(state_path, state)
        log_event(log_path, {"source": "facebook", "status": "calibration_login_blocked", "error": str(exc)})
        print(f"Facebook Marketplace login gate detected. Cooling down for {args.cooldown_seconds}s.", file=sys.stderr)
        return 1, []
    except ConnectorBlockedError as exc:
        set_cooldown(state, args.cooldown_seconds, str(exc))
        if not args.no_state:
            save_state(state_path, state)
        log_event(log_path, {"source": "facebook", "status": "calibration_blocked_or_empty", "error": str(exc)})
        print(f"Facebook Marketplace calibration did not expose cards. Cooling down for {args.cooldown_seconds}s.", file=sys.stderr)
        return 1, []
    except PlaywrightError as exc:
        state["last_error"] = str(exc)
        if not args.no_state:
            save_state(state_path, state)
        log_event(log_path, {"source": "facebook", "status": "calibration_failed", "error": str(exc)})
        print(f"Facebook Marketplace calibration failed: {exc}", file=sys.stderr)
        if args.browser == "chromium":
            print("If Chromium is not installed, run: python -m playwright install chromium", file=sys.stderr)
        return 1, []


def run_browser_calibration(args: argparse.Namespace) -> list[dict[str, Any]]:
    targets = resolve_targets(args)
    keywords = list(DEFAULT_RECON_KEYWORDS)
    if args.include_keyword:
        keywords.extend(args.include_keyword)

    with sync_playwright() as playwright:
        browser_instance, context = launch_facebook_context(playwright, args)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            configure_discovery_page(page, args)

            if args.login:
                run_login(page)
                return []

            records: list[dict[str, Any]] = []
            for target in targets:
                try:
                    records.append(calibration_record(scrape_target(page, target, args, keywords)))
                except LoginBlockedError:
                    raise
                except ConnectorBlockedError as exc:
                    records.append(calibration_error_record(target, str(exc)))
            return records
        finally:
            context.close()
            if browser_instance is not None:
                browser_instance.close()


def calibration_record(result: MarketplaceTargetResult) -> dict[str, Any]:
    return {
        "targetId": result.target.id,
        "label": result.target.label or None,
        "groups": list(result.target.groups),
        "query": result.target.query,
        "url": result.url,
        "cadenceSeconds": result.target.cadence_seconds,
        "candidateCount": result.candidates_count,
        "matchedCount": result.matched_count,
        "selectedCount": len(result.cards),
        "skippedCount": result.skipped_count,
        "blockedCount": result.blocked_count,
        "matchedKeywords": list(result.matched_keywords),
        "blockedKeywords": list(result.blocked_keywords),
        "sampleTitles": [card.title for card in result.cards[:5]],
        "sampleIds": [card.item_id for card in result.cards[:5]],
    }


def calibration_error_record(target: SourceTarget, error: str) -> dict[str, Any]:
    return {
        "targetId": target.id,
        "label": target.label or None,
        "groups": list(target.groups),
        "query": target.query,
        "url": build_search_url(target),
        "cadenceSeconds": target.cadence_seconds,
        "candidateCount": 0,
        "matchedCount": 0,
        "selectedCount": 0,
        "skippedCount": 0,
        "blockedCount": 0,
        "matchedKeywords": [],
        "blockedKeywords": [],
        "sampleTitles": [],
        "sampleIds": [],
        "error": error,
    }


def run_once(args: argparse.Namespace) -> tuple[int, list[dict[str, Any]]]:
    state_path = Path(args.state_file)
    log_path = None if args.no_state else Path(args.log_file)
    state = default_state() if args.no_state else load_state(state_path)
    state["last_run_at"] = now_utc().isoformat()

    cooldown_remaining = 0 if args.ignore_cooldown else cooldown_seconds_remaining(state)
    if cooldown_remaining > 0:
        log_event(
            log_path,
            {
                "source": "facebook",
                "status": "cooldown_skip",
                "cooldown_remaining_seconds": cooldown_remaining,
            },
        )
        print(f"Facebook connector is cooling down for {cooldown_remaining}s.", file=sys.stderr)
        return 0, []

    if args.access_mode == "http-probe":
        event = run_http_probe(args)
        log_event(log_path, event)
        print(json.dumps(event, ensure_ascii=False, indent=2), file=sys.stderr)
        return (0 if event.get("has_marketplace_item") else 1), []

    try:
        listings = run_browser_fetch(args, state)
        if args.ai_parse and listings:
            listings = enrich_listings_with_ai(listings, args, log_path)

        listings = dedupe_listings(listings)
        new_listings = filter_new_listings(listings, state)
        update_seen_state(state, listings, args.max_seen)
        clear_cooldown(state)
        state["last_success_at"] = now_utc().isoformat()
        state["last_error"] = None
        if not args.no_state:
            save_state(state_path, state)
        log_event(
            log_path,
            {
                "source": "facebook",
                "status": "success",
                "normalized": len(listings),
                "new": len(new_listings),
                "details": bool(args.details),
                "headless": bool(args.headless),
            },
        )
    except LoginBlockedError as exc:
        set_cooldown(state, args.cooldown_seconds, str(exc))
        if not args.no_state:
            save_state(state_path, state)
        log_event(log_path, {"source": "facebook", "status": "login_blocked", "error": str(exc)})
        print(f"Facebook Marketplace login gate detected. Cooling down for {args.cooldown_seconds}s.", file=sys.stderr)
        return 1, []
    except ConnectorBlockedError as exc:
        set_cooldown(state, args.cooldown_seconds, str(exc))
        if not args.no_state:
            save_state(state_path, state)
        log_event(log_path, {"source": "facebook", "status": "blocked_or_empty", "error": str(exc)})
        print(f"Facebook Marketplace fetch did not expose cards. Cooling down for {args.cooldown_seconds}s.", file=sys.stderr)
        return 1, []
    except PlaywrightError as exc:
        state["last_error"] = str(exc)
        if not args.no_state:
            save_state(state_path, state)
        log_event(log_path, {"source": "facebook", "status": "failed", "error": str(exc)})
        print(f"Facebook Marketplace scrape failed: {exc}", file=sys.stderr)
        if args.browser == "chromium":
            print("If Chromium is not installed, run: python -m playwright install chromium", file=sys.stderr)
        return 1, []

    selected = new_listings if args.emit == "new" else listings
    return 0, selected


def run_browser_fetch(args: argparse.Namespace, state: dict[str, Any]) -> list[dict[str, Any]]:
    targets = resolve_targets(args)
    keywords = list(DEFAULT_RECON_KEYWORDS)
    if args.include_keyword:
        keywords.extend(args.include_keyword)

    with sync_playwright() as playwright:
        browser_instance, context = launch_facebook_context(playwright, args)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            configure_discovery_page(page, args)

            if args.login:
                run_login(page)
                return []

            all_cards: list[MarketplaceCard] = []
            for target in targets:
                all_cards.extend(scrape_target(page, target, args, keywords).cards)

            cards = dedupe_cards(all_cards)
            if not cards:
                raise ConnectorBlockedError("No Facebook Marketplace cards found")

            fetched_at = now_utc()
            listings: list[dict[str, Any]] = []
            for card in cards:
                detail = scrape_detail(page, card, args) if should_fetch_detail(card, state, args) else None
                if detail and detail.error:
                    print(f"Detail fetch failed for {card.item_id}: {detail.error}", file=sys.stderr)
                listings.append(normalize_card(card, detail, fetched_at))
            return listings
        finally:
            context.close()
            if browser_instance is not None:
                browser_instance.close()


def enrich_listings_with_ai(
    listings: list[dict[str, Any]],
    args: argparse.Namespace,
    log_path: Path | None,
) -> list[dict[str, Any]]:
    if str(SCRAPER_DIR) not in sys.path:
        sys.path.insert(0, str(SCRAPER_DIR))
    try:
        from reddit.nvidia_parser import NvidiaParserError, enrich_listings_with_nvidia
    except ImportError as exc:
        log_event(log_path, {"source": "facebook", "status": "ai_parse_unavailable", "error": str(exc)})
        print(f"NVIDIA AI parsing unavailable: {exc}", file=sys.stderr)
        return listings

    try:
        return enrich_listings_with_nvidia(
            listings,
            model=args.ai_model,
            batch_size=args.ai_batch_size,
            rate_limit_seconds=args.ai_rate_limit,
            timeout=args.ai_timeout,
            prefer_ai=args.ai_prefer,
        )
    except NvidiaParserError as exc:
        log_event(log_path, {"source": "facebook", "status": "ai_parse_failed", "error": str(exc)})
        print(f"NVIDIA AI parsing skipped: {exc}", file=sys.stderr)
        return listings


def guarded_run_once(args: argparse.Namespace) -> tuple[int, list[dict[str, Any]]]:
    if args.no_state:
        return run_once(args)

    try:
        with FileLock(Path(args.lock_file), args.lock_stale_seconds):
            return run_once(args)
    except AlreadyRunningError as exc:
        log_event(Path(args.log_file), {"source": "facebook", "status": "locked", "error": str(exc)})
        print(str(exc), file=sys.stderr)
        return 2, []


def guarded_run_calibration(args: argparse.Namespace) -> tuple[int, list[dict[str, Any]]]:
    if args.no_state:
        return run_calibration(args)

    try:
        with FileLock(Path(args.lock_file), args.lock_stale_seconds):
            return run_calibration(args)
    except AlreadyRunningError as exc:
        log_event(Path(args.log_file), {"source": "facebook", "status": "calibration_locked", "error": str(exc)})
        print(str(exc), file=sys.stderr)
        return 2, []


def watch(args: argparse.Namespace) -> int:
    iteration = 0
    last_code = 0
    while True:
        iteration += 1
        last_code, listings = guarded_run_once(args)
        print_listings(listings, args.format)
        if args.max_iterations and iteration >= args.max_iterations:
            return last_code
        sleep_for = max(1, args.interval)
        if args.jitter:
            sleep_for += random.randint(0, args.jitter)
        time.sleep(sleep_for)


def print_calibration(records: list[dict[str, Any]], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return
    if output_format == "jsonl":
        for record in records:
            print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        return

    if not records:
        print("No Facebook Marketplace calibration records found.")
        return

    for record in records:
        label = f" - {record['label']}" if record.get("label") else ""
        print(f"{record['targetId']}{label}")
        print(f"  query: {record['query']}")
        print(
            "  candidates/matched/selected/skipped/blocked: "
            f"{record['candidateCount']}/{record['matchedCount']}/{record['selectedCount']}/"
            f"{record['skippedCount']}/{record['blockedCount']}"
        )
        if record.get("matchedKeywords"):
            print(f"  matched: {', '.join(record['matchedKeywords'][:8])}")
        if record.get("blockedKeywords"):
            print(f"  blocked: {', '.join(record['blockedKeywords'][:8])}")
        if record.get("sampleTitles"):
            print("  samples:")
            for title in record["sampleTitles"][:5]:
                print(f"    - {title}")
        if record.get("error"):
            print(f"  error: {record['error']}")
        print()


def target_summary(target: SourceTarget) -> dict[str, Any]:
    return {
        "id": target.id,
        "label": target.label or None,
        "groups": list(target.groups),
        "query": target.query,
        "location": target.location,
        "categoryId": target.category_id,
        "categorySlug": target.category_slug,
        "exact": target.exact,
        "radius": target.radius,
        "daysSinceListed": target.days_since_listed,
        "deliveryMethod": target.delivery_method,
        "availability": target.availability,
        "cadenceSeconds": target.cadence_seconds,
        "limit": target.limit,
        "candidateLimit": target.candidate_limit,
        "maxScrolls": target.max_scrolls,
        "positiveKeywords": list(target.positive_keywords),
        "blockedKeywords": list(target.blocked_keywords),
        "notes": target.notes or None,
    }


def print_targets(targets: list[SourceTarget], output_format: str) -> None:
    summaries = [target_summary(target) for target in targets]
    if output_format == "json":
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        return
    if output_format == "jsonl":
        for summary in summaries:
            print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return

    for target in targets:
        groups = f" [{', '.join(target.groups)}]" if target.groups else ""
        cadence = f", {target.cadence_seconds}s" if target.cadence_seconds else ""
        print(f"{target.id}{groups}: {target.query}{cadence}")


def print_listings(listings: list[dict[str, Any]], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(listings, ensure_ascii=False, indent=2))
        return
    if output_format == "jsonl":
        for listing in listings:
            print(json.dumps(listing, ensure_ascii=False, separators=(",", ":")))
        return

    if not listings:
        print("No Facebook Marketplace listings found.")
        return

    for index, listing in enumerate(listings, start=1):
        print("=" * 88)
        print(f"{index}. {listing['title']}")
        print(f"Seller: {listing.get('sellerName') or '-'}")
        print(f"Posted: {listing.get('postedAt') or '-'}")
        print(f"Status: {listing.get('status') or '-'}")
        print(f"Category: {listing.get('category') or '-'}")
        print(f"Brand: {listing.get('brand') or '-'}")
        print(f"Price: {listing.get('price') if listing.get('price') is not None else '-'}")
        locations = listing.get("locationTexts") or []
        print(f"Locations: {', '.join(locations) if locations else '-'}")
        print(f"Condition: {listing.get('conditionText') or '-'}")
        print(f"URL: {listing['sourceUrl']}")
        images = listing.get("images") or []
        if images:
            print(f"Image: {images[0].get('sourceUrl')}")
        print()
        print(listing.get("description") or "[no description found]")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and normalize Facebook Marketplace listings for RECON.")
    parser.add_argument("--once", action="store_true", help="Run one fetch cycle. This is the default mode.")
    parser.add_argument("--watch", action="store_true", help="Run continuously.")
    parser.add_argument("--max-iterations", type=int, default=0, help="Stop watch mode after this many iterations.")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between watch-mode checks.")
    parser.add_argument("--jitter", type=int, default=8, help="Random extra seconds in watch mode.")
    parser.add_argument("--emit", choices=["all", "new"], default=None, help="Print all fetched listings or only unseen ones.")
    parser.add_argument("--only-new", action="store_true", help="Alias for --emit new.")
    parser.add_argument("--format", choices=["text", "json", "jsonl"], default="text", help="Output format.")
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Marketplace search query. Can be repeated. Default: vga",
    )
    parser.add_argument(
        "--targets-file",
        default=str(DEFAULT_TARGETS_FILE),
        help="JSON file containing reviewed Facebook Marketplace source targets.",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=None,
        help="Named source target id from --targets-file. Can be repeated.",
    )
    parser.add_argument(
        "--target-group",
        action="append",
        default=None,
        help="Source target group from --targets-file, such as hot, parts, peripherals, or discovery.",
    )
    parser.add_argument("--list-targets", action="store_true", help="List configured source targets and exit.")
    parser.add_argument(
        "--calibrate-targets",
        action="store_true",
        help="Fetch target result windows and print per-target noise/relevance metrics without updating seen IDs.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Number of relevant cards per query.")
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=60,
        help="Number of visible cards to inspect before RECON relevance filtering.",
    )
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Marketplace location slug.")
    parser.add_argument("--category-id", default=DEFAULT_CATEGORY_ID, help="Marketplace category id.")
    parser.add_argument("--details", action="store_true", help="Open listing pages for description/condition.")
    parser.add_argument(
        "--detail-scope",
        choices=["new", "all"],
        default="new",
        help="With state enabled, fetch detail pages only for new listings or for every fetched listing.",
    )
    parser.add_argument("--login", action="store_true", help="Open browser for one-time Facebook login/session setup.")
    parser.add_argument("--headless", action="store_true", help="Run browser headless. Not recommended for first login.")
    parser.add_argument(
        "--browser",
        choices=("chrome", "chromium"),
        default="chrome",
        help="Use installed Chrome or Playwright Chromium.",
    )
    parser.add_argument(
        "--access-mode",
        choices=("browser", "http-probe"),
        default="browser",
        help="Use the browser connector or run a direct anonymous HTTP reachability probe.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent browser profile directory used only with --login or --session-mode persistent.",
    )
    parser.add_argument(
        "--session-mode",
        choices=("ephemeral", "persistent"),
        default="ephemeral",
        help="Use a fresh logged-out browser context by default; persistent is explicit legacy/session mode.",
    )
    parser.add_argument("--load-assets", action="store_true", help="Load images, media, fonts, and styles during discovery.")
    parser.add_argument(
        "--include-keyword",
        action="append",
        default=None,
        help="Extra RECON relevance keyword. Can be repeated.",
    )
    parser.add_argument(
        "--no-relevance-filter",
        action="store_true",
        help="Print raw Marketplace cards without PC/tech/gaming filtering.",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Navigation/selector timeout in seconds.")
    parser.add_argument("--wait-ms", type=int, default=3000, help="Extra wait after page load for Marketplace JS.")
    parser.add_argument("--max-scrolls", type=int, default=3, help="Maximum bounded search-result scrolls per query.")
    parser.add_argument("--scroll-wait-ms", type=int, default=1000, help="Wait after each bounded search-result scroll.")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="State JSON path.")
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE), help="Duplicate-run lock path.")
    parser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE), help="JSONL run log path.")
    parser.add_argument("--max-seen", type=int, default=500, help="Maximum seen IDs retained in state.")
    parser.add_argument("--cooldown-seconds", type=int, default=300, help="Cooldown after login gate, block, or empty fetch.")
    parser.add_argument("--ignore-cooldown", action="store_true", help="Ignore active cooldown state.")
    parser.add_argument("--no-state", action="store_true", help="Do not read/write state, lock, or run logs.")
    parser.add_argument("--lock-stale-seconds", type=int, default=900, help="Remove lock files older than this many seconds.")
    parser.add_argument("--ai-parse", action="store_true", help="Enrich parsed listing fields with NVIDIA AI extraction.")
    parser.add_argument("--ai-prefer", action="store_true", help="Let AI values replace rule-parser values when available.")
    parser.add_argument("--ai-model", default=None, help="NVIDIA model ID for AI parsing.")
    parser.add_argument("--ai-batch-size", type=int, default=5, help="Listings per NVIDIA parser request.")
    parser.add_argument("--ai-rate-limit", type=float, default=2.0, help="Seconds between NVIDIA parser requests.")
    parser.add_argument("--ai-timeout", type=int, default=45, help="NVIDIA parser timeout in seconds.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent header for direct HTTP probes.")
    args = parser.parse_args()

    if args.limit is not None and (args.limit < 1 or args.limit > 100):
        parser.error("--limit must be between 1 and 100.")
    if args.limit is not None and args.candidate_limit < args.limit:
        parser.error("--candidate-limit must be greater than or equal to --limit.")
    if args.interval < 60:
        parser.error("--interval must be at least 60 seconds for Facebook Marketplace.")
    if args.ai_batch_size < 1 or args.ai_batch_size > 10:
        parser.error("--ai-batch-size must be between 1 and 10.")
    if args.timeout < 5:
        parser.error("--timeout must be at least 5 seconds.")
    if args.wait_ms < 0:
        parser.error("--wait-ms must be zero or greater.")
    if args.max_scrolls < 0 or args.max_scrolls > 10:
        parser.error("--max-scrolls must be between 0 and 10.")
    if args.scroll_wait_ms < 0:
        parser.error("--scroll-wait-ms must be zero or greater.")

    if args.only_new:
        args.emit = "new"
    elif args.emit is None:
        args.emit = "new" if args.watch else "all"

    return args


def main() -> int:
    args = parse_args()
    try:
        if args.list_targets:
            targets = resolve_targets(args) if args.target or args.target_group else load_source_targets(Path(args.targets_file))
            print_targets(targets, args.format)
            return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        if args.watch:
            return watch(args)

        if args.calibrate_targets:
            code, records = guarded_run_calibration(args)
            print_calibration(records, args.format)
            return code

        code, listings = guarded_run_once(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print_listings(listings, args.format)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
