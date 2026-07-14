from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b"
DEFAULT_STATE_FILE = Path(__file__).resolve().parents[1] / ".state" / "nvidia_ai.json"
DEFAULT_COOLDOWN_SECONDS = 300
INVALID_OUTPUT_FAILURE_THRESHOLD = 2
MAX_OUTPUT_TOKENS = 4096

SYSTEM_PROMPT = """
You are RECON's strict semantic parser for Indonesian second-hand technology listings.
You receive batches from Reddit, Instagram, or Facebook Marketplace and must return only JSON that
matches the supplied schema. Do not use Markdown, explanations, notes, confidence, or extra keys.

Output discipline:
- Return exactly one result for every input item, with the exact same externalId. Do not omit,
  duplicate, rename, reorder across items, or invent an externalId.
- All semantic fields are AI-owned. There is no local rule-parser output to preserve or prefer.
- Inspect the title, description, platform, and sourceFacts together. Do not return null just
  to avoid reasoning. Make the best evidence-based inference unless a rule below explicitly requires
  null.
- Never copy a whole title, description, URL, phone number, seller advertisement, or specification
  block into conditionText, locationTexts, category, or brand.
- isListing is true only when the item is actually offering a product for sale. It is false for
  memes, announcements, reviews, promotions without a specific offered item, and wanted-to-buy posts.
- title is a concise product title derived from the seller text. Do not use a caption paragraph,
  promotional slogan, price, location, or contact instruction as the title.
- price is the seller's asking price normalized to integer rupiah. Market knowledge may choose the
  scale of a seller-written shorthand, but must not invent a different base asking price.
- status must be AVAILABLE, SOLD, UNKNOWN, or null and must come from the listing evidence.
- category is the broad type of the primary item being sold. brand is the manufacturer of that
  primary item, not the seller and not a component mentioned in its specifications.

Facebook Marketplace rules:
- Facebook card text is compact and may combine price, title, and location. Separate those concepts;
  never treat the entire card line as one extracted field.

- conditionText:
  1. Normalize conditionText to exactly one of: "Baru / BNIB", "Like New", "Bekas - baik",
     "Bekas - normal", "Bekas - minus", or null.
  2. Use "Bekas - baik" for explicit mulus/no-minus/very-good wording.
  3. Use "Bekas - normal" for ordinary used/second/pemakaian wording without a defect.
  4. Use "Bekas - minus" when a defect, damage, or repair need is stated.
  5. Use "Baru / BNIB" for baru, BNIB, BNOB, sealed, or equivalent unused wording.
  6. Use null when no condition evidence exists. Do not invent condition quality.
  7. A condition must not be the product title, specs, location, price, contact instruction, URL, or
     seller promotion.

- category and brand:
  1. Identify the primary product from the title before considering specs or bundled accessories.
  2. A laptop containing Core i5, RAM, SSD, Radeon, NVIDIA, or VGA remains category Laptop; those are
     specifications, not the primary product category. Its brand is the laptop maker.
  3. A monitor containing VGA, HDMI, IPS, GPU-related compatibility, or a bundled cable remains
     category Monitor.
  4. A motherboard containing DDR3/DDR4/DDR5, RAM support, CPU names, or an M.2 slot remains category
     Motherboard.
  5. PS2/PS3/PS4/PS5, Xbox, and Nintendo console hardware -> Game Console. A game disc/cartridge ->
     Game. A stick, controller, gamepad, or Joy-Con sold separately -> Controller.
  6. Steam Deck, ROG Ally, Legion Go, and similar portable PCs -> Handheld PC.
  7. ROG Ally -> brand ASUS even when Xbox compatibility is mentioned. An HP laptop with Intel or
     NVIDIA specs -> brand HP. An LG monitor with VGA/HDMI -> brand LG.
  8. Infer from distinctive model families when possible. Use null only when neither text nor a known
     model family supports a brand or category.

- locationTexts:
  1. Return only public geographic place names such as city, regency, district, or area.
  2. Return concise canonical area names, not the seller's whole location sentence.
  3. "COD Laptop Second Murah ..." does not make "Laptop Second Murah ..." a location. COD is a
     transaction method unless followed by a real place name.
  4. Never return a phone number, price, delivery method, product title, seller slogan, or full address.

- price:
  1. Return null for Gratis/Free/Rp0, "tanya harga", "ask price", DM/PM/chat/inbox-for-price, or an
     obvious contact-only/dummy price such as 12345, 123456, repeated placeholder digits, or another
     number whose surrounding text clearly says the real price must be requested from the seller.
  2. Bare small values such as 1, 100, 200, 450, 800, 1900, 2650, or 3000 are not automatically dummy
     values. Infer the intended rupiah scale from the primary product and realistic Indonesian used
     pricing.
  3. PS4 2650 -> 2650000; PS4 3000 -> 3000000; a low-end used laptop priced 1 can mean 1000000;
     mouse/keyboard 100 can mean 100000; controller 200 can mean 200000; monitor 800 can mean 800000;
     PS5 11 can mean 11000000 when that scale fits the exact product.
  4. Do not assume every value below 100 means millions. Steam Deck 65 can mean 6500000 rather than
     65000000; a PS4 controller 85 can mean 85000 rather than 85000000.
  5. Standard shorthand remains exact: 9.6jt -> 9600000, 3.5 juta -> 3500000, 350rb -> 350000.
  6. If the seller's raw number and product make one scale clearly more likely, return that normalized
     scale. If the number is a contact placeholder, return null instead of estimating a market price.

Instagram-specific examples remain: Rode VideoMic -> brand Rode and category Audio or Peripheral;
Xiaomi 13 Ultra -> brand Xiaomi and category Smartphone; Call of Duty / Black Ops -> brand Activision
and category Game; Genki Sase Switch -> brand Genki and category Controller; Moza R3 -> brand Moza and
category Peripheral; Gigabyte H610M -> brand Gigabyte and category Motherboard; XPG CORE REACTOR PSU ->
brand ADATA and category Power Supply; Attack Shark R3 -> brand Attack Shark and category Mouse;
Corsair K100/K70 -> brand Corsair and category Keyboard; BenQ Zowie XL2411K -> brand BenQ and category
Monitor.

Do not extract model, specs, warranty, minus details, evidence, confidence, or notes as new output
keys. Those remain available in the original description.
""".strip()

PARSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "externalId": {"type": "string"},
                    "isListing": {"type": "boolean"},
                    "title": {"type": "string"},
                    "price": {"type": ["integer", "null"]},
                    "locationTexts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "conditionText": {
                        "type": ["string", "null"],
                        "enum": [
                            "Baru / BNIB",
                            "Like New",
                            "Bekas - baik",
                            "Bekas - normal",
                            "Bekas - minus",
                            None,
                        ],
                    },
                    "status": {
                        "type": ["string", "null"],
                        "enum": ["AVAILABLE", "SOLD", "UNKNOWN", None],
                    },
                    "category": {"type": ["string", "null"]},
                    "brand": {"type": ["string", "null"]},
                },
                "required": [
                    "externalId",
                    "isListing",
                    "title",
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
        enriched.extend(merge_ai_results(batch, analyses))
    return enriched


class NvidiaParseClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int,
        state_path: Path | None = None,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.state_path = state_path or DEFAULT_STATE_FILE
        self.cooldown_seconds = max(60, cooldown_seconds)

    def parse_batch(self, listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._ensure_circuit_closed()
        payload = self._build_payload(listings, guided=True)
        try:
            analyses = self._request(payload)
        except NvidiaParserError as exc:
            if not is_guided_json_rejection(exc):
                self._record_failure(exc)
                raise
            try:
                analyses = self._request(self._build_payload(listings, guided=False))
            except NvidiaParserError as fallback_exc:
                self._record_failure(fallback_exc)
                raise

        try:
            validate_ai_batch_result(listings, analyses)
        except NvidiaParserError as exc:
            self._record_failure(exc)
            raise
        self._record_success()
        return analyses

    def _ensure_circuit_closed(self) -> None:
        state = load_circuit_state(self.state_path)
        cooldown_until = parse_datetime(state.get("cooldown_until"))
        if not cooldown_until:
            return
        remaining = int((cooldown_until - now_utc()).total_seconds())
        if remaining <= 0:
            self._record_success()
            return
        reason = str(state.get("last_failure_kind") or "AI failure")
        raise NvidiaParserError(f"NVIDIA parser cooling down for {remaining}s after {reason}")

    def _record_failure(self, exc: NvidiaParserError) -> None:
        kind = classify_nvidia_error(exc)
        state = load_circuit_state(self.state_path)
        failures = int(state.get("consecutive_failures") or 0) + 1
        should_open = kind in {"capacity", "rate_limit"} or (
            kind == "invalid_output" and failures >= INVALID_OUTPUT_FAILURE_THRESHOLD
        )
        next_state: dict[str, Any] = {
            "consecutive_failures": failures,
            "last_failure_at": now_utc().isoformat(),
            "last_failure_kind": kind,
            "cooldown_until": None,
        }
        if should_open:
            next_state["cooldown_until"] = (
                now_utc() + timedelta(seconds=self.cooldown_seconds)
            ).isoformat()
        save_circuit_state(self.state_path, next_state)

    def _record_success(self) -> None:
        self.state_path.unlink(missing_ok=True)

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
                    "content": SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "top_p": 0.7,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "stream": False,
        }
        if guided:
            payload["nvext"] = {"guided_json": PARSE_SCHEMA}
        return payload


def validate_ai_batch_result(
    listings: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
) -> None:
    expected_ids = [str(listing.get("externalId") or "") for listing in listings]
    returned_ids = [
        str(item.get("externalId") or "")
        for item in analyses
        if isinstance(item, dict)
    ]
    if len(returned_ids) != len(expected_ids) or set(returned_ids) != set(expected_ids):
        raise NvidiaParserError("NVIDIA parser did not return exactly one result for every listing")


def is_guided_json_rejection(exc: NvidiaParserError) -> bool:
    message = str(exc).lower()
    rejected_request = "http 400" in message or "http 422" in message
    guided_marker = any(marker in message for marker in ("guided_json", "nvext", "json schema"))
    return rejected_request and guided_marker


def classify_nvidia_error(exc: NvidiaParserError) -> str:
    message = str(exc).lower()
    if "http 429" in message or "rate limit" in message:
        return "rate_limit"
    if "http 503" in message or "resourceexhausted" in message or "request limit reached" in message:
        return "capacity"
    if any(
        marker in message
        for marker in (
            "non-json",
            "invalid response json",
            "exactly one result",
            "json root was not an object",
        )
    ):
        return "invalid_output"
    if "request failed" in message:
        return "transport"
    return "other"


def load_circuit_state(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_circuit_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(state, separators=(",", ":")) + "\n", encoding="utf-8")
    temp_path.replace(path)


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def build_prompt(listings: list[dict[str, Any]]) -> str:
    items = []
    for listing in listings:
        items.append(
            {
                "platform": listing.get("platform") or "",
                "externalId": listing.get("externalId") or "",
                "title": listing.get("title") or "",
                "description": listing.get("description") or "",
                "sourceFacts": {
                    "sellerName": listing.get("sellerName"),
                    "postedAt": listing.get("postedAt"),
                    **(
                        listing.get("_sourceFacts")
                        if isinstance(listing.get("_sourceFacts"), dict)
                        else {}
                    ),
                },
            }
        )

    return (
        "Review and enrich every listing below according to the system instructions.\n"
        "Return one item per input in the same order, using each externalId exactly once.\n"
        f"Return JSON matching this schema: {json.dumps(PARSE_SCHEMA, ensure_ascii=False)}\n\n"
        f"Items:\n{json.dumps({'items': items}, ensure_ascii=False)}"
    )


def merge_ai_results(
    listings: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        str(item.get("externalId") or ""): item
        for item in analyses
        if isinstance(item, dict)
    }
    expected_ids = [str(listing.get("externalId") or "") for listing in listings]
    if len(by_id) != len(expected_ids) or set(by_id) != set(expected_ids):
        raise NvidiaParserError("NVIDIA parser did not return exactly one result for every listing")

    merged: list[dict[str, Any]] = []
    for listing in listings:
        item = dict(listing)
        analysis = by_id.get(str(item.get("externalId") or ""))
        if analysis:
            if analysis.get("isListing") is not True:
                continue
            item["title"] = blank_to_none(analysis.get("title")) or item["title"]
            item["price"] = normalize_ai_price(analysis.get("price"))
            item["locationTexts"] = normalize_ai_locations(analysis.get("locationTexts"))
            item["conditionText"] = normalize_ai_condition(analysis.get("conditionText"))
            item["status"] = normalize_ai_status(analysis.get("status")) or "UNKNOWN"
            item["category"] = blank_to_none(analysis.get("category"))
            item["brand"] = blank_to_none(analysis.get("brand"))
            item.pop("_sourceFacts", None)
        merged.append(item)
    return merged


def normalize_ai_condition(value: Any) -> str | None:
    condition = blank_to_none(value)
    allowed = {
        "Baru / BNIB",
        "Like New",
        "Bekas - baik",
        "Bekas - normal",
        "Bekas - minus",
    }
    return condition if condition in allowed else None


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
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise NvidiaParserError("NVIDIA parser returned non-JSON content") from exc
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as nested_exc:
            raise NvidiaParserError("NVIDIA parser returned non-JSON content") from nested_exc
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
