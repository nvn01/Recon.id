from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scraper.facebook.embedded import extract_marketplace_detail, extract_marketplace_records
from scraper.facebook.facebook_marketplace import (
    DEFAULT_TARGETS_FILE,
    ConnectorBlockedError,
    MarketplaceCard,
    MarketplaceTargetResult,
    build_search_url,
    card_from_embedded_record,
    collect_target_cards,
    load_source_targets,
    normalize_card,
    run_once,
    scrape_detail,
    should_fetch_detail,
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
                                            "marketplace_listing_seller": {
                                                "id": "100012345678901",
                                                "name": "Public Seller",
                                            },
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


def marketplace_detail_payload(*, item_id: str = "4471077899839221") -> dict:
    return {
        "require": [
            {
                "data": {
                    "viewer": {
                        "marketplace_product_details_page": {
                            "marketplace_listing_renderable_target": {
                                "id": item_id,
                                "marketplace_listing_seller": {
                                    "id": "100012345678901",
                                    "user_id": "100012345678901",
                                    "name": "Anonymous Detail Seller",
                                },
                                "redacted_description": {"text": "Public listing description"},
                            }
                        }
                    }
                }
            }
        ]
    }


class FacebookDiscoveryTests(unittest.TestCase):
    def test_zero_relevant_result_clears_prior_cooldown_as_successful_access(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "facebook.json"
            log_path = Path(tmpdir) / "facebook.jsonl"
            state_path.write_text(
                json.dumps({
                    "cooldown_until": "2099-01-01T00:00:00+00:00",
                    "last_error": "old failure",
                }),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                state_file=str(state_path),
                log_file=str(log_path),
                no_state=False,
                ignore_cooldown=True,
                access_mode="browser",
                ai_parse=False,
                max_seen=500,
                details=False,
                headless=True,
                cooldown_seconds=300,
                emit="all",
            )

            with patch("scraper.facebook.facebook_marketplace.run_browser_fetch", return_value=[]):
                code, listings, status = run_once(args, include_status=True)

            saved_state = json.loads(state_path.read_text(encoding="utf-8"))
            [event] = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual((code, listings, status), (0, [], "no_new_data"))
        self.assertIsNone(saved_state["cooldown_until"])
        self.assertIsNone(saved_state["last_error"])
        self.assertIsNotNone(saved_state["last_success_at"])
        self.assertEqual(event["status"], "no_new_data")

    def test_candidate_page_with_zero_relevant_cards_is_valid_no_new_data(self):
        target = source_target_from_record(
            {"id": "category-cell-phone-accessories", "categorySlug": "cell-phone-accessories"},
            1,
        )
        result = MarketplaceTargetResult(
            target=target,
            url=build_search_url(target),
            cards=[],
            candidates_count=24,
            matched_count=0,
            skipped_count=20,
            blocked_count=4,
        )

        self.assertEqual(collect_target_cards([result]), [])

    def test_page_without_any_marketplace_candidates_remains_blocked(self):
        target = source_target_from_record(
            {"id": "category-computers", "categorySlug": "computers"},
            1,
        )
        result = MarketplaceTargetResult(
            target=target,
            url=build_search_url(target),
            cards=[],
            candidates_count=0,
            matched_count=0,
            skipped_count=0,
            blocked_count=0,
        )

        with self.assertRaises(ConnectorBlockedError):
            collect_target_cards([result])

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
            patch("scraper.facebook.facebook_marketplace.extract_embedded_detail", return_value={}),
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

    def test_detail_attempts_are_independent_from_discovery_seen_state(self):
        card = MarketplaceCard(
            item_id="123",
            url="https://www.facebook.com/marketplace/item/123/",
            price="",
            title="GPU",
            location="",
            is_newly_listed=False,
            image_url="",
            image_alt="",
            raw_text="GPU",
        )
        state = {
            "seen_external_ids": ["123"],
            "seen_source_urls": ["https://www.facebook.com/marketplace/item/123/"],
            "detail_attempted_external_ids": [],
            "detail_attempted_source_urls": [],
        }
        args = SimpleNamespace(details=True, no_state=False, detail_scope="new")

        self.assertTrue(should_fetch_detail(card, state, args))

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

    def test_anonymous_detail_payload_exposes_public_seller_identity(self):
        detail = extract_marketplace_detail(
            ["not-json", json.dumps(marketplace_detail_payload())],
            item_id="4471077899839221",
        )

        self.assertEqual(detail["sellerName"], "Anonymous Detail Seller")
        self.assertEqual(detail["sellerId"], "100012345678901")
        self.assertEqual(detail["description"], "Public listing description")

    def test_detail_payload_does_not_borrow_related_seller(self):
        detail = extract_marketplace_detail(
            [json.dumps(marketplace_detail_payload(item_id="999"))],
            item_id="4471077899839221",
        )

        self.assertEqual(detail, {})

    def test_source_metadata_survives_ai_candidate_normalization(self):
        [record] = extract_marketplace_records([json.dumps(marketplace_payload(sold=True))], limit=10)
        card = card_from_embedded_record(record)

        listing = normalize_card(card, None, datetime(2026, 7, 10, tzinfo=timezone.utc))

        self.assertIsNone(listing["price"])
        self.assertEqual(listing["status"], "SOLD")
        self.assertEqual(listing["sellerName"], "Public Seller")
        self.assertEqual(listing["sellerExternalId"], "100012345678901")
        self.assertEqual(listing["images"][0]["sourceUrl"], "https://cdn.example/facebook.jpg")

if __name__ == "__main__":
    unittest.main()
