"""Shared normalized listing contract for RECON scraper outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


LISTING_KEYS = (
    "platform",
    "sourceUrl",
    "externalId",
    "title",
    "description",
    "category",
    "brand",
    "price",
    "locationTexts",
    "conditionText",
    "sellerName",
    "status",
    "postedAt",
    "firstFetchedAt",
    "lastFetchedAt",
    "images",
)

IMAGE_KEYS = ("sourceUrl", "position", "altText")
PLATFORMS = {"REDDIT", "INSTAGRAM", "FACEBOOK"}
STATUSES = {"AVAILABLE", "SOLD", "UNKNOWN"}


class ListingContractError(ValueError):
    """Raised when connector output does not match the shared listing shape."""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_listing(value: dict[str, Any]) -> dict[str, Any]:
    """Return a cleaned Prisma-facing listing dict or raise ListingContractError."""
    if not isinstance(value, dict):
        raise ListingContractError("listing must be an object")

    cleaned: dict[str, Any] = {key: value.get(key) for key in LISTING_KEYS}
    errors: list[str] = []

    platform = string_or_none(cleaned["platform"])
    if platform:
        platform = platform.upper()
    if platform not in PLATFORMS:
        errors.append("platform must be REDDIT, INSTAGRAM, or FACEBOOK")
    cleaned["platform"] = platform

    status = string_or_none(cleaned["status"])
    if status:
        status = status.upper()
    if status not in STATUSES:
        errors.append("status must be AVAILABLE, SOLD, or UNKNOWN")
    cleaned["status"] = status

    for key in ("sourceUrl", "title", "description", "firstFetchedAt", "lastFetchedAt"):
        if not string_or_none(cleaned[key]):
            errors.append(f"{key} is required")

    cleaned["sourceUrl"] = string_or_none(cleaned["sourceUrl"]) or ""
    cleaned["externalId"] = string_or_none(cleaned["externalId"])
    cleaned["title"] = string_or_none(cleaned["title"]) or ""
    cleaned["description"] = string_or_none(cleaned["description"]) or ""
    cleaned["category"] = string_or_none(cleaned["category"])
    cleaned["brand"] = string_or_none(cleaned["brand"])
    cleaned["conditionText"] = string_or_none(cleaned["conditionText"])
    cleaned["sellerName"] = string_or_none(cleaned["sellerName"])
    cleaned["postedAt"] = iso_datetime_or_none(cleaned["postedAt"], "postedAt", errors)
    cleaned["firstFetchedAt"] = iso_datetime_required(cleaned["firstFetchedAt"], "firstFetchedAt", errors)
    cleaned["lastFetchedAt"] = iso_datetime_required(cleaned["lastFetchedAt"], "lastFetchedAt", errors)

    price = cleaned["price"]
    if price is None:
        cleaned["price"] = None
    elif isinstance(price, bool) or not isinstance(price, int):
        errors.append("price must be an integer or null")
    elif price < 0:
        errors.append("price must be zero or greater")

    locations = cleaned["locationTexts"]
    if locations is None:
        cleaned["locationTexts"] = []
    elif isinstance(locations, list):
        cleaned["locationTexts"] = [item.strip() for item in locations if isinstance(item, str) and item.strip()]
    else:
        errors.append("locationTexts must be a string array")
        cleaned["locationTexts"] = []

    images = cleaned["images"]
    if images is None:
        cleaned["images"] = []
    elif isinstance(images, list):
        cleaned["images"] = validate_images(images, errors)
    else:
        errors.append("images must be an array")
        cleaned["images"] = []

    if errors:
        identity = cleaned.get("externalId") or cleaned.get("sourceUrl") or "<unknown>"
        raise ListingContractError(f"{identity}: {'; '.join(errors)}")

    return cleaned


def validate_listings(values: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        try:
            valid.append(validate_listing(value))
        except ListingContractError as exc:
            invalid.append({"index": index, "error": str(exc), "sourceUrl": value.get("sourceUrl") if isinstance(value, dict) else None})
    return valid, invalid


def validate_images(images: list[Any], errors: list[str]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for index, image in enumerate(images):
        if not isinstance(image, dict):
            errors.append(f"images[{index}] must be an object")
            continue
        source_url = string_or_none(image.get("sourceUrl"))
        if not source_url:
            errors.append(f"images[{index}].sourceUrl is required")
            continue
        position = image.get("position", index)
        if isinstance(position, bool) or not isinstance(position, int):
            errors.append(f"images[{index}].position must be an integer")
            continue
        cleaned.append(
            {
                "sourceUrl": source_url,
                "position": position,
                "altText": string_or_none(image.get("altText")),
            }
        )
    return cleaned


def string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def iso_datetime_required(value: Any, field: str, errors: list[str]) -> str:
    parsed = iso_datetime_or_none(value, field, errors)
    return parsed or ""


def iso_datetime_or_none(value: Any, field: str, errors: list[str]) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        errors.append(f"{field} must be an ISO datetime string or null")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be an ISO datetime string or null")
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()
