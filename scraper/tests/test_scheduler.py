from __future__ import annotations

import unittest
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scraper.scheduler import (
    build_jobs,
    is_job_due,
    record_job_state,
    scheduler_status,
    summarize_orchestrator_output,
)


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
