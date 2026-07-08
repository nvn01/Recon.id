from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper.burn_in_report import build_report


class BurnInReportTests(unittest.TestCase):
    def test_report_prefers_orchestrator_records_to_avoid_scheduler_double_counting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            summary = {
                "connectors": [{"connector": "reddit", "ok": True, "status": "success"}],
                "storage": {
                    "summary": {
                        "requested": 3,
                        "deduplicated": 3,
                        "duplicates": 0,
                        "inserted": 3,
                        "updated": 0,
                        "imagesDeleted": 0,
                        "imagesInserted": 3,
                    }
                },
            }
            write_jsonl(
                logs_dir / "scheduler_runs.jsonl",
                {
                    "logged_at": "2026-07-08T09:00:00+00:00",
                    "source": "scheduler",
                    "status": "success",
                    "summary": summary,
                },
            )
            write_jsonl(
                logs_dir / "scraper_runs.jsonl",
                {
                    "logged_at": "2026-07-08T09:00:00+00:00",
                    "source": "orchestrator",
                    **summary,
                },
            )

            report = build_report(logs_dir, since=datetime(2026, 7, 8, 8, 0, tzinfo=timezone.utc))

        self.assertEqual(report["connectorStatusCounts"], {"reddit": {"success": 1}})
        self.assertEqual(report["storageTotals"]["requested"], 3)
        self.assertEqual(report["storageTotals"]["inserted"], 3)
        self.assertEqual(report["yieldSummary"]["newListingsInserted"], 3)
        self.assertEqual(report["yieldSummary"]["newPerSuccessfulRun"], 3.0)
        self.assertEqual(report["records"]["scheduler"], 1)
        self.assertEqual(report["records"]["orchestrator"], 1)


def write_jsonl(path: Path, record: dict[str, object]) -> None:
    path.write_text(json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
