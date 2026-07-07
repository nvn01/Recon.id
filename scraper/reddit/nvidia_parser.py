from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b"

PARSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "externalId": {"type": "string"},
                    "price": {"type": ["integer", "null"]},
                    "locationTexts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "conditionText": {"type": ["string", "null"]},
                    "status": {
                        "type": ["string", "null"],
                        "enum": ["AVAILABLE", "SOLD", "UNKNOWN", None],
                    },
                    "category": {"type": ["string", "null"]},
                    "brand": {"type": ["string", "null"]},
                },
                "required": [
                    "externalId",
                    "price",
                    "locationTexts",
                    "conditionText",
                    "status",
                    "category",
                    "brand",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}


class NvidiaParserError(RuntimeError):
    pass


def enrich_listings_with_nvidia(
    listings: list[dict[str, Any]],
    *,
    model: str | None = None,
    batch_size: int = 5,
    rate_limit_seconds: float = 2.0,
    timeout: int = 45,
    prefer_ai: bool = False,
) -> list[dict[str, Any]]:
    load_dotenv_if_present()
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        raise NvidiaParserError("NVIDIA_API_KEY is not configured")

    selected_model = model or os.environ.get("NVIDIA_PARSE_MODEL", DEFAULT_MODEL)
    base_url = os.environ.get("NVIDIA_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    client = NvidiaParseClient(api_key=api_key, base_url=base_url, model=selected_model, timeout=timeout)

    enriched: list[dict[str, Any]] = []
    for index in range(0, len(listings), batch_size):
        batch = listings[index : index + batch_size]
        if index:
            time.sleep(max(0.0, rate_limit_seconds))
        analyses = client.parse_batch(batch)
        enriched.extend(merge_ai_results(batch, analyses, prefer_ai=prefer_ai))
    return enriched


class NvidiaParseClient:
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: int) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def parse_batch(self, listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payload = self._build_payload(listings, guided=True)
        try:
            return self._request(payload)
        except NvidiaParserError:
            return self._request(self._build_payload(listings, guided=False))

    def _request(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = safe_error_body(exc)
            raise NvidiaParserError(f"NVIDIA parser HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise NvidiaParserError(f"NVIDIA parser request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise NvidiaParserError("NVIDIA parser returned invalid response JSON") from exc

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return parse_model_json(content).get("items", [])

    def _build_payload(self, listings: list[dict[str, Any]], *, guided: bool) -> dict[str, Any]:
        prompt = build_prompt(listings)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract Indonesian used computer, laptop, PC part, and peripheral sale listing fields. "
                        "Return only JSON. Do not guess: use null for fields not supported by text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "top_p": 0.7,
            "max_tokens": 2048,
            "stream": False,
        }
        if guided:
            payload["nvext"] = {"guided_json": PARSE_SCHEMA}
        return payload


def build_prompt(listings: list[dict[str, Any]]) -> str:
    items = []
    for listing in listings:
        items.append(
            {
                "externalId": listing.get("externalId") or "",
                "title": listing.get("title") or "",
                "description": listing.get("description") or "",
                "ruleParsed": {
                    "price": listing.get("price"),
                    "locationTexts": listing.get("locationTexts") or [],
                    "conditionText": listing.get("conditionText"),
                    "status": listing.get("status"),
                    "category": listing.get("category"),
                    "brand": listing.get("brand"),
                },
            }
        )

    return (
        "Extract listing fields from these Indonesian used-item sale listings.\n"
        "Rules:\n"
        "- price must be integer rupiah, no punctuation, no currency string.\n"
        "- Shorthand Indonesian prices: 9.6jt = 9600000, 3.5 juta = 3500000, 350rb = 350000.\n"
        "- If price is ambiguous, return null.\n"
        "- status must be AVAILABLE, SOLD, UNKNOWN, or null.\n"
        "- locationTexts must be an array. Return multiple public areas/cities when the post gives more than one.\n"
        "- Keep conditionText as short text copied or lightly normalized from the post.\n"
        "- category must be a broad product group such as Laptop, Handheld PC, GPU, RAM, Storage, Monitor, Keyboard, Mouse, Network Adapter, Peripheral, or Desktop PC.\n"
        "- brand must be the product brand or manufacturer only, not the seller name.\n"
        "- Do not extract model, specs, warranty, minus, evidence, confidence, or notes. Those remain in the original description field.\n"
        f"Return JSON matching this schema: {json.dumps(PARSE_SCHEMA, ensure_ascii=False)}\n\n"
        f"Items:\n{json.dumps({'items': items}, ensure_ascii=False)}"
    )


def merge_ai_results(
    listings: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    *,
    prefer_ai: bool,
) -> list[dict[str, Any]]:
    by_id = {
        str(item.get("externalId") or ""): item
        for item in analyses
        if isinstance(item, dict)
    }
    merged: list[dict[str, Any]] = []
    for listing in listings:
        item = dict(listing)
        analysis = by_id.get(str(item.get("externalId") or ""))
        if analysis:
            apply_field(item, analysis, "price", prefer_ai=prefer_ai)
            apply_field(item, analysis, "locationTexts", prefer_ai=prefer_ai)
            apply_field(item, analysis, "conditionText", prefer_ai=prefer_ai)
            apply_field(item, analysis, "status", prefer_ai=prefer_ai)
            apply_field(item, analysis, "category", prefer_ai=prefer_ai)
            apply_field(item, analysis, "brand", prefer_ai=prefer_ai)
        merged.append(item)
    return merged


def apply_field(item: dict[str, Any], analysis: dict[str, Any], field: str, *, prefer_ai: bool) -> None:
    value = analysis.get(field)
    if field == "price":
        value = normalize_ai_price(value)
    elif field == "locationTexts":
        value = normalize_ai_locations(value)
    elif field == "status":
        value = normalize_ai_status(value)
    else:
        value = blank_to_none(value)

    if value is None or value == []:
        return
    if prefer_ai or item.get(field) in (None, "", "UNKNOWN", []):
        item[field] = value


def normalize_ai_price(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if 10_000 <= value <= 200_000_000 else None
    if isinstance(value, float):
        amount = int(value)
        return amount if 10_000 <= amount <= 200_000_000 else None
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            amount = int(digits)
            return amount if 10_000 <= amount <= 200_000_000 else None
    return None


def normalize_ai_status(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    status = value.strip().upper()
    return status if status in {"AVAILABLE", "SOLD", "UNKNOWN"} else None


def normalize_ai_locations(value: Any) -> list[str]:
    raw_values: list[Any]
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, str):
        raw_values = [part for part in value.replace("/", ",").split(",")]
    else:
        return []

    seen: set[str] = set()
    locations: list[str] = []
    for raw_value in raw_values:
        location = blank_to_none(raw_value)
        if not location:
            continue
        location = location[:160]
        key = location.casefold()
        if key in seen:
            continue
        seen.add(key)
        locations.append(location)
        if len(locations) >= 8:
            break
    return locations


def blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def parse_model_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NvidiaParserError("NVIDIA parser returned non-JSON content") from exc
    if not isinstance(parsed, dict):
        raise NvidiaParserError("NVIDIA parser JSON root was not an object")
    return parsed


def safe_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        text = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    text = text.replace(os.environ.get("NVIDIA_API_KEY", ""), "[redacted]")
    return text[:500]


def load_dotenv_if_present() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value
