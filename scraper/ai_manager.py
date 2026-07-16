"""Central mixed-platform NVIDIA parser manager for durable raw candidates."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from scraper.candidate_pool import CandidatePool, DEFAULT_POOL_PATH, LeasedCandidate
from scraper.media.instagram_r2 import MediaCacheBatch, cache_instagram_media
from scraper.reddit.nvidia_parser import enrich_listings_with_nvidia
from scraper.shared.config import DEFAULT_CONFIG_PATH, float_value, load_config, table
from scraper.shared.listing_contract import validate_listings
from scraper.shared.runtime import (
    AlreadyRunningError,
    EgressConfigError,
    FileLock,
    configure_urllib_egress,
    resolve_egress_config,
)
from scraper.storage.postgres import require_database_url, upsert_listings
from scraper.storage.run_log import write_run_log


SCRAPER_DIR = Path(__file__).resolve().parent
DEFAULT_MANAGER_LOG_FILE = SCRAPER_DIR / ".logs" / "ai_manager.jsonl"
DEFAULT_MANAGER_LOCK_FILE = SCRAPER_DIR / ".state" / "ai_manager.lock"


def resolve_scraper_path(value: Any, default: Path) -> Path:
    if not value:
        return default
    path = Path(str(value))
    return path if path.is_absolute() else SCRAPER_DIR / path


def configured_value(cli_value: Any, configured: Any, default: Any) -> Any:
    if cli_value is not None:
        return cli_value
    return configured if configured is not None else default


def process_batch(
    pool: CandidatePool,
    candidates: list[LeasedCandidate],
    *,
    database_url: str | None,
    write_db: bool,
    enrich_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] = enrich_listings_with_nvidia,
    media_cache_fn: Callable[[list[dict[str, Any]]], MediaCacheBatch] = cache_instagram_media,
    upsert_fn: Callable[..., Any] = upsert_listings,
    retry_seconds: int = 300,
    now: datetime | None = None,
) -> dict[str, Any]:
    candidate_ids = [candidate.id for candidate in candidates]
    platforms = sorted({candidate.platform for candidate in candidates})
    try:
        parsed = enrich_fn([candidate.payload for candidate in candidates])
        valid, invalid = validate_listings(parsed)
        if invalid:
            raise ValueError(f"AI manager produced {len(invalid)} invalid listings")
        media_result = media_cache_fn(valid)
        valid = media_result.listings
        storage_summary = None
        if write_db and valid:
            resolved_url = require_database_url(database_url)
            storage_summary = upsert_fn(resolved_url, valid).as_dict()
        pool.complete(candidate_ids, now=now)
        return {
            "ok": True,
            "items": len(candidates),
            "parsed": len(parsed),
            "validated": len(valid),
            "platforms": platforms,
            "media": media_result.as_dict(),
            "storage": storage_summary,
            "error": None,
        }
    except Exception as exc:
        safe_error = f"{type(exc).__name__}: {str(exc).replace(chr(10), ' ')[:800]}"
        pool.retry(candidate_ids, error=safe_error, delay_seconds=retry_seconds, now=now)
        return {
            "ok": False,
            "items": len(candidates),
            "parsed": 0,
            "validated": 0,
            "platforms": platforms,
            "media": None,
            "storage": None,
            "error": safe_error,
        }


def run_manager(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    manager_config = table(config, "ai_manager")
    pool_path = resolve_scraper_path(args.pool_path or manager_config.get("pool_path"), DEFAULT_POOL_PATH)
    log_path = resolve_scraper_path(args.log_file or manager_config.get("log_file"), DEFAULT_MANAGER_LOG_FILE)
    batch_size = max(
        1,
        min(10, int(configured_value(args.batch_size, manager_config.get("batch_size"), 2))),
    )
    max_wait = max(
        0.0,
        float(configured_value(args.max_wait_seconds, manager_config.get("max_wait_seconds"), 30.0)),
    )
    poll_seconds = max(
        0.2,
        float(configured_value(args.poll_seconds, manager_config.get("poll_seconds"), 2.0)),
    )
    rate_limit_seconds = max(0.0, float_value(manager_config.get("rate_limit_seconds"), 5.0))
    retry_seconds = max(
        1,
        int(configured_value(args.retry_seconds, manager_config.get("retry_seconds"), 300)),
    )
    lease_seconds = max(
        30,
        int(configured_value(args.lease_seconds, manager_config.get("lease_seconds"), 300)),
    )
    pool = CandidatePool(pool_path)
    database_url = args.database_url

    while True:
        batch = pool.lease_batch(
            batch_size=batch_size,
            max_wait_seconds=0 if args.once else max_wait,
            lease_seconds=lease_seconds,
        )
        if batch:
            result = process_batch(
                pool,
                batch,
                database_url=database_url,
                write_db=args.write_db,
                enrich_fn=lambda listings: enrich_listings_with_nvidia(
                    listings,
                    batch_size=batch_size,
                    rate_limit_seconds=rate_limit_seconds,
                ),
                retry_seconds=retry_seconds,
            )
            record = {
                "source": "ai_manager",
                "loggedAt": datetime.now().astimezone().isoformat(),
                **result,
                "queue": pool.stats(),
            }
            write_run_log(log_path, record)
            print(json.dumps(record, ensure_ascii=False, separators=(",", ":")), flush=True)
            if args.once:
                return 0 if result["ok"] else 1
            time.sleep(rate_limit_seconds)
            continue
        if args.once:
            return 0
        time.sleep(poll_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process durable mixed-platform scraper candidates with NVIDIA AI.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--pool-path", default=None)
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--lock-file", default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--max-wait-seconds", type=float, default=None)
    parser.add_argument("--poll-seconds", type=float, default=None)
    parser.add_argument("--retry-seconds", type=int, default=None)
    parser.add_argument("--lease-seconds", type=int, default=None)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--write-db", action="store_true")
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
    manager_config = table(config, "ai_manager")
    lock_path = resolve_scraper_path(args.lock_file or manager_config.get("lock_file"), DEFAULT_MANAGER_LOCK_FILE)
    try:
        with FileLock(lock_path, stale_seconds=900):
            return run_manager(args)
    except AlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
