from __future__ import annotations

import unittest

from scraper.reddit.backfill_images import build_post_rss_url, desired_image_urls


class RedditImageBackfillTests(unittest.TestCase):
    def test_build_post_rss_url_keeps_only_a_canonical_reddit_post(self):
        self.assertEqual(
            build_post_rss_url(
                "https://www.reddit.com/r/jualbeliindonesia/comments/abc123/example/?utm_source=test"
            ),
            "https://www.reddit.com/r/jualbeliindonesia/comments/abc123/example/.rss",
        )
        self.assertEqual(
            build_post_rss_url("https://evil.example/comments/abc123/example/"),
            "",
        )

    def test_desired_urls_upgrade_existing_previews_and_preserve_gallery_order(self):
        self.assertEqual(
            desired_image_urls(
                [
                    "https://preview.redd.it/first.jpg?width=140&auto=webp",
                    "https://preview.redd.it/first.jpg?width=1280&auto=webp",
                    "https://preview.redd.it/second.jpg?width=1280&auto=webp",
                ],
                [],
            ),
            [
                "https://i.redd.it/first.jpg",
                "https://i.redd.it/second.jpg",
            ],
        )

    def test_missing_existing_images_can_be_recovered_from_post_rss(self):
        self.assertEqual(
            desired_image_urls(
                [],
                [
                    "https://preview.redd.it/recovered.png?width=1080&auto=webp",
                ],
            ),
            ["https://i.redd.it/recovered.png"],
        )


if __name__ == "__main__":
    unittest.main()
