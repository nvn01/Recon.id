"""Resumable production backfill for existing Instagram listing images."""

from __future__ import annotations

import argparse
import json

from scraper.media.instagram_r2 import InstagramR2Cache, MediaCacheError, R2Config
from scraper.storage.postgres import require_database_url


SELECT_BATCH_SQL = """
SELECT image.id, image.source_url
FROM listing_images AS image
JOIN listings AS listing ON listing.id = image.listing_id
WHERE listing.platform = 'instagram'::listing_platform
  AND image.cached_url IS NULL
  AND image.id > %s
ORDER BY image.id
LIMIT %s
"""

UPDATE_IMAGE_SQL = """
UPDATE listing_images
SET cached_url = %(cached_url)s,
    storage_key = %(storage_key)s,
    content_hash = %(content_hash)s,
    content_type = %(content_type)s,
    byte_size = %(byte_size)s,
    cached_at = %(cached_at)s
WHERE id = %(id)s AND cached_url IS NULL
"""


def run_backfill(database_url: str | None, *, batch_size: int, max_items: int | None) -> dict[str, int]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - verified in the scraper image.
        raise MediaCacheError("Install scraper dependencies before running the backfill.") from exc

    config = R2Config.from_env()
    if config is None:
        raise MediaCacheError("R2 configuration is required for the Instagram media backfill.")
    cache = InstagramR2Cache(config)
    url = require_database_url(database_url)
    summary = {"selected": 0, "cached": 0, "reused": 0, "failed": 0}
    last_id = ""

    with psycopg.connect(url, connect_timeout=15) as connection:
        while max_items is None or summary["selected"] < max_items:
            remaining = batch_size if max_items is None else min(batch_size, max_items - summary["selected"])
            with connection.cursor() as cursor:
                cursor.execute(SELECT_BATCH_SQL, (last_id, remaining))
                rows = cursor.fetchall()
            if not rows:
                break
            for image_id, source_url in rows:
                last_id = str(image_id)
                summary["selected"] += 1
                try:
                    cached = cache.cache_image(str(source_url))
                except MediaCacheError:
                    summary["failed"] += 1
                    continue
                fields = cached.image_fields()
                with connection.cursor() as cursor:
                    cursor.execute(
                        UPDATE_IMAGE_SQL,
                        {
                            "id": image_id,
                            "cached_url": fields["cachedUrl"],
                            "storage_key": fields["storageKey"],
                            "content_hash": fields["contentHash"],
                            "content_type": fields["contentType"],
                            "byte_size": fields["byteSize"],
                            "cached_at": fields["cachedAt"],
                        },
                    )
                connection.commit()
                summary["reused" if cached.reused else "cached"] += 1
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache existing Instagram listing images in Cloudflare R2.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-items", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1 or args.batch_size > 100:
        raise SystemExit("--batch-size must be between 1 and 100")
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be greater than zero")
    try:
        summary = run_backfill(args.database_url, batch_size=args.batch_size, max_items=args.max_items)
    except MediaCacheError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, separators=(",", ":")))
        return 1
    print(json.dumps({"ok": summary["failed"] == 0, **summary}, separators=(",", ":")))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
