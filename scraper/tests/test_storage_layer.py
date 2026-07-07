from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scraper.storage.postgres import (
    StorageError,
    deduplicate_listings,
    image_rows,
    listing_to_db_row,
    require_database_url,
    safe_database_url,
)
from scraper.storage.run_log import write_run_log


def sample_listing(**overrides):
    value = {
        "platform": "REDDIT",
        "sourceUrl": "https://example.test/listing/1",
        "externalId": "abc123",
        "title": "RTX 3060 Ti",
        "description": "Seller text",
        "category": "GPU",
        "brand": "NVIDIA",
        "price": 3200000,
        "locationTexts": ["Jakarta", "Tangerang"],
        "conditionText": "Bekas",
        "sellerName": "seller",
        "status": "AVAILABLE",
        "postedAt": "2026-07-07T10:30:00+07:00",
        "firstFetchedAt": "2026-07-07T04:00:00+00:00",
        "lastFetchedAt": "2026-07-07T04:05:00+00:00",
        "images": [
            {"sourceUrl": "https://example.test/0.jpg", "position": 0, "altText": "front"},
            {"sourceUrl": "https://example.test/old.jpg", "position": 1, "altText": "old"},
            {"sourceUrl": "https://example.test/new.jpg", "position": 1, "altText": "new"},
        ],
    }
    value.update(overrides)
    return value


class StorageLayerTests(unittest.TestCase):
    def test_require_database_url_prefers_scraper_database_url(self):
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://web:secret@localhost:5432/recon",
                "SCRAPER_DATABASE_URL": "postgresql://scraper:secret@postgres:5432/recon",
            },
            clear=True,
        ):
            self.assertEqual(
                require_database_url(None),
                "postgresql://scraper:secret@postgres:5432/recon",
            )

    def test_require_database_url_rejects_missing_url(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(StorageError):
                require_database_url(None)

    def test_safe_database_url_redacts_password(self):
        self.assertEqual(
            safe_database_url("postgresql://recon:secret@postgres:5432/recon_dev"),
            "postgresql://recon:***@postgres:5432/recon_dev",
        )

    def test_deduplicate_listings_keeps_last_by_source_url(self):
        first = sample_listing(title="old title")
        second = sample_listing(title="new title")
        third = sample_listing(sourceUrl="https://example.test/listing/2")

        result = deduplicate_listings([first, second, third])

        self.assertEqual(result.duplicates, 1)
        self.assertEqual([item["title"] for item in result.listings], ["new title", "RTX 3060 Ti"])

    def test_listing_to_db_row_maps_contract_to_snake_case(self):
        row = listing_to_db_row(sample_listing(), listing_id="listing_123")

        self.assertEqual(row["id"], "listing_123")
        self.assertEqual(row["platform"], "reddit")
        self.assertEqual(row["source_url"], "https://example.test/listing/1")
        self.assertEqual(row["external_id"], "abc123")
        self.assertEqual(row["location_texts"], ["Jakarta", "Tangerang"])
        self.assertEqual(row["status"], "available")
        self.assertIsNone(row["posted_at"].tzinfo)
        self.assertEqual(row["posted_at"], datetime(2026, 7, 7, 3, 30))

    def test_image_rows_keep_last_image_per_position(self):
        rows = image_rows("listing_123", sample_listing()["images"])

        self.assertEqual([row["position"] for row in rows], [0, 1])
        self.assertEqual(rows[1]["source_url"], "https://example.test/new.jpg")
        self.assertEqual(rows[1]["alt_text"], "new")

    def test_write_run_log_appends_jsonl_and_redacts_sensitive_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scraper-runs.jsonl"
            write_run_log(
                path,
                {
                    "source": "orchestrator",
                    "status": "success",
                    "databaseUrl": "postgresql://recon:secret@postgres:5432/recon_dev",
                    "counts": {"inserted": 1},
                },
            )

            [line] = path.read_text(encoding="utf-8").splitlines()
            event = json.loads(line)

        self.assertEqual(event["source"], "orchestrator")
        self.assertEqual(event["databaseUrl"], "postgresql://recon:***@postgres:5432/recon_dev")
        self.assertEqual(event["counts"], {"inserted": 1})
        self.assertIn("logged_at", event)


if __name__ == "__main__":
    unittest.main()
