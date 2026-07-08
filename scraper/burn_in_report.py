"""Summarize RECON scraper burn-in logs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scraper.shared.runtime import parse_iso_datetime


SCRAPER_DIR = Path(__file__).resolve().parent
DEFAULT_LOGS_DIR = SCRAPER_DIR / ".logs"


def main() -> int:
    args = parse_args()
    logs_dir = Path(args.logs_dir)
    since = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)
    report = build_report(logs_dir, since=since)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(markdown_report(report))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a concise scraper burn-in report from JSONL logs.")
    parser.add_argument("--logs-dir", default=str(DEFAULT_LOGS_DIR), help="Directory containing scraper JSONL logs.")
    parser.add_argument("--since-hours", type=float, default=6.0, help="Only include records newer than this many hours.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="Report format.")
    return parser.parse_args()


def build_report(logs_dir: Path, *, since: datetime) -> dict[str, Any]:
    records = load_records(logs_dir, since=since)
    scheduler_records = [record for record in records if record.get("source") == "scheduler"]
    orchestrator_records = [record for record in records if record.get("source") == "orchestrator"]
    connector_records = connector_records_from(orchestrator_records, scheduler_records)
    storage_totals = storage_totals_from(orchestrator_records, scheduler_records)
    degraded = [
        record
        for record in scheduler_records + connector_records
        if str(record.get("status")) in {"degraded", "failed", "rate_limited", "login_blocked", "blocked_or_empty"}
        or record.get("ok") is False
    ]

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "windowStart": since.isoformat(),
        "logsDir": str(logs_dir),
        "records": {
            "total": len(records),
            "scheduler": len(scheduler_records),
            "orchestrator": len(orchestrator_records),
            "connector": len(connector_records),
        },
        "schedulerStatusCounts": counter_by(scheduler_records, "status"),
        "connectorStatusCounts": connector_status_counts(connector_records),
        "storageTotals": storage_totals,
        "latestConnectorStatus": latest_connector_status(connector_records),
        "latestDegraded": degraded[-5:],
        "readiness": readiness(connector_records, storage_totals, degraded),
    }


def load_records(logs_dir: Path, *, since: datetime) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not logs_dir.exists():
        return records
    for path in sorted(logs_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            logged_at = parse_iso_datetime(str(record.get("logged_at") or record.get("finished_at") or ""))
            if logged_at and logged_at < since:
                continue
            record["_logFile"] = path.name
            records.append(record)
    records.sort(key=lambda record: str(record.get("logged_at") or record.get("finished_at") or ""))
    return records


def connector_records_from(
    orchestrator_records: list[dict[str, Any]],
    scheduler_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_records = orchestrator_records
    if not source_records:
        source_records = []
        for scheduler_record in scheduler_records:
            summary = scheduler_record.get("summary") if isinstance(scheduler_record.get("summary"), dict) else {}
            if isinstance(summary, dict):
                source_records.append({**summary, "logged_at": scheduler_record.get("logged_at"), "_logFile": scheduler_record.get("_logFile")})

    for record in source_records:
        for connector in record.get("connectors") or []:
            if isinstance(connector, dict):
                records.append({**connector, "logged_at": record.get("logged_at"), "_logFile": record.get("_logFile")})
    return records


def storage_totals_from(
    orchestrator_records: list[dict[str, Any]],
    scheduler_records: list[dict[str, Any]],
) -> dict[str, int]:
    totals: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    if orchestrator_records:
        candidates.extend(orchestrator_records)
    else:
        for scheduler in scheduler_records:
            summary = scheduler.get("summary") if isinstance(scheduler.get("summary"), dict) else {}
            if isinstance(summary, dict):
                candidates.append(summary)

    for record in candidates:
        storage = record.get("storage") if isinstance(record.get("storage"), dict) else {}
        summary = storage.get("summary") if isinstance(storage.get("summary"), dict) else {}
        for key in ("requested", "deduplicated", "duplicates", "inserted", "updated", "imagesDeleted", "imagesInserted"):
            totals[key] += int(summary.get(key) or 0)
    return dict(totals)


def connector_status_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        connector = str(record.get("connector") or "unknown")
        status = str(record.get("status") or "unknown")
        counts[connector][status] += 1
    return {connector: dict(counter) for connector, counter in counts.items()}


def latest_connector_status(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        connector = str(record.get("connector") or "")
        if connector:
            latest[connector] = record
    return latest


def readiness(records: list[dict[str, Any]], storage_totals: dict[str, int], degraded: list[dict[str, Any]]) -> dict[str, Any]:
    required = {"reddit", "instagram", "facebook"}
    seen = {str(record.get("connector")) for record in records if record.get("connector")}
    healthy_statuses = {"success", "no_new_data", "cooldown_skip"}
    latest = latest_connector_status(records)
    connector_ready = {
        connector: connector in latest and str(latest[connector].get("status")) in healthy_statuses
        for connector in required
    }
    return {
        "allConnectorsObserved": required.issubset(seen),
        "latestConnectorReady": connector_ready,
        "hasStorageWrites": bool(storage_totals.get("inserted") or storage_totals.get("updated")),
        "degradedEvents": len(degraded),
        "phase3Ready": required.issubset(seen)
        and all(connector_ready.values())
        and bool(storage_totals.get("inserted") or storage_totals.get("updated"))
        and not degraded,
    }


def counter_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(record.get(key) or "unknown") for record in records))


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# RECON Phase 3 Burn-In Report",
        "",
        f"- Generated: {report['generatedAt']}",
        f"- Window start: {report['windowStart']}",
        f"- Logs: {report['logsDir']}",
        f"- Records: {report['records']}",
        "",
        "## Scheduler Status",
    ]
    for status, count in sorted(report["schedulerStatusCounts"].items()):
        lines.append(f"- {status}: {count}")

    lines.append("")
    lines.append("## Connector Status")
    for connector, counts in sorted(report["connectorStatusCounts"].items()):
        parts = ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
        lines.append(f"- {connector}: {parts}")

    lines.append("")
    lines.append("## Storage Totals")
    for key, value in sorted(report["storageTotals"].items()):
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("## Readiness")
    readiness_data = report["readiness"]
    for key, value in readiness_data.items():
        lines.append(f"- {key}: {value}")

    if report["latestDegraded"]:
        lines.append("")
        lines.append("## Latest Degraded Events")
        for event in report["latestDegraded"]:
            connector = event.get("connector") or event.get("job_id") or event.get("source") or "unknown"
            lines.append(f"- {connector}: {event.get('status')} ({event.get('_logFile')})")

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
