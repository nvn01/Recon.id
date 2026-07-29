"""Logged-out Facebook buy/sell group discovery for RECON."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from scraper.facebook_groups.embedded import extract_group_posts, timestamp_iso
from scraper.shared.runtime import (
    AlreadyRunningError,
    FileLock,
    clear_cooldown,
    cooldown_seconds_remaining,
    default_runtime_state,
    load_runtime_state,
    log_event,
    save_runtime_state,
    set_cooldown,
)


SCRAPER_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS_FILE = Path(__file__).resolve().parent / "source_targets.json"
DEFAULT_STATE_FILE = SCRAPER_DIR / ".state" / "facebook_groups.json"
DEFAULT_LOCK_FILE = SCRAPER_DIR / ".state" / "facebook_groups.lock"
DEFAULT_LOG_FILE = SCRAPER_DIR / ".logs" / "facebook_groups.jsonl"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
)
GROUP_FEED_OPERATION = "GroupsCometFeedRegularStoriesPaginationQuery"
MAX_CAPTURED_RESPONSE_BYTES = 4 * 1024 * 1024


class FacebookGroupsError(RuntimeError):
    """Base connector failure."""


class FacebookGroupsAccessError(FacebookGroupsError):
    """Facebook returned a block, rate limit, or login wall."""


@dataclass(frozen=True)
class GroupTarget:
    id: str
    group_id: str
    name: str
    url: str
    sorting_setting: str


def load_targets(path: Path) -> list[GroupTarget]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FacebookGroupsError(f"Cannot read Facebook Groups targets: {type(exc).__name__}") from exc
    records = loaded.get("targets") if isinstance(loaded, dict) else None
    if not isinstance(records, list):
        raise FacebookGroupsError("Facebook Groups targets file must contain a targets array.")

    targets: list[GroupTarget] = []
    seen: set[str] = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        target_id = str(record.get("id") or "").strip()
        group_id = str(record.get("groupId") or "").strip()
        url = str(record.get("url") or "").strip()
        if not target_id or target_id in seen or not group_id or not valid_group_url(url):
            raise FacebookGroupsError(f"Invalid Facebook Groups target at position {index}.")
        seen.add(target_id)
        targets.append(
            GroupTarget(
                id=target_id,
                group_id=group_id,
                name=str(record.get("name") or target_id).strip(),
                url=url,
                sorting_setting=str(record.get("sortingSetting") or "CHRONOLOGICAL").strip(),
            )
        )
    return targets


def select_targets(targets: Iterable[GroupTarget], requested: Iterable[str] | None) -> list[GroupTarget]:
    requested_ids = {str(value).strip() for value in (requested or []) if str(value).strip()}
    selected = [target for target in targets if not requested_ids or target.id in requested_ids]
    missing = requested_ids.difference(target.id for target in selected)
    if missing:
        raise FacebookGroupsError(f"Unknown Facebook Groups target: {', '.join(sorted(missing))}")
    return selected


def valid_group_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() in {"facebook.com", "www.facebook.com"}
        and parsed.path.startswith("/groups/")
    )


def run_browser_fetch(args: argparse.Namespace) -> list[dict[str, Any]]:
    targets = select_targets(load_targets(Path(args.targets_file)), args.target)
    fetched_at = datetime.now(timezone.utc).isoformat()
    listings: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        launch_options: dict[str, Any] = {"headless": True}
        if args.browser == "chrome":
            launch_options["channel"] = "chrome"
        browser = playwright.chromium.launch(**launch_options)
        try:
            context = browser.new_context(user_agent=args.user_agent, locale="id-ID")
            try:
                for target in targets:
                    listings.extend(fetch_target(context, target, args, fetched_at))
            finally:
                context.close()
        finally:
            browser.close()
    return listings


def fetch_target(
    context: Any,
    target: GroupTarget,
    args: argparse.Namespace,
    fetched_at: str,
) -> list[dict[str, Any]]:
    page = context.new_page()
    captured_responses: list[str] = []

    def capture_group_feed(response: Any) -> None:
        if len(captured_responses) >= 3:
            return
        try:
            request = response.request
            if request.resource_type not in {"xhr", "fetch"}:
                return
            parsed = urlsplit(response.url)
            if (parsed.hostname or "").lower() not in {"facebook.com", "www.facebook.com"}:
                return
            post_data = request.post_data or ""
            if GROUP_FEED_OPERATION not in post_data:
                return
            body = response.text()
            if 0 < len(body.encode("utf-8")) <= MAX_CAPTURED_RESPONSE_BYTES:
                captured_responses.append(body)
        except Exception:
            return

    page.on("response", capture_group_feed)
    if args.block_assets:
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "media", "font", "stylesheet"}
            else route.continue_(),
        )

    try:
        response = page.goto(target.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        http_status = response.status if response is not None else None
        if http_status in {401, 403, 429}:
            raise FacebookGroupsAccessError(f"Facebook Groups returned HTTP {http_status}.")
        if http_status is not None and http_status >= 400:
            raise FacebookGroupsError(f"Facebook Groups returned HTTP {http_status}.")

        deadline = time.monotonic() + max(0.25, args.wait_ms / 1000)
        posts: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            script_texts = page.locator('script[type="application/json"]').all_text_contents()
            posts = extract_group_posts(
                script_texts,
                captured_responses,
                group_id=target.group_id,
                limit=args.limit,
            )
            if len(posts) >= args.limit:
                break
            page.wait_for_timeout(250)

        final_url = page.url
        visible_text = page.locator("body").inner_text(timeout=2000)[:5000]
        if looks_like_login_wall(final_url, visible_text):
            raise FacebookGroupsAccessError("Facebook Groups login wall detected.")
        if not posts:
            raise FacebookGroupsAccessError("Facebook Groups feed did not expose group stories.")
        return normalize_posts(posts, target=target, fetched_at=fetched_at)
    finally:
        page.close()


def looks_like_login_wall(final_url: str, text: str) -> bool:
    lowered_url = final_url.lower()
    lowered_text = " ".join(text.lower().split())
    return (
        "/login" in lowered_url
        or "/checkpoint" in lowered_url
        or "log in to facebook" in lowered_text
        or "masuk ke facebook" in lowered_text
    )


def normalize_posts(
    posts: Iterable[dict[str, Any]],
    *,
    target: GroupTarget,
    fetched_at: str,
) -> list[dict[str, Any]]:
    listings: list[dict[str, Any]] = []
    for post in posts:
        message = str(post.get("message") or "").strip()
        images = post.get("images") if isinstance(post.get("images"), list) else []
        commerce = post.get("commerce") if isinstance(post.get("commerce"), dict) else {}
        if not message or not images:
            continue

        post_id = str(post.get("postId") or "").strip()
        source_url = str(post.get("permalink") or "").strip() or fallback_permalink(target, post_id)
        seller_name = str(post.get("sellerName") or commerce.get("sellerName") or "").strip() or None
        title = next((line.strip() for line in message.splitlines() if line.strip()), f"Facebook post {post_id}")
        source_facts = {
            "sourceType": "facebook_group",
            "groupId": target.group_id,
            "groupName": target.name,
            "sortingSetting": target.sorting_setting,
            "sellerId": str(post.get("sellerId") or commerce.get("sellerId") or "").strip() or None,
            "sellerName": seller_name,
            "formattedPrice": str(commerce.get("formattedPrice") or "").strip() or None,
            "locationText": str(commerce.get("locationText") or "").strip() or None,
            "productId": str(commerce.get("productId") or "").strip() or None,
            "usedAttachedStory": bool(post.get("usedAttachedStory")),
        }
        listings.append(
            {
                "platform": "FACEBOOK_GROUP",
                "sourceUrl": source_url,
                "externalId": f"{target.group_id}:{post_id}",
                "title": title[:300],
                "description": message,
                "category": None,
                "brand": None,
                "price": None,
                "locationTexts": [],
                "conditionText": None,
                "sellerName": seller_name,
                "status": "UNKNOWN",
                "postedAt": timestamp_iso(post.get("publishedTimestamp")),
                "firstFetchedAt": fetched_at,
                "lastFetchedAt": fetched_at,
                "images": [
                    {
                        "sourceUrl": str(image.get("url") or "").strip(),
                        "position": position,
                        "altText": str(image.get("alt") or "").strip() or None,
                    }
                    for position, image in enumerate(images)
                    if isinstance(image, dict) and str(image.get("url") or "").startswith("https://")
                ],
                "_sourceFacts": source_facts,
            }
        )
    return listings


def fallback_permalink(target: GroupTarget, post_id: str) -> str:
    group_route = urlsplit(target.url).path.strip("/").split("/", 1)[-1]
    return f"https://www.facebook.com/groups/{group_route}/posts/{post_id}/"


def run_once(
    args: argparse.Namespace,
    *,
    include_status: bool = False,
) -> tuple[int, list[dict[str, Any]]] | tuple[int, list[dict[str, Any]], str]:
    state_path = Path(args.state_file)
    log_path = None if args.no_state else Path(args.log_file)
    state = default_runtime_state() if args.no_state else load_runtime_state(state_path)
    remaining = 0 if args.ignore_cooldown else cooldown_seconds_remaining(state)
    if remaining > 0:
        log_event(
            log_path,
            {
                "source": "facebook_groups",
                "status": "cooldown_skip",
                "cooldown_remaining_seconds": remaining,
            },
        )
        return format_result(0, [], "cooldown_skip", include_status)

    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    try:
        listings = run_browser_fetch(args)
    except FacebookGroupsAccessError as exc:
        set_cooldown(state, args.cooldown_seconds, str(exc))
        status = "access_blocked"
        code = 1
        listings = []
        error = str(exc)
    except Exception as exc:
        status = "failed"
        code = 1
        listings = []
        error = f"{type(exc).__name__}: Facebook Groups fetch failed"
        state["last_error"] = error
    else:
        clear_cooldown(state)
        state["last_success_at"] = datetime.now(timezone.utc).isoformat()
        state["last_error"] = None
        status = "success" if listings else "no_new_data"
        code = 0
        error = None

    if not args.no_state:
        save_runtime_state(state_path, state)
    log_event(
        log_path,
        {
            "source": "facebook_groups",
            "status": status,
            "targets": list(args.target or []),
            "normalized": len(listings),
            "error": error,
        },
    )
    return format_result(code, listings, status, include_status)


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
    except AlreadyRunningError:
        return format_result(2, [], "locked", include_status)


def format_result(
    code: int,
    listings: list[dict[str, Any]],
    status: str,
    include_status: bool,
) -> tuple[int, list[dict[str, Any]]] | tuple[int, list[dict[str, Any]], str]:
    return (code, listings, status) if include_status else (code, listings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Facebook buy/sell group posts for RECON.")
    parser.add_argument("--targets-file", default=str(DEFAULT_TARGETS_FILE))
    parser.add_argument("--target", action="append", default=None)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--browser", choices=("chrome", "chromium"), default="chrome")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--wait-ms", type=int, default=6500)
    parser.add_argument("--block-assets", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE))
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE))
    parser.add_argument("--log-file", default=str(DEFAULT_LOG_FILE))
    parser.add_argument("--cooldown-seconds", type=int, default=3600)
    parser.add_argument("--ignore-cooldown", action="store_true")
    parser.add_argument("--no-state", action="store_true")
    parser.add_argument("--lock-stale-seconds", type=int, default=900)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--format", choices=("json", "jsonl"), default="json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = guarded_run_once(args, include_status=True)
    code, listings, status = result
    payload = {"ok": code == 0, "status": status, "listings": listings}
    if args.format == "jsonl":
        for listing in listings:
            print(json.dumps(listing, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
