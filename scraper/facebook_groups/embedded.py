"""Parse Facebook Group stories from embedded and streamed Relay JSON."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def extract_group_posts(
    script_texts: Iterable[str],
    response_texts: Iterable[str] = (),
    *,
    group_id: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return the newest unique outer stories for one configured group."""
    by_id: dict[str, dict[str, Any]] = {}
    for text in (*list(script_texts), *list(response_texts)):
        for payload in parse_json_payloads(text):
            for value in walk_objects_without_attached(payload):
                post_id = scalar_id(value.get("post_id"))
                if not post_id or not looks_like_story(value):
                    continue
                record = story_record(value)
                if not record or record.get("groupId") != group_id:
                    continue
                existing = by_id.get(post_id)
                by_id[post_id] = merge_records(existing, record) if existing else record

    ordered = sorted(
        by_id.values(),
        key=lambda item: (int(item.get("publishedTimestamp") or 0), str(item.get("postId") or "")),
        reverse=True,
    )
    return ordered[: max(1, limit)]


def parse_json_payloads(text: str) -> Iterator[Any]:
    raw = str(text or "").strip()
    if not raw:
        return
    if raw.startswith("for (;;);"):
        raw = raw[len("for (;;);") :]
    try:
        yield json.loads(raw)
        return
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    cursor = 0
    while cursor < len(raw):
        positions = [position for position in (raw.find("{", cursor), raw.find("[", cursor)) if position >= 0]
        if not positions:
            return
        start = min(positions)
        try:
            payload, end = decoder.raw_decode(raw, start)
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        yield payload
        cursor = end


def walk_objects(payload: Any) -> Iterator[dict[str, Any]]:
    stack = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            yield value
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)


def looks_like_story(value: dict[str, Any]) -> bool:
    return any(
        key in value
        for key in (
            "message",
            "actors",
            "target_group",
            "attachments",
            "attached_story",
            "comet_sections",
            "permalink_url",
            "wwwURL",
        )
    )


def story_record(story: dict[str, Any]) -> dict[str, Any] | None:
    post_id = scalar_id(story.get("post_id"))
    target_group = story.get("target_group")
    group_id = scalar_id(target_group.get("id")) if isinstance(target_group, dict) else ""
    if not post_id or not group_id:
        return None

    attached = attached_story(story)
    message = message_text(story)
    images = photo_records(story)
    actor = actor_record(story)
    used_attached_story = False
    if attached:
        if not message:
            message = message_text(attached)
            used_attached_story = bool(message)
        if not images:
            images = photo_records(attached)
            used_attached_story = used_attached_story or bool(images)
        if not actor:
            actor = actor_record(attached)

    commerce = commerce_record(story)
    if attached:
        commerce = {**commerce_record(attached), **commerce}

    return {
        "postId": post_id,
        "groupId": group_id,
        "permalink": canonical_facebook_url(story_url(story)),
        "message": message,
        "sellerId": scalar_id(actor.get("id")) if actor else "",
        "sellerName": str(actor.get("name") or "").strip() if actor else "",
        "publishedTimestamp": story_timestamp(story),
        "images": images,
        "commerce": commerce,
        "usedAttachedStory": used_attached_story,
    }


