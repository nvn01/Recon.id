from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper.candidate_pool import CandidatePool
from scraper.facebook_groups.embedded import extract_group_posts
from scraper.facebook_groups.facebook_groups import (
    DEFAULT_TARGETS_FILE,
    GroupTarget,
    load_targets,
    normalize_posts,
)


FIXTURE = Path(__file__).parent / "fixtures" / "facebook_group_feed.json"


class FacebookGroupsDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_extracts_three_newest_outer_posts_and_merges_relay_variants(self):
        posts = extract_group_posts(
            [json.dumps(self.fixture["initial"])],
            [f"for (;;);{json.dumps(self.fixture['pagination'])}"],
            group_id="group-1",
            limit=3,
        )

        self.assertEqual([post["postId"] for post in posts], ["post-102", "post-101", "post-103"])
        sale = posts[1]
        self.assertEqual(sale["sellerName"], "Public Seller")
        self.assertEqual(sale["commerce"]["formattedPrice"], "Rp2.700.000")
        self.assertEqual(len(sale["images"]), 1)
        self.assertNotIn("tracking", sale["permalink"])

    def test_flattens_attached_story_evidence_but_keeps_outer_identity(self):
        posts = extract_group_posts(
            [],
            [json.dumps(self.fixture["pagination"])],
            group_id="group-1",
            limit=3,
        )
        shared = next(post for post in posts if post["postId"] == "post-103")

        self.assertEqual(shared["postId"], "post-103")
        self.assertEqual(shared["sellerName"], "Shared Seller")
        self.assertEqual(shared["message"], "Dijual PC gaming Ryzen 5 lengkap")
        self.assertTrue(shared["usedAttachedStory"])
        self.assertEqual(shared["images"][0]["url"], "https://scontent-test.fbcdn.net/pc.jpg")

    def test_applies_image_gate_after_the_three_post_window(self):
        posts = extract_group_posts(
            [json.dumps(self.fixture["initial"])],
            [json.dumps(self.fixture["pagination"])],
            group_id="group-1",
            limit=3,
        )
        target = GroupTarget(
            id="test-group",
            group_id="group-1",
            name="Test Group",
            url="https://www.facebook.com/groups/test-group/?sorting_setting=CHRONOLOGICAL",
            sorting_setting="CHRONOLOGICAL",
        )
        listings = normalize_posts(
            posts,
            target=target,
            fetched_at=datetime(2026, 7, 29, tzinfo=timezone.utc).isoformat(),
        )

        self.assertEqual(
            [listing["externalId"] for listing in listings],
            ["group-1:post-101", "group-1:post-103"],
        )
        self.assertNotIn("group-1:post-104", [listing["externalId"] for listing in listings])
        self.assertTrue(all(listing["platform"] == "FACEBOOK_GROUP" for listing in listings))
        self.assertTrue(all(listing["images"] for listing in listings))
        self.assertTrue(all(listing["_sourceFacts"]["sourceType"] == "facebook_group" for listing in listings))

    def test_same_group_post_does_not_board_the_train_twice(self):
        posts = extract_group_posts(
            [json.dumps(self.fixture["initial"])],
            [],
            group_id="group-1",
            limit=3,
        )
        target = GroupTarget(
            id="test-group",
            group_id="group-1",
            name="Test Group",
            url="https://www.facebook.com/groups/test-group/?sorting_setting=CHRONOLOGICAL",
            sorting_setting="CHRONOLOGICAL",
        )
        listings = normalize_posts(
            posts,
            target=target,
            fetched_at="2026-07-29T00:00:00+00:00",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            first = pool.enqueue(listings, source_id="facebook-groups:test-group")
            edited = [{**listing, "description": f"{listing['description']}\nedited"} for listing in listings]
            second = pool.enqueue(edited, source_id="facebook-groups:test-group")

        self.assertEqual(first.enqueued, len(listings))
        self.assertEqual(second.enqueued, 0)
        self.assertEqual(second.unchanged, len(listings))

    def test_wtb_with_a_photo_is_left_for_ai_instead_of_keyword_filtered(self):
        target = GroupTarget(
            id="test-group",
            group_id="group-1",
            name="Test Group",
            url="https://www.facebook.com/groups/test-group/?sorting_setting=CHRONOLOGICAL",
            sorting_setting="CHRONOLOGICAL",
        )
        listings = normalize_posts(
            [
                {
                    "postId": "post-wtb-photo",
                    "message": "WTB laptop budget 7 juta",
                    "images": [{"url": "https://scontent-test.fbcdn.net/wtb.jpg", "alt": ""}],
                    "commerce": {},
                }
            ],
            target=target,
            fetched_at="2026-07-29T00:00:00+00:00",
        )

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["description"], "WTB laptop budget 7 juta")

    def test_all_requested_group_targets_are_configured(self):
        targets = load_targets(DEFAULT_TARGETS_FILE)

        self.assertEqual(len(targets), 11)
        self.assertEqual(targets[0].id, "jualbelivga")
        self.assertEqual(targets[-1].id, "jual-komputer-bandung")
        self.assertTrue(all("sorting_setting=" in target.url for target in targets))


if __name__ == "__main__":
    unittest.main()
