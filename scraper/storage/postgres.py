"""PostgreSQL upsert layer for normalized RECON scraper listings."""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


VALID_PLATFORMS = {"REDDIT", "INSTAGRAM", "FACEBOOK"}
VALID_STATUSES = {"AVAILABLE", "SOLD", "UNKNOWN"}
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
        "sslpassword",
        "token",
    }
)


class StorageError(RuntimeError):
    """Raised when scraper storage cannot safely write listings."""


@dataclass(frozen=True)
class DeduplicatedListings:
    listings: list[dict[str, Any]]
    duplicates: int


@dataclass
class UpsertSummary:
    requested: int = 0
    deduplicated: int = 0
    duplicates: int = 0
    inserted: int = 0
    updated: int = 0
    imagesDeleted: int = 0
    imagesInserted: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


UPSERT_LISTING_SQL = """
INSERT INTO listings (
    id,
    platform,
    source_url,
    external_id,
    title,
    description,
    category,
    brand,
    price,
    location_texts,
    condition_text,
    seller_name,
    status,
    posted_at,
    first_fetched_at,
    last_fetched_at
)
VALUES (
    %(id)s,
    %(platform)s::listing_platform,
    %(source_url)s,
    %(external_id)s,
    %(title)s,
    %(description)s,
    %(category)s,
    %(brand)s,
    %(price)s,
    %(location_texts)s::TEXT[],
    %(condition_text)s,
    %(seller_name)s,
    %(status)s::listing_status,
    %(posted_at)s,
    %(first_fetched_at)s,
    %(last_fetched_at)s
)
ON CONFLICT (source_url)
DO UPDATE SET
    platform = EXCLUDED.platform,
    external_id = EXCLUDED.external_id,
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    brand = EXCLUDED.brand,
    price = EXCLUDED.price,
    location_texts = EXCLUDED.location_texts,
    condition_text = EXCLUDED.condition_text,
    seller_name = EXCLUDED.seller_name,
    status = EXCLUDED.status,
    posted_at = EXCLUDED.posted_at,
    last_fetched_at = EXCLUDED.last_fetched_at,
    updated_at = CURRENT_TIMESTAMP
RETURNING id, (xmax = 0) AS inserted
"""

DELETE_IMAGES_SQL = "DELETE FROM listing_images WHERE listing_id = %s"

INSERT_IMAGE_SQL = """
INSERT INTO listing_images (
    id,
    listing_id,
    source_url,
    position,
    alt_text
)
VALUES (
    %(id)s,
    %(listing_id)s,
    %(source_url)s,
    %(position)s,
    %(alt_text)s
)
"""


