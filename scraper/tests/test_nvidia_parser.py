from __future__ import annotations

import unittest

from scraper.reddit.nvidia_parser import SYSTEM_PROMPT, build_prompt, merge_ai_results


class NvidiaParserPromptTests(unittest.TestCase):
    def test_system_prompt_explains_product_aware_facebook_enrichment(self):
        prompt = build_prompt(
            [
                {
                    "platform": "facebook",
                    "externalId": "fb-1",
                    "title": "PS4 Resmi",
                    "description": "IDR3,000",
                    "price": 3_000,
                }
            ]
        )

        self.assertIn("Facebook Marketplace rules", SYSTEM_PROMPT)
        self.assertIn("PS4 3000 -> 3000000", SYSTEM_PROMPT)
        self.assertIn("controller 200 can mean 200000", SYSTEM_PROMPT)
        self.assertIn("Steam Deck 65 can mean 6500000", SYSTEM_PROMPT)
        self.assertIn("123456", SYSTEM_PROMPT)
        self.assertIn("Bekas - normal", SYSTEM_PROMPT)
        self.assertIn("XPG CORE REACTOR", SYSTEM_PROMPT)
        self.assertIn("Attack Shark R3", SYSTEM_PROMPT)
        self.assertIn("Review and enrich every listing", prompt)

    def test_prompt_includes_platform_for_source_specific_reasoning(self):
        prompt = build_prompt(
            [
                {
                    "platform": "instagram",
                    "externalId": "ig-1",
                    "title": "CORSAIR K100 RGB",
                    "description": "Keyboard gaming Corsair",
                }
            ]
        )

        self.assertIn('"platform": "instagram"', prompt)

    def test_ai_result_owns_all_semantic_fields(self):
        listings = [{"externalId": "fb-1", "platform": "FACEBOOK", "title": "raw", "price": 123_456}]
        analyses = [
            {
                "externalId": "fb-1",
                "isListing": True,
                "title": "PS4 Slim 500GB",
                "price": None,
                "locationTexts": ["Jakarta"],
                "conditionText": "Bekas - baik",
                "status": "AVAILABLE",
                "category": "Game Console",
                "brand": "Sony",
            }
        ]

        [parsed] = merge_ai_results(listings, analyses)

        self.assertEqual(parsed["title"], "PS4 Slim 500GB")
        self.assertIsNone(parsed["price"])
        self.assertEqual(parsed["conditionText"], "Bekas - baik")
        self.assertEqual(parsed["category"], "Game Console")

    def test_ai_can_reject_non_listing_content(self):
        listings = [{"externalId": "ig-1", "platform": "INSTAGRAM", "title": "raw"}]
        analyses = [{"externalId": "ig-1", "isListing": False}]

        self.assertEqual(merge_ai_results(listings, analyses), [])


if __name__ == "__main__":
    unittest.main()
