from __future__ import annotations

import unittest

from scraper.instagram.backfill_carousels import (
    PendingCarousel,
    additional_image_rows,
)


class InstagramCarouselBackfillTests(unittest.TestCase):
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
                    {"node": {"display_url": "https://cdn.example/cover.jpg?token=new"}},
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
                    {"node": {"display_url": "https://scontent.cdninstagram.com/new-path/two.jpg"}},
                ]
            },
        }

        rows = additional_image_rows(pending, detail)

        self.assertEqual(
            [(row["position"], row["source_url"]) for row in rows],
            [(1, "https://scontent.cdninstagram.com/new-path/two.jpg")],
        )


if __name__ == "__main__":
    unittest.main()
