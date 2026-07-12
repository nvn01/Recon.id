from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from scraper.facebook.embedded import extract_marketplace_records
from scraper.facebook.facebook_marketplace import (
    DEFAULT_TARGETS_FILE,
    MarketplaceCard,
    build_search_url,
    card_from_embedded_record,
    extract_brand,
    load_source_targets,
    normalize_card,
    scrape_detail,
    source_target_from_record,
    uses_persistent_profile,
)


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
    def test_committed_targets_are_the_three_requested_jakarta_categories(self):
        targets = load_source_targets(DEFAULT_TARGETS_FILE)

        self.assertEqual(
            [target.category_slug for target in targets],
            ["cell-phone-accessories", "video-games-consoles", "computers"],
        )
        self.assertTrue(all(target.location == "jakarta" for target in targets))
        self.assertTrue(all(target.radius == 500 for target in targets))
        self.assertTrue(all(target.sort_by == "creation_time_descend" for target in targets))

    def test_category_target_builds_localized_newest_first_url_without_search_query(self):
        target = source_target_from_record(
            {
                "id": "category-computers",
                "categorySlug": "computers",
                "location": "jakarta",
                "sortBy": "creation_time_descend",
                "radius": 500,
            },
            1,
        )

        self.assertEqual(
            build_search_url(target),
            "https://www.facebook.com/marketplace/jakarta/computers/"
            "?sortBy=creation_time_descend&radius=500",
        )

    def test_brand_extraction_ignores_negated_competitor_mentions(self):
        titles = (
            "PC Komputer Gaming Set AMD RX 6800 XT High End not RTX not intel 4070 5070",
            "PC AMD Ryzen bukan Intel",
            "PC AMD Ryzen tanpa Intel",
            "PC AMD Ryzen non-Intel",
        )

        for title in titles:
            with self.subTest(title=title):
                self.assertEqual(extract_brand(title), "AMD")

    def test_brand_extraction_keeps_positive_intel_mentions(self):
        self.assertEqual(extract_brand("PC gaming Intel Core i7 RTX 4070"), "Intel")

    def test_detail_fetch_uses_canonical_facebook_item_url(self):
        card = MarketplaceCard(
            item_id="123",
            url="https://evil.example/marketplace/item/123",
            price="",
            title="GPU",
            location="",
            is_newly_listed=False,
            image_url="",
            image_alt="",
            raw_text="GPU",
        )
        args = SimpleNamespace(wait_ms=0, timeout=1)

        with (
            patch("scraper.facebook.facebook_marketplace.open_marketplace") as open_marketplace,
            patch("scraper.facebook.facebook_marketplace.extract_page_text", return_value=""),
        ):
            scrape_detail(object(), card, args)

        self.assertEqual(
            open_marketplace.call_args.args[1],
            "https://www.facebook.com/marketplace/item/123/",
        )

    def test_logged_out_discovery_does_not_use_persistent_profile(self):
        self.assertFalse(uses_persistent_profile(SimpleNamespace(login=False, session_mode="ephemeral")))
        self.assertTrue(uses_persistent_profile(SimpleNamespace(login=True, session_mode="ephemeral")))
        self.assertTrue(uses_persistent_profile(SimpleNamespace(login=False, session_mode="persistent")))

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

    def test_structured_facebook_shorthand_prices_expand_using_product_context(self):
        cases = (
            ("PS4 Resmi", 3_000, 3_000_000, "Game Console"),
            ("PS4 slim seri 20 500gb", 2_650, 2_650_000, "Game Console"),
            ("PlayStation portable", 390, 390_000, "Game Console"),
            ("PlayStation", 450, 450_000, "Game Console"),
            ("PS5 slim console disc edition", 11, 11_000_000, "Game Console"),
            ("Laptop axioo mybook 14 lite", 400, 400_000, "Laptop"),
        )

        for title, raw_price, expected_price, expected_category in cases:
            with self.subTest(title=title, raw_price=raw_price):
                card = MarketplaceCard(
                    item_id="123",
                    url="https://www.facebook.com/marketplace/item/123/",
                    price=f"IDR{raw_price:,}",
                    title=title,
                    location="Jakarta",
                    is_newly_listed=True,
                    image_url="",
                    image_alt="",
                    raw_text=title,
                    price_amount=raw_price,
                )

                listing = normalize_card(card, None, datetime(2026, 7, 12, tzinfo=timezone.utc))

                self.assertEqual(listing["price"], expected_price)
                self.assertEqual(listing["category"], expected_category)


if __name__ == "__main__":
    unittest.main()
