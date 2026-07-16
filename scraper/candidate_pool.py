"""Durable scraper-side candidate queue with stable source-evidence deduplication."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import urlsplit, urlunsplit


DEFAULT_POOL_PATH = Path(__file__).resolve().parent / ".state" / "candidate_pool.sqlite3"


@dataclass(frozen=True)
class EnqueueSummary:
    received: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    enqueued: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "received": self.received,
            "new": self.new,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "enqueued": self.enqueued,
        }


@dataclass(frozen=True)
class LeasedCandidate:
    id: str
    candidate_key: str
    platform: str
    source_id: str
    fingerprint: str
    payload: dict[str, Any]
    attempts: int
    enqueued_at: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.split("?", 1)[0].split("#", 1)[0]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", ""))


def canonical_image_url(value: Any) -> str:
    return canonical_url(value)


def candidate_key(listing: dict[str, Any]) -> str:
    platform = str(listing.get("platform") or "UNKNOWN").upper()
    identity = str(listing.get("externalId") or "").strip() or canonical_url(listing.get("sourceUrl"))
    if not identity:
        raise ValueError("candidate requires externalId or sourceUrl")
    return f"{platform}:{identity}"


def evidence_fingerprint(listing: dict[str, Any]) -> str:
    # This fingerprint is the AI-work identity, not a byte-for-byte snapshot of
    # every source field. Instagram can expose a different CDN path and postedAt
    # value for the same post between otherwise identical fetches. Neither is
    # semantic input that should send an already-reviewed listing back to AI.
    evidence = {
        "platform": str(listing.get("platform") or "UNKNOWN").upper(),
        "sourceUrl": canonical_url(listing.get("sourceUrl")),
        "externalId": str(listing.get("externalId") or ""),
        "title": listing.get("title"),
        "description": listing.get("description"),
        "sellerName": listing.get("sellerName"),
        "sourceFacts": listing.get("_sourceFacts") if isinstance(listing.get("_sourceFacts"), dict) else {},
    }
    serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"v2:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


class CandidatePool:
    def __init__(self, path: Path | str = DEFAULT_POOL_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_state (
                    candidate_key TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    candidate_key TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    enqueued_at TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    leased_at TEXT,
                    done_at TEXT,
                    error TEXT,
                    UNIQUE(candidate_key, fingerprint)
                );

                CREATE INDEX IF NOT EXISTS candidates_ready_idx
                    ON candidates(status, available_at, enqueued_at);
                """
            )

    def enqueue(
        self,
        listings: Iterable[dict[str, Any]],
        *,
        source_id: str,
        now: datetime | None = None,
    ) -> EnqueueSummary:
        timestamp = (now or utc_now()).astimezone(timezone.utc).isoformat()
        received = new = changed = unchanged = enqueued = 0
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for listing in listings:
                received += 1
                key = candidate_key(listing)
                platform = str(listing.get("platform") or "UNKNOWN").upper()
                fingerprint = evidence_fingerprint(listing)
                existing = connection.execute(
                    "SELECT fingerprint FROM source_state WHERE candidate_key = ?",
                    (key,),
                ).fetchone()
                if existing is None:
                    new += 1
                    connection.execute(
                        """
                        INSERT INTO source_state (
                            candidate_key, platform, source_id, fingerprint,
                            first_seen_at, last_seen_at, seen_count
                        ) VALUES (?, ?, ?, ?, ?, ?, 1)
                        """,
                        (key, platform, source_id, fingerprint, timestamp, timestamp),
                    )
                    enqueued += self._enqueue_version(
                        connection,
                        listing=listing,
                        key=key,
                        platform=platform,
                        source_id=source_id,
                        fingerprint=fingerprint,
                        timestamp=timestamp,
                    )
                    continue

                if str(existing["fingerprint"]) == fingerprint:
                    unchanged += 1
                    connection.execute(
                        """
                        UPDATE source_state
                        SET last_seen_at = ?, seen_count = seen_count + 1, source_id = ?
                        WHERE candidate_key = ?
                        """,
                        (timestamp, source_id, key),
                    )
                    connection.execute(
                        """
                        UPDATE candidates
                        SET platform = ?, source_id = ?, payload_json = ?
                        WHERE candidate_key = ? AND fingerprint = ? AND status = 'pending'
                        """,
                        (
                            platform,
                            source_id,
                            json.dumps(listing, ensure_ascii=False, separators=(",", ":")),
                            key,
                            fingerprint,
                        ),
                    )
                    continue

                changed += 1
                connection.execute(
                    """
                    UPDATE source_state
                    SET platform = ?, source_id = ?, fingerprint = ?,
                        last_seen_at = ?, seen_count = seen_count + 1
                    WHERE candidate_key = ?
                    """,
                    (platform, source_id, fingerprint, timestamp, key),
                )
                self._supersede_pending_versions(
                    connection,
                    candidate_key=key,
                    keep_fingerprint=fingerprint,
                    timestamp=timestamp,
                )
                enqueued += self._enqueue_version(
                    connection,
                    listing=listing,
                    key=key,
                    platform=platform,
                    source_id=source_id,
                    fingerprint=fingerprint,
                    timestamp=timestamp,
                )
        return EnqueueSummary(received, new, changed, unchanged, enqueued)

    def _supersede_pending_versions(
        self,
        connection: sqlite3.Connection,
        *,
        candidate_key: str,
        keep_fingerprint: str,
        timestamp: str,
    ) -> None:
        connection.execute(
            """
            UPDATE candidates
            SET status = 'done', done_at = ?, leased_at = NULL,
                error = 'superseded by newer source evidence'
            WHERE candidate_key = ? AND fingerprint != ? AND status = 'pending'
            """,
            (timestamp, candidate_key, keep_fingerprint),
        )

    def _enqueue_version(
        self,
        connection: sqlite3.Connection,
        *,
        listing: dict[str, Any],
        key: str,
        platform: str,
        source_id: str,
        fingerprint: str,
        timestamp: str,
    ) -> int:
        existing = connection.execute(
            "SELECT status FROM candidates WHERE candidate_key = ? AND fingerprint = ?",
            (key, fingerprint),
        ).fetchone()
        payload_json = json.dumps(listing, ensure_ascii=False, separators=(",", ":"))
        if existing is None:
            connection.execute(
                """
                INSERT INTO candidates (
                    id, candidate_key, platform, source_id, fingerprint,
                    payload_json, status, enqueued_at, available_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (str(uuid.uuid4()), key, platform, source_id, fingerprint, payload_json, timestamp, timestamp),
            )
            return 1
        if str(existing["status"]) == "done":
            connection.execute(
                """
                UPDATE candidates
                SET platform = ?, source_id = ?, payload_json = ?, status = 'pending',
                    enqueued_at = ?, available_at = ?, leased_at = NULL,
                    done_at = NULL, attempts = 0, error = NULL
                WHERE candidate_key = ? AND fingerprint = ?
                """,
                (platform, source_id, payload_json, timestamp, timestamp, key, fingerprint),
            )
            return 1
        return 0

    def lease_train(
        self,
        *,
        max_items: int,
        lease_seconds: int = 300,
        now: datetime | None = None,
    ) -> list[LeasedCandidate]:
        """Lease one mixed-platform train, preferring never-attempted work.

        The manager calls this once per departure interval. Older pending
        versions of a post are closed before boarding so one source post can
        occupy at most one seat in a train.
        """
        current = (now or utc_now()).astimezone(timezone.utc)
        current_iso = current.isoformat()
        stale_iso = (current - timedelta(seconds=max(1, lease_seconds))).isoformat()
        capacity = max(1, min(50, int(max_items)))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE candidates
                SET status = 'pending', available_at = ?, leased_at = NULL,
                    error = COALESCE(error, 'stale lease recovered')
                WHERE status = 'leased' AND leased_at <= ?
                """,
                (current_iso, stale_iso),
            )
            connection.execute(
                """
                UPDATE candidates AS candidate
                SET status = 'done', done_at = ?, leased_at = NULL,
                    error = 'superseded by newer pending version'
                WHERE candidate.status = 'pending'
                  AND EXISTS (
                    SELECT 1
                    FROM candidates AS newer
                    WHERE newer.candidate_key = candidate.candidate_key
                      AND newer.status = 'pending'
                      AND (
                        newer.enqueued_at > candidate.enqueued_at
                        OR (newer.enqueued_at = candidate.enqueued_at AND newer.id > candidate.id)
                      )
                  )
                """,
                (current_iso,),
            )
            ready = connection.execute(
                """
                SELECT * FROM candidates
                WHERE status = 'pending' AND available_at <= ?
                ORDER BY CASE WHEN attempts = 0 THEN 0 ELSE 1 END,
                         enqueued_at, id
                LIMIT ?
                """,
                (current_iso, capacity),
            ).fetchall()
            if not ready:
                return []
            ids = [str(row["id"]) for row in ready]
            connection.executemany(
                """
                UPDATE candidates
                SET status = 'leased', leased_at = ?, attempts = attempts + 1, error = NULL
                WHERE id = ? AND status = 'pending'
                """,
                [(current_iso, candidate_id) for candidate_id in ids],
            )
            return [self._leased_candidate(row) for row in ready]

    def lease_batch(
        self,
        *,
        batch_size: int,
        max_wait_seconds: float,
        lease_seconds: int = 300,
        now: datetime | None = None,
    ) -> list[LeasedCandidate]:
        current = (now or utc_now()).astimezone(timezone.utc)
        current_iso = current.isoformat()
        stale_iso = (current - timedelta(seconds=max(1, lease_seconds))).isoformat()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE candidates
                SET status = 'pending', available_at = ?, leased_at = NULL,
                    error = COALESCE(error, 'stale lease recovered')
                WHERE status = 'leased' AND leased_at <= ?
                """,
                (current_iso, stale_iso),
            )
            ready = connection.execute(
                """
                SELECT * FROM candidates
                WHERE status = 'pending' AND available_at <= ?
                ORDER BY enqueued_at, id
                """,
                (current_iso,),
            ).fetchall()
            if not ready:
                return []
            oldest = datetime.fromisoformat(str(ready[0]["enqueued_at"]))
            waited = (current - oldest).total_seconds()
            if len(ready) < max(1, batch_size) and waited < max(0.0, max_wait_seconds):
                return []
            selected = ready[: max(1, batch_size)]
            ids = [str(row["id"]) for row in selected]
            connection.executemany(
                """
                UPDATE candidates
                SET status = 'leased', leased_at = ?, attempts = attempts + 1, error = NULL
                WHERE id = ? AND status = 'pending'
                """,
                [(current_iso, candidate_id) for candidate_id in ids],
            )
            return [self._leased_candidate(row) for row in selected]

    def _leased_candidate(self, row: sqlite3.Row) -> LeasedCandidate:
        return LeasedCandidate(
            id=str(row["id"]),
            candidate_key=str(row["candidate_key"]),
            platform=str(row["platform"]),
            source_id=str(row["source_id"]),
            fingerprint=str(row["fingerprint"]),
            payload=json.loads(str(row["payload_json"])),
            attempts=int(row["attempts"]) + 1,
            enqueued_at=str(row["enqueued_at"]),
        )

    def complete(self, candidate_ids: Iterable[str], *, now: datetime | None = None) -> None:
        timestamp = (now or utc_now()).astimezone(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.executemany(
                """
                UPDATE candidates
                SET status = 'done', done_at = ?, leased_at = NULL, error = NULL
                WHERE id = ? AND status = 'leased'
                """,
                [(timestamp, candidate_id) for candidate_id in candidate_ids],
            )

    def retry(
        self,
        candidate_ids: Iterable[str],
        *,
        error: str,
        delay_seconds: int,
        now: datetime | None = None,
    ) -> None:
        current = (now or utc_now()).astimezone(timezone.utc)
        available = (current + timedelta(seconds=max(0, delay_seconds))).isoformat()
        safe_error = str(error).replace("\n", " ")[:1000]
        with self._connection() as connection:
            connection.executemany(
                """
                UPDATE candidates
                SET status = 'pending', available_at = ?, leased_at = NULL, error = ?
                WHERE id = ? AND status = 'leased'
                """,
                [(available, safe_error, candidate_id) for candidate_id in candidate_ids],
            )

    def stats(self) -> dict[str, int]:
        counts = {"pending": 0, "leased": 0, "done": 0}
        with self._connection() as connection:
            rows = connection.execute("SELECT status, count(*) AS count FROM candidates GROUP BY status").fetchall()
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
        return counts
