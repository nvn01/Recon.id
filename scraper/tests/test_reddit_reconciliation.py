from __future__ import annotations

import unittest

from scraper.reddit.reconcile import SELECT_ROTATING_CANDIDATE_SQL, classify_flair, extract_current_flair, old_reddit_url


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

    def test_query_rotates_one_item_inside_the_latest_window(self):
        self.assertIn("WITH latest_ready", SELECT_ROTATING_CANDIDATE_SQL)
        self.assertIn("ORDER BY COALESCE(posted_at, first_fetched_at) DESC", SELECT_ROTATING_CANDIDATE_SQL)
        self.assertIn("ORDER BY last_fetched_at ASC", SELECT_ROTATING_CANDIDATE_SQL)
        self.assertTrue(SELECT_ROTATING_CANDIDATE_SQL.strip().endswith("LIMIT 1"))

    def test_old_reddit_fallback_preserves_only_the_canonical_post_path(self):
        self.assertEqual(
            old_reddit_url("https://www.reddit.com/r/jualbeliindonesia/comments/abc123/item/?utm_source=test"),
            "https://old.reddit.com/r/jualbeliindonesia/comments/abc123/item/",
        )


if __name__ == "__main__":
    unittest.main()
