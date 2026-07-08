from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scraper.main import run_instagram, should_lock_orchestrator
from scraper.shared.runtime import (
    AlreadyRunningError,
    EgressConfigError,
    FileLock,
    RetryPolicy,
    clear_cooldown,
    configure_urllib_egress,
    cooldown_seconds_remaining,
    default_runtime_state,
    resolve_egress_config,
    retry_call,
    set_cooldown,
)


class RuntimeGuardrailTests(unittest.TestCase):
    def test_file_lock_blocks_duplicate_run_and_releases_on_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "scraper.lock"
            with FileLock(lock_path, stale_seconds=60):
                self.assertTrue(lock_path.exists())
                with self.assertRaises(AlreadyRunningError):
                    with FileLock(lock_path, stale_seconds=60):
                        pass

            self.assertFalse(lock_path.exists())

    def test_file_lock_removes_stale_lock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "scraper.lock"
            lock_path.write_text("stale", encoding="utf-8")
            stale_mtime = time.time() - 120
            os.utime(lock_path, (stale_mtime, stale_mtime))

            with FileLock(lock_path, stale_seconds=30):
                self.assertTrue(lock_path.exists())

    def test_cooldown_state_can_be_set_measured_and_cleared(self):
        state = default_runtime_state()
        now = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)

        set_cooldown(state, 90, "rate limited", now=now)

        self.assertEqual(
            cooldown_seconds_remaining(
                state,
                now=datetime(2026, 7, 7, 12, 0, 30, tzinfo=timezone.utc),
            ),
            60,
        )
        self.assertEqual(state["last_error"], "rate limited")

        clear_cooldown(state)

        self.assertIsNone(state["cooldown_until"])

    def test_retry_call_uses_exponential_backoff_and_jitter(self):
        calls = 0
        sleeps: list[float] = []

        def flaky_call() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise TimeoutError("temporary")
            return "ok"

        result = retry_call(
            flaky_call,
            policy=RetryPolicy(attempts=3, base_seconds=2.0, max_seconds=10.0, jitter_seconds=1.5),
            should_retry=lambda exc: isinstance(exc, TimeoutError),
            sleep=sleeps.append,
            random_uniform=lambda _low, high: high,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(calls, 3)
        self.assertEqual(sleeps, [3.5, 5.5])

    def test_retry_call_stops_after_last_attempt(self):
        sleeps: list[float] = []

        with self.assertRaises(TimeoutError):
            retry_call(
                lambda: (_ for _ in ()).throw(TimeoutError("still down")),
                policy=RetryPolicy(attempts=2, base_seconds=1.0, max_seconds=5.0, jitter_seconds=0.0),
                should_retry=lambda exc: isinstance(exc, TimeoutError),
                sleep=sleeps.append,
            )

        self.assertEqual(sleeps, [1.0])

    def test_egress_defaults_to_direct_even_when_proxy_url_is_present(self):
        config = resolve_egress_config({"SCRAPER_PROXY_URL": "http://user:pass@proxy.test:8080"})

        self.assertEqual(config.mode, "direct")
        self.assertIsNone(config.proxy_url)
        self.assertEqual(config.as_log_dict()["proxyUrl"], None)

    def test_proxy_egress_requires_explicit_allow_flag(self):
        with self.assertRaises(EgressConfigError):
            resolve_egress_config(
                {
                    "SCRAPER_EGRESS_MODE": "proxy",
                    "SCRAPER_PROXY_URL": "http://proxy.test:8080",
                }
            )

    def test_proxy_egress_redacts_proxy_credentials_in_logs(self):
        config = resolve_egress_config(
            {
                "SCRAPER_EGRESS_MODE": "proxy",
                "SCRAPER_ALLOW_PROXY": "true",
                "SCRAPER_PROXY_URL": "http://user:secret@proxy.test:8080",
            }
        )

        self.assertEqual(config.mode, "proxy")
        self.assertEqual(config.proxy_url, "http://user:secret@proxy.test:8080")
        self.assertEqual(config.as_log_dict()["proxyUrl"], "http://user:***@proxy.test:8080")

    def test_proxy_egress_sets_urllib_proxy_env_explicitly(self):
        config = resolve_egress_config(
            {
                "SCRAPER_EGRESS_MODE": "proxy",
                "SCRAPER_ALLOW_PROXY": "true",
                "SCRAPER_PROXY_URL": "http://proxy.test:8080",
            }
        )
        environ = {"HTTP_PROXY": "http://old-proxy.test:8080"}

        configure_urllib_egress(config, environ)

        self.assertEqual(environ["HTTP_PROXY"], "http://proxy.test:8080")
        self.assertEqual(environ["HTTPS_PROXY"], "http://proxy.test:8080")

    def test_vpn_egress_requires_explicit_allow_flag(self):
        with self.assertRaises(EgressConfigError):
            resolve_egress_config({"SCRAPER_EGRESS_MODE": "vpn"})

    def test_orchestrator_lock_applies_to_stateful_all_or_write_runs(self):
        base = {
            "no_state": False,
            "write_db": False,
            "all": False,
            "reddit": False,
            "instagram": False,
            "facebook": False,
        }

        self.assertTrue(should_lock_orchestrator(SimpleNamespace(**base)))
        self.assertTrue(should_lock_orchestrator(SimpleNamespace(**{**base, "write_db": True, "reddit": True})))
        self.assertTrue(should_lock_orchestrator(SimpleNamespace(**{**base, "all": True})))
        self.assertFalse(should_lock_orchestrator(SimpleNamespace(**{**base, "reddit": True})))
        self.assertFalse(should_lock_orchestrator(SimpleNamespace(**{**base, "write_db": True, "no_state": True})))

    def test_instagram_rate_limit_cooldown_is_account_scoped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "instagram_accounts.json"
            log_path = Path(tmpdir) / "instagram_accounts.jsonl"
            calls: list[list[str]] = []

            def fake_run_accounts(accounts, **_kwargs):
                calls.append(list(accounts))
                listings = []
                results = []
                for account in accounts:
                    if account == "blocked.shop":
                        results.append(
                            {
                                "account": account,
                                "ok": False,
                                "http_status": 429,
                                "returned_count": 0,
                                "normalized_count": 0,
                                "skipped_count": 0,
                                "error": "Instagram HTTP 429",
                                "latest_shortcode": None,
                            }
                        )
                        continue
                    results.append(
                        {
                            "account": account,
                            "ok": True,
                            "http_status": 200,
                            "returned_count": 1,
                            "normalized_count": 1,
                            "skipped_count": 0,
                            "error": None,
                            "latest_shortcode": "abc123",
                        }
                    )
                    listings.append(sample_instagram_listing(account))
                return listings, results

            args = SimpleNamespace(
                instagram_account=None,
                limit=1,
                no_state=False,
                ignore_cooldown=False,
                ai_parse=False,
                ai_prefer=False,
            )
            config = {
                "run": {},
                "instagram": {
                    "accounts": {
                        "names": ["blocked.shop", "open.shop"],
                        "cooldown_seconds": 600,
                        "retries": 1,
                    }
                },
            }

            with (
                patch("scraper.main.DEFAULT_INSTAGRAM_STATE_FILE", state_path),
                patch("scraper.main.DEFAULT_INSTAGRAM_LOG_FILE", log_path),
                patch("scraper.main.run_accounts", side_effect=fake_run_accounts),
            ):
                first = run_instagram(args, config)
                second = run_instagram(args, config)

        self.assertEqual(calls, [["blocked.shop", "open.shop"], ["open.shop"]])
        self.assertEqual(first["status"], "degraded")
        self.assertEqual(second["status"], "success")
        skipped = [account for account in second["accounts"] if account.get("skipped_by_cooldown")]
        self.assertEqual(skipped[0]["account"], "blocked.shop")


def sample_instagram_listing(account: str) -> dict[str, object]:
    return {
        "platform": "INSTAGRAM",
        "sourceUrl": f"https://www.instagram.com/p/{account}/",
        "externalId": account,
        "title": "Laptop gaming RTX",
        "description": "Laptop gaming RTX\nHarga Rp 10.000.000\nLokasi Jakarta",
        "category": "Laptop",
        "brand": "ASUS",
        "price": 10_000_000,
        "locationTexts": ["Jakarta"],
        "conditionText": None,
        "sellerName": account,
        "status": "AVAILABLE",
        "postedAt": "2026-07-08T00:00:00+00:00",
        "firstFetchedAt": "2026-07-08T00:00:00+00:00",
        "lastFetchedAt": "2026-07-08T00:00:00+00:00",
        "images": [],
    }


if __name__ == "__main__":
    unittest.main()
