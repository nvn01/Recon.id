from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper.facebook.embedded import extract_marketplace_records
from scraper.facebook.facebook_marketplace import card_from_embedded_record, normalize_card
from scraper.instagram.embedded import extract_profile_posts
from scraper.instagram.instagram import normalize_post as normalize_instagram_post
from scraper.reddit.reddit import normalize_post as normalize_reddit_post
from scraper.reddit.reddit import parse_feed


FIXTURES = Path(__file__).with_name("fixtures")
FETCHED_AT = datetime(2026, 7, 12, tzinfo=timezone.utc)


class ParserFixtureRegressionTests(unittest.TestCase):
    def test_reddit_fixture_preserves_ai_candidate_source_fields(self):
        xml = (FIXTURES / "reddit_feed.xml").read_text(encoding="utf-8")
        [post] = parse_feed(xml, limit=10)

        listing = normalize_reddit_post(post, FETCHED_AT)

        self.assertEqual(listing["externalId"], "reconfixture")
        self.assertIsNone(listing["price"])
        self.assertIsNone(listing["brand"])
        self.assertIsNone(listing["category"])
        self.assertEqual(listing["locationTexts"], [])
        self.assertIsNone(listing["conditionText"])
        self.assertEqual(listing["status"], "UNKNOWN")
        self.assertEqual(listing["images"][0]["sourceUrl"], "https://i.redd.it/reconfixture.jpg")

    def test_instagram_fixture_preserves_raw_ai_candidate(self):
        payload = (FIXTURES / "instagram_profile.json").read_text(encoding="utf-8")
        [post] = extract_profile_posts([payload])

        listing = normalize_instagram_post("chemicy.consignment", post, FETCHED_AT)

        self.assertEqual(listing["externalId"], "IGFIXTURE1")
        self.assertEqual(listing["title"], "IGFIXTURE1")
        self.assertIsNone(listing["price"])
        self.assertIsNone(listing["category"])
        self.assertIsNone(listing["brand"])
        self.assertEqual(listing["locationTexts"], [])
        self.assertIsNone(listing["conditionText"])
        self.assertEqual(listing["status"], "UNKNOWN")

    def test_facebook_fixture_preserves_raw_ai_candidate(self):
        payload = json.loads((FIXTURES / "facebook_marketplace.json").read_text(encoding="utf-8"))
        [record] = extract_marketplace_records([json.dumps(payload)], limit=10)

        listing = normalize_card(card_from_embedded_record(record), None, FETCHED_AT)

        self.assertEqual(listing["externalId"], "4471077899839221")
        self.assertIsNone(listing["price"])
        self.assertIsNone(listing["category"])
        self.assertIsNone(listing["brand"])
        self.assertEqual(listing["locationTexts"], [])
        self.assertEqual(listing["status"], "SOLD")
        self.assertEqual(listing["sellerName"], "Fixture Seller")

    def test_reddit_current_flair_sets_status_without_ai(self):
        base_post = {
            "title": "RTX 3070",
            "description": "Ready",
            "url": "https://www.reddit.com/r/jualbeliindonesia/comments/abc123/item/",
            "atom_id": "t3_abc123",
            "author": "seller",
            "images": [],
        }

        available = normalize_reddit_post({**base_post, "flair": "WTS: Electronics"}, FETCHED_AT)
        sold = normalize_reddit_post({**base_post, "flair": "SOLD OUT"}, FETCHED_AT)

        self.assertEqual(available["status"], "AVAILABLE")
        self.assertEqual(sold["status"], "SOLD")


if __name__ == "__main__":
    unittest.main()
