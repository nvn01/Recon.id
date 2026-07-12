"""Build daily data-quality and manual-review reports from normalized listings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from scraper.storage.postgres import require_database_url


SCRAPER_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRAPER_DIR / ".logs" / "reports"
COVERAGE_TARGET = 0.80
REQUIRED_FIELDS = ("platform", "sourceUrl", "title", "description", "status", "firstFetchedAt")
QUALITY_FIELDS = ("price", "category", "brand", "locationTexts", "conditionText", "postedAt", "status", "images")
AMBIGUOUS_CONDITIONS = {"bekas", "like new", "mulus", "normal", "second", "used"}
SOLD_MARKER = re.compile(r"\b(sold\s*out|soldout|sold|terjual|laku|booked)\b", flags=re.I)

LISTINGS_QUERY = """
SELECT
    listing.id,
    listing.platform::text AS platform,
    listing.source_url AS "sourceUrl",
    listing.external_id AS "externalId",
    listing.title,
    listing.description,
    listing.category,
    listing.brand,
    listing.price,
    listing.location_texts AS "locationTexts",
    listing.condition_text AS "conditionText",
    listing.status::text AS status,
    listing.posted_at AS "postedAt",
    listing.first_fetched_at AS "firstFetchedAt",
    (SELECT COUNT(*) FROM listing_images image WHERE image.listing_id = listing.id) AS "imageCount"
