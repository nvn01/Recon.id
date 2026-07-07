"""RECON scraper orchestrator.

Runs selected platform connectors and validates their output against the shared
listing contract. This file intentionally does not write to PostgreSQL.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.instagram.instagram import run_accounts
from scraper.reddit.nvidia_parser import NvidiaParserError
from scraper.shared.config import DEFAULT_CONFIG_PATH, float_value, int_value, load_config, string_list, table
from scraper.shared.listing_contract import validate_listings


SCRAPER_DIR = Path(__file__).resolve().parent


def main() -> int:
    args = parse_args()
    started_at = now_iso()
    config = load_config(args.config)

    selected = selected_connectors(args, config)
    results: list[dict[str, Any]] = []
    all_listings: list[dict[str, Any]] = []

    for connector in selected:
        result = run_connector(connector, args, config)
        results.append(result)
        all_listings.extend(result.get("listings", []))

    finished_at = now_iso()
    output = {
        "ok": all(result["ok"] for result in results),
        "startedAt": started_at,
        "finishedAt": finished_at,
        "durationMs": elapsed_ms(started_at, finished_at),
        "databaseWrite": False,
        "selectedConnectors": selected,
        "summary": {
            "connectors": len(results),
            "succeeded": sum(1 for result in results if result["ok"]),
            "failed": sum(1 for result in results if not result["ok"]),
            "listings": len(all_listings),
        },
        "connectors": results,
    }

    print_json(output, args.format)
    return 0 if output["ok"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RECON scraper connectors without database writes.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to scraper source TOML config.")
    parser.add_argument("--reddit", action="store_true", help="Run Reddit connector.")
    parser.add_argument("--instagram", action="store_true", help="Run Instagram connector.")
    parser.add_argument("--facebook", action="store_true", help="Run Facebook Marketplace connector.")
    parser.add_argument("--all", action="store_true", help="Run every enabled connector. This is the default if no connector flag is given.")
    parser.add_argument("--limit", type=int, default=None, help="Override per-source listing limit.")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json", help="Output format.")
    parser.add_argument("--no-state", action="store_true", help="Do not read/write connector state, locks, or run logs.")
    parser.add_argument("--ignore-cooldown", action="store_true", help="Ignore active local connector cooldown state.")
    parser.add_argument("--ai-parse", action="store_true", help="Enable optional batched NVIDIA AI enrichment.")
    parser.add_argument("--ai-prefer", action="store_true", help="Let AI values replace rule-parser values when available.")
    parser.add_argument("--headless", action="store_true", help="Force Facebook browser runs to be headless.")
    parser.add_argument("--facebook-details", action="store_true", help="Fetch Facebook detail pages for richer fields.")
    parser.add_argument("--facebook-target", action="append", default=None, help="Facebook target id from source_targets.json. Can be repeated.")
    parser.add_argument("--facebook-target-group", action="append", default=None, help="Facebook target group from source_targets.json. Can be repeated.")
    parser.add_argument("--instagram-account", action="append", default=None, help="Instagram account username. Can be repeated.")
    return parser.parse_args()


def selected_connectors(args: argparse.Namespace, config: dict[str, Any]) -> list[str]:
    requested = {
        "reddit": args.reddit,
        "instagram": args.instagram,
        "facebook": args.facebook,
    }
    if args.all or not any(requested.values()):
        return [
            name
            for name, section in (
                ("reddit", table(config, "reddit", "wts_computers")),
                ("instagram", table(config, "instagram", "accounts")),
                ("facebook", table(config, "facebook", "marketplace")),
            )
            if section.get("enabled", True)
        ]
    return [name for name, enabled in requested.items() if enabled]


def run_connector(connector: str, args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    try:
        if connector == "reddit":
            result = run_reddit(args, config)
        elif connector == "instagram":
            result = run_instagram(args, config)
        elif connector == "facebook":
            result = run_facebook(args, config)
        else:
            raise ValueError(f"unknown connector: {connector}")
    except Exception as exc:
        result = {
            "connector": connector,
            "ok": False,
            "status": "failed",
            "exitCode": 1,
            "httpStatus": None,
            "transport": None,
            "error": str(exc),
            "normalized": 0,
            "validated": 0,
            "validationErrors": [],
            "listings": [],
        }
    result["durationMs"] = int((time.monotonic() - started) * 1000)
    return result


def run_reddit(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    from scraper.reddit import reddit

    run_config = table(config, "run")
    reddit_config = table(config, "reddit", "wts_computers")
    limit = effective_limit(args, reddit_config, run_config)
    reddit_args = SimpleNamespace(
        limit=limit,
        subreddit=reddit_config.get("subreddit", reddit.SUBREDDIT),
        flair=reddit_config.get("flair", reddit.FLAIR),
        retries=int_value(reddit_config.get("retries"), 2),
        retry_wait=int_value(reddit_config.get("retry_wait_seconds"), 20),
        timeout=int_value(reddit_config.get("timeout_seconds"), int_value(run_config.get("timeout_seconds"), 30)),
        emit="all",
        format="json",
        state_file=str(reddit.DEFAULT_STATE_FILE),
        lock_file=str(reddit.DEFAULT_LOCK_FILE),
        log_file=str(reddit.DEFAULT_LOG_FILE),
        max_seen=500,
        cooldown_seconds=int_value(reddit_config.get("cooldown_seconds"), 300),
        ignore_cooldown=args.ignore_cooldown,
        no_state=args.no_state,
        lock_stale_seconds=900,
        image_mode=str(reddit_config.get("image_mode") or "rss"),
        image_detail_scope="new",
        image_retries=1,
        image_timeout=20,
        image_detail_delay=1.0,
        ai_parse=args.ai_parse,
        ai_prefer=args.ai_prefer,
        ai_model=None,
        ai_batch_size=int_value(run_config.get("ai_batch_size"), 5),
        ai_rate_limit=float_value(run_config.get("ai_rate_limit_seconds"), 2.0),
        ai_timeout=45,
        user_agent=reddit.DEFAULT_USER_AGENT,
    )
    code, listings = reddit.guarded_run_once(reddit_args)
    valid, invalid = validate_listings(listings)
    ok = code == 0 and not invalid
    return {
        "connector": "reddit",
        "ok": ok,
        "status": "success" if ok else "failed",
        "exitCode": code,
        "httpStatus": 200 if code == 0 else None,
        "httpStatusSource": "inferred from successful urllib fetch",
        "transport": "reddit_rss",
        "sourceUrl": reddit_config.get("url"),
        "normalized": len(listings),
        "validated": len(valid),
        "validationErrors": invalid,
        "listings": valid,
    }


def run_instagram(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    run_config = table(config, "run")
    instagram_config = table(config, "instagram", "accounts")
    accounts = args.instagram_account or string_list(instagram_config.get("names"))
    limit = effective_limit(args, instagram_config, run_config)
    listings, account_results = run_accounts(
        accounts,
        limit=limit,
        max_posts_per_account=int_value(instagram_config.get("max_posts_per_account"), 10),
        timeout=int_value(instagram_config.get("timeout_seconds"), int_value(run_config.get("timeout_seconds"), 30)),
        delay_seconds=float_value(instagram_config.get("delay_seconds"), 1.0),
    )
    ai_parse_error = None
    if args.ai_parse and listings:
        try:
            listings = enrich_with_nvidia(listings, args, run_config)
        except NvidiaParserError as exc:
            ai_parse_error = str(exc)
    valid, invalid = validate_listings(listings)
    failed_accounts = [result for result in account_results if not result["ok"]]
    ok = not failed_accounts and not invalid
    statuses = sorted({result["http_status"] for result in account_results if result["http_status"] is not None})
    return {
        "connector": "instagram",
        "ok": ok,
        "status": "success" if ok else "partial" if valid else "failed",
        "exitCode": 0 if ok else 1,
        "httpStatus": statuses[0] if len(statuses) == 1 else statuses,
        "transport": "instagram_web_profile_info",
        "accounts": account_results,
        "aiParse": {
            "requested": bool(args.ai_parse),
            "applied": bool(args.ai_parse and listings and ai_parse_error is None),
            "error": ai_parse_error,
        },
        "normalized": len(listings),
        "validated": len(valid),
        "validationErrors": invalid,
        "listings": valid,
    }


def run_facebook(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    from scraper.facebook import facebook_marketplace as facebook

    run_config = table(config, "run")
    facebook_config = table(config, "facebook", "marketplace")
    targets_file = Path(str(facebook_config.get("targets_file") or facebook.DEFAULT_TARGETS_FILE))
    if not targets_file.is_absolute():
        targets_file = (SCRAPER_DIR / "config" / targets_file).resolve()
    target_ids = args.facebook_target or string_list(facebook_config.get("target_ids"))
    target_groups = args.facebook_target_group or string_list(facebook_config.get("target_groups"))
    limit = effective_limit(args, facebook_config, run_config)

    facebook_args = SimpleNamespace(
        once=True,
        watch=False,
        max_iterations=0,
        interval=60,
        jitter=0,
        emit="all",
        only_new=False,
        format="json",
        query=None,
        targets_file=str(targets_file),
        target=target_ids or None,
        target_group=target_groups or None,
        list_targets=False,
        calibrate_targets=False,
        limit=limit,
        candidate_limit=int_value(facebook_config.get("candidate_limit"), 20),
        location=str(facebook_config.get("location") or facebook.DEFAULT_LOCATION),
        category_id=str(facebook_config.get("category_id") or facebook.DEFAULT_CATEGORY_ID),
        details=bool(args.facebook_details or facebook_config.get("details", False)),
        detail_scope="new",
        login=False,
        headless=bool(args.headless or facebook_config.get("headless", True)),
        browser=str(facebook_config.get("browser") or "chrome"),
        access_mode="browser",
        profile_dir=str(facebook.DEFAULT_PROFILE_DIR),
        include_keyword=None,
        no_relevance_filter=False,
        timeout=int_value(facebook_config.get("timeout_seconds"), int_value(run_config.get("timeout_seconds"), 30)),
        wait_ms=int_value(facebook_config.get("wait_ms"), 3000),
        max_scrolls=int_value(facebook_config.get("max_scrolls"), 1),
        scroll_wait_ms=int_value(facebook_config.get("scroll_wait_ms"), 1000),
        state_file=str(facebook.DEFAULT_STATE_FILE),
        lock_file=str(facebook.DEFAULT_LOCK_FILE),
        log_file=str(facebook.DEFAULT_LOG_FILE),
        max_seen=500,
        cooldown_seconds=int_value(facebook_config.get("cooldown_seconds"), 300),
        ignore_cooldown=args.ignore_cooldown,
        no_state=args.no_state,
        lock_stale_seconds=900,
        ai_parse=args.ai_parse,
        ai_prefer=args.ai_prefer,
        ai_model=None,
        ai_batch_size=int_value(run_config.get("ai_batch_size"), 5),
        ai_rate_limit=float_value(run_config.get("ai_rate_limit_seconds"), 2.0),
        ai_timeout=45,
        user_agent=facebook.DEFAULT_USER_AGENT,
    )
    code, listings = facebook.guarded_run_once(facebook_args)
    valid, invalid = validate_listings(listings)
    ok = code == 0 and not invalid
    return {
        "connector": "facebook",
        "ok": ok,
        "status": "success" if ok else "failed",
        "exitCode": code,
        "httpStatus": None,
        "httpStatusSource": "not available from browser card extraction",
        "transport": "playwright_browser",
        "targetsFile": str(targets_file),
        "targetIds": target_ids,
        "targetGroups": target_groups,
        "normalized": len(listings),
        "validated": len(valid),
        "validationErrors": invalid,
        "listings": valid,
    }


def enrich_with_nvidia(listings: list[dict[str, Any]], args: argparse.Namespace, run_config: dict[str, Any]) -> list[dict[str, Any]]:
    from scraper.reddit.nvidia_parser import enrich_listings_with_nvidia

    return enrich_listings_with_nvidia(
        listings,
        batch_size=int_value(run_config.get("ai_batch_size"), 5),
        rate_limit_seconds=float_value(run_config.get("ai_rate_limit_seconds"), 2.0),
        prefer_ai=args.ai_prefer,
    )


def effective_limit(args: argparse.Namespace, source_config: dict[str, Any], run_config: dict[str, Any]) -> int:
    configured = args.limit if args.limit is not None else source_config.get("limit", run_config.get("limit", 3))
    return max(1, min(100, int_value(configured, 3)))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def elapsed_ms(started_at: str, finished_at: str) -> int:
    started = datetime.fromisoformat(started_at)
    finished = datetime.fromisoformat(finished_at)
    return int((finished - started).total_seconds() * 1000)


def print_json(output: dict[str, Any], output_format: str) -> None:
    if output_format == "jsonl":
        for result in output["connectors"]:
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
