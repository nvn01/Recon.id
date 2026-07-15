from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scraper.candidate_pool import CandidatePool
from scraper.scheduler import (
    build_jobs,
    coalesce_due_jobs,
    is_job_due,
    record_job_state,
    run_job,
    scheduler_status,
    summarize_orchestrator_output,
)
from scraper.shared.runtime import AlreadyRunningError, FileLock
from scraper.shared.config import DEFAULT_CONFIG_PATH, load_config


def sample_config():
    return {
        "run": {"limit": 3},
        "scheduler": {
            "reddit": {"enabled": True, "cadence_seconds": 300, "limit": 3},
            "instagram": {
                "enabled": True,
                "cadence_seconds": 3600,
                "stagger_seconds": 300,
                "limit": 1,
                "per_account": True,
            },
            "facebook": {
                "enabled": True,
                "cadence_seconds": 900,
                "limit": 1,
                "headless": True,
                "browser": "chromium",
            },
        },
        "reddit": {"wts_computers": {"enabled": True, "limit": 3}},
        "instagram": {"accounts": {"enabled": True, "names": ["first.shop", "second.shop"]}},
        "facebook": {"marketplace": {"enabled": True, "target_ids": ["gpu-rtx"], "headless": True}},
    }


class SchedulerTests(unittest.TestCase):
    def test_production_config_rolls_reddit_flairs_without_a_request_burst(self):
        config = load_config(DEFAULT_CONFIG_PATH)
        reddit_config = config["reddit"]["wts_computers"]
        reddit_jobs = [job for job in build_jobs(config) if job.connector == "reddit"]

        self.assertEqual(
            reddit_config["flairs"],
            [
                "WTS: Computers & Peripherals",
                "WTS: Electronics",
                "WTS: Video Games & Consoles",
                "WTS: Smartphones & Tablets",
            ],
        )
        self.assertEqual(len(reddit_config["urls"]), 4)
        self.assertEqual(config["scheduler"]["reddit"]["cadence_seconds"], 240)
        self.assertEqual(config["scheduler"]["reddit"]["stagger_seconds"], 60)
        self.assertEqual(reddit_config["feed_delay_seconds"], 5.0)
        self.assertEqual(len(reddit_jobs), 4)
        self.assertEqual([job.initial_delay_seconds for job in reddit_jobs], [0, 60, 120, 180])
        self.assertTrue(all(job.cadence_seconds == 240 for job in reddit_jobs))
        self.assertEqual(
            [job.args[2] for job in reddit_jobs],
            reddit_config["flairs"],
        )

    def test_scheduler_lock_blocks_a_second_scheduler_instance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "scheduler.lock"
            with FileLock(lock_path, stale_seconds=60):
                with self.assertRaises(AlreadyRunningError):
                    with FileLock(lock_path, stale_seconds=60):
                        pass

    def test_run_job_keeps_database_url_out_of_process_arguments_and_logs(self):
        fixture_url = "postgresql://scraper:test-placeholder-123@postgres:5432/recon"
        [job] = [item for item in build_jobs(sample_config()) if item.id == "reddit"]

        with patch("scraper.scheduler.subprocess.run") as runner:
            runner.return_value.returncode = 0
            runner.return_value.stdout = '{"ok":true,"summary":{"listings":0},"connectors":[]}'
            runner.return_value.stderr = ""

            result = run_job(
                job,
                config_path="scraper/config/sources.toml",
                write_db=True,
                database_url=fixture_url,
                timeout=30,
            )

        command = runner.call_args.args[0]
        child_env = runner.call_args.kwargs["env"]
        self.assertNotIn("--database-url", command)
        self.assertNotIn(fixture_url, command)
        self.assertEqual(child_env["SCRAPER_DATABASE_URL"], fixture_url)
        self.assertNotIn(fixture_url, result.command)

    def test_run_job_queues_raw_candidates_without_ai_or_database_write(self):
        [job] = [item for item in build_jobs(sample_config()) if item.id == "reddit"]
        listing = {
            "platform": "REDDIT",
            "sourceUrl": "https://reddit.com/r/example/comments/queued",
            "externalId": "queued",
            "title": "Raw seller title",
            "description": "Raw seller text",
            "category": "OTHER",
            "brand": None,
            "price": None,
            "locationTexts": [],
            "conditionText": None,
            "sellerName": "seller",
            "status": "UNKNOWN",
            "postedAt": None,
            "firstFetchedAt": "2026-07-15T00:00:00+00:00",
            "lastFetchedAt": "2026-07-15T00:00:00+00:00",
            "images": [],
        }
        output = {
            "ok": True,
            "summary": {"listings": 1},
            "connectors": [
                {
                    "connector": "reddit",
                    "ok": True,
                    "status": "success",
                    "normalized": 1,
                    "validated": 1,
                    "validationErrors": [],
                    "listings": [listing],
                    "candidates": [{**listing, "_sourceFacts": {"priceAmount": 1_000_000}}],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            pool = CandidatePool(Path(tmpdir) / "pool.sqlite3")
            with patch("scraper.scheduler.subprocess.run") as runner:
                runner.return_value.returncode = 0
                runner.return_value.stdout = json.dumps(output)
                runner.return_value.stderr = ""
                result = run_job(
                    job,
                    config_path="scraper/config/sources.toml",
                    write_db=False,
                    database_url=None,
                    timeout=30,
                    queue_candidates=True,
                    candidate_pool=pool,
                )

            command = runner.call_args.args[0]
            self.assertNotIn("--write-db", command)
            self.assertNotIn("--ai-parse", command)
            self.assertEqual(pool.stats()["pending"], 1)
            self.assertEqual(result.summary["candidatePool"]["enqueued"], 1)
            [queued] = pool.lease_batch(batch_size=1, max_wait_seconds=0)
            self.assertEqual(queued.payload["_sourceFacts"]["priceAmount"], 1_000_000)

    def test_operational_report_job_is_read_only_and_keeps_database_url_in_environment(self):
        fixture_url = "postgresql://reporter:test-placeholder-123@postgres:5432/recon"
        config = sample_config()
        config["scheduler"]["operational_report"] = {
            "enabled": True,
            "cadence_seconds": 86_400,
            "output_dir": ".logs/reports",
        }
        [job] = [item for item in build_jobs(config) if item.connector == "operations"]

        with patch("scraper.scheduler.subprocess.run") as runner:
            runner.return_value.returncode = 0
            runner.return_value.stdout = '{"ok":true,"summary":{"listings":1},"connectors":[]}'
            runner.return_value.stderr = ""
            result = run_job(job, config_path="ignored.toml", write_db=True, database_url=fixture_url, timeout=30)

        command = runner.call_args.args[0]
        self.assertIn("scraper.operational_report", command)
        self.assertNotIn("--write-db", command)
        self.assertNotIn(fixture_url, command)
        self.assertEqual(runner.call_args.kwargs["env"]["SCRAPER_DATABASE_URL"], fixture_url)
        self.assertNotIn(fixture_url, result.command)

    def test_production_config_checks_all_instagram_accounts_inside_five_minute_cycle(self):
        config = load_config(DEFAULT_CONFIG_PATH)
        jobs = [job for job in build_jobs(config) if job.connector == "instagram"]

        self.assertEqual(len(jobs), 7)
        self.assertTrue(all(job.cadence_seconds == 315 for job in jobs))
        self.assertEqual([job.initial_delay_seconds for job in jobs], [0, 45, 90, 135, 180, 225, 270])
        self.assertTrue(all(job.args[-2:] == ("--limit", "10") for job in jobs))
        self.assertEqual(config["instagram"]["accounts"]["browser"], "chrome")
        self.assertEqual(config["instagram"]["accounts"]["browser_mode"], "headed")
        self.assertEqual(config["instagram"]["accounts"]["browser_wait_ms"], 8_000)
        self.assertTrue(all("--ai-parse" not in job.args for job in jobs))
        self.assertEqual(config["scheduler"]["facebook"]["browser"], "chrome")
        self.assertEqual(config["facebook"]["marketplace"]["browser"], "chrome")

        facebook_jobs = [job for job in build_jobs(config) if job.connector == "facebook"]
        self.assertTrue(all(job.cadence_seconds == 180 for job in facebook_jobs))
        self.assertEqual([job.initial_delay_seconds for job in facebook_jobs], [0, 60, 120])
        self.assertTrue(all("--ai-parse" not in job.args for job in facebook_jobs))

        [operations_job] = [job for job in build_jobs(config) if job.connector == "operations"]
        self.assertEqual(operations_job.cadence_seconds, 86_400)
        self.assertEqual(operations_job.module, "scraper.operational_report")
        self.assertEqual(operations_job.args, ("--output-dir", ".logs/reports"))

    def test_scraper_image_runs_commands_inside_virtual_display(self):
        dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("xvfb", dockerfile.lower())
        self.assertIn("tini", dockerfile.lower())
        self.assertIn('ENTRYPOINT ["tini", "--", "xvfb-run"', dockerfile)
        self.assertIn('CMD ["python", "-m", "scraper.scheduler", "--once", "--queue-candidates"]', dockerfile)

        compose = (Path(__file__).parents[2] / "docker-compose.yml").read_text(encoding="utf-8")
        scraper_service = compose.split("  scraper:", maxsplit=1)[1].split("\n  scraper-scheduler:", maxsplit=1)[0]
        self.assertNotIn("    init: true", scraper_service)
        self.assertNotIn("    command:", scraper_service)
        self.assertIn("  scraper-ai-manager:", compose)
        self.assertIn("scraper.ai_manager", compose)

    def test_build_jobs_splits_instagram_accounts_and_uses_connector_specific_args(self):
        jobs = build_jobs(sample_config())

        self.assertEqual([job.id for job in jobs], ["reddit", "instagram:first.shop", "instagram:second.shop", "facebook"])
        self.assertEqual(jobs[0].args, ("--reddit", "--limit", "3"))
        self.assertEqual(jobs[1].args, ("--instagram", "--instagram-account", "first.shop", "--limit", "1"))
        self.assertEqual(jobs[2].initial_delay_seconds, 300)
        self.assertIn("--facebook-browser", jobs[3].args)
        self.assertIn("chromium", jobs[3].args)

    def test_build_jobs_can_split_facebook_targets_with_staggered_cadence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            targets_file = Path(tmpdir) / "targets.json"
            targets_file.write_text(
                json.dumps(
                    {
                        "targets": [
                            {"id": "gpu-rtx", "groups": ["hot"], "cadenceSeconds": 60, "limit": 5},
                            {"id": "laptop-gaming", "groups": ["hot"], "cadenceSeconds": 60, "limit": 5},
                            {"id": "keyboard-mechanical", "groups": ["peripherals"], "cadenceSeconds": 300},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            config = sample_config()
            config["scheduler"]["facebook"].update(
                {
                    "split_targets": True,
                    "target_groups": ["hot"],
                    "target_cadence_seconds": 600,
                    "target_stagger_seconds": 60,
                    "limit": 3,
                }
            )
            config["facebook"]["marketplace"] = {
                "enabled": True,
                "targets_file": str(targets_file),
                "headless": True,
            }

            jobs = [job for job in build_jobs(config) if job.connector == "facebook"]

        self.assertEqual([job.id for job in jobs], ["facebook:gpu-rtx", "facebook:laptop-gaming"])
        self.assertEqual(jobs[0].cadence_seconds, 600)
        self.assertEqual(jobs[1].initial_delay_seconds, 60)
        self.assertEqual(
            jobs[0].args,
            (
                "--facebook",
                "--facebook-target",
                "gpu-rtx",
                "--limit",
                "3",
                "--headless",
                "--facebook-browser",
                "chromium",
            ),
        )

    def test_initial_stagger_prevents_all_instagram_accounts_from_being_due_at_start(self):
        jobs = build_jobs(sample_config())
        state = {"startedAt": "2026-07-08T00:00:00+00:00", "jobs": {}}
        now = datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc)

        due = [job.id for job in jobs if is_job_due(job, state, now)]

        self.assertIn("instagram:first.shop", due)
        self.assertNotIn("instagram:second.shop", due)

    def test_restart_coalesces_missed_instagram_jobs_into_staggered_due_times(self):
        config = load_config(DEFAULT_CONFIG_PATH)
        jobs = [job for job in build_jobs(config) if job.connector == "instagram"]
        state = {"startedAt": "2026-07-08T00:00:00+00:00", "jobs": {}}
        now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)

        due = coalesce_due_jobs(jobs, state, now)

        self.assertEqual([job.id for job in due], ["instagram:chemicy.consignment"])
        for index, job in enumerate(jobs[1:], start=1):
            next_due = datetime.fromisoformat(state["jobs"][job.id]["nextDueAt"])
            self.assertEqual((next_due - now).total_seconds(), index * 45)

    def test_record_job_state_sets_next_due_from_cadence(self):
        [job] = [item for item in build_jobs(sample_config()) if item.id == "reddit"]
        state = {"startedAt": "2026-07-08T00:00:00+00:00", "jobs": {}}
        run = type(
            "Run",
            (),
            {
                "started_at": "2026-07-08T00:00:00+00:00",
                "finished_at": "2026-07-08T00:00:02+00:00",
                "status": "success",
                "exit_code": 0,
            },
        )()

        record_job_state(state, job, run, datetime(2026, 7, 8, 0, 0, 2, tzinfo=timezone.utc))

        self.assertEqual(state["jobs"]["reddit"]["nextDueAt"], "2026-07-08T00:05:02+00:00")

    def test_summarize_orchestrator_output_drops_listing_payloads(self):
        output = {
            "ok": True,
            "selectedConnectors": ["reddit"],
            "summary": {"connectors": 1, "succeeded": 1, "failed": 0, "listings": 1},
            "storage": {"summary": {"inserted": 1, "updated": 0, "duplicates": 0}},
            "connectors": [
                {
                    "connector": "reddit",
                    "ok": True,
                    "status": "success",
                    "exitCode": 0,
                    "normalized": 1,
                    "validated": 1,
                    "validationErrors": [],
                    "listings": [{"description": "large payload"}],
                }
            ],
        }

        summary = summarize_orchestrator_output(output)

        self.assertEqual(summary["connectors"][0]["connector"], "reddit")
        self.assertNotIn("listings", summary["connectors"][0])

    def test_scheduler_status_maps_zero_listing_success_to_no_new_data(self):
        summary = {
            "ok": True,
            "summary": {"listings": 0},
            "connectors": [{"connector": "instagram", "status": "no_new_data"}],
        }

        self.assertEqual(scheduler_status(0, summary), "no_new_data")


if __name__ == "__main__":
    unittest.main()
