"""Dry-run-first repair for historical Reddit image rows."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from scraper.reddit.reddit import (
    DEFAULT_USER_AGENT,
    RateLimitedError,
    canonical_url,
    fetch_text,
    parse_feed,
    unique_image_urls,
)
from scraper.shared.runtime import (
    EgressConfigError,
    configure_urllib_egress,
    resolve_egress_config,
)
from scraper.storage.postgres import new_record_id, require_database_url


SELECT_BATCH_SQL = """
WITH selected_listings AS (
    SELECT id, source_url, title
    FROM listings
    WHERE platform = 'reddit'::listing_platform
      AND id > %s
    ORDER BY id
    LIMIT %s
)
SELECT
    listing.id,
    listing.source_url,
    listing.title,
    image.source_url,
    image.position
FROM selected_listings AS listing
LEFT JOIN listing_images AS image ON image.listing_id = listing.id
ORDER BY listing.id, image.position
"""

DELETE_IMAGES_SQL = "DELETE FROM listing_images WHERE listing_id = %s"

INSERT_IMAGE_SQL = """
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
"""


def build_post_rss_url(source_url: str) -> str:
    canonical = canonical_url(source_url)
    if not canonical:
        return ""
    parsed = urlsplit(canonical)
    if "/comments/" not in parsed.path:
        return ""
    return urlunsplit(("https", "www.reddit.com", f"{parsed.path}.rss", "", ""))


def desired_image_urls(
    existing_urls: Iterable[str],
    fetched_urls: Iterable[str],
) -> list[str]:
    existing = unique_image_urls(existing_urls)
    return existing or unique_image_urls(fetched_urls)


def fetch_post_rss_images(
    source_url: str,
    *,
    user_agent: str,
    timeout: int,
) -> list[str]:
    rss_url = build_post_rss_url(source_url)
    if not rss_url:
        return []
    payload = fetch_text(
        rss_url,
        user_agent,
        retries=1,
        retry_wait=0,
        retry_jitter=0,
        timeout=timeout,
    )
    posts = parse_feed(payload, limit=1)
    if not posts:
        return []
    return unique_image_urls(posts[0].get("images", []))


def grouped_rows(rows: Iterable[tuple[Any, ...]]) -> list[dict[str, Any]]:
    listings: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for listing_id, source_url, title, image_url, _position in rows:
        key = str(listing_id)
        listing = by_id.get(key)
        if listing is None:
            listing = {
                "id": key,
                "source_url": str(source_url),
                "title": str(title),
                "images": [],
            }
            by_id[key] = listing
            listings.append(listing)
        if image_url:
            listing["images"].append(str(image_url))
    return listings


def replace_images(
    connection: Any,
    *,
    listing_id: str,
    title: str,
    urls: list[str],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(DELETE_IMAGES_SQL, (listing_id,))
        for position, source_url in enumerate(urls):
            cursor.execute(
                INSERT_IMAGE_SQL,
                {
                    "id": new_record_id(),
                    "listing_id": listing_id,
                    "source_url": source_url,
                    "position": position,
                    "alt_text": f"{title} image {position + 1}",
                },
            )
    connection.commit()


def run_backfill(
    database_url: str | None,
    *,
    batch_size: int,
    max_items: int | None,
    apply: bool,
    fetch_missing: bool,
    fetch_delay_seconds: float,
    timeout: int,
    user_agent: str,
) -> dict[str, int]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - verified in the scraper image.
        raise RuntimeError("Install scraper dependencies before running the Reddit image backfill.") from exc

    url = require_database_url(database_url)
    summary = {
        "scanned": 0,
        "changed": 0,
        "rewritten": 0,
        "recovered": 0,
        "unchanged": 0,
        "missing": 0,
        "failed": 0,
        "rate_limited": 0,
    }
    after_id = ""
    fetched_missing = 0
    detail_blocked = False

    with psycopg.connect(url, connect_timeout=15) as connection:
        while max_items is None or summary["scanned"] < max_items:
            remaining = (
                batch_size
                if max_items is None
                else min(batch_size, max_items - summary["scanned"])
            )
            with connection.cursor() as cursor:
                cursor.execute(SELECT_BATCH_SQL, (after_id, remaining))
                listings = grouped_rows(cursor.fetchall())
            if not listings:
                break

            for listing in listings:
                after_id = listing["id"]
                summary["scanned"] += 1
                existing_urls = list(listing["images"])
                fetched_urls: list[str] = []

                if not existing_urls and fetch_missing and not detail_blocked:
                    if fetched_missing and fetch_delay_seconds > 0:
                        time.sleep(fetch_delay_seconds)
                    fetched_missing += 1
                    try:
                        fetched_urls = fetch_post_rss_images(
                            listing["source_url"],
                            user_agent=user_agent,
                            timeout=timeout,
                        )
                    except RateLimitedError:
                        summary["rate_limited"] += 1
                        detail_blocked = True
                    except Exception:
                        summary["failed"] += 1

                desired_urls = desired_image_urls(existing_urls, fetched_urls)
                if not desired_urls:
                    summary["missing"] += 1
                    continue
                if desired_urls == existing_urls:
                    summary["unchanged"] += 1
                    continue

                summary["changed"] += 1
                if not existing_urls:
                    summary["recovered"] += 1
                if apply:
                    replace_images(
                        connection,
                        listing_id=listing["id"],
                        title=listing["title"],
                        urls=desired_urls,
                    )
                    summary["rewritten"] += 1

            if len(listings) < remaining:
                break
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Canonicalize Reddit images to full-resolution i.redd.it assets, "
            "remove duplicate carousel frames, and optionally recover missing rows from post RSS."
        )
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--fetch-missing", action="store_true")
    parser.add_argument("--fetch-delay-seconds", type=float, default=15.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write repaired rows. Without this flag the command is a dry run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1 or args.batch_size > 100:
        raise SystemExit("--batch-size must be between 1 and 100")
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be greater than zero")
    if args.fetch_delay_seconds < 0:
        raise SystemExit("--fetch-delay-seconds cannot be negative")
    if args.timeout < 1:
        raise SystemExit("--timeout must be greater than zero")

    try:
        configure_urllib_egress(resolve_egress_config())
        summary = run_backfill(
            args.database_url,
            batch_size=args.batch_size,
            max_items=args.max_items,
            apply=args.apply,
            fetch_missing=args.fetch_missing,
            fetch_delay_seconds=args.fetch_delay_seconds,
            timeout=args.timeout,
            user_agent=args.user_agent,
        )
    except (EgressConfigError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, separators=(",", ":")))
        return 1

    print(
        json.dumps(
            {
                "ok": summary["failed"] == 0 and summary["rate_limited"] == 0,
                "dryRun": not args.apply,
                **summary,
            },
            separators=(",", ":"),
        )
    )
    return 0 if summary["failed"] == 0 and summary["rate_limited"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
