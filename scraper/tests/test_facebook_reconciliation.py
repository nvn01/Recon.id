from __future__ import annotations

import json
import unittest

from scraper.facebook.reconcile import extract_status_evidence, is_expected_detail_url


def detail_payload(*, item_id: str = "123", sold: bool, live: bool) -> str:
    return json.dumps(
        {
            "require": [
                {
                    "data": {
                        "marketplace_listing": {
                            "id": item_id,
                            "is_sold": sold,
                            "is_live": live,
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
    def test_matching_structured_sold_signal_wins(self):
        evidence = extract_status_evidence([detail_payload(sold=True, live=False)], "123", "")

        self.assertEqual(evidence.status, "sold")
        self.assertEqual(evidence.signal, "structured_is_sold")

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
