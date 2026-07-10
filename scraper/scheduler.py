"""Production-shaped scheduler for RECON scraper runs.

The scheduler runs short, source-specific orchestrator commands. It does not
replace connector cooldowns or locks; it spaces out when those one-shot commands
are attempted and writes concise scheduler JSONL summaries.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scraper.shared.config import DEFAULT_CONFIG_PATH, float_value, int_value, load_config, string_list, table
from scraper.shared.runtime import AlreadyRunningError, FileLock, parse_iso_datetime
from scraper.storage.run_log import write_run_log


SCRAPER_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEDULER_STATE_FILE = SCRAPER_DIR / ".state" / "scheduler.json"
DEFAULT_SCHEDULER_LOG_FILE = SCRAPER_DIR / ".logs" / "scheduler_runs.jsonl"
DEFAULT_SCHEDULER_LOCK_FILE = SCRAPER_DIR / ".state" / "scheduler.lock"
DEFAULT_SCHEDULER_LOCK_STALE_SECONDS = 7200
DEFAULT_CATCH_UP_SPACING_SECONDS = 60


@dataclass(frozen=True)
class ScheduleJob:
    id: str
    connector: str
    cadence_seconds: int
    args: tuple[str, ...]
    initial_delay_seconds: int = 0
    jitter_seconds: int = 0


@dataclass(frozen=True)
class JobRun:
    job_id: str
    connector: str
    command: list[str]
    status: str
    exit_code: int
    started_at: str
    finished_at: str
    duration_ms: int
    summary: dict[str, Any]
    stderr_tail: str | None = None


@dataclass(frozen=True)
class FacebookTargetPlan:
    id: str
    groups: tuple[str, ...] = ()
    cadence_seconds: int | None = None
    limit: int | None = None


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    scheduler_config = table(config, "scheduler")
    state_path = resolve_path(args.state_file or scheduler_config.get("state_file"), DEFAULT_SCHEDULER_STATE_FILE)
    log_path = resolve_path(args.log_file or scheduler_config.get("log_file"), DEFAULT_SCHEDULER_LOG_FILE)
    lock_path = resolve_path(args.lock_file or scheduler_config.get("lock_file"), DEFAULT_SCHEDULER_LOCK_FILE)
    lock_stale_seconds = max(
        60,
        int_value(scheduler_config.get("lock_stale_seconds"), DEFAULT_SCHEDULER_LOCK_STALE_SECONDS),
    )
    loop_sleep_seconds = max(1.0, float_value(scheduler_config.get("loop_sleep_seconds"), 30.0))
    job_timeout_seconds = max(30, int_value(scheduler_config.get("job_timeout_seconds"), 300))

    jobs = filter_jobs(build_jobs(config), args.connector, args.exclude_connector)
    if not jobs:
        print("No scheduler jobs are enabled.", flush=True)
        return 0

    try:
        with FileLock(lock_path, lock_stale_seconds):
            return run_scheduler_loop(
                args,
                jobs,
                state_path=state_path,
                log_path=log_path,
                loop_sleep_seconds=loop_sleep_seconds,
                job_timeout_seconds=job_timeout_seconds,
            )
    except AlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def run_scheduler_loop(
    args: argparse.Namespace,
    jobs: list[ScheduleJob],
    *,
    state_path: Path,
    log_path: Path,
    loop_sleep_seconds: float,
    job_timeout_seconds: int,
) -> int:
    state = load_scheduler_state(state_path)
    cycle = 0
    while True:
        cycle += 1
        now = now_utc()
        ensure_scheduler_started(state, now)
        due_jobs = coalesce_due_jobs(jobs, state, now, run_due_now=args.run_due_now)

        if not due_jobs:
            print_no_due(jobs, state, now)
            save_scheduler_state(state_path, state)
        for job in due_jobs:
            run = run_job(
                job,
                config_path=args.config,
                write_db=args.write_db,
                database_url=args.database_url,
                timeout=job_timeout_seconds,
            )
            record_job_state(state, job, run, now_utc())
            save_scheduler_state(state_path, state)
            write_run_log(log_path, {"source": "scheduler", **asdict(run)})
            print(format_run_summary(run), flush=True)

        if args.once:
            return 0
        if args.max_cycles and cycle >= args.max_cycles:
            return 0

        sleep_for = seconds_until_next_due(jobs, state, now_utc(), max_sleep=loop_sleep_seconds)
        time.sleep(sleep_for)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RECON scraper connector jobs on source-specific cadences.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to scraper source TOML config.")
    parser.add_argument("--state-file", default=None, help="Scheduler state JSON path.")
    parser.add_argument("--log-file", default=None, help="Scheduler JSONL summary log path.")
    parser.add_argument("--lock-file", default=None, help="Scheduler lock file path.")
    parser.add_argument("--once", action="store_true", help="Run currently due jobs once, then exit.")
    parser.add_argument("--max-cycles", type=int, default=0, help="Stop after this many scheduler cycles.")
    parser.add_argument("--run-due-now", action="store_true", help="Treat jobs without prior attempts as due immediately.")
    parser.add_argument("--write-db", action="store_true", help="Pass --write-db to each orchestrator command.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL override passed to scraper.main through SCRAPER_DATABASE_URL.",
    )
    parser.add_argument("--connector", action="append", choices=("reddit", "instagram", "facebook"), help="Only run this connector.")
    parser.add_argument("--exclude-connector", action="append", choices=("reddit", "instagram", "facebook"), help="Skip this connector.")
    return parser.parse_args()


def build_jobs(config: dict[str, Any]) -> list[ScheduleJob]:
    jobs: list[ScheduleJob] = []
    jobs.extend(build_reddit_jobs(config))
    jobs.extend(build_instagram_jobs(config))
    jobs.extend(build_facebook_jobs(config))
    return jobs


def build_reddit_jobs(config: dict[str, Any]) -> list[ScheduleJob]:
    source_config = table(config, "reddit", "wts_computers")
    schedule_config = table(config, "scheduler", "reddit")
    if not source_config.get("enabled", True) or not schedule_config.get("enabled", True):
        return []

    cadence = max(60, int_value(schedule_config.get("cadence_seconds"), 300))
    limit = max(1, int_value(schedule_config.get("limit"), int_value(source_config.get("limit"), 3)))
    jitter = max(0, int_value(schedule_config.get("jitter_seconds"), 0))
    return [
        ScheduleJob(
            id="reddit",
            connector="reddit",
            cadence_seconds=cadence,
            args=("--reddit", "--limit", str(limit)),
            jitter_seconds=jitter,
        )
    ]


def build_instagram_jobs(config: dict[str, Any]) -> list[ScheduleJob]:
    source_config = table(config, "instagram", "accounts")
    schedule_config = table(config, "scheduler", "instagram")
    if not source_config.get("enabled", True) or not schedule_config.get("enabled", True):
        return []

    cadence = max(300, int_value(schedule_config.get("cadence_seconds"), 3600))
    stagger = max(0, int_value(schedule_config.get("stagger_seconds"), 300))
    jitter = max(0, int_value(schedule_config.get("jitter_seconds"), 0))
    limit = max(1, int_value(schedule_config.get("limit"), 1))
    accounts = string_list(source_config.get("names"))
    per_account = bool_value(schedule_config.get("per_account"), default=True)

    if not accounts:
        return []
    if not per_account:
        return [
            ScheduleJob(
                id="instagram",
                connector="instagram",
                cadence_seconds=cadence,
                args=("--instagram", "--limit", str(limit)),
                jitter_seconds=jitter,
            )
        ]

    return [
        ScheduleJob(
            id=f"instagram:{account}",
            connector="instagram",
            cadence_seconds=cadence,
            args=("--instagram", "--instagram-account", account, "--limit", str(limit)),
            initial_delay_seconds=index * stagger,
            jitter_seconds=jitter,
        )
        for index, account in enumerate(accounts)
    ]


def build_facebook_jobs(config: dict[str, Any]) -> list[ScheduleJob]:
    source_config = table(config, "facebook", "marketplace")
    schedule_config = table(config, "scheduler", "facebook")
    if not source_config.get("enabled", True) or not schedule_config.get("enabled", True):
        return []

    cadence = max(60, int_value(schedule_config.get("cadence_seconds"), 900))
    jitter = max(0, int_value(schedule_config.get("jitter_seconds"), 0))
    limit = max(1, int_value(schedule_config.get("limit"), int_value(source_config.get("limit"), 1)))
    browser = str(schedule_config.get("browser") or source_config.get("browser") or "").strip()
    headless = bool_value(schedule_config.get("headless"), default=bool_value(source_config.get("headless"), default=True))
    target_ids = string_list(schedule_config.get("target_ids")) or string_list(source_config.get("target_ids"))
    target_groups = string_list(schedule_config.get("target_groups")) or string_list(source_config.get("target_groups"))
    split_targets = bool_value(schedule_config.get("split_targets"), default=False)

    if split_targets:
        targets_file = resolve_facebook_targets_path(source_config.get("targets_file"))
        targets = select_facebook_targets(load_facebook_targets(targets_file), target_ids, target_groups)
        if targets:
            return build_facebook_target_jobs(
                targets,
                schedule_config=schedule_config,
                default_cadence=cadence,
                default_limit=limit,
                jitter=jitter,
                browser=browser,
                headless=headless,
            )

    job_args: list[str] = ["--facebook", "--limit", str(limit)]
    for target_id in target_ids:
        job_args.extend(["--facebook-target", target_id])
    for target_group in target_groups:
        job_args.extend(["--facebook-target-group", target_group])
    if headless:
        job_args.append("--headless")
    if browser:
        job_args.extend(["--facebook-browser", browser])

    return [
        ScheduleJob(
            id="facebook",
            connector="facebook",
            cadence_seconds=cadence,
            args=tuple(job_args),
            jitter_seconds=jitter,
        )
    ]


def build_facebook_target_jobs(
    targets: list[FacebookTargetPlan],
    *,
    schedule_config: dict[str, Any],
    default_cadence: int,
    default_limit: int,
    jitter: int,
    browser: str,
    headless: bool,
) -> list[ScheduleJob]:
    target_stagger = max(0, int_value(schedule_config.get("target_stagger_seconds"), 60))
    target_cadence_override = int_value(schedule_config.get("target_cadence_seconds"), 0)
    jobs: list[ScheduleJob] = []

    for index, target in enumerate(targets):
        cadence = target_cadence_override or target.cadence_seconds or default_cadence
        cadence = max(60, cadence)
        limit = max(1, int_value(schedule_config.get("limit"), target.limit or default_limit))
        job_args: list[str] = ["--facebook", "--facebook-target", target.id, "--limit", str(limit)]
        if headless:
            job_args.append("--headless")
        if browser:
            job_args.extend(["--facebook-browser", browser])

        jobs.append(
            ScheduleJob(
                id=f"facebook:{target.id}",
                connector="facebook",
                cadence_seconds=cadence,
                args=tuple(job_args),
                initial_delay_seconds=index * target_stagger,
                jitter_seconds=jitter,
            )
        )
    return jobs


def resolve_facebook_targets_path(value: Any) -> Path:
    raw = Path(str(value or "../facebook/source_targets.json"))
    if raw.is_absolute():
        return raw
    return (SCRAPER_DIR / "config" / raw).resolve()


def load_facebook_targets(path: Path) -> list[FacebookTargetPlan]:
    if not path.exists():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    records = loaded.get("targets", []) if isinstance(loaded, dict) else loaded
    if not isinstance(records, list):
        return []

    targets: list[FacebookTargetPlan] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        target_id = str(record.get("id") or f"target-{index}").strip()
        if not target_id:
            continue
        targets.append(
            FacebookTargetPlan(
                id=target_id,
                groups=tuple(raw_string_list(record.get("groups") or record.get("group"))),
                cadence_seconds=optional_int(record.get("cadenceSeconds") or record.get("cadence_seconds")),
                limit=optional_int(record.get("limit")),
            )
        )
    return targets


def select_facebook_targets(
    targets: list[FacebookTargetPlan],
    target_ids: list[str],
    target_groups: list[str],
) -> list[FacebookTargetPlan]:
    requested_ids = set(target_ids)
    requested_groups = set(target_groups)
    selected: list[FacebookTargetPlan] = []
    seen: set[str] = set()

    for target in targets:
        if requested_ids and target.id in requested_ids and target.id not in seen:
            selected.append(target)
            seen.add(target.id)

    for target in targets:
        if target.id in seen:
            continue
        if requested_groups and requested_groups.intersection(target.groups):
            selected.append(target)
            seen.add(target.id)

    return selected


def raw_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    parsed = str(value).strip()
    return [parsed] if parsed else []


def optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def filter_jobs(jobs: list[ScheduleJob], include: list[str] | None, exclude: list[str] | None) -> list[ScheduleJob]:
    include_set = set(include or [])
    exclude_set = set(exclude or [])
    return [
        job
        for job in jobs
        if (not include_set or job.connector in include_set) and job.connector not in exclude_set
    ]


def load_scheduler_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"startedAt": None, "jobs": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"startedAt": None, "jobs": {}}
    if not isinstance(loaded, dict):
        return {"startedAt": None, "jobs": {}}
    loaded.setdefault("startedAt", None)
    loaded.setdefault("jobs", {})
    if not isinstance(loaded["jobs"], dict):
        loaded["jobs"] = {}
    return loaded


def save_scheduler_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def ensure_scheduler_started(state: dict[str, Any], now: datetime) -> None:
    if not parse_iso_datetime(str(state.get("startedAt") or "")):
        state["startedAt"] = now.isoformat()


def is_job_due(job: ScheduleJob, state: dict[str, Any], now: datetime, *, run_due_now: bool = False) -> bool:
    job_state = get_job_state(state, job)
    next_due = parse_iso_datetime(str(job_state.get("nextDueAt") or ""))
    if next_due:
        return now >= next_due
    if run_due_now:
        return True

    scheduler_started = parse_iso_datetime(str(state.get("startedAt") or "")) or now
    initial_due = scheduler_started + timedelta(seconds=job.initial_delay_seconds)
    return now >= initial_due


def coalesce_due_jobs(
    jobs: list[ScheduleJob],
    state: dict[str, Any],
    now: datetime,
    *,
    run_due_now: bool = False,
    catch_up_spacing_seconds: int = DEFAULT_CATCH_UP_SPACING_SECONDS,
) -> list[ScheduleJob]:
    """Keep missed jobs from a connector from running in one burst.

    A stopped scheduler can come back with several jobs whose due times are all
    in the past.  Run the first due job for each connector now, then move the
    remaining due jobs into the future using their configured initial offsets.
    This preserves the rolling account/target cadence after a restart while
    still allowing different connectors to make progress in the same cycle.
    """
    due_jobs = [job for job in jobs if is_job_due(job, state, now, run_due_now=run_due_now)]
    if len(due_jobs) <= 1:
        return due_jobs

    spacing = max(1, int(catch_up_spacing_seconds))
    due_by_connector: dict[str, list[ScheduleJob]] = {}
    for job in due_jobs:
        due_by_connector.setdefault(job.connector, []).append(job)

    selected_ids: set[str] = set()
    scheduler_jobs = state.setdefault("jobs", {})
    for connector_jobs in due_by_connector.values():
        ordered = sorted(connector_jobs, key=lambda job: (job.initial_delay_seconds, job.id))
        first = ordered[0]
        selected_ids.add(first.id)
        previous_offset = 0
        for job in ordered[1:]:
            offset = job.initial_delay_seconds - first.initial_delay_seconds
            if offset <= previous_offset:
                offset = previous_offset + spacing
            previous_offset = offset
            job_state = scheduler_jobs.get(job.id)
            if not isinstance(job_state, dict):
                job_state = {"connector": job.connector}
                scheduler_jobs[job.id] = job_state
            job_state["nextDueAt"] = (now + timedelta(seconds=offset)).isoformat()

    # Keep the original config order so connector logs stay deterministic.
    return [job for job in due_jobs if job.id in selected_ids]


def record_job_state(state: dict[str, Any], job: ScheduleJob, run: JobRun, now: datetime) -> None:
    jitter = random.randint(0, job.jitter_seconds) if job.jitter_seconds > 0 else 0
    next_due = now + timedelta(seconds=job.cadence_seconds + jitter)
    state.setdefault("jobs", {})[job.id] = {
        "connector": job.connector,
        "lastAttemptAt": run.started_at,
        "lastFinishedAt": run.finished_at,
        "lastStatus": run.status,
        "lastExitCode": run.exit_code,
        "nextDueAt": next_due.isoformat(),
    }


def get_job_state(state: dict[str, Any], job: ScheduleJob) -> dict[str, Any]:
    jobs = state.setdefault("jobs", {})
    value = jobs.get(job.id)
    if isinstance(value, dict):
        return value
    return {}


def seconds_until_next_due(jobs: list[ScheduleJob], state: dict[str, Any], now: datetime, *, max_sleep: float) -> float:
    due_times: list[datetime] = []
    for job in jobs:
        job_state = get_job_state(state, job)
        next_due = parse_iso_datetime(str(job_state.get("nextDueAt") or ""))
        if next_due:
            due_times.append(next_due)
            continue
        scheduler_started = parse_iso_datetime(str(state.get("startedAt") or "")) or now
        due_times.append(scheduler_started + timedelta(seconds=job.initial_delay_seconds))

    if not due_times:
        return max_sleep
    seconds = min((due_time - now).total_seconds() for due_time in due_times)
    return max(1.0, min(max_sleep, seconds))


def run_job(
    job: ScheduleJob,
    *,
    config_path: str,
    write_db: bool,
    database_url: str | None,
    timeout: int,
) -> JobRun:
    command = [sys.executable, "-m", "scraper.main", "--config", config_path, *job.args, "--format", "json"]
    if write_db:
        command.append("--write-db")
    child_env = None
    if database_url:
        child_env = os.environ.copy()
        child_env["SCRAPER_DATABASE_URL"] = database_url

    started_at = now_utc()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=child_env,
        )
        output = parse_json_output(completed.stdout)
        summary = summarize_orchestrator_output(output)
        status = scheduler_status(completed.returncode, summary)
        exit_code = int(completed.returncode)
        stderr_tail = tail_text(completed.stderr)
    except subprocess.TimeoutExpired as exc:
        summary = {
            "ok": False,
            "selectedConnectors": [job.connector],
            "connectors": [{"connector": job.connector, "status": "timeout"}],
            "storage": None,
        }
        status = "degraded"
        exit_code = 124
        stderr_tail = tail_text((exc.stderr or "") if isinstance(exc.stderr, str) else "")

    finished_at = now_utc()
    return JobRun(
        job_id=job.id,
        connector=job.connector,
        command=list(command),
        status=status,
        exit_code=exit_code,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        summary=summary,
        stderr_tail=stderr_tail,
    )


def parse_json_output(stdout: str) -> dict[str, Any] | None:
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        loaded = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def summarize_orchestrator_output(output: dict[str, Any] | None) -> dict[str, Any]:
    if not output:
        return {
            "ok": False,
            "selectedConnectors": [],
            "summary": None,
            "storage": None,
            "connectors": [],
            "error": "orchestrator did not return JSON",
        }

    connector_summaries = []
    for connector in output.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        connector_summaries.append(
            {
                "connector": connector.get("connector"),
                "ok": connector.get("ok"),
                "status": connector.get("status"),
                "exitCode": connector.get("exitCode"),
                "normalized": connector.get("normalized"),
                "validated": connector.get("validated"),
                "validationErrors": len(connector.get("validationErrors") or []),
                "durationMs": connector.get("durationMs"),
            }
        )

    storage = output.get("storage") if isinstance(output.get("storage"), dict) else None
    return {
        "ok": bool(output.get("ok")),
        "selectedConnectors": output.get("selectedConnectors") or [],
        "summary": output.get("summary"),
        "storage": storage,
        "connectors": connector_summaries,
        "error": output.get("error"),
    }


def scheduler_status(exit_code: int, summary: dict[str, Any]) -> str:
    connectors = summary.get("connectors") or []
    statuses = {str(connector.get("status") or "") for connector in connectors if isinstance(connector, dict)}
    if "cooldown_skip" in statuses and len(statuses) == 1:
        return "cooldown_skip"
    if exit_code == 0 and summary.get("ok"):
        listing_count = 0
        run_summary = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
        if isinstance(run_summary, dict):
            listing_count = int(run_summary.get("listings") or 0)
        return "success" if listing_count else "no_new_data"
    return "degraded"


def format_run_summary(run: JobRun) -> str:
    run_summary = run.summary.get("summary") if isinstance(run.summary.get("summary"), dict) else {}
    storage = run.summary.get("storage") if isinstance(run.summary.get("storage"), dict) else {}
    storage_summary = storage.get("summary") if isinstance(storage.get("summary"), dict) else {}
    listings = run_summary.get("listings", 0) if isinstance(run_summary, dict) else 0
    requested = storage_summary.get("requested", 0) if isinstance(storage_summary, dict) else 0
    deduplicated = storage_summary.get("deduplicated", 0) if isinstance(storage_summary, dict) else 0
    inserted = storage_summary.get("inserted", 0) if isinstance(storage_summary, dict) else 0
    updated = storage_summary.get("updated", 0) if isinstance(storage_summary, dict) else 0
    duplicates = storage_summary.get("duplicates", 0) if isinstance(storage_summary, dict) else 0
    return (
        f"{run.finished_at} {run.job_id} {run.status} exit={run.exit_code} "
        f"listings={listings} requested={requested} deduped={deduplicated} "
        f"inserted={inserted} updated={updated} duplicates={duplicates} "
        f"durationMs={run.duration_ms}"
    )


def print_no_due(jobs: list[ScheduleJob], state: dict[str, Any], now: datetime) -> None:
    next_due = []
    for job in jobs:
        job_state = get_job_state(state, job)
        due_at = parse_iso_datetime(str(job_state.get("nextDueAt") or ""))
        if due_at:
            next_due.append((due_at, job.id))
    if not next_due:
        print(f"{now.isoformat()} no_due waiting_for_initial_offsets", flush=True)
        return
    due_at, job_id = min(next_due, key=lambda item: item[0])
    remaining = max(0, int((due_at - now).total_seconds()))
    print(f"{now.isoformat()} no_due next={job_id} in={remaining}s", flush=True)


def tail_text(value: str, max_chars: int = 1200) -> str | None:
    text = value.strip()
    if not text:
        return None
    return text[-max_chars:]


def resolve_path(value: Any, default: Path) -> Path:
    if not value:
        return default
    path = Path(str(value))
    if path.is_absolute():
        return path
    return SCRAPER_DIR / path


def bool_value(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
