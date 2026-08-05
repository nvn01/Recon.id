"""Bounded sold-status reconciliation for known Facebook Marketplace listings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from scraper.facebook.facebook_marketplace import (
    configure_discovery_page,
    extract_page_text,
    launch_facebook_context,
    looks_login_blocked,
    open_marketplace,
)
from scraper.storage.postgres import StorageError, require_database_url


SELECT_RECONCILIATION_CANDIDATES_SQL = """
WITH latest_ready AS (
    SELECT id, external_id, source_url, status, last_fetched_at,
           COALESCE(posted_at, first_fetched_at) AS listed_at
    FROM listings
    WHERE platform = 'facebook'::listing_platform
      AND status IN ('available'::listing_status, 'unknown'::listing_status)
      AND external_id ~ '^[0-9]+$'
      AND source_url ~ '^https://www\\.facebook\\.com/marketplace/item/[0-9]+/?$'
    ORDER BY COALESCE(posted_at, first_fetched_at) DESC, id DESC
    LIMIT %s
)
SELECT external_id, source_url, status::text
FROM latest_ready
ORDER BY last_fetched_at ASC NULLS FIRST, listed_at DESC, id
LIMIT 1
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
  AND platform = 'facebook'::listing_platform
  AND status IN ('available'::listing_status, 'unknown'::listing_status)
