from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scraper.ai.nvidia_parser import (
    SYSTEM_PROMPT,
    NvidiaParseClient,
    NvidiaParserError,
    build_prompt,
    classify_nvidia_error,
    merge_ai_results,
    validate_ai_batch_result,
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

    def test_prompt_forbids_instagram_shortcode_titles(self):
        self.assertIn("Instagram shortcode or externalId", SYSTEM_PROMPT)

    def test_instagram_ai_result_rejects_shortcode_title(self):
        listings = [
            {
                "platform": "INSTAGRAM",
                "externalId": "DbnmUuQiWPT",
                "title": "DbnmUuQiWPT",
                "description": "keychron v1 max bnob brown sw",
            }
        ]
        analyses = [
            {
                "externalId": "DbnmUuQiWPT",
                "isListing": True,
                "title": "DbnmUuQiWPT",
            }
        ]

        with self.assertRaisesRegex(NvidiaParserError, "invalid Instagram title"):
            validate_ai_batch_result(listings, analyses)

    def test_instagram_merge_rejects_blank_title_instead_of_using_shortcode(self):
        listings = [
            {
                "platform": "INSTAGRAM",
                "externalId": "Dbnl-CSTNsp",
                "title": "Dbnl-CSTNsp",
                "description": "VortexSeries Mono Series V2 Wired",
            }
        ]
        analyses = [
            {
                "externalId": "Dbnl-CSTNsp",
                "isListing": True,
                "title": " ",
                "price": 215_000,
                "locationTexts": ["Purwokerto"],
                "conditionText": "Bekas - baik",
                "status": "AVAILABLE",
                "category": "Keyboard",
                "brand": "Vortex",
                "sellerName": None,
            }
        ]

        with self.assertRaisesRegex(NvidiaParserError, "invalid Instagram title"):
            merge_ai_results(listings, analyses)

    def test_invalid_instagram_title_counts_as_invalid_model_output(self):
        error = NvidiaParserError(
            "NVIDIA parser returned invalid Instagram title for DbnmUuQiWPT"
        )

        self.assertEqual(classify_nvidia_error(error), "invalid_output")

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

    def test_source_sold_status_wins_over_ai_for_marketplace_and_reddit(self):
        listings = [
            {"externalId": "fb-sold", "platform": "FACEBOOK", "title": "SSD", "status": "SOLD"},
            {"externalId": "rd-sold", "platform": "REDDIT", "title": "GPU", "status": "SOLD"},
        ]
        analyses = [
            {"externalId": "fb-sold", "isListing": True, "title": "SSD", "status": "AVAILABLE"},
            {"externalId": "rd-sold", "isListing": True, "title": "GPU", "status": "AVAILABLE"},
        ]

        parsed = merge_ai_results(listings, analyses)

        self.assertEqual([item["status"] for item in parsed], ["SOLD", "SOLD"])

    def test_facebook_group_listing_never_uses_ai_sold_status(self):
        listings = [
            {
                "externalId": "group-post-1",
                "platform": "FACEBOOK_GROUP",
                "title": "raw",
                "status": "UNKNOWN",
                "_sourceFacts": {"sourceType": "facebook_group"},
            }
        ]
        analyses = [
            {
                "externalId": "group-post-1",
                "isListing": True,
                "title": "RTX 2060 Super",
                "price": 2_700_000,
                "locationTexts": ["Bandung"],
                "conditionText": "Bekas - baik",
                "status": "SOLD",
                "category": "Graphics Card",
                "brand": "Palit",
                "sellerName": None,
            }
        ]

        [parsed] = merge_ai_results(listings, analyses)

        self.assertEqual(parsed["status"], "AVAILABLE")
        self.assertNotIn("_sourceFacts", parsed)

    def test_prompt_explains_facebook_group_wtb_and_sold_rules(self):
        self.assertIn("Facebook Group rules", SYSTEM_PROMPT)
        self.assertIn("WTB/wanted-to-buy", SYSTEM_PROMPT)
        self.assertIn("does not track SOLD", SYSTEM_PROMPT)

    def test_prompt_restricts_facebook_group_posts_to_recon_product_scope(self):
        self.assertIn("computers, PC components, PC peripherals, or gaming", SYSTEM_PROMPT)
        self.assertIn("motorcycles, cars, and bicycles", SYSTEM_PROMPT)
        self.assertIn("kitchen or household appliances", SYSTEM_PROMPT)
        self.assertIn("mixers, blenders", SYSTEM_PROMPT)
        self.assertIn("isListing false even when the post is a real WTS offer", SYSTEM_PROMPT)

    def test_facebook_group_ai_rejection_drops_irrelevant_sale_but_keeps_pc_listing(self):
        listings = [
            {
                "externalId": "group-mixer",
                "platform": "FACEBOOK_GROUP",
                "title": "Mixer 7 liter",
                "description": "Dimahar aja mixer kapasitas 7 liter",
                "_sourceFacts": {"sourceType": "facebook_group"},
            },
            {
                "externalId": "group-gpu",
                "platform": "FACEBOOK_GROUP",
                "title": "WTS RTX 2060 Super",
                "description": "Palit RTX 2060 Super 8GB harga 2.700.000",
                "_sourceFacts": {"sourceType": "facebook_group"},
            },
        ]
        analyses = [
            {"externalId": "group-mixer", "isListing": False},
            {
                "externalId": "group-gpu",
                "isListing": True,
                "title": "Palit RTX 2060 Super 8GB",
                "price": 2_700_000,
                "locationTexts": [],
                "conditionText": "Bekas - baik",
                "status": "AVAILABLE",
                "category": "Graphics Card",
                "brand": "Palit",
                "sellerName": None,
            },
        ]

        [accepted] = merge_ai_results(listings, analyses)

        self.assertEqual(accepted["externalId"], "group-gpu")
        self.assertNotIn("_sourceFacts", accepted)

    def test_non_group_connectors_keep_their_existing_ai_listing_decision(self):
        listings = [
            {
                "externalId": "instagram-phone",
                "platform": "INSTAGRAM",
                "title": "Xiaomi 13 Ultra",
            }
        ]
        analyses = [
            {
                "externalId": "instagram-phone",
                "isListing": True,
                "title": "Xiaomi 13 Ultra",
                "price": 9_000_000,
                "locationTexts": [],
                "conditionText": "Bekas - baik",
                "status": "AVAILABLE",
                "category": "Smartphone",
                "brand": "Xiaomi",
                "sellerName": None,
            }
        ]

        [accepted] = merge_ai_results(listings, analyses)

        self.assertEqual(accepted["category"], "Smartphone")

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
