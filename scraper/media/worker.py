"""Independent PostgreSQL-to-R2 worker for uncached Instagram images."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ContextManager

from scraper.media.instagram_r2 import InstagramR2Cache, MediaCacheError, R2Config
from scraper.shared.config import DEFAULT_CONFIG_PATH, load_config, table
from scraper.shared.runtime import (
    AlreadyRunningError,
    EgressConfigError,
    FileLock,
    configure_urllib_egress,
    resolve_egress_config,
)
from scraper.storage.postgres import require_database_url
from scraper.storage.run_log import write_run_log


SCRAPER_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG_FILE = SCRAPER_DIR / ".logs" / "instagram_media_worker.jsonl"
DEFAULT_LOCK_FILE = SCRAPER_DIR / ".state" / "instagram_media_worker.lock"

SELECT_PENDING_SQL = """
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


@dataclass(frozen=True)
class PendingImage:
    id: str
    source_url: str


@dataclass
class MediaWorkerBatch:
    selected: int = 0
    updated: int = 0
    cached: int = 0
    reused: int = 0
    failed: int = 0
    skipped: int = 0
    next_cursor: str = ""

    def as_dict(self) -> dict[str, int]:
        return {
            "selected": self.selected,
            "updated": self.updated,
            "cached": self.cached,
            "reused": self.reused,
            "failed": self.failed,
            "skipped": self.skipped,
        }


def resolve_scraper_path(value: Any, default: Path) -> Path:
    if not value:
        return default
    path = Path(str(value))
    return path if path.is_absolute() else SCRAPER_DIR / path


def configured_value(cli_value: Any, configured: Any, default: Any) -> Any:
    if cli_value is not None:
        return cli_value
    return configured if configured is not None else default


def require_r2_cache(env: Mapping[str, str] | None = None) -> InstagramR2Cache:
    config = R2Config.from_env(env)
    if config is None:
        raise MediaCacheError("R2 configuration is required for the Instagram media worker.")
    return InstagramR2Cache(config)


def cache_pending_images(
    images: list[PendingImage],
    *,
    cache: InstagramR2Cache,
    update_fn: Callable[[str, dict[str, Any]], bool],
) -> MediaWorkerBatch:
    result = MediaWorkerBatch(
        selected=len(images),
        next_cursor=images[-1].id if images else "",
    )
    for image in images:
        try:
            cached = cache.cache_image(image.source_url)
        except MediaCacheError:
            result.failed += 1
            continue

        if not update_fn(image.id, cached.image_fields()):
            result.skipped += 1
            continue

        result.updated += 1
        if cached.reused:
            result.reused += 1
        else:
            result.cached += 1
    return result


def cache_pending_batch(
    database_url: str | None,
    *,
    after_id: str,
    batch_size: int,
    cache: InstagramR2Cache,
    connect_fn: Callable[[str], ContextManager[Any]] | None = None,
) -> MediaWorkerBatch:
    if batch_size < 1 or batch_size > 100:
        raise ValueError("batch_size must be between 1 and 100")

    url = require_database_url(database_url)
    if connect_fn is None:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - verified in the scraper image.
            raise MediaCacheError("Install scraper dependencies before running the media worker.") from exc

        def connect_fn(value: str) -> ContextManager[Any]:
            return psycopg.connect(value, connect_timeout=15)

    with connect_fn(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(SELECT_PENDING_SQL, (after_id, batch_size))
            images = [PendingImage(id=str(row[0]), source_url=str(row[1])) for row in cursor.fetchall()]

        def update_image(image_id: str, fields: dict[str, Any]) -> bool:
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
                updated = cursor.rowcount == 1
            connection.commit()
            return updated

        return cache_pending_images(images, cache=cache, update_fn=update_image)


def run_worker(
    args: argparse.Namespace,
    *,
    cache: InstagramR2Cache | None = None,
    batch_fn: Callable[..., MediaWorkerBatch] = cache_pending_batch,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    config = load_config(args.config)
    worker_config = table(config, "media_worker")
    batch_size = max(1, min(100, int(configured_value(args.batch_size, worker_config.get("batch_size"), 25))))
    poll_seconds = max(
        1.0,
        float(configured_value(args.poll_seconds, worker_config.get("poll_seconds"), 60.0)),
    )
    log_path = resolve_scraper_path(args.log_file or worker_config.get("log_file"), DEFAULT_LOG_FILE)
    database_url = require_database_url(args.database_url)
    cache = cache or require_r2_cache()
    cursor_id = ""

    while True:
        try:
            result = batch_fn(
                database_url,
                after_id=cursor_id,
                batch_size=batch_size,
                cache=cache,
            )
            record = {
                "source": "instagram_media_worker",
                "loggedAt": datetime.now().astimezone().isoformat(),
                "ok": True,
                **result.as_dict(),
                "error": None,
            }
        except Exception as exc:
            result = None
            record = {
                "source": "instagram_media_worker",
                "loggedAt": datetime.now().astimezone().isoformat(),
                "ok": False,
                "error": f"{type(exc).__name__}: media worker cycle failed",
            }

        write_run_log(log_path, record)
        print(json.dumps(record, ensure_ascii=False, separators=(",", ":")), flush=True)
        if args.once:
            return 0 if record["ok"] else 1

        if result is not None and result.selected >= batch_size:
            cursor_id = result.next_cursor
            continue

        cursor_id = ""
        sleep_fn(poll_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache pending Instagram listing images in Cloudflare R2.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--poll-seconds", type=float, default=None)
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--lock-file", default=None)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        configure_urllib_egress(resolve_egress_config())
    except EgressConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    config = load_config(args.config)
    worker_config = table(config, "media_worker")
    lock_path = resolve_scraper_path(args.lock_file or worker_config.get("lock_file"), DEFAULT_LOCK_FILE)
    try:
        with FileLock(lock_path, stale_seconds=900):
            return run_worker(args)
    except AlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"{type(exc).__name__}: media worker startup failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
