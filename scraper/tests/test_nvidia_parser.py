from __future__ import annotations

import unittest

from scraper.reddit.nvidia_parser import build_prompt


class NvidiaParserPromptTests(unittest.TestCase):
    def test_prompt_explains_product_aware_facebook_shorthand_prices(self):
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

        self.assertIn("Facebook Marketplace", prompt)
        self.assertIn("3000 = 3000000", prompt)
        self.assertIn("450 = 450000", prompt)
        self.assertIn("product type", prompt)
        self.assertIn("XPG CORE REACTOR", prompt)
        self.assertIn("Attack Shark R3", prompt)

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


if __name__ == "__main__":
    unittest.main()
