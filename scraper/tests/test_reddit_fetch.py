import io
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import call, patch

from scraper.reddit import reddit


class RedditFetchTests(unittest.TestCase):
    def test_rss_images_use_original_reddit_assets_and_remove_thumbnail_duplicates(self):
        content = """
        <a href="https://preview.redd.it/first.jpeg?width=140&amp;height=140&amp;auto=webp">thumb</a>
        <img src="https://preview.redd.it/first.jpeg?width=1280&amp;format=pjpg&amp;auto=webp">
        <img src="https://preview.redd.it/second.jpg?width=1280&amp;format=pjpg&amp;auto=webp">
        """

        self.assertEqual(
            reddit.extract_image_urls(content),
            [
                "https://i.redd.it/first.jpeg",
                "https://i.redd.it/second.jpg",
            ],
        )

    def test_gallery_metadata_returns_one_original_image_per_item_in_gallery_order(self):
        payload = [
            {
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": "gallery",
                                "gallery_data": {
                                    "items": [
                                        {"media_id": "second"},
                                        {"media_id": "first"},
                                    ]
                                },
                                "media_metadata": {
                                    "first": {
                                        "status": "valid",
                                        "m": "image/jpeg",
                                        "s": {
                                            "u": "https://preview.redd.it/first.jpg?auto=webp"
                                        },
                                        "p": [
                                            {
                                                "u": "https://preview.redd.it/first.jpg?width=1080&amp;auto=webp",
                                                "x": 1080,
                                                "y": 1440,
                                            }
                                        ],
                                    },
                                    "second": {
                                        "status": "valid",
                                        "m": "image/jpeg",
                                        "s": {
                                            "u": "https://preview.redd.it/second.jpg?auto=webp"
                                        },
                                        "p": [
                                            {
                                                "u": "https://preview.redd.it/second.jpg?width=1080&amp;auto=webp",
                                                "x": 1080,
                                                "y": 1440,
                                            }
                                        ],
                                    },
                                },
                                "preview": {
                                    "images": [
                                        {
                                            "source": {
                                                "url": "https://preview.redd.it/second.jpg?width=640&amp;auto=webp"
                                            }
                                        }
                                    ]
                                },
                            }
                        }
                    ]
                }
            }
        ]

        self.assertEqual(
            reddit.extract_images_from_reddit_json(payload),
            [
                "https://i.redd.it/second.jpg",
                "https://i.redd.it/first.jpg",
            ],
        )

    def test_fetch_flair_feeds_keeps_all_sources_and_waits_between_them(self):
        flairs = [
            "WTS: Computers & Peripherals",
            "WTS: Electronics",
            "WTS: Video Games & Consoles",
            "WTS: Smartphones & Tablets",
        ]
        args = SimpleNamespace(
            limit=15,
            subreddit="jualbeliindonesia",
            user_agent=reddit.DEFAULT_USER_AGENT,
            retries=2,
            retry_wait=20,
            retry_jitter_seconds=1.0,
            timeout=30,
            feed_delay_seconds=3.0,
        )

        with (
            patch("scraper.reddit.reddit.fetch_text", return_value="<feed />") as fetch_text,
            patch(
                "scraper.reddit.reddit.parse_feed",
                side_effect=lambda _xml, _limit: [
                    {
                        "url": "https://www.reddit.com/r/jualbeliindonesia/comments/shared/example/",
                        "atom_id": "t3_shared",
                    }
                ],
            ) as parse_feed,
            patch("scraper.reddit.reddit.time.sleep") as sleep,
        ):
            posts = reddit.fetch_flair_feeds(args, flairs)

        self.assertEqual(len(posts), 1)
        self.assertEqual(fetch_text.call_count, 4)
        self.assertEqual(parse_feed.call_count, 4)
        self.assertEqual(
            [
                urllib.parse.parse_qs(urllib.parse.urlparse(item.args[0]).query)["q"][0]
                for item in fetch_text.call_args_list
            ],
            [f'flair:"{flair}"' for flair in flairs],
        )
        self.assertEqual(sleep.call_args_list, [call(3.0), call(3.0), call(3.0)])

    def test_canonical_url_rejects_non_reddit_hosts(self):
        self.assertEqual(reddit.canonical_url("https://evil.example/comments/abc/"), "")
        self.assertEqual(
            reddit.build_post_json_urls("https://evil.example/comments/abc/", None),
            [],
        )

    def test_fetch_text_retries_transient_url_error(self):
        responses = [
            urllib.error.URLError(TimeoutError("The handshake operation timed out")),
            io.BytesIO(b"<feed></feed>"),
        ]

        def fake_urlopen(_request, timeout):
            self.assertEqual(timeout, 30)
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with (
            patch("scraper.reddit.reddit.urllib.request.urlopen", side_effect=fake_urlopen),
            patch("scraper.reddit.reddit.time.sleep") as sleep,
            patch("scraper.reddit.reddit.random.uniform", return_value=0.0),
        ):
            payload = reddit.fetch_text(
                "https://www.reddit.com/r/jualbeliindonesia/search.rss",
                reddit.DEFAULT_USER_AGENT,
                retries=2,
                retry_wait=20,
                retry_jitter=1.0,
                timeout=30,
            )

        self.assertEqual(payload, "<feed></feed>")
        sleep.assert_called_once_with(20.0)

    def test_fetch_text_retries_tls_verification_error_without_disabling_verification(self):
        responses = [
            urllib.error.URLError(
                "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate"
            ),
            io.BytesIO(b"<feed></feed>"),
        ]

        def fake_urlopen(_request, timeout):
            self.assertEqual(timeout, 30)
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with (
            patch("scraper.reddit.reddit.urllib.request.urlopen", side_effect=fake_urlopen) as urlopen,
            patch("scraper.reddit.reddit.time.sleep") as sleep,
            patch("scraper.reddit.reddit.random.uniform", return_value=0.0),
        ):
            payload = reddit.fetch_text(
                "https://www.reddit.com/r/jualbeliindonesia/search.rss",
                reddit.DEFAULT_USER_AGENT,
                retries=2,
                retry_wait=20,
                retry_jitter=1.0,
                timeout=30,
            )

        self.assertEqual(payload, "<feed></feed>")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(20.0)

    def test_fetch_text_never_accepts_a_persistently_invalid_certificate(self):
        error = urllib.error.URLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate"
        )
        with (
            patch("scraper.reddit.reddit.urllib.request.urlopen", side_effect=error) as urlopen,
            patch("scraper.reddit.reddit.time.sleep") as sleep,
            patch("scraper.reddit.reddit.random.uniform", return_value=0.0),
        ):
            with self.assertRaises(urllib.error.URLError):
                reddit.fetch_text(
                    "https://www.reddit.com/r/jualbeliindonesia/search.rss",
                    reddit.DEFAULT_USER_AGENT,
                    retries=2,
                    retry_wait=20,
                    retry_jitter=1.0,
                    timeout=30,
                )

        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_args_list, [unittest.mock.call(20.0), unittest.mock.call(20.0)])

    def test_fetch_text_gets_one_extra_verified_attempt_after_timeout_then_tls_failure(self):
        responses = [
            urllib.error.URLError(TimeoutError("The handshake operation timed out")),
            urllib.error.URLError(
                "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate"
            ),
            io.BytesIO(b"<feed></feed>"),
        ]

        def fake_urlopen(_request, timeout):
            self.assertEqual(timeout, 30)
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with (
            patch("scraper.reddit.reddit.urllib.request.urlopen", side_effect=fake_urlopen) as urlopen,
            patch("scraper.reddit.reddit.time.sleep") as sleep,
            patch("scraper.reddit.reddit.random.uniform", return_value=0.0),
        ):
            payload = reddit.fetch_text(
                "https://www.reddit.com/r/jualbeliindonesia/search.rss",
                reddit.DEFAULT_USER_AGENT,
                retries=2,
                retry_wait=20,
                retry_jitter=1.0,
                timeout=30,
            )

        self.assertEqual(payload, "<feed></feed>")
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_args_list, [unittest.mock.call(20.0), unittest.mock.call(20.0)])

    def test_tls_verification_error_is_classified(self):
        self.assertTrue(
            reddit.is_tls_verification_error(
                urllib.error.URLError(
                    "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate"
                )
            )
        )
        self.assertFalse(reddit.is_tls_verification_error(urllib.error.URLError("The handshake operation timed out")))


if __name__ == "__main__":
    unittest.main()
