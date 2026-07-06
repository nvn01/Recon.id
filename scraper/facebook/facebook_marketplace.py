"""
Starter Facebook Marketplace probe for RECON data collection.

This is intentionally simple:
- no database
- no JSON export
- no backend/app integration
- uses a browser session because Facebook Marketplace is JS/session-driven

First-time setup:
    python "scraper/facebook/facebook_marketplace.py" --login

Then scrape sample cards:
    python "scraper/facebook/facebook_marketplace.py" --query vga --limit 5

For listing descriptions/condition:
    python "scraper/facebook/facebook_marketplace.py" --query vga --limit 5 --details
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_LOCATION = "jakarta"
DEFAULT_CATEGORY_ID = "479353692612078"  # Facebook Marketplace Electronics category
DEFAULT_PROFILE_DIR = Path(__file__).resolve().parent / ".facebook-profile"
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
    "switch",
    "steam deck",
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


def keyword_matches(text: str, keyword: str) -> bool:
    lower = text.lower()
    keyword_lower = keyword.lower().strip()
    if not keyword_lower:
        return False

    if keyword_lower in {"pc", "gpu", "vga", "rtx", "gtx", "ram", "ssd", "hdd", "psu"}:
        return bool(re.search(rf"\b{re.escape(keyword_lower)}\b", lower))

    return keyword_lower in lower


def matched_keywords(card: MarketplaceCard, keywords: list[str]) -> list[str]:
    searchable_text = " ".join((card.raw_text, card.image_alt))
    return [keyword for keyword in keywords if keyword_matches(searchable_text, keyword)]


def build_search_url(location: str, query: str, category_id: str) -> str:
    params = urlencode(
        {
            "sortBy": "creation_time_descend",
            "query": query,
            "category_id": category_id,
            "exact": "false",
        }
    )
    return f"https://www.facebook.com/marketplace/{location}/search?{params}"


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


def extract_cards(page, limit: int) -> list[MarketplaceCard]:
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


def parse_detail_text(text: str) -> dict[str, str]:
    lines = compact_lines(text)
    detail: dict[str, str] = {
        "posted": "",
        "condition": "",
        "description": "",
        "approx_location": "",
        "seller": "",
    }

    for line in lines:
        if line.startswith("Ditawarkan ") and not detail["posted"]:
            detail["posted"] = line
        if "Perkiraan lokasi" in line and not detail["approx_location"]:
            detail["approx_location"] = line

    if "Kondisi" in lines:
        condition_index = lines.index("Kondisi")
        if condition_index + 1 < len(lines):
            detail["condition"] = lines[condition_index + 1]

        description_start = condition_index + 2
    elif "Detail" in lines:
        description_start = lines.index("Detail") + 1
    else:
        description_start = 0

    stop_labels = {
        "Informasi penjual",
        "Detail penjual",
        "Kirim pesan ke penjual",
        "Kirim",
        "Pilihan hari ini",
    }
    description_parts: list[str] = []
    for line in lines[description_start:]:
        if line in stop_labels:
            break
        if "Perkiraan lokasi" in line:
            continue
        description_parts.append(line)

    detail["description"] = "\n".join(description_parts).strip()

    if "Detail penjual" in lines:
        seller_index = lines.index("Detail penjual")
        if seller_index + 1 < len(lines):
            detail["seller"] = lines[seller_index + 1]

    return detail


def open_marketplace(page, url: str, wait_ms: int, timeout_ms: int) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(wait_ms)


def scrape_query(page, query: str, args: argparse.Namespace, keywords: list[str]) -> list[MarketplaceCard]:
    url = build_search_url(args.location, query, args.category_id)
    print(f"Fetching Facebook Marketplace query: {query}", file=sys.stderr)
    print(f"URL: {url}", file=sys.stderr)

    open_marketplace(page, url, args.wait_ms, args.timeout * 1000)

    try:
        page.wait_for_selector('a[href*="/marketplace/item/"]', timeout=args.timeout * 1000)
    except PlaywrightTimeoutError:
        page_text = extract_page_text(page, max_chars=1500)
        print("No Marketplace item cards appeared.", file=sys.stderr)
        if looks_login_blocked(page_text):
            print(
                "The page looks login-gated. Run with --login first, then rerun the scrape command.",
                file=sys.stderr,
            )
        else:
            print("Page text sample:", file=sys.stderr)
            print(page_text, file=sys.stderr)
        return []

    candidates = extract_cards(page, args.candidate_limit)
    if args.no_relevance_filter:
        return candidates[: args.limit]

    selected: list[MarketplaceCard] = []
    skipped = 0
    for card in candidates:
        if matched_keywords(card, keywords):
            selected.append(card)
        else:
            skipped += 1

        if len(selected) >= args.limit:
            break

    if skipped:
        print(f"Skipped {skipped} non-RECON Marketplace cards for query: {query}", file=sys.stderr)

    return selected


def scrape_detail(page, card: MarketplaceCard, args: argparse.Namespace) -> dict[str, str]:
    try:
        open_marketplace(page, card.url, args.wait_ms, args.timeout * 1000)
        return parse_detail_text(extract_page_text(page, max_chars=7000))
    except PlaywrightError as exc:
        return {"error": str(exc)}


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


def print_card(index: int, card: MarketplaceCard, detail: dict[str, str] | None, keywords: list[str]) -> None:
    print("=" * 88)
    print(f"{index}. {card.title or '[title not parsed]'}")
    print(f"Price:    {card.price or '[price not parsed]'}")
    print(f"Location: {card.location or '[location not parsed]'}")
    print(f"New:      {'yes' if card.is_newly_listed else 'no'}")
    print(f"Item ID:  {card.item_id}")
    print(f"URL:      {card.url}")
    print(f"Image:    {card.image_url or '[no image found]'}")
    matches = matched_keywords(card, keywords)
    if matches:
        print(f"Matched:  {', '.join(matches[:8])}")

    if card.image_alt:
        print(f"Alt:      {card.image_alt}")

    if detail:
        if detail.get("error"):
            print(f"Detail:   [failed] {detail['error']}")
            return

        print()
        print("Detail page:")
        if detail.get("posted"):
            print(f"Posted:      {detail['posted']}")
        if detail.get("condition"):
            print(f"Condition:   {detail['condition']}")
        if detail.get("approx_location"):
            print(f"Approx loc:  {detail['approx_location']}")
        if detail.get("seller"):
            print(f"Seller:      {detail['seller']}")
        if detail.get("description"):
            print()
            print(detail["description"])


def run_login(page) -> None:
    print("Opening Facebook Marketplace login/session page.", file=sys.stderr)
    page.goto("https://www.facebook.com/marketplace/", wait_until="domcontentloaded", timeout=60_000)
    print("Log in or verify Marketplace access in the opened browser window.", file=sys.stderr)
    input("Press Enter here after the browser session is ready...")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Facebook Marketplace sample cards for RECON.")
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Marketplace search query. Can be repeated. Default: vga",
    )
    parser.add_argument("--limit", type=int, default=5, help="Number of cards per query.")
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=40,
        help="Number of visible cards to inspect before RECON relevance filtering.",
    )
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Marketplace location slug.")
    parser.add_argument("--category-id", default=DEFAULT_CATEGORY_ID, help="Marketplace category id.")
    parser.add_argument("--details", action="store_true", help="Open each listing and fetch description/condition.")
    parser.add_argument("--login", action="store_true", help="Open browser for one-time Facebook login/session setup.")
    parser.add_argument("--headless", action="store_true", help="Run browser headless. Not recommended for first login.")
    parser.add_argument(
        "--browser",
        choices=("chrome", "chromium"),
        default="chrome",
        help="Use installed Chrome or Playwright Chromium.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent browser profile directory used for Facebook session cookies.",
    )
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
    args = parser.parse_args()

    queries = args.query or ["vga"]
    keywords = list(DEFAULT_RECON_KEYWORDS)
    if args.include_keyword:
        keywords.extend(args.include_keyword)

    profile_dir = Path(args.profile_dir).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome" if args.browser == "chrome" else None,
                headless=args.headless,
                locale="id-ID",
                viewport={"width": 1440, "height": 900},
            )
            page = context.pages[0] if context.pages else context.new_page()

            if args.login:
                run_login(page)
                context.close()
                return 0

            all_cards: list[MarketplaceCard] = []
            seen_ids: set[str] = set()

            for query in queries:
                cards = scrape_query(page, query, args, keywords)
                for card in cards:
                    if card.item_id in seen_ids:
                        continue
                    seen_ids.add(card.item_id)
                    all_cards.append(card)

            if not all_cards:
                print("No Facebook Marketplace cards found.")
                context.close()
                return 1

            for index, card in enumerate(all_cards, start=1):
                detail = scrape_detail(page, card, args) if args.details else None
                print_card(index, card, detail, keywords)
                print()

            context.close()
            return 0
    except PlaywrightError as exc:
        print(f"Facebook Marketplace scrape failed: {exc}", file=sys.stderr)
        if args.browser == "chromium":
            print("If Chromium is not installed, run: python -m playwright install chromium", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
