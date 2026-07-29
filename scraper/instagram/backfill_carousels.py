"""Bounded, resumable backfill for Instagram carousel child image rows."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from scraper.instagram.instagram import (
    DEFAULT_USER_AGENT,
    image_urls,
    instagram_json_payload,
    wait_for_post_detail,
)
from scraper.storage.postgres import (
    canonical_media_source_url,
    new_record_id,
    require_database_url,
)


SELECT_CANDIDATES_SQL = """
SELECT listing.id, listing.external_id, image.source_url
FROM listings AS listing
JOIN listing_images AS image ON image.listing_id = listing.id
WHERE listing.platform = 'instagram'::listing_platform
  AND listing.first_fetched_at >= %(since)s
  AND listing.id > %(after_id)s
GROUP BY listing.id, listing.external_id, image.source_url
HAVING COUNT(image.id) = 1
   AND MIN(image.position) = 0
ORDER BY listing.id
LIMIT %(limit)s
"""

INSERT_CHILD_IMAGE_SQL = """
INSERT INTO listing_images (
    id,
    listing_id,
    source_url,
    position,
    alt_text
)
VALUES (
    %(id)s,
    %(listing_id)s,
    %(source_url)s,
    %(position)s,
    %(alt_text)s
)
ON CONFLICT (listing_id, position) DO NOTHING
"""


class CarouselBackfillError(RuntimeError):
    """Raised when the bounded carousel backfill cannot run safely."""


@dataclass(frozen=True)
class PendingCarousel:
    listing_id: str
    external_id: str
    cover_url: str


def additional_image_rows(
    pending: PendingCarousel,
    detail: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build only the child rows; the existing cached cover remains position zero."""
    shortcode = str(detail.get("shortcode") or detail.get("code") or "").strip()
    if shortcode != pending.external_id:
        return []

    urls = image_urls(detail)
    if len(urls) < 2:
        return []

    cover_identity = canonical_media_source_url(pending.cover_url)
    if canonical_media_source_url(urls[0]) != cover_identity:
        # Instagram can rotate signed query values, but the media path for the
        # same cover must still match before child positions are trusted.
        return []

    return [
        {
            "id": new_record_id(),
            "listing_id": pending.listing_id,
            "source_url": source_url,
            "position": position,
            "alt_text": pending.external_id,
        }
        for position, source_url in enumerate(urls[1:], start=1)
    ]


