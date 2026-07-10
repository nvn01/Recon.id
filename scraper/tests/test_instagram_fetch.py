from __future__ import annotations

import unittest
from unittest.mock import patch

from scraper.instagram.embedded import extract_profile_posts
from scraper.instagram.instagram import InstagramFetchError, fetch_profile_resilient


class InstagramFetchTests(unittest.TestCase):
    def test_auto_fetch_uses_embedded_browser_profile_without_direct_api_request(self):
        payload = {"data": {"user": {"edge_owner_to_timeline_media": {"edges": []}}}}

        with (
            patch("scraper.instagram.instagram.fetch_profile_browser", return_value=(200, payload)) as browser,
            patch("scraper.instagram.instagram.fetch_profile") as direct,
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
        browser.assert_called_once()
        direct.assert_not_called()

    def test_auto_fetch_does_not_fall_back_to_direct_api_after_browser_block(self):
        with (
            patch(
                "scraper.instagram.instagram.fetch_profile_browser",
                side_effect=InstagramFetchError("Instagram browser HTTP 429", status=429),
            ),
            patch("scraper.instagram.instagram.fetch_profile") as direct,
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

        direct.assert_not_called()

    def test_embedded_profile_posts_sort_by_numeric_pk_and_normalize_relay_fields(self):
        payload = {
            "props": {
                "polaris_ordered_timeline_connection": {
                    "edges": [
                        {
                            "node": {
                                "code": "OLDER",
                                "pk": "100",
                                "caption": {"text": "Harga Rp1.000.000\nLokasi Jakarta"},
                                "display_uri": "https://cdn.example/older.jpg",
                                "media_type": 1,
                            }
                        },
                        {
                            "node": {
                                "code": "NEWER",
                                "pk": "200",
                                "caption": {"text": "Harga Rp2.000.000\nKondisi mulus"},
                                "display_uri": "https://cdn.example/newer.jpg",
                                "media_type": 1,
                            }
                        },
                    ]
                }
            }
        }

        posts = extract_profile_posts(["{}", __import__("json").dumps(payload)])

        self.assertEqual([post["shortcode"] for post in posts], ["NEWER", "OLDER"])
        self.assertEqual(posts[0]["edge_media_to_caption"]["edges"][0]["node"]["text"], "Harga Rp2.000.000\nKondisi mulus")
        self.assertEqual(posts[0]["display_url"], "https://cdn.example/newer.jpg")

    def test_embedded_profile_posts_deduplicate_same_shortcode(self):
        connection = {
            "polaris_ordered_timeline_connection": {
                "edges": [
                    {"node": {"code": "SAME", "pk": "300", "caption": {"text": "Harga Rp3.000.000"}}}
                ]
            }
        }

        posts = extract_profile_posts([__import__("json").dumps(connection), __import__("json").dumps(connection)])

        self.assertEqual([post["shortcode"] for post in posts], ["SAME"])


if __name__ == "__main__":
    unittest.main()
