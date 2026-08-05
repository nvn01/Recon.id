"""Reconcile recent ready Reddit listings against each post's current flair."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from scraper.reddit.reddit import (
    DEFAULT_USER_AGENT,
    RateLimitedError,
    canonical_url,
    fetch_text,
)
from scraper.storage.postgres import StorageError, require_database_url


SELECT_RECENT_READY_SQL = """
SELECT external_id, source_url, status::text
FROM listings
WHERE platform = 'reddit'::listing_platform
  AND status IN ('available'::listing_status, 'unknown'::listing_status)
  AND external_id ~ '^[A-Za-z0-9]+$'
  AND COALESCE(posted_at, first_fetched_at) >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')
ORDER BY COALESCE(posted_at, first_fetched_at) DESC, id
"""

UPDATE_RECONCILIATION_RESULT_SQL = """
UPDATE listings
SET status = COALESCE(%(status)s::listing_status, status),
    last_fetched_at = %(checked_at)s,
    updated_at = CASE
        WHEN %(status)s::text IS NOT NULL AND status::text <> %(status)s::text THEN CURRENT_TIMESTAMP
        ELSE updated_at
    END
WHERE source_url = %(source_url)s
  AND platform = 'reddit'::listing_platform
  AND status IN ('available'::listing_status, 'unknown'::listing_status)
"""


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


def load_candidates(database_url: str, window_days: int) -> list[ReconciliationCandidate]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - runtime dependency guard.
        raise StorageError("Install scraper database dependencies before reconciliation.") from exc

    try:
        with psycopg.connect(database_url, connect_timeout=15) as connection:
            with connection.cursor() as cursor:
                cursor.execute(SELECT_RECENT_READY_SQL, (window_days,))
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


def extract_current_flair(page_text: str, external_id: str) -> str | None:
    decoded = html.unescape(page_text)
    escaped_id = re.escape(external_id)

    # Current Reddit renders the target as a shreddit-post custom element.
    for tag in re.findall(r"<shreddit-post\b[^>]*>", decoded, flags=re.I):
        if not re.search(rf"(?:t3_)?{escaped_id}\b", tag, flags=re.I):
            continue
        flair = attribute_value(tag, "post-flair")
        if flair:
            return clean_flair(flair)

    # Old Reddit keeps the target thing id and its flair label close together.
    target_match = re.search(rf"(?:thing_)?t3_{escaped_id}\b", decoded, flags=re.I)
    if target_match:
        nearby = decoded[target_match.start() : target_match.start() + 12_000]
        label = re.search(
            r"<span\b[^>]*class=[\"'][^\"']*linkflairlabel[^\"']*[\"'][^>]*>(.*?)</span>",
            nearby,
            flags=re.I | re.S,
        )
        if label:
            return clean_flair(re.sub(r"<[^>]+>", "", label.group(1)))

    # Embedded post data uses link_flair_text; restrict the scan to the target
    # id neighborhood so recommendations cannot supply the status.
    for match in re.finditer(escaped_id, decoded, flags=re.I):
        nearby = decoded[max(0, match.start() - 2_000) : match.start() + 8_000]
        flair_match = re.search(r'"link_flair_text"\s*:\s*"((?:\\.|[^"\\])*)"', nearby)
        if flair_match:
            return clean_flair(decode_json_string(flair_match.group(1)))
    return None


def attribute_value(tag: str, name: str) -> str | None:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*([\"'])(.*?)\1", tag, flags=re.I | re.S)
    return match.group(2) if match else None


def decode_json_string(value: str) -> str:
    try:
        return str(json.loads(f'"{value}"'))
    except json.JSONDecodeError:
        return value


def clean_flair(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def classify_flair(flair: str | None) -> FlairEvidence:
    if not flair:
        return FlairEvidence(flair=None, status=None, signal="flair_not_exposed")
    normalized = clean_flair(flair).casefold()
    if normalized == "sold out":
        return FlairEvidence(flair=flair, status="sold", signal="sold_out_flair")
    if normalized.startswith("wts:"):
        return FlairEvidence(flair=flair, status="available", signal="wts_flair")
    return FlairEvidence(flair=flair, status=None, signal="unrecognized_flair")


def inspect_candidate(candidate: ReconciliationCandidate, args: argparse.Namespace) -> FlairEvidence:
    url = canonical_url(candidate.source_url)
    if not url:
        return FlairEvidence(flair=None, status=None, signal="invalid_source_url", checked=False)
    page_text: str | None = None
    for attempt_url in (url, old_reddit_url(url)):
        try:
            page_text = fetch_text(
                attempt_url,
                args.user_agent,
                retries=args.retries,
                retry_wait=args.retry_wait,
                retry_jitter=args.retry_jitter_seconds,
                timeout=args.timeout,
                accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            )
            break
        except RateLimitedError:
            raise
        except urllib.error.HTTPError as exc:
            # The deployed network has historically received 403 from some
            # Reddit surfaces. Try old Reddit once, then stop the whole batch.
            if exc.code == 403 and attempt_url != old_reddit_url(url):
                continue
            print(f"Reddit reconciliation failed for {candidate.external_id}: HTTP {exc.code}", file=sys.stderr)
            return FlairEvidence(flair=None, status=None, signal=f"http_{exc.code}", checked=False)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"Reddit reconciliation failed for {candidate.external_id}: {type(exc).__name__}", file=sys.stderr)
            return FlairEvidence(flair=None, status=None, signal=f"fetch_{type(exc).__name__}", checked=False)
    if page_text is None:
        return FlairEvidence(flair=None, status=None, signal="fetch_empty", checked=False)
    return classify_flair(extract_current_flair(page_text, candidate.external_id))


def old_reddit_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit(("https", "old.reddit.com", parsed.path, "", ""))


def reconcile(database_url: str, args: argparse.Namespace) -> ReconciliationSummary:
    candidates = load_candidates(database_url, args.window_days)
    summary = ReconciliationSummary(selected=len(candidates))
    results: list[tuple[ReconciliationCandidate, FlairEvidence]] = []
    for index, candidate in enumerate(candidates):
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
        if index + 1 < len(candidates) and args.delay_seconds > 0:
            time.sleep(args.delay_seconds)

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
    parser.add_argument("--window-days", type=int, default=3)
    parser.add_argument("--delay-seconds", type=float, default=5.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-wait", type=int, default=20)
    parser.add_argument("--retry-jitter-seconds", type=float, default=1.0)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()
    if args.window_days < 1 or args.window_days > 30:
        parser.error("--window-days must be between 1 and 30.")
    if args.delay_seconds < 0:
        parser.error("--delay-seconds must be zero or greater.")
    if args.timeout < 5:
        parser.error("--timeout must be at least 5 seconds.")
    if args.retries < 1 or args.retries > 3:
        parser.error("--retries must be between 1 and 3.")
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
