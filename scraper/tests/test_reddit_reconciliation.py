from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import patch

from scraper.reddit.reconcile import (
    SELECT_ROTATING_CANDIDATE_SQL,
    ReconciliationCandidate,
    build_sold_feed_url,
    extract_feed_external_ids,
    inspect_candidate,
)


SOLD_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>t3_other</id>
    <title>Other sold listing</title>
    <link rel="alternate" href="https://www.reddit.com/r/jualbeliindonesia/comments/other/item/" />
    <updated>2026-08-05T10:00:00+00:00</updated>
  </entry>
  <entry>
    <id>t3_abc123</id>
    <title>Target sold listing</title>
    <link rel="alternate" href="https://www.reddit.com/r/jualbeliindonesia/comments/abc123/item/" />
    <updated>2026-08-05T09:00:00+00:00</updated>
  </entry>
</feed>
"""


class RedditReconciliationTests(unittest.TestCase):
    def test_sold_feed_matches_only_the_selected_external_id(self):
        self.assertEqual(extract_feed_external_ids(SOLD_FEED, 100), {"other", "abc123"})

    @patch("scraper.reddit.reconcile.fetch_text", return_value=SOLD_FEED)
    def test_selected_post_in_sold_feed_is_marked_sold(self, fetch_text_mock):
        evidence = inspect_candidate(self.candidate("abc123"), self.args())

        self.assertEqual(evidence.status, "sold")
        self.assertEqual(evidence.flair, "SOLD OUT")
        self.assertEqual(evidence.signal, "sold_out_feed_match")
        fetch_text_mock.assert_called_once()

    @patch("scraper.reddit.reconcile.fetch_text", return_value=SOLD_FEED)
    def test_absence_from_sold_feed_preserves_existing_status(self, fetch_text_mock):
        evidence = inspect_candidate(self.candidate("still_ready"), self.args())

        self.assertIsNone(evidence.status)
        self.assertEqual(evidence.signal, "not_in_recent_sold_feed")
        self.assertTrue(evidence.checked)
        fetch_text_mock.assert_called_once()

    @patch("scraper.reddit.reconcile.fetch_text", return_value="not xml")
    def test_invalid_sold_feed_does_not_advance_the_listing(self, fetch_text_mock):
        evidence = inspect_candidate(self.candidate("abc123"), self.args())

        self.assertIsNone(evidence.status)
        self.assertEqual(evidence.signal, "invalid_sold_feed")
        self.assertFalse(evidence.checked)
        fetch_text_mock.assert_called_once()

    def test_sold_feed_url_uses_one_reddit_rss_search_request(self):
        url = build_sold_feed_url(100, "jualbeliindonesia")

        self.assertIn("/r/jualbeliindonesia/search.rss?", url)
        self.assertIn("flair%3A%22SOLD+OUT%22", url)
        self.assertIn("limit=100", url)

    def test_query_rotates_one_item_inside_the_latest_window(self):
        self.assertIn("WITH latest_ready", SELECT_ROTATING_CANDIDATE_SQL)
        self.assertIn("ORDER BY COALESCE(posted_at, first_fetched_at) DESC", SELECT_ROTATING_CANDIDATE_SQL)
        self.assertIn("ORDER BY last_fetched_at ASC", SELECT_ROTATING_CANDIDATE_SQL)
        self.assertTrue(SELECT_ROTATING_CANDIDATE_SQL.strip().endswith("LIMIT 1"))

    @staticmethod
    def candidate(external_id: str) -> ReconciliationCandidate:
        return ReconciliationCandidate(
            external_id=external_id,
            source_url=f"https://www.reddit.com/r/jualbeliindonesia/comments/{external_id}/item/",
            current_status="available",
        )

    @staticmethod
    def args() -> Namespace:
        return Namespace(
            sold_feed_limit=100,
            subreddit="jualbeliindonesia",
            user_agent="test-agent",
            retries=1,
            retry_wait=1,
            retry_jitter_seconds=0.0,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
