"""Shared runtime guardrails for RECON scraper runs."""

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Callable, Mapping, MutableMapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


T = TypeVar("T")
TRUE_VALUES = {"1", "true", "yes", "on"}
PROXY_SCHEMES = {"http", "https"}
SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "key",
        "password",
        "passphrase",
        "pwd",
        "secret",
        "token",
    }
)


class AlreadyRunningError(RuntimeError):
    """Raised when a duplicate scraper run lock already exists."""


class EgressConfigError(RuntimeError):
    """Raised when egress env flags are incomplete or unsafe."""


class FileLock(AbstractContextManager["FileLock"]):
    """Small cross-process lock based on atomic file creation."""

    def __init__(self, path: Path, stale_seconds: int) -> None:
        self.path = path
        self.stale_seconds = max(1, stale_seconds)
        self.fd: int | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._remove_stale_lock()
        try:
            self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise AlreadyRunningError(f"lock already exists: {self.path}") from exc

        payload = {
            "pid": os.getpid(),
            "created_at": now_utc().isoformat(),
        }
        os.write(self.fd, json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _remove_stale_lock(self) -> None:
        try:
            age = time.time() - self.path.stat().st_mtime
        except FileNotFoundError:
            return
        if age > self.stale_seconds:
            self.path.unlink(missing_ok=True)


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 1
    base_seconds: float = 1.0
    max_seconds: float = 30.0
    jitter_seconds: float = 0.0

    def normalized(self) -> "RetryPolicy":
        attempts = max(1, self.attempts)
        base_seconds = max(0.0, self.base_seconds)
        max_seconds = max(base_seconds, self.max_seconds)
        jitter_seconds = max(0.0, self.jitter_seconds)
        return RetryPolicy(
            attempts=attempts,
            base_seconds=base_seconds,
            max_seconds=max_seconds,
            jitter_seconds=jitter_seconds,
        )


@dataclass(frozen=True)
class EgressConfig:
    mode: str = "direct"
    proxy_url: str | None = None

    def as_log_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "proxyUrl": redact_url(self.proxy_url) if self.proxy_url else None,
        }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def default_runtime_state() -> dict[str, Any]:
    return {
        "cooldown_until": None,
        "last_run_at": None,
        "last_success_at": None,
        "last_error": None,
    }


def load_runtime_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_runtime_state()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_runtime_state()

    state = default_runtime_state()
    if isinstance(loaded, dict):
        state.update(loaded)
    return state


def save_runtime_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def cooldown_seconds_remaining(state: Mapping[str, Any], now: datetime | None = None) -> int:
    cooldown_until = parse_iso_datetime(str(state.get("cooldown_until") or ""))
    if not cooldown_until:
        return 0
    current = now or now_utc()
    return max(0, int((cooldown_until - current).total_seconds()))


def set_cooldown(state: MutableMapping[str, Any], seconds: int, reason: str, *, now: datetime | None = None) -> None:
    until = (now or now_utc()) + timedelta(seconds=max(1, seconds))
    state["cooldown_until"] = until.isoformat()
    state["last_error"] = reason


def clear_cooldown(state: MutableMapping[str, Any]) -> None:
    state["cooldown_until"] = None


