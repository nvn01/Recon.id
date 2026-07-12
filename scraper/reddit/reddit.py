"""
Fetch and normalize latest r/jualbeliindonesia WTS computer/peripheral posts.

Reddit JSON endpoints currently return 403 from this environment, so this
connector uses Reddit search RSS/Atom as the primary public fetch path.
"""

from __future__ import annotations

import argparse
import html
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
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET

try:
    from .nvidia_parser import NvidiaParserError, enrich_listings_with_nvidia
except ImportError:
    from nvidia_parser import NvidiaParserError, enrich_listings_with_nvidia


SUBREDDIT = "jualbeliindonesia"
FLAIR = "WTS: Computers & Peripherals"
REDDIT_HOSTS = {"reddit.com", "www.reddit.com", "old.reddit.com", "redd.it", "www.redd.it"}
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
PLATFORM = "REDDIT"
SCRIPT_DIR = Path(__file__).resolve().parent
SCRAPER_DIR = SCRIPT_DIR.parent
DEFAULT_STATE_DIR = SCRAPER_DIR / ".state"
DEFAULT_LOG_DIR = SCRAPER_DIR / ".logs"
DEFAULT_STATE_FILE = DEFAULT_STATE_DIR / "reddit_wts_computers.json"
DEFAULT_LOCK_FILE = DEFAULT_STATE_DIR / "reddit_wts_computers.lock"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "reddit_wts_computers.jsonl"
DEFAULT_USER_AGENT = "ReconDataCollection/0.2 by local developer"