def require_database_url(explicit_url: str | None) -> str:
    value = explicit_url or os.environ.get("SCRAPER_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not value:
        raise StorageError("Set SCRAPER_DATABASE_URL or DATABASE_URL before using --write-db.")
    scheme = urlsplit(value).scheme
    if scheme not in {"postgresql", "postgres"}:
        raise StorageError("Database URL must use postgresql:// or postgres://.")
    return value


def safe_database_url(url: str | None) -> str | None:
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

        auth = parts.username or ""
        if auth:
            auth = f"{auth}:***@"

        port = f":{parts.port}" if parts.port else ""
        netloc = f"{auth}{host}{port}"

    return urlunsplit((parts.scheme, netloc, parts.path, query, fragment))


def deduplicate_listings(listings: list[dict[str, Any]]) -> DeduplicatedListings:
    by_source_url: dict[str, dict[str, Any]] = {}
    duplicates = 0

    for listing in listings:
        source_url = str(listing.get("sourceUrl") or "").strip()
        if not source_url:
            raise StorageError("Cannot write listing without sourceUrl.")
        if source_url in by_source_url:
            duplicates += 1
        by_source_url[source_url] = listing

    return DeduplicatedListings(listings=list(by_source_url.values()), duplicates=duplicates)


def listing_to_db_row(listing: dict[str, Any], listing_id: str | None = None) -> dict[str, Any]:
    return {
        "id": listing_id or new_record_id(),
        "platform": enum_to_db_value(listing.get("platform"), VALID_PLATFORMS, "platform"),
        "source_url": required_string(listing.get("sourceUrl"), "sourceUrl"),
        "external_id": optional_string(listing.get("externalId")),
        "title": required_string(listing.get("title"), "title"),
        "description": required_string(listing.get("description"), "description"),
        "category": optional_string(listing.get("category")),
        "brand": optional_string(listing.get("brand")),
        "price": optional_int(listing.get("price"), "price"),
        "location_texts": string_list(listing.get("locationTexts")),
        "condition_text": optional_string(listing.get("conditionText")),
        "seller_name": optional_string(listing.get("sellerName")),
        "status": enum_to_db_value(listing.get("status"), VALID_STATUSES, "status"),
        "posted_at": utc_naive_datetime(listing.get("postedAt"), "postedAt", required=False),
        "first_fetched_at": utc_naive_datetime(listing.get("firstFetchedAt"), "firstFetchedAt", required=True),
        "last_fetched_at": utc_naive_datetime(listing.get("lastFetchedAt"), "lastFetchedAt", required=True),
    }


def image_rows(listing_id: str, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_position: dict[int, dict[str, Any]] = {}

    for image in images:
        position = optional_int(image.get("position"), "images.position")
        if position is None:
            raise StorageError("Image position is required.")
        source_url = required_string(image.get("sourceUrl"), "images.sourceUrl")
        by_position[position] = {
            "id": new_record_id(),
            "listing_id": listing_id,
            "source_url": source_url,
            "position": position,
            "alt_text": optional_string(image.get("altText")),
        }

    return [by_position[position] for position in sorted(by_position)]


def upsert_listings(database_url: str | None, listings: list[dict[str, Any]]) -> UpsertSummary:
    url = require_database_url(database_url)

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - covered by runtime verification.
        raise StorageError("Install scraper database dependencies with: python -m pip install -r scraper/requirements.txt") from exc

    try:
        with psycopg.connect(url, connect_timeout=15) as connection:
            return upsert_listings_with_connection(connection, listings)
    except psycopg.Error as exc:
        raise StorageError(f"Database write failed: {type(exc).__name__}") from exc


def upsert_listings_with_connection(connection: Any, listings: list[dict[str, Any]]) -> UpsertSummary:
    deduplicated = deduplicate_listings(listings)
    summary = UpsertSummary(
        requested=len(listings),
        deduplicated=len(deduplicated.listings),
        duplicates=deduplicated.duplicates,
    )

    with connection.transaction():
        with connection.cursor() as cursor:
            for listing in deduplicated.listings:
                row = listing_to_db_row(listing)
                cursor.execute(UPSERT_LISTING_SQL, row)
                result = cursor.fetchone()
                if not result:
                    raise StorageError("Listing upsert did not return a row.")

                listing_id, inserted = result
                if inserted:
                    summary.inserted += 1
                else:
                    summary.updated += 1

                cursor.execute(DELETE_IMAGES_SQL, (listing_id,))
                summary.imagesDeleted += max(cursor.rowcount or 0, 0)

                rows = image_rows(str(listing_id), listing.get("images") or [])
                if rows:
                    cursor.executemany(INSERT_IMAGE_SQL, rows)
                    summary.imagesInserted += len(rows)

    return summary


def enum_to_db_value(value: Any, allowed: set[str], field: str) -> str:
    if value is None:
        raise StorageError(f"{field} is required.")
    normalized = str(value).strip().upper()
    if normalized not in allowed:
        raise StorageError(f"{field} must be one of: {', '.join(sorted(allowed))}.")
    return normalized.lower()


def required_string(value: Any, field: str) -> str:
    parsed = optional_string(value)
    if parsed is None:
        raise StorageError(f"{field} is required.")
    return parsed


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    parsed = str(value).strip()
    return parsed or None


def optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise StorageError(f"{field} must be an integer or null.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise StorageError(f"{field} must be an integer or null.") from exc
    if parsed < 0:
        raise StorageError(f"{field} must be zero or greater.")
    return parsed


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StorageError("locationTexts must be a list.")
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def utc_naive_datetime(value: Any, field: str, *, required: bool) -> datetime | None:
    if value in {None, ""}:
        if required:
            raise StorageError(f"{field} is required.")
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise StorageError(f"{field} must be an ISO datetime.") from exc
    else:
        raise StorageError(f"{field} must be an ISO datetime.")

    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def new_record_id() -> str:
    return uuid.uuid4().hex
