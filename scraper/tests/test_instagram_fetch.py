from __future__ import annotations

import unittest
from unittest.mock import patch

from scraper.instagram.instagram import InstagramFetchError, fetch_profile_resilient


class InstagramFetchTests(unittest.TestCase):
    def test_auto_fetch_falls_back_to_browser_on_direct_rate_limit(self):
        payload = {"data": {"user": {"edge_owner_to_timeline_media": {"edges": []}}}}

        with (
            patch(
                "scraper.instagram.instagram.fetch_profile",
                side_effect=InstagramFetchError("Instagram HTTP 429", status=429),
            ) as direct,
            patch("scraper.instagram.instagram.fetch_profile_browser", return_value=(200, payload)) as browser,
        ):
            status, result = fetch_profile_resilient(
                "blocked.shop",
                timeout=30,
                user_agent="test-agent",
                fetch_mode="auto",
                browser="chromium",
                headless=True,
                browser_wait_ms=2500,
            )

        self.assertEqual(status, 200)
        self.assertEqual(result, payload)
        direct.assert_called_once()
        browser.assert_called_once()

    def test_auto_fetch_does_not_mask_non_block_errors(self):
        with (
            patch(
                "scraper.instagram.instagram.fetch_profile",
                side_effect=InstagramFetchError("Instagram HTTP 404", status=404),
            ),
            patch("scraper.instagram.instagram.fetch_profile_browser") as browser,
        ):
            with self.assertRaises(InstagramFetchError):
                fetch_profile_resilient(
                    "missing.shop",
                    timeout=30,
                    user_agent="test-agent",
                    fetch_mode="auto",
                    browser="chromium",
                    headless=True,
                    browser_wait_ms=2500,
                )

        browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
