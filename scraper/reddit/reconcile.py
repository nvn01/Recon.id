"""Reconcile recent ready Reddit listings against each post's current flair."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from scraper.reddit.reddit import (
    DEFAULT_USER_AGENT,
    SUBREDDIT,
    RateLimitedError,
    build_rss_url,
    extract_external_id,
    fetch_text,
    parse_feed,
)
from scraper.storage.postgres import StorageError, require_database_url
from scraper.storage.reconciliation_visibility import REDDIT_RECONCILIATION_VISIBILITY_SQL


SELECT_ROTATING_CANDIDATE_SQL = f"""
WITH latest_ready AS (
    SELECT listing.id, listing.external_id, listing.source_url, listing.status, listing.last_fetched_at,
           COALESCE(listing.posted_at, listing.first_fetched_at) AS listed_at
    FROM listings AS listing
    WHERE listing.platform = 'reddit'::listing_platform
      AND listing.status IN ('available'::listing_status, 'unknown'::listing_status)
      AND listing.external_id ~ '^[A-Za-z0-9]+$'
      {REDDIT_RECONCILIATION_VISIBILITY_SQL}
    ORDER BY COALESCE(posted_at, first_fetched_at) DESC, id DESC
    LIMIT %s
)
SELECT external_id, source_url, status::text
FROM latest_ready
ORDER BY last_fetched_at ASC NULLS FIRST, listed_at DESC, id
LIMIT 1
"""

UPDATE_RECONCILIATION_RESULT_SQL = f"""
UPDATE listings AS listing
SET status = COALESCE(%(status)s::listing_status, listing.status),
    last_fetched_at = %(checked_at)s,
    updated_at = CASE
        WHEN %(status)s::text IS NOT NULL AND listing.status::text <> %(status)s::text THEN CURRENT_TIMESTAMP
        ELSE listing.updated_at
    END
WHERE listing.source_url = %(source_url)s
  AND listing.platform = 'reddit'::listing_platform
  AND listing.status IN ('available'::listing_status, 'unknown'::listing_status)
  {REDDIT_RECONCILIATION_VISIBILITY_SQL}