def merge_records(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in ("permalink", "message", "sellerId", "sellerName"):
        if not merged.get(key) and incoming.get(key):
            merged[key] = incoming[key]
    merged["publishedTimestamp"] = max(
        int(existing.get("publishedTimestamp") or 0),
        int(incoming.get("publishedTimestamp") or 0),
    )
    merged["usedAttachedStory"] = bool(existing.get("usedAttachedStory") or incoming.get("usedAttachedStory"))
    merged["commerce"] = {**(existing.get("commerce") or {}), **(incoming.get("commerce") or {})}

    seen_urls: set[str] = set()
    images: list[dict[str, str]] = []
    for image in [*(existing.get("images") or []), *(incoming.get("images") or [])]:
        url = str(image.get("url") or "").strip() if isinstance(image, dict) else ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        images.append({"url": url, "alt": str(image.get("alt") or "").strip()})
    merged["images"] = images
    return merged


def attached_story(story: dict[str, Any]) -> dict[str, Any]:
    direct = story.get("attached_story")
    if isinstance(direct, dict):
        return direct
    for value in walk_objects(story):
        candidate = value.get("attached_story")
        if isinstance(candidate, dict):
            return candidate
    return {}


def message_text(story: dict[str, Any]) -> str:
    direct = text_field(story.get("message"))
    if direct:
        return direct
    for value in walk_objects_without_attached(story):
        text = text_field(value.get("message"))
        if text:
            return text
    return ""


def text_field(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    text = value.get("text")
    return str(text or "").strip() if not isinstance(text, dict) else text_field(text)


def actor_record(story: dict[str, Any]) -> dict[str, Any]:
    actors = story.get("actors")
    if isinstance(actors, list):
        for actor in actors:
            if isinstance(actor, dict) and (actor.get("id") or actor.get("name")):
                return actor
    for value in walk_objects_without_attached(story):
        actors = value.get("actors")
        if not isinstance(actors, list):
            continue
        for actor in actors:
            if isinstance(actor, dict) and (actor.get("id") or actor.get("name")):
                return actor
    return {}


def photo_records(story: dict[str, Any]) -> list[dict[str, str]]:
    roots: list[Any] = []
    for value in walk_objects_without_attached(story):
        attachments = value.get("attachments")
        if isinstance(attachments, (list, dict)):
            roots.append(attachments)

    images: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in roots:
        for value in walk_objects(root):
            if str(value.get("__typename") or "") != "Photo":
                continue
            url = first_image_uri(value)
            if not url or url in seen:
                continue
            seen.add(url)
            images.append(
                {
                    "url": url,
                    "alt": str(value.get("accessibility_caption") or "").strip(),
                }
            )
    return images


def first_image_uri(photo: dict[str, Any]) -> str:
    for key in ("image", "viewer_image", "photo_image"):
        image = photo.get(key)
        if isinstance(image, dict):
            uri = str(image.get("uri") or image.get("url") or "").strip()
            if uri.startswith("https://"):
                return uri
    for value in walk_objects(photo):
        uri = str(value.get("uri") or "").strip()
        if uri.startswith("https://") and "fbcdn" in (urlsplit(uri).hostname or "").lower():
            return uri
    return ""


def commerce_record(story: dict[str, Any]) -> dict[str, Any]:
    for value in walk_objects_without_attached(story):
        if str(value.get("__typename") or "") != "GroupCommerceProductItem":
            continue
        price = value.get("formatted_price")
        location = value.get("location_text")
        seller = value.get("marketplace_listing_seller")
        return {
            "productId": scalar_id(value.get("id") or nested_id(value.get("product_item"))),
            "formattedPrice": text_field(price),
            "locationText": text_field(location),
            "sellerId": scalar_id(seller.get("id")) if isinstance(seller, dict) else "",
            "sellerName": str(seller.get("name") or "").strip() if isinstance(seller, dict) else "",
        }
    return {}


def nested_id(value: Any) -> str:
    return scalar_id(value.get("id")) if isinstance(value, dict) else ""


def story_url(story: dict[str, Any]) -> str:
    for key in ("permalink_url", "url", "wwwURL"):
        value = str(story.get(key) or "").strip()
        if value.startswith("https://") and "/groups/" in value:
            return value
    for value in walk_objects_without_attached(story):
        for key in ("permalink_url", "url", "wwwURL"):
            candidate = str(value.get(key) or "").strip()
            if candidate.startswith("https://") and "/groups/" in candidate and "/posts/" in candidate:
                return candidate
    return ""


def canonical_facebook_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"facebook.com", "www.facebook.com"}:
        return ""
    return urlunsplit(("https", "www.facebook.com", parsed.path.rstrip("/") + "/", "", ""))


def story_timestamp(story: dict[str, Any]) -> int:
    for key in ("creation_time", "publish_time"):
        value = optional_int(story.get(key))
        if value:
            return value
    for value in walk_objects_without_attached(story):
        for key in ("creation_time", "publish_time"):
            timestamp = optional_int(value.get(key))
            if timestamp:
                return timestamp
    return 0


def timestamp_iso(value: Any) -> str | None:
    timestamp = optional_int(value)
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def scalar_id(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    return str(value).strip()


def walk_objects_without_attached(payload: Any) -> Iterator[dict[str, Any]]:
    stack = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            yield value
            stack.extend(item for key, item in value.items() if key != "attached_story")
        elif isinstance(value, list):
            stack.extend(value)
