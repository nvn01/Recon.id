from __future__ import annotations

import unittest

from scraper.reddit.reconcile import SELECT_RECENT_READY_SQL, classify_flair, extract_current_flair, old_reddit_url


class RedditReconciliationTests(unittest.TestCase):
    def test_current_shreddit_post_sold_out_flair_is_matched_by_id(self):
        page = """
        <shreddit-post id="t3_other" post-flair="WTS: Electronics"></shreddit-post>
        <shreddit-post id="t3_abc123" post-flair="SOLD OUT"></shreddit-post>
        """

        evidence = classify_flair(extract_current_flair(page, "abc123"))

        self.assertEqual(evidence.status, "sold")
        self.assertEqual(evidence.signal, "sold_out_flair")

    def test_current_wts_flair_confirms_available(self):
        page = '<shreddit-post id="t3_abc123" post-flair="WTS: Electronics"></shreddit-post>'

        evidence = classify_flair(extract_current_flair(page, "abc123"))

        self.assertEqual(evidence.status, "available")

    def test_old_reddit_flair_is_read_near_target_post(self):
        page = """
        <div id="thing_t3_abc123" class="thing linkflair">
          <span class="linkflairlabel">SOLD OUT</span>
        </div>
        """

        self.assertEqual(extract_current_flair(page, "abc123"), "SOLD OUT")

    def test_related_post_flair_cannot_close_target(self):
        page = '<shreddit-post id="t3_other" post-flair="SOLD OUT"></shreddit-post>'

        self.assertIsNone(extract_current_flair(page, "abc123"))

    def test_query_uses_three_day_window_instead_of_latest_count(self):
        self.assertIn("COALESCE(posted_at, first_fetched_at)", SELECT_RECENT_READY_SQL)
        self.assertIn("INTERVAL '1 day'", SELECT_RECENT_READY_SQL)
        self.assertNotIn("LIMIT", SELECT_RECENT_READY_SQL)

    def test_old_reddit_fallback_preserves_only_the_canonical_post_path(self):
        self.assertEqual(
            old_reddit_url("https://www.reddit.com/r/jualbeliindonesia/comments/abc123/item/?utm_source=test"),
            "https://old.reddit.com/r/jualbeliindonesia/comments/abc123/item/",
        )


if __name__ == "__main__":
    unittest.main()
