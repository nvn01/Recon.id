"""Fetch and normalize recent Instagram public profile posts for RECON."""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scraper.instagram.embedded import extract_profile_posts
    from scraper.reddit import reddit as rule_parser
    from scraper.shared.runtime import RetryPolicy, retry_after_seconds_from_headers, retry_call
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from instagram.embedded import extract_profile_posts
    from reddit import reddit as rule_parser
    from shared.runtime import RetryPolicy, retry_after_seconds_from_headers, retry_call


PLATFORM = "INSTAGRAM"
WEB_PROFILE_INFO_URL = "https://www.instagram.com/api/v1/users/web_profile_info/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
INSTAGRAM_APP_ID = "936619743392459"

SALE_MARKERS = (
    "harga",
    "price",
    "condition",
    "kondisi",
    "lokasi",
    "location",
    "garansi",
    "ready",
    "consign price",
    "code item",
    "kelengkapan",
    "rp",
    "idr",
)
SOLD_MARKERS = ("sold out", "soldout", "sold", "terjual", "laku", "booked")
ACCOUNT_SOLD_MARKERS: dict[str, tuple[str, ...]] = {
    "thelazytitip": ("sold",),
    "consigngaming": ("soldout", "sold out"),
    "gamecentral.id": ("sold out",),
}
INSTAGRAM_CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Desktop PC", ("fullset pc", "pc gaming", "pc rakitan", "desktop pc", "komputer gaming")),
    ("PC Case", ("case pc", "pc case", "casing pc", "chassis")),
    ("Monitor", ("monitor", "zowie xl", "240hz", "144hz", "165hz")),
    ("Keyboard", ("keyboard", "k100 rgb", "k70 rgb", "ducky one", "keychron")),
    ("Mouse", ("mouse", "attack shark", "razer viper", "deathadder")),
    ("Power Supply", ("power supply", "psu", "core reactor")),
    ("Game Console", ("playstation", "ps4", "ps5", "xbox", "nintendo switch")),
    ("Motherboard", ("motherboard", "mainboard", "mobo", "h610", "h610m", "b450", "b550", "b650", "x570", "z690", "z790")),
    ("Smartphone", ("xiaomi", "redmi", "poco", "iphone", "samsung galaxy", "oppo", "vivo", "realme")),
    ("Game", ("call of duty", "black ops", "final fantasy", "complete edition", "ps4 game", "ps5 game", "nintendo switch game")),
    ("Controller", ("controller", "gamepad", "dualsense", "dualshock", "joycon", "joy-con", "genki sase", "genki shadowcast")),
    ("Drawing Tablet", ("drawing tablet", "pen tablet", "veikk", "wacom", "huion")),
    ("Audio", ("speaker", "maono", "microphone", "mic ", "videomic")),
    ("Peripheral", ("headset", "headphone", "earphone", "webcam", "moza", "steering wheel", "pedals")),
)
INSTAGRAM_BRAND_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Corsair", ("corsair",)),
    ("BenQ", ("benq", "zowie")),
    ("Huawei", ("huawei",)),
    ("Ducky", ("ducky",)),
    ("RayNeo", ("rayneo",)),
    ("Cube Gaming", ("cube gaming",)),
    ("Attack Shark", ("attack shark",)),
    ("ADATA", ("adata", "xpg")),
    ("Rode", ("rode", "videomic")),
    ("Xiaomi", ("xiaomi", "redmi", "poco")),
    ("Activision", ("call of duty", "black ops")),
    ("Square Enix", ("final fantasy",)),
    ("Genki", ("genki",)),
    ("Moza", ("moza",)),
    ("Veikk", ("veikk",)),
    ("Wacom", ("wacom",)),
    ("Huion", ("huion",)),
    ("Maono", ("maono",)),
    ("Sony", ("sony",)),
    ("Sharp", ("sharp",)),
)


@dataclass(frozen=True)
class InstagramAccountResult:
    account: str
    ok: bool
    http_status: int | None
    transport: str
    returned_count: int
    normalized_count: int
    skipped_count: int
    error: str | None
    latest_shortcode: str | None


