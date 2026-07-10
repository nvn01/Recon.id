from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from scraper.facebook.embedded import extract_marketplace_records
from scraper.facebook.facebook_marketplace import card_from_embedded_record, normalize_card


def marketplace_payload(*, sold: bool = False) -> dict:
    return {
        "require": [
            {
                "data": {
                    "marketplace_search": {
                        "feed_units": {
                            "edges": [
                                {
                                    "node": {
                                        "listing": {
                                            "id": "4471077899839221",
                                            "marketplace_listing_title": "ASUS TUF RTX 3070",
                                            "listing_price": {
                                                "formatted_amount": "IDR14,500,000",
                                                "amount": "14500000",
                                            },
                                            "location": {
                                                "reverse_geocode": {
                                                    "city_page": {"display_name": "Jakarta, Indonesia"}
                                                }
                                            },
                                            "primary_listing_photo": {
                                                "image": {"uri": "https://cdn.example/facebook.jpg"}
                                            },
                                            "marketplace_listing_seller": {"name": "Public Seller"},
                                            "if_gk_just_listed_tag_on_search_feed": True,
                                            "is_live": not sold,
                                            "is_sold": sold,
                                            "is_pending": False,
                                            "is_hidden": False,
                                        }
                                    }
                                }
                            ],
                            "page_info": {"has_next_page": True, "end_cursor": "opaque"},
                        }
                    }
                }
            }
        ]
    }


class FacebookDiscoveryTests(unittest.TestCase):
    def test_embedded_marketplace_payload_exposes_complete_discovery_record(self):
        records = extract_marketplace_records(["not-json", json.dumps(marketplace_payload())], limit=10)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["itemId"], "4471077899839221")
        self.assertEqual(records[0]["title"], "ASUS TUF RTX 3070")
        self.assertEqual(records[0]["priceAmount"], 14500000)
        self.assertEqual(records[0]["location"], "Jakarta, Indonesia")
        self.assertEqual(records[0]["image"], "https://cdn.example/facebook.jpg")
        self.assertTrue(records[0]["isLive"])
        self.assertFalse(records[0]["isSold"])

    def test_embedded_marketplace_payload_deduplicates_listing_ids(self):
        payload = json.dumps(marketplace_payload())

        records = extract_marketplace_records([payload, payload], limit=10)

        self.assertEqual([record["itemId"] for record in records], ["4471077899839221"])

    def test_structured_sold_status_and_exact_price_survive_normalization(self):
        [record] = extract_marketplace_records([json.dumps(marketplace_payload(sold=True))], limit=10)
        card = card_from_embedded_record(record)

        listing = normalize_card(card, None, datetime(2026, 7, 10, tzinfo=timezone.utc))

        self.assertEqual(listing["price"], 14500000)
        self.assertEqual(listing["status"], "SOLD")
        self.assertEqual(listing["sellerName"], "Public Seller")
        self.assertEqual(listing["images"][0]["sourceUrl"], "https://cdn.example/facebook.jpg")


if __name__ == "__main__":
    unittest.main()