def log_event(path: Path | None, event: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"logged_at": now_utc().isoformat(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def retry_call(
    call: Callable[[], T],
    *,
    policy: RetryPolicy,
    should_retry: Callable[[Exception], bool],
    sleep: Callable[[float], None] = time.sleep,
    random_uniform: Callable[[float, float], float] = random.uniform,
    on_retry: Callable[[Exception, int, int, float], None] | None = None,
) -> T:
    normalized = policy.normalized()

    for attempt in range(1, normalized.attempts + 1):
        try:
            return call()
        except Exception as exc:
            if attempt >= normalized.attempts or not should_retry(exc):
                raise
            delay = retry_delay_seconds(attempt, normalized, getattr(exc, "retry_after_seconds", None), random_uniform)
            if on_retry:
                on_retry(exc, attempt + 1, normalized.attempts, delay)
            sleep(delay)

    raise RuntimeError("retry loop exited without a result")


def retry_delay_seconds(
    failed_attempt: int,
    policy: RetryPolicy,
    retry_after_seconds: int | float | None = None,
    random_uniform: Callable[[float, float], float] = random.uniform,
) -> float:
    if retry_after_seconds is not None:
        return max(0.0, float(retry_after_seconds))

    base = min(policy.max_seconds, policy.base_seconds * (2 ** max(0, failed_attempt - 1)))
    if policy.jitter_seconds <= 0:
        return base
    return base + random_uniform(0.0, policy.jitter_seconds)


def retry_after_seconds_from_headers(headers: Any, *, now: datetime | None = None) -> int | None:
    raw_value = headers.get("Retry-After") if headers else None
    if not raw_value:
        return None
    raw_text = str(raw_value).strip()
    if raw_text.isdigit():
        return max(1, int(raw_text))
    try:
        retry_at = parsedate_to_datetime(raw_text)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    delta = retry_at.astimezone(timezone.utc) - (now or now_utc())
    return max(1, int(delta.total_seconds()))


def resolve_egress_config(env: Mapping[str, str] | None = None) -> EgressConfig:
    values = env if env is not None else os.environ
    mode = str(values.get("SCRAPER_EGRESS_MODE") or "direct").strip().lower()
    proxy_url = clean_string(values.get("SCRAPER_PROXY_URL"))

    if mode not in {"direct", "proxy", "vpn"}:
        raise EgressConfigError("SCRAPER_EGRESS_MODE must be direct, proxy, or vpn.")
    if mode == "direct":
        return EgressConfig(mode="direct", proxy_url=None)
    if mode == "proxy":
        if not truthy(values.get("SCRAPER_ALLOW_PROXY")):
            raise EgressConfigError("Set SCRAPER_ALLOW_PROXY=true before using proxy egress.")
        if not proxy_url:
            raise EgressConfigError("Set SCRAPER_PROXY_URL before using proxy egress.")
        validate_proxy_url(proxy_url)
        return EgressConfig(mode="proxy", proxy_url=proxy_url)
    if not truthy(values.get("SCRAPER_ALLOW_VPN")):
        raise EgressConfigError("Set SCRAPER_ALLOW_VPN=true before using vpn egress.")
    return EgressConfig(mode="vpn", proxy_url=None)


def configure_urllib_egress(config: EgressConfig, environ: MutableMapping[str, str] | None = None) -> None:
    target = environ if environ is not None else os.environ
    proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
    if config.mode != "proxy" or not config.proxy_url:
        for key in proxy_keys:
            target.pop(key, None)
        return
    target["HTTP_PROXY"] = config.proxy_url
    target["HTTPS_PROXY"] = config.proxy_url
    target["http_proxy"] = config.proxy_url
    target["https_proxy"] = config.proxy_url


def playwright_proxy_settings(config: EgressConfig) -> dict[str, str] | None:
    if config.mode == "proxy" and config.proxy_url:
        return {"server": config.proxy_url}
    return None


def clean_string(value: Any) -> str | None:
    if value is None:
        return None
    parsed = str(value).strip()
    return parsed or None


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in TRUE_VALUES


def validate_proxy_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme.lower() not in PROXY_SCHEMES or not parts.hostname:
        raise EgressConfigError("SCRAPER_PROXY_URL must be an http:// or https:// URL.")


def redact_url(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    query = parts.query
    query_pairs = parse_qsl(query, keep_blank_values=True)
    if query_pairs and any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in query_pairs):
        query = urlencode(
            [
                (key, "***" if key.lower() in SENSITIVE_QUERY_KEYS else value)
                for key, value in query_pairs
            ]
        )
    fragment = "***" if parts.fragment else ""
    if parts.password is None and query == parts.query and fragment == parts.fragment:
        return url

    netloc = parts.netloc
    if parts.password is not None:
        host = parts.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"

        username = parts.username or ""
        auth = f"{username}:***@" if username else ""
        port = f":{parts.port}" if parts.port else ""
        netloc = f"{auth}{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, query, fragment))