SOLD_MARKERS = (
    "sold out",
    "sold",
    "terjual",
    "laku",
    "booked",
)
AVAILABLE_MARKERS = (
    "#ready",
    "#chemicyready",
    "ready",
    "available",
)
PRICE_CONTEXT_WORDS = (
    "harga",
    "price",
    "cod",
    "tokped",
    "toco",
    "shopee",
    "nego",
    "nett",
    "net aja",
    "jual",
    "wts",
    "rp",
)
LOCATION_WORDS = (
    "lokasi",
    "cod",
    "kirim",
    "ekspedisi",
    "prefer",
)
KNOWN_LOCATIONS = (
    "Jakarta Selatan",
    "Jakarta Barat",
    "Jakarta Timur",
    "Jakarta Utara",
    "Jakarta Pusat",
    "Jakarta",
    "Jaksel",
    "Jakbar",
    "Jaktim",
    "Jakut",
    "Jakpus",
    "Bandung",
    "Surabaya",
    "Sleman",
    "Yogyakarta",
    "Jogja",
    "DIY",
    "Kudus",
    "Jawa Tengah",
    "Jepara",
    "Kediri",
    "Malang",
    "Tangerang",
    "Bekasi",
    "Depok",
    "Bogor",
    "Semarang",
    "Solo",
    "Denpasar",
)
CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("GPU", ("gpu", "vga", "rtx", "gtx", "radeon", "geforce")),
    ("CPU", ("cpu", "processor", "prosesor", "ryzen", "core i", "intel i3", "intel i5", "intel i7", "intel i9")),
    ("RAM", ("ram", "ddr3", "ddr4", "ddr5", "sodimm", "so-dimm", "memory")),
    ("Storage", ("ssd", "hdd", "nvme", "harddisk", "hard disk", "m.2", "sata")),
    ("Motherboard", ("motherboard", "mainboard", "mobo")),
    ("Network Adapter", ("wifi", "wi-fi", "router", "modem", "lan card", "network adapter", "adapter wifi")),
    ("Monitor", ("monitor", "lcd", "ips", "oled", "va panel", "hz")),
    ("Keyboard", ("keyboard", "keychron", "mechanical", "mecha")),
    ("Mouse", ("mouse", "logitech g", "razer viper", "deathadder")),
    ("Desktop PC", ("pc rakitan", "desktop", "mini pc", "workstation", "komputer")),
    ("Handheld PC", ("legion go", "steam deck", "rog ally", "pc handheld", "pc handled", "handheld pc")),
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
    ("Sapphire", ("sapphire",)),
    ("PowerColor", ("powercolor", "power color")),
    ("Palit", ("palit",)),
    ("Galax", ("galax",)),
    ("Colorful", ("colorful",)),
    ("Corsair", ("corsair",)),
    ("Kingston", ("kingston", "hyperx", "hyper x")),
    ("ADATA", ("adata", "xpg")),
    ("Micron", ("micron",)),
    ("Samsung", ("samsung",)),
    ("Crucial", ("crucial",)),
    ("Western Digital", ("western digital", "wd", "wdc")),
    ("Seagate", ("seagate",)),
    ("Logitech", ("logitech",)),
    ("Razer", ("razer",)),
    ("SteelSeries", ("steelseries", "steel series")),
    ("TP-Link", ("tp-link", "tp link", "tplink")),
    ("Mercusys", ("mercusys",)),
    ("D-Link", ("d-link", "d link", "dlink")),
    ("Tenda", ("tenda",)),
    ("V-Gen", ("v-gen", "vgen")),
    ("TeamGroup", ("teamgroup", "team group")),
)
DIRECT_CONDITION_KEYWORDS = (
    "kondisi",
    "condition",
    "bekas",
    "second",
    "2nd",
    "like new",
    "no minus",
    "minus",
    "fungsi normal",
    "pemakaian",
)
WEAK_CONDITION_KEYWORDS = (
    "fullset",
    "full set",
    "garansi",
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class HtmlToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.parts.append(f" {href} ")

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self.parts))
        raw = re.sub(r"\r\n?", "\n", raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


class RateLimitedError(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


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


def fetch_text(
    url: str,
    user_agent: str,
    retries: int,
    retry_wait: int,
    retry_jitter: float = 0.0,
    timeout: int = 30,
) -> str:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    max_attempts = retries
    tls_recovery_added = False
    attempt = 1
    while attempt <= max_attempts:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                wait = retry_wait_with_jitter(exc, retry_wait, retry_jitter)
                print(f"Reddit returned 429. Waiting {wait:.1f}s before retry {attempt + 1}/{retries}...", file=sys.stderr)
                time.sleep(wait)
                attempt += 1
                continue
            if exc.code == 429:
                raise RateLimitedError("Reddit returned HTTP 429", retry_after_seconds(exc)) from exc
            raise
        except urllib.error.URLError as exc:
            tls_verification_failed = is_tls_verification_error(exc)
            if tls_verification_failed and not tls_recovery_added:
                max_attempts += 1
                tls_recovery_added = True
            if attempt < max_attempts and (is_retryable_transport_error(exc) or tls_verification_failed):
                wait = retry_wait_seconds(retry_wait, retry_jitter)
                failure_kind = "TLS verification" if tls_verification_failed else "transport"
                print(
                    f"Reddit {failure_kind} error ({exc}). Waiting {wait:.1f}s before verified retry "
                    f"{attempt + 1}/{max_attempts}...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                attempt += 1
                continue
            raise
        except TimeoutError as exc:
            if attempt < max_attempts:
                wait = retry_wait_seconds(retry_wait, retry_jitter)
                print(
                    f"Reddit request timed out ({exc}). Waiting {wait:.1f}s before retry "
                    f"{attempt + 1}/{max_attempts}...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                attempt += 1
                continue
            raise

    raise RuntimeError("fetch failed without a specific HTTP error")


def retry_after_seconds(exc: urllib.error.HTTPError) -> int | None:
    raw_value = exc.headers.get("Retry-After") if exc.headers else None
    if not raw_value:
        return None
    raw_value = raw_value.strip()
    if raw_value.isdigit():
        return max(1, int(raw_value))
    try:
        retry_at = parsedate_to_datetime(raw_value)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    delta = retry_at.astimezone(timezone.utc) - now_utc()
    return max(1, int(delta.total_seconds()))


def retry_wait_with_jitter(exc: urllib.error.HTTPError, retry_wait: int, retry_jitter: float) -> float:
    retry_after = retry_after_seconds(exc)
    if retry_after is not None:
        return float(retry_after)
    return retry_wait_seconds(retry_wait, retry_jitter)


def retry_wait_seconds(retry_wait: int, retry_jitter: float) -> float:
    return float(retry_wait) + random.uniform(0.0, max(0.0, retry_jitter))


def is_retryable_transport_error(exc: urllib.error.URLError) -> bool:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, TimeoutError):
        return True
    reason_text = str(reason or exc).lower()
    retryable_markers = (
        "timed out",
        "temporarily unavailable",
        "temporary failure",
        "connection reset",
        "connection aborted",
        "remote end closed",
        "handshake operation timed out",
    )
    return any(marker in reason_text for marker in retryable_markers)


def is_tls_verification_error(exc: Exception) -> bool:
    reason = getattr(exc, "reason", None)
    reason_text = str(reason or exc).lower()
    markers = (
        "certificate verify failed",
        "self-signed certificate",
        "unable to get local issuer certificate",
        "hostname mismatch",
    )
    return any(marker in reason_text for marker in markers)


def build_rss_url(limit: int, subreddit: str = SUBREDDIT, flair: str = FLAIR) -> str:
    query = urllib.parse.urlencode(
        {
            "q": f'flair:"{flair}"',
            "restrict_sr": "1",
            "sort": "new",
            "limit": str(limit),
        }
    )
    return f"https://www.reddit.com/r/{subreddit}/search.rss?{query}"


def parsedate_to_datetime(value: str) -> datetime:
    from email.utils import parsedate_to_datetime as parse_email_date

    return parse_email_date(value)


def clean_html(value: str) -> str:
    parser = HtmlToText()
    parser.feed(value or "")
    return parser.text()


def clean_description(value: str, post_url: str) -> str:
    lines = [line.strip() for line in value.splitlines()]
    if lines and post_url and lines[0].rstrip("/") == post_url.rstrip("/"):
        lines = lines[1:]

    cleaned = "\n".join(line for line in lines if line).strip()
    cleaned = re.sub(r"(https?://\S+)\s+\1", r"\1", cleaned)
    cleaned = re.sub(
        r"\s+submitted by\s+https://www\.reddit\.com/user/\S+\s+/u/\S+.*$",
        "",
        cleaned,
        flags=re.S,
    )
    return cleaned.strip()


def extract_image_urls(content_html: str) -> list[str]:
    value = html.unescape(content_html or "")
    urls = re.findall(r"https?://[^\s\"'<>]+", value)
    return unique_image_urls(urls)


def unique_image_urls(urls: Iterable[str]) -> list[str]:
    images: list[str] = []
    for url in urls:
        clean = html.unescape(str(url)).rstrip(").,]")
        lower = clean.lower()
        if (
            "i.redd.it/" in lower
            or "preview.redd.it/" in lower
            or re.search(r"\.(?:jpg|jpeg|png|webp)(?:\?|$)", lower)
        ):
            if clean not in images:
                images.append(clean)
    return images


def fetch_post_detail_images(
    post: dict[str, Any],
    *,
    user_agent: str,
    retries: int,
    retry_wait: int,
    retry_jitter: float,
    timeout: int,
) -> list[str]:
    external_id = extract_external_id(str(post.get("url", "")), str(post.get("atom_id", "")))
    candidates = build_post_json_urls(str(post.get("url", "")), external_id)
    last_error: Exception | None = None

    for url in candidates:
        try:
            payload = fetch_json(url, user_agent, retries, retry_wait, retry_jitter, timeout)
        except RateLimitedError:
            raise
        except Exception as exc:
            last_error = exc
            continue

        images = extract_images_from_reddit_json(payload)
        if images:
            return images

    if last_error:
        raise last_error
    return []


def build_post_json_urls(post_url: str, external_id: str | None) -> list[str]:
    urls: list[str] = []
    if external_id:
        urls.extend(
            [
                f"https://www.reddit.com/comments/{external_id}.json?raw_json=1",
                f"https://old.reddit.com/comments/{external_id}.json?raw_json=1",
            ]
        )

    canonical = canonical_url(post_url)
    if canonical:
        urls.append(f"{canonical.rstrip('/')}.json?raw_json=1")

    return unique_prefix(urls, 4)


def fetch_json(
    url: str,
    user_agent: str,
    retries: int,
    retry_wait: int,
    retry_jitter: float,
    timeout: int,
) -> Any:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json,*/*;q=0.8",
    }

    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                wait = retry_wait_with_jitter(exc, retry_wait, retry_jitter)
                print(
                    f"Reddit image detail returned 429. Waiting {wait:.1f}s before retry {attempt + 1}/{retries}...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            if exc.code == 429:
                raise RateLimitedError("Reddit image detail returned HTTP 429", retry_after_seconds(exc)) from exc
            raise
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Reddit image detail returned invalid JSON from {url}") from exc

    raise RuntimeError("JSON fetch failed without a specific HTTP error")


def extract_images_from_reddit_json(payload: Any) -> list[str]:
    submission = find_submission_payload(payload)
    if not submission:
        return []

    urls: list[str] = []
    gallery_data = submission.get("gallery_data") if isinstance(submission.get("gallery_data"), dict) else {}
    media_metadata = submission.get("media_metadata") if isinstance(submission.get("media_metadata"), dict) else {}
    gallery_items = gallery_data.get("items") if isinstance(gallery_data.get("items"), list) else []

    media_ids = [
        str(item.get("media_id") or "")
        for item in gallery_items
        if isinstance(item, dict) and item.get("media_id")
    ]
    if not media_ids:
        media_ids = [str(media_id) for media_id in media_metadata.keys()]

    for media_id in media_ids:
        metadata = media_metadata.get(media_id)
        if isinstance(metadata, dict):
            urls.extend(extract_images_from_media_metadata(metadata))

    preview = submission.get("preview") if isinstance(submission.get("preview"), dict) else {}
    preview_images = preview.get("images") if isinstance(preview.get("images"), list) else []
    for image in preview_images:
        if isinstance(image, dict):
            source = image.get("source") if isinstance(image.get("source"), dict) else {}
            urls.append(source.get("url") or "")

    for key in ("url_overridden_by_dest", "url"):
        value = submission.get(key)
        if isinstance(value, str):
            urls.append(value)

    return unique_image_urls(urls)


def find_submission_payload(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list) and payload:
        return find_submission_payload(payload[0])
    if not isinstance(payload, dict):
        return None

    children = (
        payload.get("data", {})
        .get("children", [])
        if isinstance(payload.get("data"), dict)
        else []
    )
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                continue
            data = child.get("data")
            if isinstance(data, dict) and data.get("id"):
                return data
    return None


def extract_images_from_media_metadata(metadata: dict[str, Any]) -> list[str]:
    if metadata.get("status") and metadata.get("status") != "valid":
        return []
    if metadata.get("m") and not str(metadata.get("m")).startswith("image/"):
        return []

    urls: list[str] = []
    source = metadata.get("s") if isinstance(metadata.get("s"), dict) else {}
    for key in ("u", "gif"):
        value = source.get(key)
        if isinstance(value, str):
            urls.append(value)

    previews = metadata.get("p") if isinstance(metadata.get("p"), list) else []
    if previews:
        largest = max(
            (preview for preview in previews if isinstance(preview, dict)),
            key=lambda preview: int(preview.get("x") or 0) * int(preview.get("y") or 0),
            default=None,
        )
        if largest and isinstance(largest.get("u"), str):
            urls.append(largest["u"])

    return urls


def enrich_posts_with_detail_images(
    posts: list[dict[str, Any]],
    *,
    state: dict[str, Any],
    no_state: bool,
    mode: str,
    scope: str,
    user_agent: str,
    retries: int,
    retry_wait: int,
    retry_jitter: float,
    timeout: int,
    delay_seconds: float,
) -> list[dict[str, Any]]:
    if mode == "rss":
        return posts

    enriched: list[dict[str, Any]] = []
    detail_attempts = 0
    for post in posts:
        item = dict(post)
        if should_fetch_detail_images(item, state, no_state=no_state, scope=scope):
            if detail_attempts and delay_seconds > 0:
                time.sleep(delay_seconds)
            detail_attempts += 1
            try:
                detail_images = fetch_post_detail_images(
                    item,
                    user_agent=user_agent,
                    retries=retries,
                    retry_wait=retry_wait,
                    retry_jitter=retry_jitter,
                    timeout=timeout,
                )
            except RateLimitedError as exc:
                print(f"Reddit image detail rate-limited; keeping RSS images for remaining posts: {exc}", file=sys.stderr)
                enriched.append(item)
                enriched.extend(dict(remaining) for remaining in posts[len(enriched) :])
                return enriched
            except Exception as exc:
                if mode == "auto":
                    print(f"Reddit image detail unavailable; keeping RSS images this run: {exc}", file=sys.stderr)
                    enriched.append(item)
                    enriched.extend(dict(remaining) for remaining in posts[len(enriched) :])
                    return enriched
                if mode == "detail":
                    print(f"Reddit image detail failed; keeping RSS image for {item.get('url')}: {exc}", file=sys.stderr)
                enriched.append(item)
                continue

            merged_images = unique_image_urls(detail_images + list(item.get("images", [])))
            if merged_images:
                item["images"] = merged_images
        enriched.append(item)
    return enriched


def should_fetch_detail_images(
    post: dict[str, Any],
    state: dict[str, Any],
    *,
    no_state: bool,
    scope: str,
) -> bool:
    if no_state or scope == "all":
        return True
    external_id = str(extract_external_id(str(post.get("url", "")), str(post.get("atom_id", ""))) or "")
    source_url = canonical_url(str(post.get("url", "")))
    seen_ids = set(str(value) for value in state.get("seen_external_ids", []) if value)
    seen_urls = set(str(value) for value in state.get("seen_source_urls", []) if value)
    return not ((external_id and external_id in seen_ids) or (source_url and source_url in seen_urls))


def parse_feed(xml_text: str, limit: int) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    posts: list[dict[str, Any]] = []

    for entry in root.findall("atom:entry", ATOM_NS)[:limit]:
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS).strip()
        updated = entry.findtext("atom:updated", default="", namespaces=ATOM_NS).strip()
        author = entry.findtext("atom:author/atom:name", default="", namespaces=ATOM_NS).strip()
        atom_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS).strip()
        content_html = entry.findtext("atom:content", default="", namespaces=ATOM_NS)
        body = clean_html(content_html)
        images = extract_image_urls(content_html)

        url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            href = link.attrib.get("href", "")
            rel = link.attrib.get("rel", "")
            if href and (rel == "alternate" or "/comments/" in href):
                url = href
                break
            if href and not url:
                url = href

        if not url:
            match = re.search(r"https://www\.reddit\.com/r/jualbeliindonesia/comments/\S+", body)
            if match:
                url = match.group(0)

        body = clean_description(body, url)

        posts.append(
            {
                "title": title,
                "updated": updated,
                "author": author,
                "url": url,
                "atom_id": atom_id,
                "description": body,
                "images": images,
            }
        )

    return posts


def normalize_post(post: dict[str, Any], fetched_at: datetime | None = None) -> dict[str, Any]:
    title = str(post.get("title", "")).strip()
    description = str(post.get("description", "")).strip()
    text = "\n".join(part for part in [title, description] if part)
    fetched_at_text = (fetched_at or now_utc()).isoformat()
    images = [
        {
            "sourceUrl": image_url,
            "position": index,
            "altText": post.get("title") or None,
        }
        for index, image_url in enumerate(post.get("images", []))
    ]

    return {
        "platform": PLATFORM,
        "sourceUrl": canonical_url(str(post.get("url", ""))),
        "externalId": extract_external_id(str(post.get("url", "")), str(post.get("atom_id", ""))),
        "title": title,
        "description": description,
        "category": extract_category(text),
        "brand": extract_brand(text),
        "price": extract_price(text),
        "locationTexts": extract_locations(text),
        "conditionText": extract_condition(description) or extract_condition(text),
        "sellerName": str(post.get("author", "")).strip() or None,
        "status": extract_status(text),
        "postedAt": normalize_datetime_string(str(post.get("updated", ""))),
        "firstFetchedAt": fetched_at_text,
        "lastFetchedAt": fetched_at_text,
        "images": images,
    }


def normalize_datetime_string(value: str) -> str | None:
    parsed = parse_iso_datetime(value)
    return parsed.isoformat() if parsed else None


def canonical_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or (parsed.hostname or "").lower() not in REDDIT_HOSTS:
        return ""
    path = parsed.path
    if not path.endswith("/"):
        path = f"{path}/"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def extract_external_id(url: str, atom_id: str = "") -> str | None:
    match = re.search(r"/comments/([a-z0-9]+)/", url, flags=re.I)
    if match:
        return match.group(1)
    if atom_id:
        match = re.search(r"(?:t3_)?([a-z0-9]+)$", atom_id, flags=re.I)
        if match:
            return match.group(1)
    return None


def extract_status(text: str) -> str:
    lower = normalize_spaces(text).lower()
    if any(marker in lower for marker in SOLD_MARKERS):
        return "SOLD"
    if any(marker in lower for marker in AVAILABLE_MARKERS):
        return "AVAILABLE"
    return "AVAILABLE"


def extract_price(text: str) -> int | None:
    candidates: list[tuple[int, int, int]] = []
    for line_number, raw_line in enumerate(iter_lines(text)):
        line = raw_line.strip()
        lower = line.lower()
        has_context = any(word in lower for word in PRICE_CONTEXT_WORDS)
        context_score = 60 if has_context else 0
        if "harga new" in lower or "harga baru" in lower:
            context_score -= 45

        for match in re.finditer(r"\brp\.?\s*([0-9][0-9.,]*[0-9]|[0-9])(?:\s*(jt|juta+|rb|ribu|k))?", line, flags=re.I):
            amount = price_token_to_int(match.group(1), match.group(2))
            if amount:
                candidates.append((120 + context_score - line_number, amount, line_number))

        for match in re.finditer(r"(?<![a-z0-9.,])([0-9]+(?:[.,][0-9]+)?)(?![.,0-9])\s*(jt|juta+|rb|ribu|k)\b", line, flags=re.I):
            amount = price_token_to_int(match.group(1), match.group(2))
            if amount:
                candidates.append((80 + context_score - line_number, amount, line_number))

        if has_context:
            for match in re.finditer(r"(?<![0-9.,])([0-9]{1,3}(?:[.,][0-9]{3}){1,3})(?![0-9.,])(?:\s*(?:jt|juta+))?", line, flags=re.I):
                amount = price_token_to_int(match.group(1), None)
                if amount:
                    candidates.append((65 + context_score - line_number, amount, line_number))

    if not candidates:
        return None
    candidates.sort(key=lambda candidate: (-candidate[0], candidate[2]))
    return candidates[0][1]


def price_token_to_int(token: str, unit: str | None) -> int | None:
    token = token.strip()
    unit = (unit or "").lower()
    has_thousand_groups = bool(re.fullmatch(r"[0-9]{1,3}(?:[.,][0-9]{3})+", token))

    if unit in {"jt", "juta"} or unit.startswith("juta"):
        if has_thousand_groups:
            amount = int(re.sub(r"\D", "", token))
        else:
            amount = int(float(token.replace(",", ".")) * 1_000_000)
    elif unit in {"rb", "ribu", "k"}:
        amount = int(float(token.replace(",", ".")) * 1_000)
    elif has_thousand_groups:
        amount = int(re.sub(r"\D", "", token))
    else:
        digits = re.sub(r"\D", "", token)
        amount = int(digits) if digits else 0

    if amount < 10_000 or amount > 200_000_000:
        return None
    return amount


def extract_category(text: str) -> str | None:
    for line in iter_lines(text):
        lower = normalize_spaces(line).lower()
        for category, keywords in CATEGORY_PATTERNS:
            if any(keyword_matches(lower, keyword) for keyword in keywords):
                return category
    return None


def extract_brand(text: str) -> str | None:
    for line in iter_lines(text):
        lower = normalize_spaces(line).lower()
        for brand, keywords in BRAND_PATTERNS:
            if any(keyword_matches(lower, keyword) for keyword in keywords):
                return brand
    return None


def keyword_matches(text: str, keyword: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return bool(re.search(pattern, text, flags=re.I))


def extract_locations(text: str) -> list[str]:
    locations: list[str] = []
    for line in iter_lines(text):
        stripped = trim_value(line)
        lower = stripped.lower()

        match = re.search(r"^(?:lokasi|location|loc)\s*[:\-]?\s*(.+)$", stripped, flags=re.I)
        if match:
            locations.extend(normalize_location_values(match.group(1)))
            continue

        match = re.search(r"\bcod\s+(?:only\s+|bisa\s+di\s+|di\s+)?(.+)$", stripped, flags=re.I)
        if match:
            locations.extend(normalize_location_values(match.group(1)))
            continue

        match = re.search(r"\bprefer\s+cod\s+(.+)$", stripped, flags=re.I)
        if match:
            locations.extend(normalize_location_values(match.group(1)))
            continue

        if any(word in lower for word in LOCATION_WORDS):
            locations.extend(find_known_locations(stripped))

    for line in iter_lines(text):
        locations.extend(find_known_locations(line))
    return unique_locations(locations)


def normalize_location_values(value: str) -> list[str]:
    cleaned = cleanup_location(value)
    if not cleaned:
        return []

    known = find_known_locations(cleaned)
    if known:
        return known

    parts = re.split(r"\s*(?:,|/|;|\||&|\+|\bdan\b|\batau\b|\bor\b)\s*", cleaned, flags=re.I)
    return [part[:160] for part in (trim_value(part) for part in parts) if part]


def cleanup_location(value: str) -> str | None:
    value = trim_value(value)
    value = re.sub(r"\b(?:bisa|prefer|only|aja|dan|sekitarnya)?\s*(?:kirim|lewat|ekspedisi|paket|juga).*$", "", value, flags=re.I).strip(" ,.-")
    if not value:
        return None
    return value[:160]


def find_known_locations(value: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for location in KNOWN_LOCATIONS:
        match = re.search(rf"\b{re.escape(location)}\b", value, flags=re.I)
        if match:
            matches.append((match.start(), location))
    return unique_locations(location for _, location in sorted(matches, key=lambda item: item[0]))


def unique_locations(values: Iterable[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = trim_value(value)
        key = clean.casefold()
        if not clean or key in seen:
            continue
        seen.add(key)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def extract_condition(text: str) -> str | None:
    lines = list(iter_lines(text))
    for index, line in enumerate(lines):
        stripped = trim_value(line)
        lower = stripped.lower()
        if re.match(r"^(kondisi|condition)\s*[:\-]?\s*$", stripped, flags=re.I):
            for next_line in lines[index + 1 :]:
                next_value = trim_value(next_line)
                if next_value:
                    return next_value[:240]
        match = re.match(r"^(kondisi|condition)\s*[:\-]\s*(.+)$", stripped, flags=re.I)
        if match:
            return trim_value(match.group(2))[:240]
        if stripped.lower().startswith("wts "):
            continue
        if any(keyword in lower for keyword in DIRECT_CONDITION_KEYWORDS):
            return stripped[:240]
    for line in lines:
        stripped = trim_value(line)
        lower = stripped.lower()
        if stripped.lower().startswith("wts "):
            continue
        if any(keyword in lower for keyword in WEAK_CONDITION_KEYWORDS):
            return stripped[:240]
    return None


def iter_lines(text: str) -> Iterable[str]:
    for line in text.splitlines():
        stripped = line.strip(" \t-*")
        if stripped:
            yield stripped


def trim_value(value: str) -> str:
    value = normalize_spaces(value)
    value = value.strip(" :;,.|-")
    return value


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


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


def listing_identity(listing: dict[str, Any]) -> str:
    return str(listing.get("externalId") or listing.get("sourceUrl") or "")


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


def run_once(
    args: argparse.Namespace,
    *,
    include_status: bool = False,
) -> tuple[int, list[dict[str, Any]]] | tuple[int, list[dict[str, Any]], str]:
    state_path = Path(args.state_file)
    log_path = None if args.no_state else Path(args.log_file)
    state = default_state() if args.no_state else load_state(state_path)
    state["last_run_at"] = now_utc().isoformat()

    cooldown_remaining = 0 if args.ignore_cooldown else cooldown_seconds_remaining(state)
    if cooldown_remaining > 0:
        log_event(
            log_path,
            {
                "source": "reddit",
                "status": "cooldown_skip",
                "cooldown_remaining_seconds": cooldown_remaining,
            },
        )
        print(f"Reddit connector is cooling down for {cooldown_remaining}s.", file=sys.stderr)
        return format_run_result(0, [], "cooldown_skip", include_status)

    url = build_rss_url(args.limit, getattr(args, "subreddit", SUBREDDIT), getattr(args, "flair", FLAIR))
    print(f"Fetching: {url}", file=sys.stderr)

    try:
        xml_text = fetch_text(
            url,
            args.user_agent,
            args.retries,
            args.retry_wait,
            getattr(args, "retry_jitter_seconds", 0.0),
            args.timeout,
        )
        posts = parse_feed(xml_text, args.limit)
        posts = enrich_posts_with_detail_images(
            posts,
            state=state,
            no_state=args.no_state,
            mode=args.image_mode,
            scope=args.image_detail_scope,
            user_agent=args.user_agent,
            retries=args.image_retries,
            retry_wait=args.retry_wait,
            retry_jitter=getattr(args, "retry_jitter_seconds", 0.0),
            timeout=args.image_timeout,
            delay_seconds=args.image_detail_delay,
        )
        fetched_at = now_utc()
        listings = dedupe_listings([normalize_post(post, fetched_at) for post in posts])
        if args.ai_parse and listings:
            try:
                listings = enrich_listings_with_nvidia(
                    listings,
                    model=args.ai_model,
                    batch_size=args.ai_batch_size,
                    rate_limit_seconds=args.ai_rate_limit,
                    timeout=args.ai_timeout,
                    prefer_ai=args.ai_prefer,
                )
            except NvidiaParserError as exc:
                log_event(
                    log_path,
                    {
                        "source": "reddit",
                        "status": "ai_parse_failed",
                        "error": str(exc),
                    },
                )
                print(f"NVIDIA AI parsing skipped: {exc}", file=sys.stderr)
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
                "source": "reddit",
                "status": "success",
                "fetched": len(posts),
                "normalized": len(listings),
                "new": len(new_listings),
            },
        )
    except RateLimitedError as exc:
        wait = exc.retry_after_seconds or args.cooldown_seconds
        set_cooldown(state, wait, str(exc))
        if not args.no_state:
            save_state(state_path, state)
        log_event(
            log_path,
            {
                "source": "reddit",
                "status": "rate_limited",
                "cooldown_seconds": wait,
                "error": str(exc),
            },
        )
        print(f"Reddit rate limited this connector. Cooling down for {wait}s.", file=sys.stderr)
        return format_run_result(1, [], "rate_limited", include_status)
    except Exception as exc:
        if is_tls_verification_error(exc):
            wait = max(60, args.cooldown_seconds)
            set_cooldown(state, wait, str(exc))
            if not args.no_state:
                save_state(state_path, state)
            log_event(
                log_path,
                {
                    "source": "reddit",
                    "status": "tls_verification_failed",
                    "cooldown_seconds": wait,
                    "error": str(exc),
                },
            )
            print(f"Reddit TLS verification failed. Cooling down for {wait}s.", file=sys.stderr)
            return format_run_result(1, [], "tls_verification_failed", include_status)
        state["last_error"] = str(exc)
        if not args.no_state:
            save_state(state_path, state)
        log_event(
            log_path,
            {
                "source": "reddit",
                "status": "failed",
                "error": str(exc),
            },
        )
        print(f"Failed to fetch Reddit posts: {exc}", file=sys.stderr)
        return format_run_result(1, [], "failed", include_status)

    selected = new_listings if args.emit == "new" else listings
    return format_run_result(0, selected, "success", include_status)


def format_run_result(
    code: int,
    listings: list[dict[str, Any]],
    status: str,
    include_status: bool,
) -> tuple[int, list[dict[str, Any]]] | tuple[int, list[dict[str, Any]], str]:
    if include_status:
        return code, listings, status
    return code, listings


def dedupe_listings(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for listing in listings:
        identity = listing_identity(listing)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        deduped.append(listing)
    return deduped


def print_posts(posts: list[dict[str, Any]]) -> None:
    if not posts:
        print("No posts found.")
        return

    for index, post in enumerate(posts, start=1):
        print("=" * 80)
        print(f"{index}. {post['title']}")
        print(f"Author: {post['author']}")
        print(f"Updated: {post['updated']}")
        print(f"URL: {post['url']}")
        print()
        print(post["description"] or "[no description found]")
        print()


def print_listings(listings: list[dict[str, Any]], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(listings, ensure_ascii=False, indent=2))
        return
    if output_format == "jsonl":
        for listing in listings:
            print(json.dumps(listing, ensure_ascii=False, separators=(",", ":")))
        return

    if not listings:
        print("No posts found.")
        return

    for index, listing in enumerate(listings, start=1):
        print("=" * 80)
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
        print()
        print(listing.get("description") or "[no description found]")
        print()


def watch(args: argparse.Namespace) -> int:
    iteration = 0
    while True:
        iteration += 1
        code, listings = guarded_run_once(args)
        print_listings(listings, args.format)
        if args.max_iterations and iteration >= args.max_iterations:
            return code
        sleep_for = max(1, args.interval)
        if args.jitter:
            sleep_for += random.randint(0, args.jitter)
        time.sleep(sleep_for)


def guarded_run_once(
    args: argparse.Namespace,
    *,
    include_status: bool = False,
) -> tuple[int, list[dict[str, Any]]] | tuple[int, list[dict[str, Any]], str]:
    if args.no_state:
        return run_once(args, include_status=include_status)

    try:
        with FileLock(Path(args.lock_file), args.lock_stale_seconds):
            return run_once(args, include_status=include_status)
    except AlreadyRunningError as exc:
        log_event(
            Path(args.log_file),
            {
                "source": "reddit",
                "status": "locked",
                "error": str(exc),
            },
        )
        print(str(exc), file=sys.stderr)
        return format_run_result(2, [], "locked", include_status)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch latest Reddit WTS computer/peripheral posts.")
    parser.add_argument("--limit", type=int, default=15, help="Number of posts to fetch.")
    parser.add_argument("--subreddit", default=SUBREDDIT, help="Subreddit name for the Reddit RSS search.")
    parser.add_argument("--flair", default=FLAIR, help="Flair name for the Reddit RSS search.")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry attempts.")
    parser.add_argument("--retry-wait", type=int, default=20, help="Seconds to wait after HTTP 429.")
    parser.add_argument("--retry-jitter-seconds", type=float, default=0.0, help="Random extra seconds added to retry waits.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between watch-mode checks.")
    parser.add_argument("--jitter", type=int, default=8, help="Random extra seconds in watch mode.")
    parser.add_argument("--once", action="store_true", help="Run one fetch cycle. This is the default mode.")
    parser.add_argument("--watch", action="store_true", help="Run continuously.")
    parser.add_argument("--max-iterations", type=int, default=0, help="Stop watch mode after this many iterations.")
    parser.add_argument("--emit", choices=["all", "new"], default=None, help="Print all fetched listings or only unseen ones.")
    parser.add_argument("--only-new", action="store_true", help="Alias for --emit new.")
    parser.add_argument("--format", choices=["text", "json", "jsonl"], default="text", help="Output format.")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="State JSON path.")
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE), help="Duplicate-run lock path.")
    parser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE), help="JSONL run log path.")
    parser.add_argument("--max-seen", type=int, default=500, help="Maximum seen IDs retained in state.")
    parser.add_argument("--cooldown-seconds", type=int, default=300, help="Cooldown after final HTTP 429 when Retry-After is missing.")
    parser.add_argument("--ignore-cooldown", action="store_true", help="Ignore active cooldown state.")
    parser.add_argument("--no-state", action="store_true", help="Do not read/write state, lock, or run logs.")
    parser.add_argument("--lock-stale-seconds", type=int, default=900, help="Remove lock files older than this many seconds.")
    parser.add_argument(
        "--image-mode",
        choices=["auto", "rss", "detail"],
        default="auto",
        help="Image extraction mode. auto/detail try Reddit post JSON for full galleries and fall back to RSS images.",
    )
    parser.add_argument(
        "--image-detail-scope",
        choices=["new", "all"],
        default="new",
        help="With state enabled, fetch post image details only for new posts or for every fetched post.",
    )
    parser.add_argument("--image-retries", type=int, default=1, help="HTTP retry attempts for per-post image detail fetches.")
    parser.add_argument("--image-timeout", type=int, default=20, help="Per-post image detail timeout in seconds.")
    parser.add_argument("--image-detail-delay", type=float, default=1.0, help="Seconds between per-post image detail requests.")
    parser.add_argument("--ai-parse", action="store_true", help="Enrich parsed listing fields with NVIDIA AI extraction.")
    parser.add_argument("--ai-prefer", action="store_true", help="Let AI values replace rule-parser values when available.")
    parser.add_argument("--ai-model", default=None, help="NVIDIA model ID for AI parsing.")
    parser.add_argument("--ai-batch-size", type=int, default=5, help="Listings per NVIDIA parser request.")
    parser.add_argument("--ai-rate-limit", type=float, default=2.0, help="Seconds between NVIDIA parser requests.")
    parser.add_argument("--ai-timeout", type=int, default=45, help="NVIDIA parser timeout in seconds.")
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header sent to Reddit.",
    )
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 100:
        print("--limit must be between 1 and 100.", file=sys.stderr)
        return 2
    if args.ai_batch_size < 1 or args.ai_batch_size > 10:
        print("--ai-batch-size must be between 1 and 10.", file=sys.stderr)
        return 2
    if args.interval < 30:
        print("--interval must be at least 30 seconds for Reddit RSS.", file=sys.stderr)
        return 2
    if args.retry_jitter_seconds < 0 or args.retry_jitter_seconds > 60:
        print("--retry-jitter-seconds must be between 0 and 60.", file=sys.stderr)
        return 2
    if args.image_retries < 1 or args.image_retries > 3:
        print("--image-retries must be between 1 and 3.", file=sys.stderr)
        return 2
    if args.image_timeout < 5:
        print("--image-timeout must be at least 5 seconds.", file=sys.stderr)
        return 2
    if args.image_detail_delay < 0:
        print("--image-detail-delay must be zero or greater.", file=sys.stderr)
        return 2
    if args.only_new:
        args.emit = "new"
    elif args.emit is None:
        args.emit = "new" if args.watch else "all"

    if args.watch:
        return watch(args)

    code, listings = guarded_run_once(args)
    print_listings(listings, args.format)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
