from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper.operational_report import SCRAPER_DIR, build_reports, resolve_output_dir, write_reports


GENERATED_AT = datetime(2026, 7, 12, 6, 0, tzinfo=timezone.utc)


def listing(**overrides):
    value = {
        "id": "listing-1",
        "platform": "reddit",
        "sourceUrl": "https://example.test/listing-1",
        "externalId": "external-1",
        "title": "ASUS laptop",
        "description": "ASUS laptop\nHarga Rp10.000.000\nLokasi Jakarta\nKondisi bekas mulus",
        "category": "Laptop",
        "brand": "ASUS",
        "price": 10_000_000,
        "locationTexts": ["Jakarta"],
        "conditionText": "bekas mulus",
        "status": "available",
        "postedAt": GENERATED_AT,
        "firstFetchedAt": GENERATED_AT,
        "imageCount": 1,
    }
    value.update(overrides)
    return value


class OperationalReportTests(unittest.TestCase):
    def test_relative_report_directory_resolves_inside_persisted_scraper_logs(self):
        self.assertEqual(resolve_output_dir(Path(".logs/reports")), SCRAPER_DIR / ".logs" / "reports")

    def test_data_quality_counts_missing_and_low_confidence_fields(self):
        rows = [
            listing(),
            listing(
                id="listing-2",
                sourceUrl="https://example.test/listing-2",
                category=None,
                brand=None,
                price=None,
                locationTexts=[],
                conditionText=None,
                status="unknown",
                postedAt=None,
                imageCount=0,
            ),
        ]

        data_quality, _manual_review = build_reports(rows, generated_at=GENERATED_AT)

        self.assertEqual(data_quality["summary"]["totalListings"], 2)
        self.assertEqual(data_quality["missingRequiredFields"], {})
        self.assertEqual(
            data_quality["lowConfidenceFields"],
            {
                "brand": 1,
                "category": 1,
                "conditionText": 1,
                "images": 1,
                "locationTexts": 1,
                "postedAt": 1,
                "price": 1,
                "status": 1,
            },
        )
        self.assertEqual(data_quality["coverage"]["category"], 0.5)

    def test_manual_review_flags_ambiguous_fields_without_copying_description(self):
        rows = [
            listing(
                description="SOLD OUT\nASUS laptop",
                status="available",
                locationTexts=["Jakarta", "Bandung"],
                conditionText="normal",
            )
        ]

        _data_quality, manual_review = build_reports(rows, generated_at=GENERATED_AT)

        [item] = manual_review["items"]
        self.assertEqual(item["reasons"], ["ambiguous_condition", "multiple_locations", "sold_status_conflict"])
        self.assertNotIn("description", item)
        self.assertEqual(item["sourceUrl"], "https://example.test/listing-1")

    def test_report_writer_creates_separate_daily_and_manual_artifacts(self):
        reports = build_reports([listing()], generated_at=GENERATED_AT)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_reports(*reports, output_dir=Path(tmpdir))

            self.assertEqual({path.name for path in paths}, {
                "data-quality-2026-07-12.json",
                "manual-review-2026-07-12.json",
            })
            self.assertTrue(all(path.is_file() for path in paths))


if __name__ == "__main__":
    unittest.main()
