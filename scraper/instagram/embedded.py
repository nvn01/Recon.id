"""Parse public Instagram profile timeline data embedded in initial HTML."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any


TIMELINE_KEYS = (
    "polaris_ordered_timeline_connection",
    "edge_owner_to_timeline_media",
)


def extract_profile_posts(script_texts: Iterable[str]) -> list[dict[str, Any]]:
    """Return canonical recent posts from logged-out profile JSON scripts."""
    by_shortcode: dict[str, dict[str, Any]] = {}
    for text in script_texts:
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            continue

        for connection in timeline_connections(payload):
            edges = connection.get("edges")
            if not isinstance(edges, list):
                continue
            for edge in edges:
                node = edge.get("node") if isinstance(edge, dict) else None
                if not isinstance(node, dict):
                    continue
                post = canonical_post(node)
                shortcode = str(post.get("shortcode") or "")
                if not shortcode:
                    continue
                current = by_shortcode.get(shortcode)
                if current is None or post_sort_key(post) > post_sort_key(current):
                    by_shortcode[shortcode] = post

    return sorted(by_shortcode.values(), key=post_sort_key, reverse=True)


def timeline_connections(payload: Any) -> Iterator[dict[str, Any]]:
    for value in walk_objects(payload):
        for key in TIMELINE_KEYS:
            connection = value.get(key)
            if isinstance(connection, dict):
                yield connection


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


def canonical_post(node: dict[str, Any]) -> dict[str, Any]:
    post = dict(node)
    shortcode = str(node.get("code") or node.get("shortcode") or "")
    pk = str(node.get("pk") or node.get("id") or "")
    timestamp = integer_value(node.get("taken_at") or node.get("taken_at_timestamp"))
    caption = caption_value(node)
    display_url = first_image_url(node)

    post["shortcode"] = shortcode
    post["pk"] = pk
    if timestamp:
        post["taken_at_timestamp"] = timestamp
    if caption:
        post["edge_media_to_caption"] = {"edges": [{"node": {"text": caption}}]}
    if display_url:
        post["display_url"] = display_url

    children = node.get("carousel_media")
    if isinstance(children, list):
        sidecar_edges = []
        for child in children:
            if not isinstance(child, dict):
                continue
            child_url = first_image_url(child)
            if child_url:
                sidecar_edges.append({"node": {"display_url": child_url}})
        if sidecar_edges:
            post["edge_sidecar_to_children"] = {"edges": sidecar_edges}
    return post


def caption_value(node: dict[str, Any]) -> str:
    caption = node.get("caption")
    if isinstance(caption, dict):
        return str(caption.get("text") or "").strip()
    edges = node.get("edge_media_to_caption", {}).get("edges", [])
    if isinstance(edges, list) and edges:
        first = edges[0] if isinstance(edges[0], dict) else {}
        child = first.get("node") if isinstance(first, dict) else {}
        if isinstance(child, dict):
            return str(child.get("text") or "").strip()
    return ""


def first_image_url(node: dict[str, Any]) -> str:
    for key in ("display_uri", "display_url", "thumbnail_src"):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value

    versions = node.get("image_versions2")
    candidates = versions.get("candidates") if isinstance(versions, dict) else None
    if isinstance(candidates, list):
        for candidate in candidates:
            url = candidate.get("url") if isinstance(candidate, dict) else None
            if isinstance(url, str) and url:
                return url
    return ""


def post_sort_key(post: dict[str, Any]) -> tuple[int, int, int]:
    timestamp = integer_value(post.get("taken_at_timestamp"))
    pk = integer_value(post.get("pk"))
    return (1 if timestamp else 0, timestamp, pk)


def integer_value(value: Any) -> int:
    if isinstance(value, bool) or value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