"""

SOLD_OUT_FLAIR = "SOLD OUT"
DEFAULT_SOLD_FEED_LIMIT = 100


@dataclass(frozen=True)
class ReconciliationCandidate:
    external_id: str
    source_url: str
    current_status: str


@dataclass(frozen=True)
class FlairEvidence:
    flair: str | None
    status: str | None
    signal: str
    checked: bool = True


@dataclass
class ReconciliationSummary:
    selected: int = 0
    checked: int = 0
    sold: int = 0
    available: int = 0
    unchanged: int = 0
    failed: int = 0


def load_candidates(database_url: str, window_size: int) -> list[ReconciliationCandidate]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - runtime dependency guard.
        raise StorageError("Install scraper database dependencies before reconciliation.") from exc

    try:
        with psycopg.connect(database_url, connect_timeout=15) as connection:
            with connection.cursor() as cursor:
                cursor.execute(SELECT_ROTATING_CANDIDATE_SQL, (window_size,))
                return [
                    ReconciliationCandidate(
                        external_id=str(row[0] or ""),
                        source_url=str(row[1]),
                        current_status=str(row[2]),
                    )
                    for row in cursor.fetchall()
                ]
    except psycopg.Error as exc:
        raise StorageError(f"Reddit reconciliation read failed: {type(exc).__name__}") from exc


def persist_results(database_url: str, results: Iterable[tuple[ReconciliationCandidate, FlairEvidence]]) -> int:
    checked_results = [(candidate, evidence) for candidate, evidence in results if evidence.checked]
    if not checked_results:
        return 0

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - runtime dependency guard.
        raise StorageError("Install scraper database dependencies before reconciliation.") from exc

    checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        with psycopg.connect(database_url, connect_timeout=15) as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    for candidate, evidence in checked_results:
                        cursor.execute(
                            UPDATE_RECONCILIATION_RESULT_SQL,
                            {
                                "status": evidence.status,
                                "checked_at": checked_at,
                                "source_url": candidate.source_url,
                            },
                        )
        return len(checked_results)
    except psycopg.Error as exc:
        raise StorageError(f"Reddit reconciliation write failed: {type(exc).__name__}") from exc


def build_sold_feed_url(limit: int, subreddit: str = SUBREDDIT) -> str:
    return build_rss_url(limit, subreddit=subreddit, flair=SOLD_OUT_FLAIR)


def extract_feed_external_ids(xml_text: str, limit: int) -> set[str]:
    external_ids: set[str] = set()
    for post in parse_feed(xml_text, limit):
        external_id = extract_external_id(str(post.get("url", "")), str(post.get("atom_id", "")))
        if external_id:
            external_ids.add(external_id.casefold())
    return external_ids


def inspect_candidate(candidate: ReconciliationCandidate, args: argparse.Namespace) -> FlairEvidence:
    url = build_sold_feed_url(args.sold_feed_limit, args.subreddit)
    try:
        xml_text = fetch_text(
            url,
            args.user_agent,
            retries=args.retries,
            retry_wait=args.retry_wait,
            retry_jitter=args.retry_jitter_seconds,
            timeout=args.timeout,
            accept="application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        )
    except RateLimitedError:
        raise
    except urllib.error.HTTPError as exc:
        print(f"Reddit reconciliation failed for {candidate.external_id}: HTTP {exc.code}", file=sys.stderr)
        return FlairEvidence(flair=None, status=None, signal=f"http_{exc.code}", checked=False)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Reddit reconciliation failed for {candidate.external_id}: {type(exc).__name__}", file=sys.stderr)
        return FlairEvidence(flair=None, status=None, signal=f"fetch_{type(exc).__name__}", checked=False)

    try:
        sold_ids = extract_feed_external_ids(xml_text, args.sold_feed_limit)
    except ET.ParseError:
        print(f"Reddit reconciliation failed for {candidate.external_id}: invalid SOLD OUT feed", file=sys.stderr)
        return FlairEvidence(flair=None, status=None, signal="invalid_sold_feed", checked=False)
    if candidate.external_id.casefold() in sold_ids:
        return FlairEvidence(flair=SOLD_OUT_FLAIR, status="sold", signal="sold_out_feed_match")
    # Search-feed absence never means available. Preserve the stored status and
    # only advance the rotation timestamp after a usable SOLD OUT feed response.
    return FlairEvidence(flair=None, status=None, signal="not_in_recent_sold_feed")


def reconcile(database_url: str, args: argparse.Namespace) -> ReconciliationSummary:
    candidates = load_candidates(database_url, args.window_size)
    summary = ReconciliationSummary(selected=len(candidates))
    results: list[tuple[ReconciliationCandidate, FlairEvidence]] = []
    for candidate in candidates:
        try:
            evidence = inspect_candidate(candidate, args)
        except RateLimitedError:
            summary.failed += 1
            break
        results.append((candidate, evidence))
        if evidence.checked:
            summary.checked += 1
            if evidence.status == "sold":
                summary.sold += 1
            elif evidence.status == "available":
                summary.available += 1
            else:
                summary.unchanged += 1
        else:
            summary.failed += 1
            if evidence.signal in {"http_401", "http_403"}:
                break

    persist_results(database_url, results)
    return summary


def output_payload(summary: ReconciliationSummary, *, ok: bool, error: str | None = None) -> dict[str, Any]:
    status = "success" if ok and summary.checked else "no_new_data" if ok else "degraded"
    return {
        "ok": ok,
        "selectedConnectors": ["reddit"],
        "summary": {"listings": summary.checked, **asdict(summary)},
        "storage": None,
        "connectors": [
            {
                "connector": "reddit",
                "ok": ok,
                "status": status,
                "normalized": summary.checked,
                "validated": summary.checked,
                "validationErrors": [],
            }
        ],
        "error": error,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Revisit recent ready Reddit listings for current flair.")
    parser.add_argument("--window-size", type=int, default=60)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-wait", type=int, default=20)
    parser.add_argument("--retry-jitter-seconds", type=float, default=1.0)
    parser.add_argument("--subreddit", default=SUBREDDIT)
    parser.add_argument("--sold-feed-limit", type=int, default=DEFAULT_SOLD_FEED_LIMIT)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()
    if args.window_size < 1 or args.window_size > 500:
        parser.error("--window-size must be between 1 and 500.")
    if args.timeout < 5:
        parser.error("--timeout must be at least 5 seconds.")
    if args.retries < 1 or args.retries > 3:
        parser.error("--retries must be between 1 and 3.")
    if args.sold_feed_limit < 1 or args.sold_feed_limit > 100:
        parser.error("--sold-feed-limit must be between 1 and 100.")
    return args


def main() -> int:
    args = parse_args()
    try:
        database_url = require_database_url(args.database_url)
        summary = reconcile(database_url, args)
        payload = output_payload(summary, ok=summary.failed == 0)
        code = 0 if summary.failed == 0 else 1
    except StorageError as exc:
        summary = ReconciliationSummary()
        payload = output_payload(summary, ok=False, error=f"{type(exc).__name__}: {exc}")
        code = 1

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(
            f"Reddit reconciliation: selected={summary.selected} checked={summary.checked} "
            f"sold={summary.sold} available={summary.available} unchanged={summary.unchanged} failed={summary.failed}"
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