def fetch_post_details_browser(
    shortcodes: list[str],
    *,
    timeout_seconds: int,
    wait_ms: int,
    delay_ms: int,
    browser: str,
    headless: bool,
) -> tuple[dict[str, dict[str, Any]], int]:
    """Fetch a small list of public post pages in one fresh browser context."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - verified in the scraper image.
        raise CarouselBackfillError("Install scraper dependencies before running the carousel backfill.") from exc

    details: dict[str, dict[str, Any]] = {}
    failed = 0
    timeout_ms = max(5000, int(timeout_seconds * 1000))

    with sync_playwright() as playwright:
        launch_options: dict[str, Any] = {"headless": headless}
        if browser == "chrome":
            launch_options["channel"] = "chrome"
        browser_instance = playwright.chromium.launch(**launch_options)
        context = browser_instance.new_context(
            locale="id-ID",
            user_agent=DEFAULT_USER_AGENT,
            viewport={"width": 1365, "height": 768},
        )
        try:
            page = context.new_page()
            response_payloads: list[Any] = []

            def handle_response(response: Any) -> None:
                try:
                    payload = instagram_json_payload(response)
                    if payload is not None:
                        response_payloads.append(payload)
                except PlaywrightError:
                    return

            page.on("response", handle_response)
            for index, shortcode in enumerate(shortcodes):
                if index and delay_ms > 0:
                    page.wait_for_timeout(max(0, int(delay_ms)))
                payload_start = len(response_payloads)
                try:
                    response = page.goto(
                        f"https://www.instagram.com/p/{shortcode}/",
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                    status = int(response.status) if response is not None else 200
                    if status >= 400 or page.url.startswith("https://www.instagram.com/accounts/login"):
                        failed += 1
                        continue
                    detail = wait_for_post_detail(
                        page,
                        response_payloads,
                        shortcode,
                        payload_start=payload_start,
                        wait_ms=max(0, int(wait_ms)),
                    )
                except (PlaywrightError, PlaywrightTimeoutError):
                    failed += 1
                    continue
                if detail is None:
                    failed += 1
                    continue
                details[shortcode] = detail
        finally:
            context.close()
            browser_instance.close()
    return details, failed


def run_backfill(
    database_url: str | None,
    *,
    since: date,
    after_id: str,
    max_items: int,
    write_db: bool,
    timeout_seconds: int,
    wait_ms: int,
    delay_ms: int,
    browser: str,
    headless: bool,
    fetch_details: Callable[..., tuple[dict[str, dict[str, Any]], int]] = fetch_post_details_browser,
) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - verified in the scraper image.
        raise CarouselBackfillError("Install scraper dependencies before running the carousel backfill.") from exc

    url = require_database_url(database_url)
    with psycopg.connect(url, connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                SELECT_CANDIDATES_SQL,
                {
                    "since": since,
                    "after_id": str(after_id or ""),
                    "limit": max_items,
                },
            )
            candidates = [
                PendingCarousel(
                    listing_id=str(row[0]),
                    external_id=str(row[1]),
                    cover_url=str(row[2]),
                )
                for row in cursor.fetchall()
            ]

        details, failed = fetch_details(
            [candidate.external_id for candidate in candidates],
            timeout_seconds=timeout_seconds,
            wait_ms=wait_ms,
            delay_ms=delay_ms,
            browser=browser,
            headless=headless,
        )
        summary: dict[str, Any] = {
            "selected": len(candidates),
            "carousels": 0,
            "singleImagePosts": 0,
            "failed": failed,
            "imagesFound": 0,
            "imagesInserted": 0,
            "writeEnabled": write_db,
            "nextAfterId": candidates[-1].listing_id if candidates else str(after_id or ""),
        }
        for candidate in candidates:
            detail = details.get(candidate.external_id)
            if detail is None:
                continue
            rows = additional_image_rows(candidate, detail)
            if not rows:
                summary["singleImagePosts"] += 1
                continue
            summary["carousels"] += 1
            summary["imagesFound"] += len(rows)
            if not write_db:
                continue
            with connection.cursor() as cursor:
                cursor.executemany(INSERT_CHILD_IMAGE_SQL, rows)
                summary["imagesInserted"] += max(cursor.rowcount or 0, 0)
            connection.commit()
    return summary


def parse_since(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--since must use YYYY-MM-DD") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover and optionally insert missing Instagram carousel child images."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--since", type=parse_since, required=True)
    parser.add_argument("--after-id", default="")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--wait-ms", type=int, default=4000)
    parser.add_argument("--delay-ms", type=int, default=750)
    parser.add_argument("--browser", choices=("chromium", "chrome"), default="chrome")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Insert missing child rows. Omit for a read-only discovery run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_items < 1 or args.max_items > 25:
        raise SystemExit("--max-items must be between 1 and 25")
    if args.timeout_seconds < 5 or args.timeout_seconds > 120:
        raise SystemExit("--timeout-seconds must be between 5 and 120")
    if args.wait_ms < 0 or args.wait_ms > 15000:
        raise SystemExit("--wait-ms must be between 0 and 15000")
    if args.delay_ms < 0 or args.delay_ms > 10000:
        raise SystemExit("--delay-ms must be between 0 and 10000")
    try:
        summary = run_backfill(
            args.database_url,
            since=args.since,
            after_id=args.after_id,
            max_items=args.max_items,
            write_db=args.write_db,
            timeout_seconds=args.timeout_seconds,
            wait_ms=args.wait_ms,
            delay_ms=args.delay_ms,
            browser=args.browser,
            headless=args.headless,
        )
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:400]}"},
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps({"ok": summary["failed"] == 0, **summary}, separators=(",", ":")))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
