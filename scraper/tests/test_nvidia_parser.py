from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scraper.reddit.nvidia_parser import (
    SYSTEM_PROMPT,
    NvidiaParseClient,
    NvidiaParserError,
    build_prompt,
    merge_ai_results,
)


class NvidiaParserPromptTests(unittest.TestCase):
    def test_system_prompt_explains_product_aware_facebook_enrichment(self):
        prompt = build_prompt(
            [
                {
                    "platform": "facebook",
                    "externalId": "fb-1",
                    "title": "PS4 Resmi",
                    "description": "IDR3,000",
                    "price": 3_000,
                }
            ]
        )

        self.assertIn("Facebook Marketplace rules", SYSTEM_PROMPT)
        self.assertIn("PS4 3000 -> 3000000", SYSTEM_PROMPT)
        self.assertIn("controller 200 can mean 200000", SYSTEM_PROMPT)
        self.assertIn("Steam Deck 65 can mean 6500000", SYSTEM_PROMPT)
        self.assertIn("123456", SYSTEM_PROMPT)
        self.assertIn("Bekas - normal", SYSTEM_PROMPT)
        self.assertIn("XPG CORE REACTOR", SYSTEM_PROMPT)
        self.assertIn("Attack Shark R3", SYSTEM_PROMPT)
        self.assertIn("Review and enrich every listing", prompt)

    def test_prompt_includes_platform_for_source_specific_reasoning(self):
        prompt = build_prompt(
            [
                {
                    "platform": "instagram",
                    "externalId": "ig-1",
                    "title": "CORSAIR K100 RGB",
                    "description": "Keyboard gaming Corsair",
                }
            ]
        )

        self.assertIn('"platform": "instagram"', prompt)

    def test_prompt_requires_the_source_seller_name_without_inference(self):
        prompt = build_prompt(
            [
                {
                    "platform": "facebook",
                    "externalId": "fb-seller",
                    "title": "Acer Z476",
                    "description": "Daily listing",
                    "sellerName": "Public Seller",
                }
            ]
        )

        self.assertIn("Return sourceFacts.sellerName exactly", SYSTEM_PROMPT)
        self.assertIn('"sellerName": "Public Seller"', prompt)

    def test_ai_result_owns_all_semantic_fields(self):
        listings = [{"externalId": "fb-1", "platform": "FACEBOOK", "title": "raw", "price": 123_456}]
        analyses = [
            {
                "externalId": "fb-1",
                "isListing": True,
                "title": "PS4 Slim 500GB",
                "price": None,
                "locationTexts": ["Jakarta"],
                "conditionText": "Bekas - baik",
                "status": "AVAILABLE",
                "category": "Game Console",
                "brand": "Sony",
                "sellerName": "Wrong AI Seller",
            }
        ]

        [parsed] = merge_ai_results(listings, analyses)

        self.assertEqual(parsed["title"], "PS4 Slim 500GB")
        self.assertIsNone(parsed["price"])
        self.assertEqual(parsed["conditionText"], "Bekas - baik")
        self.assertEqual(parsed["category"], "Game Console")
        self.assertIsNone(parsed["sellerName"])

    def test_merge_preserves_the_scraper_seller_identity(self):
        listings = [
            {
                "externalId": "fb-seller",
                "platform": "FACEBOOK",
                "title": "raw",
                "sellerName": "Public Seller",
            }
        ]
        analyses = [
            {
                "externalId": "fb-seller",
                "isListing": True,
                "title": "Acer Z476",
                "price": None,
                "locationTexts": [],
                "conditionText": None,
                "status": "AVAILABLE",
                "category": "Laptop",
                "brand": "Acer",
                "sellerName": "Invented Seller",
            }
        ]

        [parsed] = merge_ai_results(listings, analyses)

        self.assertEqual(parsed["sellerName"], "Public Seller")

    def test_ai_can_reject_non_listing_content(self):
        listings = [{"externalId": "ig-1", "platform": "INSTAGRAM", "title": "raw"}]
        analyses = [{"externalId": "ig-1", "isListing": False}]

        self.assertEqual(merge_ai_results(listings, analyses), [])

    def test_non_json_response_does_not_trigger_unguided_retry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=Path(tmpdir) / "nvidia_ai.json",
            )
            error = NvidiaParserError("NVIDIA parser returned non-JSON content")

            with patch.object(client, "_request", side_effect=error) as request:
                with self.assertRaises(NvidiaParserError):
                    client.parse_batch([{"externalId": "item-1"}])

        self.assertEqual(request.call_count, 1)

    def test_guided_json_rejection_retries_once_without_guidance(self):
        analysis = {"externalId": "item-1", "isListing": False}
        with tempfile.TemporaryDirectory() as tmpdir:
            client = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=Path(tmpdir) / "nvidia_ai.json",
            )
            guided_rejection = NvidiaParserError(
                "NVIDIA parser HTTP 400: nvext guided_json is unsupported"
            )

            with patch.object(client, "_request", side_effect=[guided_rejection, [analysis]]) as request:
                result = client.parse_batch([{"externalId": "item-1"}])

        self.assertEqual(result, [analysis])
        self.assertEqual(request.call_count, 2)
        self.assertIn("nvext", request.call_args_list[0].args[0])
        self.assertNotIn("nvext", request.call_args_list[1].args[0])

    def test_capacity_failure_opens_shared_circuit_before_next_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "nvidia_ai.json"
            first = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=state_path,
            )
            capacity_error = NvidiaParserError(
                "NVIDIA parser HTTP 503: ResourceExhausted request limit reached"
            )
            with patch.object(first, "_request", side_effect=capacity_error):
                with self.assertRaises(NvidiaParserError):
                    first.parse_batch([{"externalId": "item-1"}])

            second = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=state_path,
            )
            with patch.object(second, "_request") as request:
                with self.assertRaisesRegex(NvidiaParserError, "cooling down"):
                    second.parse_batch([{"externalId": "item-2"}])

        request.assert_not_called()

    def test_degraded_function_failure_opens_shared_circuit_before_next_request(self):
        self._assert_provider_unavailable_opens_shared_circuit(
            "NVIDIA parser HTTP 400: "
            '{"status":400,"detail":"Function id test: DEGRADED function cannot be invoked"}'
        )

    def test_function_not_found_failure_opens_shared_circuit_before_next_request(self):
        self._assert_provider_unavailable_opens_shared_circuit(
            "NVIDIA parser HTTP 404: "
            '{"status":404,"detail":"Function id test version null: Specified function in '
            'account test is not found"}'
        )

    def test_generic_bad_request_does_not_open_provider_unavailable_circuit(self):
        analysis = {"externalId": "item-2", "isListing": False}
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "nvidia_ai.json"
            first = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=state_path,
            )
            with patch.object(
                first,
                "_request",
                side_effect=NvidiaParserError("NVIDIA parser HTTP 400: invalid request"),
            ):
                with self.assertRaises(NvidiaParserError):
                    first.parse_batch([{"externalId": "item-1"}])

            second = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=state_path,
            )
            with patch.object(second, "_request", return_value=[analysis]) as request:
                result = second.parse_batch([{"externalId": "item-2"}])

        self.assertEqual(result, [analysis])
        request.assert_called_once()

    def _assert_provider_unavailable_opens_shared_circuit(self, message: str):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "nvidia_ai.json"
            first = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=state_path,
            )
            with patch.object(first, "_request", side_effect=NvidiaParserError(message)) as request:
                with self.assertRaises(NvidiaParserError):
                    first.parse_batch([{"externalId": "item-1"}])

            second = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=state_path,
            )
            with patch.object(second, "_request") as blocked_request:
                with self.assertRaisesRegex(NvidiaParserError, "cooling down"):
                    second.parse_batch([{"externalId": "item-2"}])

        self.assertEqual(request.call_count, 1)
        blocked_request.assert_not_called()

    def test_two_invalid_outputs_open_shared_circuit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "nvidia_ai.json"
            for external_id in ("item-1", "item-2"):
                client = NvidiaParseClient(
                    api_key="test",
                    base_url="https://example.test/v1",
                    model="test-model",
                    timeout=1,
                    state_path=state_path,
                )
                with patch.object(
                    client,
                    "_request",
                    side_effect=NvidiaParserError("NVIDIA parser returned non-JSON content"),
                ):
                    with self.assertRaises(NvidiaParserError):
                        client.parse_batch([{"externalId": external_id}])

            blocked = NvidiaParseClient(
                api_key="test",
                base_url="https://example.test/v1",
                model="test-model",
                timeout=1,
                state_path=state_path,
            )
            with patch.object(blocked, "_request") as request:
                with self.assertRaisesRegex(NvidiaParserError, "cooling down"):
                    blocked.parse_batch([{"externalId": "item-3"}])

        request.assert_not_called()

    def test_ai_payload_has_room_for_batched_json_output(self):
        client = NvidiaParseClient(
            api_key="test",
            base_url="https://example.test/v1",
            model="test-model",
            timeout=1,
        )

        payload = client._build_payload([{"externalId": "item-1"}], guided=True)

        self.assertEqual(payload["max_tokens"], 8192)


if __name__ == "__main__":
    unittest.main()
