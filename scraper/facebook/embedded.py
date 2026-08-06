"""Parse Facebook Marketplace discovery records embedded in initial HTML."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any


def extract_marketplace_records(script_texts: Iterable[str], *, limit: int) -> list[dict[str, Any]]:
    """Extract unique Marketplace listings from logged-out Relay preloader JSON."""
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for text in script_texts:
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            continue

        for feed_units in marketplace_feeds(payload):
            edges = feed_units.get("edges")
            if not isinstance(edges, list):
                continue
            for edge in edges:
                listing = listing_from_edge(edge)
                record = discovery_record(listing)
                item_id = record.get("itemId") if record else None
                if not record or not isinstance(item_id, str) or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                records.append(record)
                if len(records) >= limit:
                    return records
    return records


def extract_marketplace_detail(script_texts: Iterable[str], *, item_id: str) -> dict[str, str]:
    """Extract seller and description from a Marketplace item Relay payload."""
    target_id = str(item_id or "").strip()
    if not target_id:
        return {}

    best_record: dict[str, str] = {}
    best_score = 0
    for text in script_texts:
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            continue

        for value in walk_objects(payload):
            if str(value.get("id") or "").strip() != target_id:
                continue

            record = detail_record(value)
            score = sum(bool(record.get(field)) for field in ("sellerName", "description"))
            if score > best_score:
                best_record = record
                best_score = score
            if best_score == 2:
                return best_record

    return best_record


def marketplace_feeds(payload: Any) -> Iterator[dict[str, Any]]:
    for value in walk_objects(payload):
        search = value.get("marketplace_search")
        feed_units = search.get("feed_units") if isinstance(search, dict) else None
        if isinstance(feed_units, dict):
            yield feed_units


def walk_objects(payload: Any) -> Iterator[dict[str, Any]]:
    stack = [payload]
    visited: set[int] = set()
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            identity = id(value)
            if identity in visited:
                continue
            visited.add(identity)
            yield value
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)


def listing_from_edge(edge: Any) -> dict[str, Any]:
    if not isinstance(edge, dict):
        return {}
    node = edge.get("node")
    if not isinstance(node, dict):
        return {}
    listing = node.get("listing")
    return listing if isinstance(listing, dict) else node


def discovery_record(listing: dict[str, Any]) -> dict[str, Any] | None:
    item_id = str(listing.get("id") or "").strip()
    title = str(listing.get("marketplace_listing_title") or listing.get("custom_title") or "").strip()
    if not item_id or not title:
        return None

    price = listing.get("listing_price")
    price = price if isinstance(price, dict) else {}
    price_formatted = str(price.get("formatted_amount") or "").strip()
    price_amount = optional_int(price.get("amount"))

    location = listing.get("location")
    reverse_geocode = location.get("reverse_geocode") if isinstance(location, dict) else None
    city_page = reverse_geocode.get("city_page") if isinstance(reverse_geocode, dict) else None
    city = str(city_page.get("display_name") or "").strip() if isinstance(city_page, dict) else ""

    photo = listing.get("primary_listing_photo")
    image = photo.get("image") if isinstance(photo, dict) else None
    image_url = str(image.get("uri") or "").strip() if isinstance(image, dict) else ""

    seller = listing.get("marketplace_listing_seller")
    seller_name = ""
    if isinstance(seller, dict):
        seller_name = str(seller.get("name") or seller.get("display_name") or "").strip()

    raw_text = "\n".join(value for value in (price_formatted, title, city) if value)
    return {
        "itemId": item_id,
        "href": f"https://www.facebook.com/marketplace/item/{item_id}/",
        "price": price_formatted,
        "priceAmount": price_amount,
        "title": title,
        "location": city,
        "image": image_url,
        "imageAlt": title,
        "text": raw_text,
        "sellerName": seller_name,
        "isNewlyListed": bool(listing.get("if_gk_just_listed_tag_on_search_feed")),
        "isLive": optional_bool(listing.get("is_live")),
        "isSold": optional_bool(listing.get("is_sold")),
        "isPending": optional_bool(listing.get("is_pending")),
        "isHidden": optional_bool(listing.get("is_hidden")),
    }


def detail_record(listing: dict[str, Any]) -> dict[str, str]:
    seller = listing.get("marketplace_listing_seller")
    seller_name = ""
    if isinstance(seller, dict):
        seller_name = str(seller.get("name") or seller.get("display_name") or "").strip()

    description = listing.get("redacted_description")
    if isinstance(description, dict):
        description_text = str(description.get("text") or "").strip()
    elif isinstance(description, str):
        description_text = description.strip()
    else:
        description_text = ""

    return {
        "sellerName": seller_name,
        "description": description_text,
    }


def optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None