class InstagramFetchError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after_seconds = retry_after_seconds


def run_accounts(
    accounts: list[str],
    *,
    limit: int = 1,
    max_posts_per_account: int = 10,
    timeout: int = 30,
    delay_seconds: float = 1.0,
    user_agent: str = DEFAULT_USER_AGENT,
    retry_policy: RetryPolicy | None = None,
    fetch_mode: str = "direct",
    browser: str = "chromium",
    headless: bool = True,
    browser_wait_ms: int = 8000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    listings: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    fetched_at = datetime.now(timezone.utc)
    policy = retry_policy or RetryPolicy(attempts=1)

    for index, account in enumerate(accounts):
        if index and delay_seconds > 0:
            time.sleep(delay_seconds)
        try:
            status, payload = retry_call(
                lambda: fetch_profile_resilient(
                    account,
                    timeout=timeout,
                    user_agent=user_agent,
                    fetch_mode=fetch_mode,
                    browser=browser,
                    headless=headless,
                    browser_wait_ms=browser_wait_ms,
                ),
                policy=policy,
                should_retry=is_retryable_fetch_error,
                on_retry=lambda exc, next_attempt, attempts, delay: print(
                    f"Instagram {account} request failed ({exc}). Waiting {delay:.1f}s before retry {next_attempt}/{attempts}...",
                    file=sys.stderr,
                ),
            )
            posts = extract_posts(payload)
            selected: list[dict[str, Any]] = []
            skipped_count = 0
            for post in posts[:max_posts_per_account]:
                if not is_listing_post(post):
                    skipped_count += 1
                    continue
                selected.append(normalize_post(account, post, fetched_at))
                if len(selected) >= limit:
                    break
            listings.extend(selected)
            results.append(
                InstagramAccountResult(
                    account=account,
                    ok=True,
                    http_status=status,
                    transport=transport_name(fetch_mode, status),
                    returned_count=len(posts),
                    normalized_count=len(selected),
                    skipped_count=skipped_count,
                    error=None,
                    latest_shortcode=posts[0].get("shortcode") if posts else None,
                ).__dict__
            )
        except InstagramFetchError as exc:
            results.append(
                InstagramAccountResult(
                    account=account,
                    ok=False,
                    http_status=exc.status,
                    transport=transport_name(fetch_mode, exc.status),
                    returned_count=0,
                    normalized_count=0,
                    skipped_count=0,
                    error=str(exc),
                    latest_shortcode=None,
                ).__dict__
            )
    return listings, results


def transport_name(fetch_mode: str, status: int | None) -> str:
    mode = (fetch_mode or "direct").strip().lower()
    if mode in {"auto", "browser"}:
        return "instagram_profile_html_browser"
    return "instagram_web_profile_info"


def fetch_profile_resilient(
    username: str,
    *,
    timeout: int,
    user_agent: str,
    fetch_mode: str,
    browser: str,
    headless: bool,
    browser_wait_ms: int,
) -> tuple[int, dict[str, Any]]:
    mode = (fetch_mode or "direct").strip().lower()
    if mode not in {"direct", "browser", "auto"}:
        raise InstagramFetchError(f"unsupported Instagram fetch_mode: {fetch_mode}")

    if mode in {"browser", "auto"}:
        return fetch_profile_browser(
            username,
            timeout=timeout,
            user_agent=user_agent,
            browser=browser,
            headless=headless,
            wait_ms=browser_wait_ms,
        )
    if mode == "direct":
        return fetch_profile(username, timeout=timeout, user_agent=user_agent)
    raise InstagramFetchError(f"unsupported Instagram fetch_mode: {fetch_mode}")


def fetch_profile(username: str, *, timeout: int, user_agent: str) -> tuple[int, dict[str, Any]]:
    query = urllib.parse.urlencode({"username": username})
    request = urllib.request.Request(
        f"{WEB_PROFILE_INFO_URL}?{query}",
        headers={
            "User-Agent": user_agent,
            "X-IG-App-ID": INSTAGRAM_APP_ID,
            "Accept": "application/json,text/plain,*/*",
            "Referer": f"https://www.instagram.com/{username}/",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), json.loads(body)
    except urllib.error.HTTPError as exc:
        raise InstagramFetchError(
            f"Instagram HTTP {exc.code}",
            status=exc.code,
            retry_after_seconds=retry_after_seconds_from_headers(exc.headers),
        ) from exc
    except urllib.error.URLError as exc:
        raise InstagramFetchError(f"Instagram request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InstagramFetchError("Instagram returned invalid JSON") from exc


def fetch_profile_browser(
    username: str,
    *,
    timeout: int,
    user_agent: str,
    browser: str,
    headless: bool,
    wait_ms: int,
) -> tuple[int, dict[str, Any]]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise InstagramFetchError("Instagram browser fallback unavailable: playwright is not installed") from exc

    timeout_ms = max(5000, int(timeout * 1000))
    try:
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {"headless": headless}
            if browser == "chrome":
                launch_options["channel"] = "chrome"
            browser_instance = playwright.chromium.launch(**launch_options)
            context = browser_instance.new_context(
                locale="id-ID",
                user_agent=user_agent,
                viewport={"width": 1365, "height": 768},
            )
            try:
                page = context.new_page()
                timeline_payloads: list[dict[str, Any]] = []
                page.on("response", lambda candidate: capture_timeline_response(candidate, timeline_payloads))
                response = page.goto(
                    f"https://www.instagram.com/{username}/",
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                status = int(response.status) if response is not None else 200
                if status >= 400:
                    raise InstagramFetchError(f"Instagram browser HTTP {status}", status=status)

                posts, script_count = wait_for_profile_posts(
                    page,
                    timeline_payloads,
                    wait_ms=wait_ms,
                )
                if not posts:
                    raise InstagramFetchError(
                        "Instagram profile browser did not expose timeline posts "
                        f"(scripts={script_count}, timelineResponses={len(timeline_payloads)})",
                        status=status,
                    )

                payload = {
                    "data": {
                        "user": {
                            "edge_owner_to_timeline_media": {
                                "edges": [{"node": post} for post in posts]
                            }
                        }
                    }
                }
                return status, payload
            finally:
                context.close()
                browser_instance.close()
    except InstagramFetchError:
        raise
    except (PlaywrightError, PlaywrightTimeoutError) as exc:
        raise InstagramFetchError(f"Instagram browser fetch failed: {exc}") from exc


def wait_for_profile_posts(
    page: Any,
    timeline_payloads: list[dict[str, Any]],
    *,
    wait_ms: int,
    poll_interval_ms: int = 250,
) -> tuple[list[dict[str, Any]], int]:
    """Pump browser events until timeline data arrives or the bounded budget expires."""
    remaining_wait_ms = max(0, int(wait_ms))
    interval_limit_ms = max(1, int(poll_interval_ms))
    while True:
        script_texts = page.locator('script[type="application/json"]').all_text_contents()
        network_texts = [json.dumps(payload) for payload in timeline_payloads]
        posts = extract_profile_posts([*script_texts, *network_texts])
        if posts or remaining_wait_ms <= 0:
            return posts, len(script_texts)

        interval_ms = min(interval_limit_ms, remaining_wait_ms)
        page.wait_for_timeout(interval_ms)
        remaining_wait_ms -= interval_ms


def capture_timeline_response(response: Any, captured: list[dict[str, Any]]) -> None:
    """Keep supported logged-out timeline JSON without binding to a rotating doc id."""
    try:
        parsed_url = urllib.parse.urlparse(str(response.url or ""))
        if parsed_url.hostname not in {"instagram.com", "www.instagram.com"}:
            return
        if int(response.status) != 200:
            return
        content_type = str((response.headers or {}).get("content-type") or "").lower()
        if "json" not in content_type and "javascript" not in content_type:
            return
        payload = response.json()
        if not isinstance(payload, dict):
            return
        if not extract_profile_posts([json.dumps(payload)]):
            return
        captured.append(payload)
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return


def is_retryable_fetch_error(exc: Exception) -> bool:
    if not isinstance(exc, InstagramFetchError):
        return False
    if exc.status is None:
        return True
    return exc.status in {408, 409, 425, 429, 500, 502, 503, 504}


def extract_posts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    user = payload.get("data", {}).get("user", {})
    edges = user.get("edge_owner_to_timeline_media", {}).get("edges", [])
    posts = [edge.get("node", {}) for edge in edges if isinstance(edge, dict)]
    posts = [post for post in posts if isinstance(post, dict) and post.get("shortcode")]
    posts.sort(key=instagram_post_sort_key, reverse=True)
    return posts


def instagram_post_sort_key(post: dict[str, Any]) -> tuple[int, int, int]:
    timestamp = integer_or_zero(post.get("taken_at_timestamp"))
    pk = integer_or_zero(post.get("pk"))
    return (1 if timestamp else 0, timestamp, pk)


def integer_or_zero(value: Any) -> int:
    if isinstance(value, bool) or value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def is_listing_post(post: dict[str, Any]) -> bool:
    caption = caption_text(post).lower()
    if not caption:
        return False
    marker_hits = sum(1 for marker in SALE_MARKERS if marker in caption)
    if marker_hits >= 2:
        return True
    return bool(re.search(r"\brp\.?\s*[0-9]", caption, flags=re.I))


def normalize_post(account: str, post: dict[str, Any], fetched_at: datetime) -> dict[str, Any]:
    caption = caption_text(post)
    shortcode = str(post.get("shortcode") or "")
    source_url = f"https://www.instagram.com/p/{shortcode}/"
    title = extract_title(caption) or shortcode
    timestamp = integer_or_zero(post.get("taken_at_timestamp"))
    posted_at = datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else None
    images = extract_images(post, title)
    combined = "\n".join(part for part in (title, caption) if part)

    category = extract_instagram_category(title, caption) or rule_parser.extract_category(combined)
    brand = extract_instagram_brand(title, caption) or rule_parser.extract_brand(combined)

    return {
        "platform": PLATFORM,
        "sourceUrl": source_url,
        "externalId": shortcode,
        "title": title,
        "description": caption,
        "category": category,
        "brand": brand,
        "price": rule_parser.extract_price(caption),
        "locationTexts": rule_parser.extract_locations(caption),
        "conditionText": rule_parser.extract_condition(caption),
        "sellerName": account,
        "status": extract_status(account, caption),
        "postedAt": posted_at,
        "firstFetchedAt": fetched_at.isoformat(),
        "lastFetchedAt": fetched_at.isoformat(),
        "images": images,
    }


def caption_text(post: dict[str, Any]) -> str:
    edges = post.get("edge_media_to_caption", {}).get("edges", [])
    if not edges:
        return ""
    node = edges[0].get("node", {}) if isinstance(edges[0], dict) else {}
    text = node.get("text") if isinstance(node, dict) else ""
    return html.unescape(str(text or "")).strip()


def extract_title(caption: str) -> str | None:
    fallback_code: str | None = None
    for raw_line in caption.splitlines():
        line = clean_line(raw_line)
        label_match = re.search(r"(?:nama produk|nama barang|product name|produk)\s*[:\-]\s*(.+)$", line, flags=re.I)
        if label_match:
            title = clean_line(label_match.group(1))
            if title:
                return title[:180]
        code_match = re.search(r"\bcode\s*(?:item)?\s*[:\-]\s*#?([A-Za-z0-9_-]+)", line, flags=re.I)
        if code_match and not fallback_code:
            fallback_code = code_match.group(1)

    skip_prefixes = (
        "#",
        "condition",
        "kondisi",
        "description",
        "deskripsi",
        "garansi",
        "location",
        "lokasi",
        "price",
        "harga",
        "code",
        "kelengkapan",
        "pembelian",
        "market price",
        "turn on",
        "line",
        "wa:",
        "whatsapp",
    )
    for raw_line in caption.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        lower = line.lower()
        if lower.startswith(skip_prefixes):
            continue
        if is_marketing_title_line(lower):
            continue
        if re.search(r"\b(rp|idr)\b|[0-9][.,][0-9]", lower) and len(line) < 32:
            continue
        if len(re.sub(r"[^A-Za-z0-9]", "", line)) < 4:
            continue
        return line[:180]
    if fallback_code:
        category_hint = category_hint_from_text(caption)
        if category_hint:
            return f"{category_hint} listing {fallback_code}"
        return f"Listing {fallback_code}"
    return None


def clean_line(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip(" -–—:.")
    return value.strip()


def is_marketing_title_line(lower: str) -> bool:
    marketing_fragments = (
        "perangkat paling murah",
        "most wanted gaming peripherals",
        "khusus buat",
        "buat yg",
        "buat yang",
        "lgi cari",
        "lagi cari",
        "punya gear nganggur",
        "daripada berdebu",
        "mending consign",
        "gak pake ribet",
        "ready for new owner",
        "turn on post notification",
        "let's order",
        "let’s order",
        "lets order",
        "click link in bio",
        "for order and consign",
        "add thelazytitip",
        "customer service",
        "trusted source",
    )
    return any(fragment in lower for fragment in marketing_fragments)


def extract_instagram_category(title: str, caption: str) -> str | None:
    title_match = match_patterns(title, INSTAGRAM_CATEGORY_PATTERNS)
    if title_match:
        return title_match
    return match_patterns(caption, INSTAGRAM_CATEGORY_PATTERNS)


def extract_instagram_brand(title: str, caption: str) -> str | None:
    title_match = match_patterns(title, INSTAGRAM_BRAND_PATTERNS)
    if title_match:
        return title_match
    return match_patterns(caption, INSTAGRAM_BRAND_PATTERNS)


def match_patterns(text: str, patterns: tuple[tuple[str, tuple[str, ...]], ...]) -> str | None:
    lower = f" {text.lower()} "
    for value, keywords in patterns:
        if any(keyword in lower for keyword in keywords):
            return value
    return None


def category_hint_from_text(text: str) -> str | None:
    category = extract_instagram_category("", text)
    if category == "Peripheral" and "headset" in text.lower():
        return "Gaming headset"
    return category


def extract_status(account: str, caption: str) -> str:
    lower = caption.lower()
    top_text = "\n".join(line for line in lower.splitlines()[:5] if line.strip())
    for marker in ACCOUNT_SOLD_MARKERS.get(account, ()):
        if marker in top_text:
            return "SOLD"
    if re.search(r"(^|\n)\s*[^\w\n]{0,4}(sold\s*out|soldout|sold|terjual|laku|booked)\b", top_text, flags=re.I):
        return "SOLD"
    if is_listing_post({"edge_media_to_caption": {"edges": [{"node": {"text": caption}}]}}):
        return "AVAILABLE"
    return "UNKNOWN"


def extract_images(post: dict[str, Any], alt_text: str) -> list[dict[str, Any]]:
    urls: list[str] = []
    for key in ("display_url", "thumbnail_src"):
        value = post.get(key)
        if isinstance(value, str) and value and value not in urls:
            urls.append(value)

    sidecar_edges = post.get("edge_sidecar_to_children", {}).get("edges", [])
    for edge in sidecar_edges if isinstance(sidecar_edges, list) else []:
        node = edge.get("node", {}) if isinstance(edge, dict) else {}
        if not isinstance(node, dict):
            continue
        for key in ("display_url", "thumbnail_src"):
            value = node.get(key)
            if isinstance(value, str) and value and value not in urls:
                urls.append(value)

    return [{"sourceUrl": url, "position": index, "altText": alt_text} for index, url in enumerate(urls)]
