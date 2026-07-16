from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scraper.ai_manager import process_batch, run_manager, wait_for_departure
from scraper.candidate_pool import CandidatePool, canonical_image_url, evidence_fingerprint
from scraper.shared.config import DEFAULT_CONFIG_PATH


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


class CandidatePoolTests(unittest.TestCase):
    def test_fingerprint_ignores_fetch_timestamps_and_signed_image_query(self):
        first = sample_listing(
            "INSTAGRAM",
            "ig-1",
            image_url="https://scontent.example/image.jpg?token=first&expires=1",
        )
        later = {
            **first,
            "firstFetchedAt": "2026-07-15T12:05:00+00:00",
            "lastFetchedAt": "2026-07-15T12:05:00+00:00",
            "images": [
                {
                    **first["images"][0],
                    "sourceUrl": "https://scontent.example/image.jpg?token=second&expires=2",
                }
            ],
        }

        self.assertEqual(canonical_image_url(first["images"][0]["sourceUrl"]), "https://scontent.example/image.jpg")
        self.assertEqual(evidence_fingerprint(first), evidence_fingerprint(later))

    def test_instagram_fingerprint_ignores_unstable_posted_at_and_cdn_image_paths(self):
        first = sample_listing(
            "INSTAGRAM",
            "ig-unstable",
            image_url="https://scontent.example/v/first-render.jpg?token=first",
        )
        refreshed = {
            **first,
            "postedAt": "2026-07-15T11:04:37+00:00",
            "images": [
                {
                    **first["images"][0],
                    "sourceUrl": "https://scontent.example/v/second-render.jpg?token=second",
                }
            ],
        }

        self.assertEqual(evidence_fingerprint(first), evidence_fingerprint(refreshed))

    def test_description_change_creates_a_new_fingerprint(self):
        first = sample_listing("REDDIT", "reddit-1")
        changed = {**first, "description": "Seller changed the price to Rp 900.000"}

        self.assertNotEqual(evidence_fingerprint(first), evidence_fingerprint(changed))

    def test_private_source_facts_are_stable_evidence_for_ai_reprocessing(self):
        first = {
            **sample_listing("FACEBOOK", "fb-1"),
            "_sourceFacts": {"priceAmount": 1_000_000, "isSold": False},
        }
        changed = {
            **first,
            "_sourceFacts": {"priceAmount": 900_000, "isSold": False},
        }

        self.assertNotEqual(evidence_fingerprint(first), evidence_fingerprint(changed))

    def test_enqueue_deduplicates_volatile_refreshes_and_keeps_real_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            first = sample_listing(
                "INSTAGRAM",
                "ig-1",
                image_url="https://scontent.example/image.jpg?token=first",
            )
            refreshed = {
                **first,
                "lastFetchedAt": "2026-07-15T12:01:00+00:00",
                "images": [{**first["images"][0], "sourceUrl": "https://scontent.example/image.jpg?token=second"}],
            }
            changed = {**refreshed, "description": "Updated seller caption"}

            initial = pool.enqueue([first], source_id="instagram:test", now=NOW)
            unchanged = pool.enqueue([refreshed], source_id="instagram:test", now=NOW + timedelta(minutes=1))
            delta = pool.enqueue([changed], source_id="instagram:test", now=NOW + timedelta(minutes=2))

            self.assertEqual(initial.as_dict(), {"received": 1, "new": 1, "changed": 0, "unchanged": 0, "enqueued": 1})
            self.assertEqual(unchanged.as_dict(), {"received": 1, "new": 0, "changed": 0, "unchanged": 1, "enqueued": 0})
            self.assertEqual(delta.as_dict(), {"received": 1, "new": 0, "changed": 1, "unchanged": 0, "enqueued": 1})
            self.assertEqual(pool.stats()["pending"], 1)
            self.assertEqual(pool.stats()["done"], 1)

    def test_unchanged_refresh_updates_pending_payload_without_new_ai_work(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            first = sample_listing(
                "INSTAGRAM",
                "ig-refresh",
                image_url="https://scontent.example/v/first-render.jpg?token=first",
            )
            refreshed = {
                **first,
                "postedAt": "2026-07-15T11:04:37+00:00",
                "lastFetchedAt": "2026-07-15T12:01:00+00:00",
                "images": [
                    {
                        **first["images"][0],
                        "sourceUrl": "https://scontent.example/v/second-render.jpg?token=second",
                    }
                ],
            }

            pool.enqueue([first], source_id="instagram:one", now=NOW)
            summary = pool.enqueue([refreshed], source_id="instagram:one", now=NOW + timedelta(seconds=30))
            [leased] = pool.lease_train(max_items=20, now=NOW + timedelta(seconds=60))

            self.assertEqual(summary.unchanged, 1)
            self.assertEqual(summary.enqueued, 0)
            self.assertEqual(leased.payload["postedAt"], "2026-07-15T11:04:37+00:00")
            self.assertEqual(
                leased.payload["images"][0]["sourceUrl"],
                "https://scontent.example/v/second-render.jpg?token=second",
            )

    def test_train_leases_the_whole_ready_mixed_platform_window(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            pool.enqueue([sample_listing("REDDIT", "reddit-1")], source_id="reddit:one", now=NOW)
            pool.enqueue([sample_listing("INSTAGRAM", "ig-1")], source_id="instagram:one", now=NOW + timedelta(seconds=29))
            pool.enqueue([sample_listing("FACEBOOK", "fb-1")], source_id="facebook:one", now=NOW + timedelta(seconds=59))
            leased = pool.lease_train(max_items=20, now=NOW + timedelta(seconds=60))

            self.assertEqual({item.platform for item in leased}, {"REDDIT", "INSTAGRAM", "FACEBOOK"})
            self.assertEqual(len(leased), 3)
            pool.complete([item.id for item in leased], now=NOW + timedelta(seconds=30))
            self.assertEqual(pool.stats()["done"], 3)

    def test_train_prioritizes_fresh_candidates_over_ready_retries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            pool.enqueue([sample_listing("INSTAGRAM", "retry-old")], source_id="instagram:one", now=NOW)
            [failed] = pool.lease_batch(batch_size=1, max_wait_seconds=0, now=NOW)
            pool.retry([failed.id], error="provider unavailable", delay_seconds=60, now=NOW)
            pool.enqueue(
                [sample_listing("FACEBOOK", "fresh-new")],
                source_id="facebook:one",
                now=NOW + timedelta(seconds=60),
            )

            [leased] = pool.lease_train(max_items=1, now=NOW + timedelta(seconds=60))

            self.assertEqual(leased.candidate_key, "FACEBOOK:fresh-new")
            self.assertEqual(leased.attempts, 1)

    def test_new_semantic_version_supersedes_older_pending_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            first = sample_listing("INSTAGRAM", "ig-edited")
            edited = {**first, "description": "Seller changed the price to Rp 900.000"}

            pool.enqueue([first], source_id="instagram:one", now=NOW)
            summary = pool.enqueue([edited], source_id="instagram:one", now=NOW + timedelta(seconds=10))

            self.assertEqual(summary.enqueued, 1)
            self.assertEqual(pool.stats()["pending"], 1)
            self.assertEqual(pool.stats()["done"], 1)
            [leased] = pool.lease_train(max_items=20, now=NOW + timedelta(seconds=60))
            self.assertEqual(leased.payload["description"], "Seller changed the price to Rp 900.000")

    def test_failed_batch_is_requeued_without_losing_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            pool.enqueue([sample_listing("FACEBOOK", "fb-1")], source_id="facebook:one", now=NOW)
            leased = pool.lease_batch(batch_size=1, max_wait_seconds=30, now=NOW)

            pool.retry(
                [item.id for item in leased],
                error="provider unavailable",
                delay_seconds=300,
                now=NOW,
            )

            self.assertEqual(pool.stats()["pending"], 1)
            self.assertEqual(pool.lease_batch(batch_size=1, max_wait_seconds=0, now=NOW + timedelta(seconds=299)), [])
            self.assertEqual(len(pool.lease_batch(batch_size=1, max_wait_seconds=0, now=NOW + timedelta(seconds=300))), 1)


class AiManagerTests(unittest.TestCase):
    def test_wait_for_departure_holds_the_train_for_the_full_interval(self):
        sleeper = Mock()

        wait_for_departure(160.0, monotonic_fn=lambda: 100.0, sleep_fn=sleeper)

        sleeper.assert_called_once_with(60.0)

    def test_one_shot_manager_leases_processes_logs_and_completes_a_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool_path = Path(tmpdir) / "pool.sqlite3"
            log_path = Path(tmpdir) / "manager.jsonl"
            pool = CandidatePool(pool_path)
            pool.enqueue([sample_listing("REDDIT", "reddit-1")], source_id="reddit:test", now=NOW)
            args = SimpleNamespace(
                config=str(DEFAULT_CONFIG_PATH),
                pool_path=str(pool_path),
                log_file=str(log_path),
                train_capacity=20,
                departure_interval_seconds=60,
                retry_seconds=300,
                lease_seconds=300,
                database_url=None,
                write_db=False,
                once=True,
            )

            with (
                patch(
                    "scraper.ai_manager.enrich_listings_with_nvidia",
                    side_effect=lambda listings, **_kwargs: listings,
                ),
                patch("builtins.print"),
            ):
                exit_code = run_manager(args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(CandidatePool(pool_path).stats()["done"], 1)
            self.assertIn('"source":"ai_manager"', log_path.read_text(encoding="utf-8"))

    def test_one_shot_manager_sends_one_mixed_platform_train_to_nvidia(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool_path = Path(tmpdir) / "pool.sqlite3"
            log_path = Path(tmpdir) / "manager.jsonl"
            pool = CandidatePool(pool_path)
            pool.enqueue(
                [
                    sample_listing("REDDIT", "reddit-1"),
                    sample_listing("INSTAGRAM", "ig-1"),
                    sample_listing("FACEBOOK", "fb-1"),
                ],
                source_id="mixed:test",
                now=NOW,
            )
            calls: list[tuple[list[dict[str, object]], dict[str, object]]] = []
            args = SimpleNamespace(
                config=str(DEFAULT_CONFIG_PATH),
                pool_path=str(pool_path),
                log_file=str(log_path),
                train_capacity=20,
                departure_interval_seconds=60,
                retry_seconds=300,
                lease_seconds=300,
                database_url=None,
                write_db=False,
                once=True,
            )

            def capture_train(listings, **kwargs):
                calls.append((listings, kwargs))
                return listings

            with (
                patch("scraper.ai_manager.enrich_listings_with_nvidia", side_effect=capture_train),
                patch("builtins.print"),
            ):
                exit_code = run_manager(args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(calls[0][0]), 3)
            self.assertEqual({item["platform"] for item in calls[0][0]}, {"REDDIT", "INSTAGRAM", "FACEBOOK"})
            self.assertEqual(calls[0][1]["batch_size"], 3)
            self.assertEqual(calls[0][1]["rate_limit_seconds"], 0.0)
            self.assertEqual(CandidatePool(pool_path).stats()["done"], 3)

    def test_manager_parses_a_mixed_batch_then_writes_and_completes_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            raw = [sample_listing("REDDIT", "reddit-1"), sample_listing("INSTAGRAM", "ig-1")]
            raw[1]["_sourceFacts"] = {"priceAmount": 1_000_000}
            pool.enqueue(raw, source_id="mixed:test", now=NOW)
            leased = pool.lease_batch(batch_size=2, max_wait_seconds=0, now=NOW)
            writes: list[list[dict[str, object]]] = []

            result = process_batch(
                pool,
                leased,
                database_url="postgresql://scraper:test-placeholder@postgres:5432/recon",
                write_db=True,
                enrich_fn=lambda listings: listings,
                upsert_fn=lambda _url, listings: writes.append(listings) or SimpleNamespace(as_dict=lambda: {"inserted": 2}),
                now=NOW,
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["platforms"], ["INSTAGRAM", "REDDIT"])
            self.assertEqual(len(writes), 1)
            self.assertEqual(len(writes[0]), 2)
            self.assertNotIn("_sourceFacts", writes[0][1])
            self.assertNotIn("media", result)
            self.assertEqual(writes[0][1]["images"][0]["sourceUrl"], "https://images.example/item.jpg")
            self.assertNotIn("cachedUrl", writes[0][1]["images"][0])
            self.assertEqual(pool.stats()["done"], 2)

    def test_manager_requeues_the_whole_batch_when_ai_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            pool.enqueue([sample_listing("REDDIT", "reddit-1")], source_id="reddit:test", now=NOW)
            leased = pool.lease_batch(batch_size=1, max_wait_seconds=0, now=NOW)
            writes: list[object] = []

            result = process_batch(
                pool,
                leased,
                database_url="postgresql://scraper:test-placeholder@postgres:5432/recon",
                write_db=True,
                enrich_fn=lambda _listings: (_ for _ in ()).throw(RuntimeError("NVIDIA unavailable")),
                upsert_fn=lambda *_args: writes.append(object()),
                retry_seconds=300,
                now=NOW,
            )

            self.assertFalse(result["ok"])
            self.assertEqual(writes, [])
            self.assertEqual(pool.stats()["pending"], 1)


def sample_listing(platform: str, external_id: str, *, image_url: str = "https://images.example/item.jpg") -> dict[str, object]:
    return {
        "platform": platform,
        "sourceUrl": f"https://example.com/{external_id}",
        "externalId": external_id,
        "title": "Raw seller listing",
        "description": "Gaming item Rp 1.000.000",
        "category": "OTHER",
        "brand": None,
        "price": None,
        "locationTexts": [],
        "conditionText": None,
        "sellerName": "seller",
        "status": "UNKNOWN",
        "postedAt": "2026-07-15T11:00:00+00:00",
        "firstFetchedAt": "2026-07-15T12:00:00+00:00",
        "lastFetchedAt": "2026-07-15T12:00:00+00:00",
        "images": [{"sourceUrl": image_url, "position": 0, "altText": None}],
    }


if __name__ == "__main__":
    unittest.main()
