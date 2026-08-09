from __future__ import annotations

import json
import unittest

from scraper.facebook.reconcile import (
    UPDATE_RECONCILIATION_RESULT_SQL,
    SELECT_RECONCILIATION_CANDIDATES_SQL,
    extract_status_evidence,
    is_expected_detail_url,
)


def detail_payload(
    *,
    item_id: str = "123",
    sold: bool,
    live: bool,
    seller_name: str = "Authenticated Seller",
) -> str:
    return json.dumps(
        {
            "require": [
                {
                    "data": {
                        "marketplace_listing": {
                            "id": item_id,
                            "is_sold": sold,
                            "is_live": live,
                            "marketplace_listing_seller": {
                                "id": "100012345678901",
                                "name": seller_name,
                            },
                        },
                        "related_listing": {
                            "id": "999",
                            "is_sold": True,
                            "is_live": False,
                        },
                    }
                }
            ]
        }
    )


class FacebookReconciliationTests(unittest.TestCase):
    def test_query_rotates_one_item_inside_the_latest_window(self):
        self.assertIn("WITH latest_ready", SELECT_RECONCILIATION_CANDIDATES_SQL)
        self.assertIn("ORDER BY COALESCE(posted_at, first_fetched_at) DESC", SELECT_RECONCILIATION_CANDIDATES_SQL)
        self.assertIn("ORDER BY last_fetched_at ASC", SELECT_RECONCILIATION_CANDIDATES_SQL)
        self.assertTrue(SELECT_RECONCILIATION_CANDIDATES_SQL.strip().endswith("LIMIT 1"))

    def test_matching_structured_sold_signal_wins(self):
        evidence = extract_status_evidence([detail_payload(sold=True, live=False)], "123", "")

        self.assertEqual(evidence.status, "sold")
        self.assertEqual(evidence.signal, "structured_is_sold")
        self.assertEqual(evidence.seller_name, "Authenticated Seller")

    def test_reconciliation_only_backfills_a_missing_seller_name(self):
        self.assertIn("seller_name = COALESCE(seller_name, %(seller_name)s)", UPDATE_RECONCILIATION_RESULT_SQL)

    def test_related_sold_listing_does_not_mark_target_sold(self):
        evidence = extract_status_evidence([detail_payload(item_id="456", sold=False, live=True)], "123", "Item")

        self.assertIsNone(evidence.status)

    def test_matching_structured_live_signal_marks_unknown_available(self):
        evidence = extract_status_evidence([detail_payload(sold=False, live=True)], "123", "")

        self.assertEqual(evidence.status, "available")
        self.assertEqual(evidence.signal, "structured_is_live")

    def test_exact_visible_sold_marker_is_accepted(self):
        evidence = extract_status_evidence([], "123", "Laptop gaming\nTerjual\nJakarta")

        self.assertEqual(evidence.status, "sold")

    def test_exact_visible_habis_marker_is_accepted(self):
        evidence = extract_status_evidence([], "123", "Samsung SSD 990 Pro\nRp1.500.000 · Habis\nBekasi")

        self.assertEqual(evidence.status, "sold")

    def test_unavailable_without_sold_evidence_keeps_existing_status(self):
        evidence = extract_status_evidence([], "123", "This listing is no longer available")

        self.assertIsNone(evidence.status)
        self.assertEqual(evidence.signal, "unavailable_without_sold_evidence")

    def test_sold_word_inside_description_is_not_enough(self):
        evidence = extract_status_evidence([], "123", "Never sold or repaired. Ready stock.")

        self.assertIsNone(evidence.status)

    def test_sold_marker_from_related_cards_is_ignored(self):
        evidence = extract_status_evidence([], "123", "Laptop ready\nRelated searches\nSold")

        self.assertIsNone(evidence.status)

    def test_web_facebook_redirect_still_matches_expected_detail(self):
        self.assertTrue(
            is_expected_detail_url(
                "https://web.facebook.com/marketplace/item/123/?_rdc=1&_rdr#",
                "123",
            )
        )
        self.assertFalse(is_expected_detail_url("https://web.facebook.com/login/", "123"))


if __name__ == "__main__":
    unittest.main()