"""

SOLD_LINES = frozenset({"habis", "sold", "sold out", "terjual", "sudah terjual"})
SOLD_PHRASES = (
    "this listing was sold",
    "this item was sold",
    "listing ini telah terjual",
    "barang ini telah terjual",
)
UNAVAILABLE_PHRASES = (
    "this listing is no longer available",
    "this item is no longer available",
    "listing ini sudah tidak tersedia",
    "barang ini sudah tidak tersedia",
)


@dataclass(frozen=True)
class ReconciliationCandidate:
    external_id: str
    source_url: str
    current_status: str


@dataclass(frozen=True)
class StatusEvidence:
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
                cursor.execute(SELECT_RECONCILIATION_CANDIDATES_SQL, (window_size,))
                return [
                    ReconciliationCandidate(
                        external_id=str(row[0] or ""),
                        source_url=str(row[1]),
                        current_status=str(row[2]),
                    )
                    for row in cursor.fetchall()
                ]
    except psycopg.Error as exc:
        raise StorageError(f"Facebook reconciliation read failed: {type(exc).__name__}") from exc


def persist_results(database_url: str, results: Iterable[tuple[ReconciliationCandidate, StatusEvidence]]) -> int:
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
        raise StorageError(f"Facebook reconciliation write failed: {type(exc).__name__}") from exc


def extract_status_evidence(script_texts: Iterable[str], external_id: str, visible_text: str) -> StatusEvidence:
    structured = extract_structured_status(script_texts, external_id)
    if structured is not None:
        return structured

    primary_text = primary_listing_text(visible_text)
    lines = [normalize_text(line) for line in primary_text.splitlines() if normalize_text(line)]
    has_visible_sold_label = any(line in SOLD_LINES for line in lines) or any(
        re.search(r"(?:^|[·|])\s*habis$", line) for line in lines[:6]
    )
    if has_visible_sold_label or any(phrase in normalize_text(primary_text) for phrase in SOLD_PHRASES):
        return StatusEvidence(status="sold", signal="visible_sold_marker")
    if any(phrase in normalize_text(primary_text) for phrase in UNAVAILABLE_PHRASES):
        # Removed, hidden, and deleted listings are not automatically equivalent to sold.
        return StatusEvidence(status=None, signal="unavailable_without_sold_evidence")
    return StatusEvidence(status=None, signal="page_checked_without_status_signal")


def extract_structured_status(script_texts: Iterable[str], external_id: str) -> StatusEvidence | None:
    for script_text in script_texts:
        try:
            payload = json.loads(script_text)
        except (TypeError, json.JSONDecodeError):
            continue
        for record in walk_dicts(payload):
            if str(record.get("id") or record.get("listing_id") or "") != external_id:
                continue
            is_sold = record.get("is_sold")
            is_live = record.get("is_live")
            if is_sold is True:
                return StatusEvidence(status="sold", signal="structured_is_sold")
            if is_sold is False and is_live is True:
                return StatusEvidence(status="available", signal="structured_is_live")
    return None


def walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def primary_listing_text(value: str) -> str:
    lines = value.splitlines()
    stop_markers = {"related searches", "today's picks", "pilihan hari ini"}
    for index, line in enumerate(lines):
        if normalize_text(line) in stop_markers:
            return "\n".join(lines[:index])
    return value


def inspect_candidate(page: Any, candidate: ReconciliationCandidate, args: argparse.Namespace) -> StatusEvidence:
    try:
        open_marketplace(page, candidate.source_url, args.wait_ms, args.timeout * 1000)
        visible_text = extract_page_text(page, max_chars=9000)
        scripts = page.locator('script[type="application/json"]').all_text_contents()
        evidence = extract_status_evidence(scripts, candidate.external_id, visible_text)
        # Logged-out detail pages can show a login modal over valid listing
        # content. Treat it as blocking only when navigation left the item URL.
        if looks_login_blocked(visible_text) and not is_expected_detail_url(page.url, candidate.external_id):
            return StatusEvidence(status=None, signal="login_blocked", checked=False)
        return evidence
    except PlaywrightError as exc:
        print(f"Facebook reconciliation failed for {candidate.external_id}: {type(exc).__name__}", file=sys.stderr)
        return StatusEvidence(status=None, signal=f"browser_{type(exc).__name__}", checked=False)


def is_expected_detail_url(url: str, external_id: str) -> bool:
    return bool(re.search(rf"/marketplace/item/{re.escape(external_id)}/?(?:[?#]|$)", url))


def reconcile(database_url: str, args: argparse.Namespace) -> ReconciliationSummary:
    candidates = load_candidates(database_url, args.window_size)
    summary = ReconciliationSummary(selected=len(candidates))
    if not candidates:
        return summary

    results: list[tuple[ReconciliationCandidate, StatusEvidence]] = []
    with sync_playwright() as playwright:
        browser_instance, context = launch_facebook_context(playwright, args)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            configure_discovery_page(page, args)
            for candidate in candidates:
                evidence = inspect_candidate(page, candidate, args)
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
                    if evidence.signal == "login_blocked":
                        break
        finally:
            context.close()
            if browser_instance is not None:
                browser_instance.close()

    persist_results(database_url, results)
    return summary


def output_payload(summary: ReconciliationSummary, *, ok: bool, error: str | None = None) -> dict[str, Any]:
    status = "success" if ok and summary.checked else "no_new_data" if ok else "degraded"
    return {
        "ok": ok,
        "selectedConnectors": ["facebook"],
        "summary": {"listings": summary.checked, **asdict(summary)},
        "storage": None,
        "connectors": [
            {
                "connector": "facebook",
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
    parser = argparse.ArgumentParser(description="Revisit known Facebook Marketplace listings for sold status.")
    parser.add_argument("--window-size", type=int, default=60, help="Newest ready listings eligible for rotation.")
    parser.add_argument("--timeout", type=int, default=30, help="Per-page timeout in seconds.")
    parser.add_argument("--wait-ms", type=int, default=0, help="Wait after each detail page load.")
    parser.add_argument("--browser", choices=("chromium", "chrome"), default="chrome")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--profile-dir", default="scraper/.facebook-profile")
    parser.add_argument("--session-mode", choices=("ephemeral", "persistent"), default="ephemeral")
    parser.add_argument("--proxy-url", default=None)
    parser.add_argument("--load-assets", action="store_true")
    parser.add_argument("--login", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.window_size < 1 or args.window_size > 500:
        parser.error("--window-size must be between 1 and 500.")
    if args.timeout < 5:
        parser.error("--timeout must be at least 5 seconds.")
    args.block_assets = not args.load_assets
    return args


def main() -> int:
    args = parse_args()
    try:
        database_url = require_database_url(args.database_url)
        summary = reconcile(database_url, args)
        payload = output_payload(summary, ok=summary.failed == 0)
        code = 0 if summary.failed == 0 else 1
    except (StorageError, PlaywrightError) as exc:
        summary = ReconciliationSummary()
        payload = output_payload(summary, ok=False, error=f"{type(exc).__name__}: {exc}")
        code = 1

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(
            f"Facebook reconciliation: selected={summary.selected} checked={summary.checked} "
            f"sold={summary.sold} available={summary.available} unchanged={summary.unchanged} failed={summary.failed}"
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
