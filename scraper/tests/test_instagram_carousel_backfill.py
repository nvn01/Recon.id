from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from scraper.instagram.backfill_carousels import (
    PendingCarousel,
    additional_image_rows,
    run_backfill,
)


class InstagramCarouselBackfillTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, connection):
            self.connection = connection
            self.rowcount = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params):
            self.connection.executions.append((sql, params))

        def fetchall(self):
            return list(self.connection.selected_rows)

        def executemany(self, sql, rows):
            inserted = list(rows)
            self.connection.inserts.extend(inserted)
            self.connection.executions.append((sql, inserted))
            self.rowcount = len(inserted)

    class FakeConnection:
        def __init__(self, selected_rows):
            self.selected_rows = selected_rows
            self.executions = []
            self.inserts = []
            self.commits = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return InstagramCarouselBackfillTests.FakeCursor(self)

        def commit(self):
            self.commits += 1

    def test_additional_image_rows_keep_existing_cover_and_add_children_in_order(self):
        pending = PendingCarousel(
            listing_id="listing-1",
            external_id="CAROUSEL",
            cover_url="https://cdn.example/cover.jpg?token=old",
        )
        detail = {
            "shortcode": "CAROUSEL",
            "display_url": "https://cdn.example/cover.jpg?token=new",
            "edge_sidecar_to_children": {
                "edges": [
                    {
                        "node": {
                            "display_url": "https://cdn.example/cover.jpg?token=new"
                        }
                    },
                    {"node": {"display_url": "https://cdn.example/two.jpg"}},
                    {"node": {"display_url": "https://cdn.example/three.jpg"}},
                ]
            },
        }

        rows = additional_image_rows(pending, detail)

        self.assertEqual(
            [(row["position"], row["source_url"]) for row in rows],
            [
                (1, "https://cdn.example/two.jpg"),
                (2, "https://cdn.example/three.jpg"),
            ],
        )
        self.assertTrue(all(row["listing_id"] == "listing-1" for row in rows))
        self.assertTrue(all(row["alt_text"] == "CAROUSEL" for row in rows))

    def test_additional_image_rows_reject_incomplete_or_mismatched_detail(self):
        pending = PendingCarousel(
            listing_id="listing-1",
            external_id="EXPECTED",
            cover_url="https://cdn.example/cover.jpg",
        )

        self.assertEqual(
            additional_image_rows(
                pending,
                {
                    "shortcode": "OTHER",
                    "display_url": "https://cdn.example/cover.jpg",
                    "edge_sidecar_to_children": {
                        "edges": [
                            {"node": {"display_url": "https://cdn.example/cover.jpg"}},
                            {"node": {"display_url": "https://cdn.example/two.jpg"}},
                        ]
                    },
                },
            ),
            [],
        )
        self.assertEqual(
            additional_image_rows(
                pending,
                {
                    "shortcode": "EXPECTED",
                    "display_url": "https://cdn.example/cover.jpg",
                },
            ),
            [],
        )

    def test_additional_image_rows_accept_rotated_cover_path_for_exact_shortcode(self):
        pending = PendingCarousel(
            listing_id="listing-1",
            external_id="EXPECTED",
            cover_url="https://scontent.cdninstagram.com/old-path/cover.jpg?token=old",
        )
        detail = {
            "shortcode": "EXPECTED",
            "display_url": "https://scontent.cdninstagram.com/new-path/cover.jpg?token=new",
            "edge_sidecar_to_children": {
                "edges": [
                    {
                        "node": {
                            "display_url": "https://scontent.cdninstagram.com/new-path/cover.jpg?token=new"
                        }
                    },
                    {
                        "node": {
                            "display_url": "https://scontent.cdninstagram.com/new-path/two.jpg"
                        }
                    },
                ]
            },
        }

        rows = additional_image_rows(pending, detail)

        self.assertEqual(
            [(row["position"], row["source_url"]) for row in rows],
            [(1, "https://scontent.cdninstagram.com/new-path/two.jpg")],
        )

    def test_run_backfill_is_dry_run_by_default_and_reports_discovered_children(self):
        connection = self.FakeConnection(
            [("listing-1", "CAROUSEL", "https://cdn.example/cover.jpg")]
        )
        psycopg = SimpleNamespace(connect=lambda *_args, **_kwargs: connection)
        details = {
            "CAROUSEL": {
                "shortcode": "CAROUSEL",
                "display_url": "https://cdn.example/cover.jpg",
                "edge_sidecar_to_children": {
                    "edges": [
                        {"node": {"display_url": "https://cdn.example/cover.jpg"}},
                        {"node": {"display_url": "https://cdn.example/two.jpg"}},
                    ]
                },
            }
        }

        with patch.dict("sys.modules", {"psycopg": psycopg}):
            summary = run_backfill(
                "postgresql://example.invalid/recon",
                since=date(2026, 7, 18),
                after_id="",
                max_items=10,
                write_db=False,
                timeout_seconds=30,
                wait_ms=4000,
                delay_ms=750,
                browser="chrome",
                headless=True,
                fetch_details=lambda *_args, **_kwargs: (details, 0),
            )

        self.assertEqual(summary["imagesFound"], 1)
        self.assertEqual(summary["imagesInserted"], 0)
        self.assertEqual(connection.inserts, [])
        self.assertEqual(connection.commits, 0)

    def test_run_backfill_inserts_only_discovered_children_when_enabled(self):
        connection = self.FakeConnection(
            [("listing-1", "CAROUSEL", "https://cdn.example/cover.jpg")]
        )
        psycopg = SimpleNamespace(connect=lambda *_args, **_kwargs: connection)
        details = {
            "CAROUSEL": {
                "shortcode": "CAROUSEL",
                "display_url": "https://cdn.example/cover.jpg",
                "edge_sidecar_to_children": {
                    "edges": [
                        {"node": {"display_url": "https://cdn.example/cover.jpg"}},
                        {"node": {"display_url": "https://cdn.example/two.jpg"}},
                        {"node": {"display_url": "https://cdn.example/three.jpg"}},
                    ]
                },
            }
        }

        with patch.dict("sys.modules", {"psycopg": psycopg}):
            summary = run_backfill(
                "postgresql://example.invalid/recon",
                since=date(2026, 7, 18),
                after_id="",
                max_items=10,
                write_db=True,
                timeout_seconds=30,
                wait_ms=4000,
                delay_ms=750,
                browser="chrome",
                headless=True,
                fetch_details=lambda *_args, **_kwargs: (details, 0),
            )

        self.assertEqual(summary["imagesInserted"], 2)
        self.assertEqual(
            [(row["position"], row["source_url"]) for row in connection.inserts],
            [
                (1, "https://cdn.example/two.jpg"),
                (2, "https://cdn.example/three.jpg"),
            ],
        )
        self.assertEqual(connection.commits, 1)


if __name__ == "__main__":
    unittest.main()
