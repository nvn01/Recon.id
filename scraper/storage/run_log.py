"""JSONL run logging for scraper orchestration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scraper.storage.postgres import safe_database_url


def write_run_log(path: Path | None, event: dict[str, Any]) -> None:
    if path is None:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"logged_at": datetime.now(timezone.utc).isoformat(), **sanitize_event(event)}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def sanitize_event(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {item_key: sanitize_event(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize_event(item) for item in value]

    key_normalized = (key or "").lower()
    if value is None:
        return None
    if key_normalized in {"databaseurl", "database_url", "scraperdatabaseurl", "scraper_database_url"}:
        return safe_database_url(str(value))
    if any(secret in key_normalized for secret in ("password", "secret", "token", "apikey", "api_key")):
        return "***"
    return value
