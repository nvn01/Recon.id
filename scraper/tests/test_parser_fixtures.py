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
    def test_reddit_fixture_preserves_database_shaped_fields(self):
        xml = (FIXTURES / "reddit_feed.xml").read_text(encoding="utf-8")
        [post] = parse_feed(xml, limit=10)

        listing = normalize_reddit_post(post, FETCHED_AT)

        self.assertEqual(listing["externalId"], "reconfixture")
        self.assertEqual(listing["price"], 12_500_000)
        self.assertEqual(listing["brand"], "ASUS")
        self.assertEqual(listing["category"], "Laptop")
        self.assertEqual(listing["locationTexts"], ["Jakarta"])
        self.assertEqual(listing["conditionText"], "bekas mulus")
        self.assertEqual(listing["status"], "AVAILABLE")
        self.assertEqual(listing["images"][0]["sourceUrl"], "https://preview.redd.it/reconfixture.jpg")

    def test_instagram_fixture_preserves_sold_marker_and_enrichment(self):
        payload = (FIXTURES / "instagram_profile.json").read_text(encoding="utf-8")
        [post] = extract_profile_posts([payload])

        listing = normalize_instagram_post("chemicy.consignment", post, FETCHED_AT)

        self.assertEqual(listing["externalId"], "IGFIXTURE1")
        self.assertEqual(listing["title"], "CORSAIR K100 RGB")
        self.assertEqual(listing["price"], 2_500_000)
        self.assertEqual(listing["category"], "Keyboard")
        self.assertEqual(listing["brand"], "Corsair")
        self.assertEqual(listing["locationTexts"], ["Tangerang"])
        self.assertEqual(listing["conditionText"], "Kondisi mulus")
        self.assertEqual(listing["status"], "SOLD")

    def test_facebook_fixture_preserves_structured_sold_state(self):
        payload = json.loads((FIXTURES / "facebook_marketplace.json").read_text(encoding="utf-8"))
        [record] = extract_marketplace_records([json.dumps(payload)], limit=10)

        listing = normalize_card(card_from_embedded_record(record), None, FETCHED_AT)

        self.assertEqual(listing["externalId"], "4471077899839221")
        self.assertEqual(listing["price"], 14_500_000)
        self.assertEqual(listing["category"], "Laptop")
        self.assertEqual(listing["brand"], "ASUS")
        self.assertEqual(listing["locationTexts"], ["Jakarta, Indonesia"])
        self.assertEqual(listing["status"], "SOLD")
        self.assertEqual(listing["sellerName"], "Fixture Seller")


if __name__ == "__main__":
    unittest.main()
