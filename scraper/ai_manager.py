"""Central mixed-platform NVIDIA parser manager for durable raw candidates."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scraper.candidate_pool import CandidatePool, DEFAULT_POOL_PATH, LeasedCandidate
from scraper.reddit.nvidia_parser import enrich_listings_with_nvidia
from scraper.shared.config import DEFAULT_CONFIG_PATH, load_config, table
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


def wait_for_departure(
    next_departure: float,
    *,
    monotonic_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    remaining = next_departure - monotonic_fn()
    if remaining > 0:
        sleep_fn(remaining)


def advance_departure(previous: float, interval_seconds: float, current: float) -> float:
    next_departure = previous + interval_seconds
    while next_departure <= current:
        next_departure += interval_seconds
    return next_departure


def process_batch(
    pool: CandidatePool,
    candidates: list[LeasedCandidate],
    *,
    database_url: str | None,
    write_db: bool,
    enrich_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] = enrich_listings_with_nvidia,
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
            "storage": None,
            "error": safe_error,
        }


def run_manager(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    manager_config = table(config, "ai_manager")
    pool_path = resolve_scraper_path(args.pool_path or manager_config.get("pool_path"), DEFAULT_POOL_PATH)
    log_path = resolve_scraper_path(args.log_file or manager_config.get("log_file"), DEFAULT_MANAGER_LOG_FILE)
    train_capacity = max(
        1,
        min(
            10,
            int(
                configured_value(
                    getattr(args, "train_capacity", None),
                    manager_config.get("train_capacity"),
                    3,
                )
            ),
        ),
    )
    departure_interval = max(
        1.0,
        float(
            configured_value(
                getattr(args, "departure_interval_seconds", None),
                manager_config.get("departure_interval_seconds"),
                60.0,
            )
        ),
    )
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
    next_departure = time.monotonic() + departure_interval

    while True:
        if not args.once:
            wait_for_departure(next_departure)
        departure_at = datetime.now(timezone.utc)
        batch = pool.lease_train(
            max_items=train_capacity,
            lease_seconds=lease_seconds,
            now=departure_at,
        )
        if batch:
            result = process_batch(
                pool,
                batch,
                database_url=database_url,
                write_db=args.write_db,
                enrich_fn=lambda listings: enrich_listings_with_nvidia(
                    listings,
                    batch_size=len(listings),
                    rate_limit_seconds=0.0,
                ),
                retry_seconds=retry_seconds,
            )
            record = {
                "source": "ai_manager",
                "loggedAt": datetime.now().astimezone().isoformat(),
                "train": {
                    "departedAt": departure_at.isoformat(),
                    "intervalSeconds": departure_interval,
                    "capacity": train_capacity,
                    "boarded": len(batch),
                },
                **result,
                "queue": pool.stats(),
            }
            write_run_log(log_path, record)
            print(json.dumps(record, ensure_ascii=False, separators=(",", ":")), flush=True)
            if args.once:
                return 0 if result["ok"] else 1
        if args.once:
            return 0
        next_departure = advance_departure(next_departure, departure_interval, time.monotonic())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process durable mixed-platform scraper candidates with NVIDIA AI.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--pool-path", default=None)
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--lock-file", default=None)
    parser.add_argument("--train-capacity", type=int, default=None)
    parser.add_argument("--departure-interval-seconds", type=float, default=None)
    parser.add_argument("--batch-size", dest="train_capacity", type=int, help=argparse.SUPPRESS)
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
