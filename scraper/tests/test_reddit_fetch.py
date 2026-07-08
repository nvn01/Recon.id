import io
import unittest
import urllib.error
from unittest.mock import patch

from scraper.reddit import reddit


class RedditFetchTests(unittest.TestCase):
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

    def test_fetch_text_does_not_retry_non_transient_url_error(self):
        with (
            patch(
                "scraper.reddit.reddit.urllib.request.urlopen",
                side_effect=urllib.error.URLError("certificate verify failed"),
            ) as urlopen,
            patch("scraper.reddit.reddit.time.sleep") as sleep,
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

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

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