FROM listings listing
ORDER BY listing.platform, listing.first_fetched_at DESC, listing.id
"""


def main() -> int:
    args = parse_args()
    try:
        rows = load_listings(require_database_url(args.database_url))
        data_quality, manual_review = build_reports(rows)
        paths = write_reports(data_quality, manual_review, output_dir=resolve_output_dir(Path(args.output_dir)))
    except Exception as exc:  # noqa: BLE001 - keep database diagnostics out of CLI output
        print(f"Operational report failed: {exc.__class__.__name__}", file=sys.stderr)
        return 1

    output = {
        "ok": True,
        "selectedConnectors": ["operations"],
        "summary": {
            "listings": data_quality["summary"]["totalListings"],
            "manualReviewItems": manual_review["summary"]["totalItems"],
            "belowCoverageTarget": data_quality["belowCoverageTarget"],
        },
        "storage": None,
        "connectors": [
            {
                "connector": "operations",
                "ok": True,
                "status": "success",
                "validated": data_quality["summary"]["totalListings"],
            }
        ],
        "reports": [str(path) for path in paths],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.format == "json" else None))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RECON daily data-quality and manual-review reports.")
    parser.add_argument("--database-url", default=None, help="Database URL override; defaults to scraper database env vars.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for dated JSON report files.")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json", help="Stdout summary format.")
    return parser.parse_args()


def load_listings(database_url: str) -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(LISTINGS_QUERY)
            return [dict(row) for row in cursor.fetchall()]


def resolve_output_dir(path: Path) -> Path:
    return path if path.is_absolute() else SCRAPER_DIR / path


def build_reports(
    rows: Iterable[dict[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    listings = list(rows)
    missing_required: Counter[str] = Counter()
    low_confidence: Counter[str] = Counter()
    quality_items: list[dict[str, Any]] = []
    manual_items: list[dict[str, Any]] = []
    platform_totals: Counter[str] = Counter()
    platform_complete: dict[str, Counter[str]] = defaultdict(Counter)

    for listing in listings:
        platform = str(listing.get("platform") or "unknown").lower()
        platform_totals[platform] += 1
        missing = missing_required_fields(listing)
        uncertain = low_confidence_fields(listing)
        reasons = manual_review_reasons(listing)
        missing_required.update(missing)
        low_confidence.update(uncertain)

        for field in QUALITY_FIELDS:
            if field not in uncertain:
                platform_complete[platform][field] += 1

        if missing or uncertain:
            quality_items.append(
                report_identity(listing)
                | {"missingRequiredFields": missing, "lowConfidenceFields": uncertain}
            )
        if reasons:
            manual_items.append(
                report_identity(listing)
                | {
                    "status": listing.get("status"),
                    "conditionText": listing.get("conditionText"),
                    "locationTexts": listing.get("locationTexts") or [],
                    "reasons": reasons,
                }
            )

    total = len(listings)
    coverage = {
        field: round((total - low_confidence[field]) / total, 4) if total else 1.0
        for field in QUALITY_FIELDS
    }
    by_platform = {
        platform: {
            "totalListings": count,
            "coverage": {
                field: round(platform_complete[platform][field] / count, 4) if count else 1.0
                for field in QUALITY_FIELDS
            },
        }
        for platform, count in sorted(platform_totals.items())
    }

    data_quality = {
        "report": "data-quality",
        "generatedAt": generated.isoformat(),
        "coverageTarget": COVERAGE_TARGET,
        "summary": {"totalListings": total, "listingsNeedingAttention": len(quality_items)},
        "missingRequiredFields": dict(sorted(missing_required.items())),
        "lowConfidenceFields": dict(sorted(low_confidence.items())),
        "coverage": coverage,
        "belowCoverageTarget": sorted(field for field, ratio in coverage.items() if ratio < COVERAGE_TARGET),
        "byPlatform": by_platform,
        "items": quality_items,
    }
    reason_counts = Counter(reason for item in manual_items for reason in item["reasons"])
    manual_review = {
        "report": "manual-review",
        "generatedAt": generated.isoformat(),
        "summary": {
            "totalListings": total,
            "totalItems": len(manual_items),
            "reasonCounts": dict(sorted(reason_counts.items())),
        },
        "items": manual_items,
    }
    return data_quality, manual_review


def missing_required_fields(listing: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if is_missing(listing.get(field))]


def low_confidence_fields(listing: dict[str, Any]) -> list[str]:
    fields = []
    for field in QUALITY_FIELDS:
        if field == "status":
            if str(listing.get(field) or "").lower() == "unknown":
                fields.append(field)
        elif field == "images":
            if int(listing.get("imageCount") or 0) <= 0:
                fields.append(field)
        elif is_missing(listing.get(field)):
            fields.append(field)
    return fields


def manual_review_reasons(listing: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    condition = str(listing.get("conditionText") or "").strip()
    if not condition:
        reasons.append("missing_condition")
    elif condition.casefold() in AMBIGUOUS_CONDITIONS:
        reasons.append("ambiguous_condition")

    locations = [str(value).strip() for value in listing.get("locationTexts") or [] if str(value).strip()]
    if not locations:
        reasons.append("missing_location")
    elif len(locations) > 1:
        reasons.append("multiple_locations")

    status = str(listing.get("status") or "").lower()
    if status == "unknown":
        reasons.append("unknown_sold_status")
    elif status != "sold" and description_has_top_sold_marker(str(listing.get("description") or "")):
        reasons.append("sold_status_conflict")
    return reasons


def description_has_top_sold_marker(description: str) -> bool:
    top_lines = [line.strip() for line in description.splitlines() if line.strip()][:5]
    return bool(SOLD_MARKER.search("\n".join(top_lines)))


def report_identity(listing: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": listing.get("id"),
        "platform": listing.get("platform"),
        "sourceUrl": listing.get("sourceUrl"),
        "externalId": listing.get("externalId"),
        "title": listing.get("title"),
    }


def is_missing(value: Any) -> bool:
    return value is None or value == "" or value == []


def write_reports(
    data_quality: dict[str, Any],
    manual_review: dict[str, Any],
    *,
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_date = str(data_quality["generatedAt"])[:10]
    paths = [
        output_dir / f"data-quality-{report_date}.json",
        output_dir / f"manual-review-{report_date}.json",
    ]
    for path, report in zip(paths, (data_quality, manual_review), strict=True):
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)
    return paths


if __name__ == "__main__":
    raise SystemExit(main())
