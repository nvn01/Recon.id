"""Fetch and normalize recent Instagram public profile posts for RECON."""

from __future__ import annotations

import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from scraper.instagram.embedded import extract_post_detail, extract_profile_posts, merge_posts
    from scraper.shared.runtime import RetryPolicy, retry_after_seconds_from_headers, retry_call
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from instagram.embedded import extract_post_detail, extract_profile_posts, merge_posts
    from shared.runtime import RetryPolicy, retry_after_seconds_from_headers, retry_call


PLATFORM = "INSTAGRAM"
WEB_PROFILE_INFO_URL = "https://www.instagram.com/api/v1/users/web_profile_info/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
INSTAGRAM_APP_ID = "936619743392459"

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
    cooldown_eligible: bool = False


class InstagramFetchError(RuntimeError):
    def __init__(
        self,
        message: str,
        status: int | None = None,
        retry_after_seconds: int | None = None,
        *,
        cooldown_eligible: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after_seconds = retry_after_seconds
        self.cooldown_eligible = cooldown_eligible


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
    carousel_cache: dict[str, list[str]] | None = None,
    carousel_detail_limit: int = 3,
    carousel_detail_wait_ms: int = 4000,
    carousel_detail_delay_ms: int = 500,
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
                    carousel_cache=carousel_cache,
                    carousel_detail_limit=carousel_detail_limit,
                    carousel_detail_wait_ms=carousel_detail_wait_ms,
                    carousel_detail_delay_ms=carousel_detail_delay_ms,
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
            post_limit = min(max_posts_per_account, max(1, limit))
            for post in posts[:post_limit]:
                selected.append(normalize_post(account, post, fetched_at))
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
                    cooldown_eligible=False,
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
                    cooldown_eligible=exc.cooldown_eligible,
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
    carousel_cache: dict[str, list[str]] | None = None,
    carousel_detail_limit: int = 3,
    carousel_detail_wait_ms: int = 4000,
    carousel_detail_delay_ms: int = 500,
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
            carousel_cache=carousel_cache,
            carousel_detail_limit=carousel_detail_limit,
            carousel_detail_wait_ms=carousel_detail_wait_ms,
            carousel_detail_delay_ms=carousel_detail_delay_ms,
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
    carousel_cache: dict[str, list[str]] | None = None,
    carousel_detail_limit: int = 3,
    carousel_detail_wait_ms: int = 4000,
    carousel_detail_delay_ms: int = 500,
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
                instagram_payloads: list[Any] = []

                def handle_response(candidate: Any) -> None:
                    try:
                        payload = instagram_json_payload(candidate)
                        if payload is None:
                            return
                        instagram_payloads.append(payload)
                        if isinstance(payload, dict) and extract_profile_posts([json.dumps(payload)]):
                            timeline_payloads.append(payload)
                    except PlaywrightError:
                        # A response callback can finish after navigation or context
                        # teardown. That race must not fail the whole account run.
                        return

                page.on("response", handle_response)
                response = page.goto(
                    f"https://www.instagram.com/{username}/",
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                status = int(response.status) if response is not None else 200
                if status >= 400:
                    raise InstagramFetchError(f"Instagram browser HTTP {status}", status=status)

                ensure_profile_not_login_redirect(page.url, page.title())

                posts, script_count = wait_for_profile_posts(
                    page,
                    timeline_payloads,
                    wait_ms=wait_ms,
                )
                if not posts:
                    final_path = urllib.parse.urlparse(page.url).path[:160]
                    page_title = page.title()[:120]
                    raise InstagramFetchError(
                        "Instagram profile browser did not expose timeline posts "
                        f"(scripts={script_count}, timelineResponses={len(timeline_payloads)}, "
                        f"finalPath={final_path!r}, title={page_title!r})",
                        status=status,
                    )

                detail_requests = 0

                def fetch_detail(shortcode: str) -> dict[str, Any] | None:
                    nonlocal detail_requests
                    if detail_requests and carousel_detail_delay_ms > 0:
                        page.wait_for_timeout(max(0, int(carousel_detail_delay_ms)))
                    detail_requests += 1
                    payload_start = len(instagram_payloads)
                    try:
                        detail_response = page.goto(
                            f"https://www.instagram.com/p/{urllib.parse.quote(shortcode, safe='')}/",
                            wait_until="domcontentloaded",
                            timeout=timeout_ms,
                        )
                        detail_status = int(detail_response.status) if detail_response is not None else 200
                        if detail_status >= 400:
                            return None
                        if urllib.parse.urlparse(page.url).path.startswith("/accounts/login"):
                            return None
                        return wait_for_post_detail(
                            page,
                            instagram_payloads,
                            shortcode,
                            payload_start=payload_start,
                            wait_ms=max(0, int(carousel_detail_wait_ms)),
                        )
                    except (PlaywrightError, PlaywrightTimeoutError):
                        return None

                posts = enrich_carousel_posts(
                    posts,
                    cache=carousel_cache if carousel_cache is not None else {},
                    max_detail_posts=max(0, int(carousel_detail_limit)),
                    fetch_detail=fetch_detail,
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


def ensure_profile_not_login_redirect(url: str, title: str) -> None:
    final_path = urllib.parse.urlparse(url).path[:160]
    if not final_path.startswith("/accounts/login"):
        return
    raise InstagramFetchError(
        "Instagram profile redirected to login "
        f"(finalPath={final_path!r}, title={title[:120]!r})",
        cooldown_eligible=True,
    )


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


def wait_for_post_detail(
    page: Any,
    response_payloads: list[Any],
    shortcode: str,
    *,
    payload_start: int,
    wait_ms: int,
    poll_interval_ms: int = 250,
) -> dict[str, Any] | None:
    """Pump browser events until the individual post exposes its carousel children."""
    remaining_wait_ms = max(0, int(wait_ms))
    interval_limit_ms = max(1, int(poll_interval_ms))
    while True:
        script_texts = page.locator('script[type="application/json"]').all_text_contents()
        network_texts = [json.dumps(payload) for payload in response_payloads[payload_start:]]
        detail = extract_post_detail([*script_texts, *network_texts], shortcode)
        if detail and carousel_image_count(detail) >= expected_carousel_count(detail):
            return detail
        if remaining_wait_ms <= 0:
            return detail

        interval_ms = min(interval_limit_ms, remaining_wait_ms)
        page.wait_for_timeout(interval_ms)
        remaining_wait_ms -= interval_ms


def enrich_carousel_posts(
    posts: list[dict[str, Any]],
    *,
    cache: dict[str, list[str]],
    max_detail_posts: int,
    fetch_detail: Callable[[str], dict[str, Any] | None],
) -> list[dict[str, Any]]:
    """Hydrate carousel children from cache or a bounded individual-post fetch."""
    enriched_posts: list[dict[str, Any]] = []
    detail_attempts = 0

    for original in posts:
        post = dict(original)
        shortcode = str(post.get("shortcode") or "").strip()
        expected_count = expected_carousel_count(post)
        if not shortcode or expected_count < 2:
            enriched_posts.append(post)
            continue

        current_urls = image_urls(post)
        if len(current_urls) >= expected_count:
            remember_carousel(cache, shortcode, current_urls)
            enriched_posts.append(post)
            continue

        cached_urls = valid_cached_urls(cache.get(shortcode))
        if len(cached_urls) >= expected_count:
            remember_carousel(cache, shortcode, cached_urls)
            enriched_posts.append(apply_image_urls(post, cached_urls))
            continue

        if detail_attempts >= max(0, int(max_detail_posts)):
            enriched_posts.append(post)
            continue

        detail_attempts += 1
        detail = fetch_detail(shortcode)
        if detail:
            post = merge_posts(post, detail)
            detail_urls = image_urls(detail)
            if len(detail_urls) >= expected_count:
                post = apply_image_urls(post, detail_urls)
                remember_carousel(cache, shortcode, detail_urls)
        enriched_posts.append(post)

    prune_carousel_cache(cache)
    return enriched_posts


def expected_carousel_count(post: dict[str, Any]) -> int:
    configured = integer_or_zero(post.get("carousel_media_count"))
    if configured >= 2:
        return configured
    if integer_or_zero(post.get("media_type")) == 8:
        return 2
    if str(post.get("product_type") or "").strip().lower() == "carousel_container":
        return 2
    return 0


def carousel_image_count(post: dict[str, Any]) -> int:
    return len(image_urls(post))


def image_urls(post: dict[str, Any]) -> list[str]:
    return [str(image["sourceUrl"]) for image in extract_images(post, str(post.get("shortcode") or ""))]


def valid_cached_urls(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    urls: list[str] = []
    for candidate in value:
        url = str(candidate or "").strip()
        if url.startswith("https://") and url not in urls:
            urls.append(url)
    return urls


def apply_image_urls(post: dict[str, Any], urls: list[str]) -> dict[str, Any]:
    enriched = dict(post)
    if urls:
        enriched["display_url"] = urls[0]
        enriched.pop("thumbnail_src", None)
    enriched["edge_sidecar_to_children"] = {
        "edges": [{"node": {"display_url": url}} for url in urls]
    }
    return enriched


def remember_carousel(cache: dict[str, list[str]], shortcode: str, urls: list[str]) -> None:
    valid_urls = valid_cached_urls(urls)
    if len(valid_urls) < 2:
        return
    cache.pop(shortcode, None)
    cache[shortcode] = valid_urls


def prune_carousel_cache(cache: dict[str, list[str]], max_entries: int = 1000) -> None:
    limit = max(1, int(max_entries))
    while len(cache) > limit:
        cache.pop(next(iter(cache)))


def capture_timeline_response(response: Any, captured: list[dict[str, Any]]) -> None:
    """Keep supported logged-out timeline JSON without binding to a rotating doc id."""
    payload = instagram_json_payload(response)
    if not isinstance(payload, dict):
        return
    if not extract_profile_posts([json.dumps(payload)]):
        return
    captured.append(payload)


def instagram_json_payload(response: Any) -> Any | None:
    """Return supported same-origin Instagram JSON for profile or post parsing."""
    try:
        parsed_url = urllib.parse.urlparse(str(response.url or ""))
        if parsed_url.hostname not in {"instagram.com", "www.instagram.com"}:
            return None
        if int(response.status) != 200:
            return None
        content_type = str((response.headers or {}).get("content-type") or "").lower()
        if "json" not in content_type and "javascript" not in content_type:
            return None
        payload = response.json()
        return payload if isinstance(payload, (dict, list)) else None
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return None


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


def normalize_post(account: str, post: dict[str, Any], fetched_at: datetime) -> dict[str, Any]:
    caption = caption_text(post)
    shortcode = str(post.get("shortcode") or "")
    source_url = f"https://www.instagram.com/p/{shortcode}/"
    title = shortcode
    timestamp = integer_or_zero(post.get("taken_at_timestamp"))
    posted_at = datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else None
    images = extract_images(post, title)
    return {
        "platform": PLATFORM,
        "sourceUrl": source_url,
        "externalId": shortcode,
        "title": title,
        "description": caption,
        "category": None,
        "brand": None,
        "price": None,
        "locationTexts": [],
        "conditionText": None,
        "sellerName": account,
        "status": "UNKNOWN",
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
