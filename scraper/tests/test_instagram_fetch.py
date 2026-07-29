from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from scraper.instagram.embedded import extract_post_detail, extract_profile_posts
from scraper.instagram.instagram import (
    InstagramFetchError,
    capture_timeline_response,
    enrich_carousel_posts,
    ensure_profile_not_login_redirect,
    extract_images,
    fetch_profile_resilient,
    run_accounts,
    wait_for_post_detail,
    wait_for_profile_posts,
)


class InstagramFetchTests(unittest.TestCase):
    def test_post_detail_parser_extracts_complete_carousel_media(self):
        payload = {
            "require": [
                {
                    "shortcode": "CAROUSEL",
                    "tracking_only": True,
                },
                {
                    "code": "CAROUSEL",
                    "pk": "900",
                    "media_type": 8,
                    "product_type": "carousel_container",
                    "display_uri": "https://cdn.example/cover.jpg",
                    "carousel_media": [
                        {"display_uri": "https://cdn.example/cover.jpg"},
                        {"display_uri": "https://cdn.example/two.jpg"},
                        {
                            "image_versions2": {
                                "candidates": [{"url": "https://cdn.example/three.jpg"}]
                            }
                        },
                    ],
                },
            ]
        }

        detail = extract_post_detail([json.dumps(payload)], "CAROUSEL")

        self.assertIsNotNone(detail)
        self.assertEqual(
            [image["sourceUrl"] for image in extract_images(detail or {}, "CAROUSEL")],
            [
                "https://cdn.example/cover.jpg",
                "https://cdn.example/two.jpg",
                "https://cdn.example/three.jpg",
            ],
        )

    def test_carousel_enrichment_fetches_detail_once_and_populates_cache(self):
        posts = [
            {
                "shortcode": "CAROUSEL",
                "media_type": 8,
                "product_type": "carousel_container",
                "carousel_media_count": 3,
                "display_url": "https://cdn.example/cover.jpg",
            },
            {
                "shortcode": "SINGLE",
                "media_type": 1,
                "product_type": "feed",
                "display_url": "https://cdn.example/single.jpg",
            },
        ]
        fetched: list[str] = []
        cache: dict[str, list[str]] = {}

        def fetch_detail(shortcode: str):
            fetched.append(shortcode)
            return {
                "shortcode": shortcode,
                "edge_sidecar_to_children": {
                    "edges": [
                        {"node": {"display_url": "https://cdn.example/cover.jpg"}},
                        {"node": {"display_url": "https://cdn.example/two.jpg"}},
                        {"node": {"display_url": "https://cdn.example/three.jpg"}},
                    ]
                },
            }

        enriched = enrich_carousel_posts(
            posts,
            cache=cache,
            max_detail_posts=3,
            fetch_detail=fetch_detail,
        )

        self.assertEqual(fetched, ["CAROUSEL"])
        self.assertEqual(len(extract_images(enriched[0], "CAROUSEL")), 3)
        self.assertEqual(
            cache["CAROUSEL"],
            [
                "https://cdn.example/cover.jpg",
                "https://cdn.example/two.jpg",
                "https://cdn.example/three.jpg",
            ],
        )
        self.assertEqual(len(extract_images(enriched[1], "SINGLE")), 1)

    def test_carousel_enrichment_reuses_cache_without_another_detail_request(self):
        posts = [
            {
                "shortcode": "CACHED",
                "media_type": 8,
                "carousel_media_count": 2,
                "display_url": "https://cdn.example/cover.jpg",
            }
        ]
        cache = {
            "CACHED": [
                "https://cdn.example/cover.jpg",
                "https://cdn.example/two.jpg",
            ]
        }

        enriched = enrich_carousel_posts(
            posts,
            cache=cache,
            max_detail_posts=3,
            fetch_detail=lambda _shortcode: self.fail("cached carousel must not be fetched again"),
        )

        self.assertEqual(len(extract_images(enriched[0], "CACHED")), 2)

    def test_carousel_enrichment_does_not_duplicate_rotated_profile_cover(self):
        posts = [
            {
                "shortcode": "ROTATED",
                "media_type": 8,
                "carousel_media_count": 2,
                "display_url": "https://scontent.cdninstagram.com/old-path/cover.jpg",
            }
        ]

        enriched = enrich_carousel_posts(
            posts,
            cache={},
            max_detail_posts=1,
            fetch_detail=lambda _shortcode: {
                "shortcode": "ROTATED",
                "display_url": "https://scontent.cdninstagram.com/new-path/cover.jpg",
                "edge_sidecar_to_children": {
                    "edges": [
                        {
                            "node": {
                                "display_url": "https://scontent.cdninstagram.com/new-path/cover.jpg"
                            }
                        },
                        {
                            "node": {
                                "display_url": "https://scontent.cdninstagram.com/new-path/two.jpg"
                            }
                        },
                    ]
                },
            },
        )

        self.assertEqual(
            [image["sourceUrl"] for image in extract_images(enriched[0], "ROTATED")],
            [
                "https://scontent.cdninstagram.com/new-path/cover.jpg",
                "https://scontent.cdninstagram.com/new-path/two.jpg",
            ],
        )

    def test_carousel_enrichment_bounds_detail_requests_and_keeps_cover_on_failure(self):
        posts = [
            {
                "shortcode": shortcode,
                "media_type": 8,
                "carousel_media_count": 2,
                "display_url": f"https://cdn.example/{shortcode}.jpg",
            }
            for shortcode in ("FIRST", "SECOND", "THIRD")
        ]
        fetched: list[str] = []

        def fetch_detail(shortcode: str):
            fetched.append(shortcode)
            return None

        enriched = enrich_carousel_posts(
            posts,
            cache={},
            max_detail_posts=2,
            fetch_detail=fetch_detail,
        )

        self.assertEqual(fetched, ["FIRST", "SECOND"])
        self.assertEqual([len(extract_images(post, post["shortcode"])) for post in enriched], [1, 1, 1])

    def test_account_collection_obeys_requested_limit(self):
        payload = {
            "data": {
                "user": {
                    "edge_owner_to_timeline_media": {
                        "edges": [
                            {
                                "node": {
                                    "shortcode": f"POST-{index}",
                                    "id": str(index),
                                    "taken_at_timestamp": 1_800_000_000 - index,
                                }
                            }
                            for index in range(5)
                        ]
                    }
                }
            }
        }

        with patch("scraper.instagram.instagram.fetch_profile_resilient", return_value=(200, payload)):
            listings, [result] = run_accounts(
                ["shop.example"],
                limit=2,
                max_posts_per_account=12,
                fetch_mode="browser",
            )

        self.assertEqual([listing["externalId"] for listing in listings], ["POST-0", "POST-1"])
        self.assertEqual(result["normalized_count"], 2)

    def test_login_redirect_is_marked_as_cooldown_eligible(self):
        with self.assertRaises(InstagramFetchError) as raised:
            ensure_profile_not_login_redirect(
                "https://www.instagram.com/accounts/login/?next=%2Fshop.example%2F",
                "Shop Example on Instagram",
            )

        self.assertTrue(raised.exception.cooldown_eligible)
        self.assertIn("accounts/login", str(raised.exception))

    def test_profile_wait_keeps_pumping_until_delayed_timeline_response(self):
        timeline_payloads: list[dict] = []
        delayed_payload = {
            "data": {
                "user": {
                    "edge_owner_to_timeline_media": {
                        "edges": [{"node": {"shortcode": "DELAYED", "id": "700"}}]
                    }
                }
            }
        }

        class FakeLocator:
            @staticmethod
            def all_text_contents():
                return []

        class FakePage:
            waited_ms = 0

            @staticmethod
            def locator(selector: str):
                self.assertEqual(selector, 'script[type="application/json"]')
                return FakeLocator()

            def wait_for_timeout(self, interval_ms: int):
                self.waited_ms += interval_ms
                if self.waited_ms == 2_750:
                    timeline_payloads.append(delayed_payload)

        page = FakePage()

        posts, script_count = wait_for_profile_posts(page, timeline_payloads, wait_ms=8_000)

        self.assertEqual([post["shortcode"] for post in posts], ["DELAYED"])
        self.assertEqual(script_count, 0)
        self.assertEqual(page.waited_ms, 2_750)

    def test_profile_wait_stops_after_bounded_budget_when_timeline_is_missing(self):
        class FakeLocator:
            @staticmethod
            def all_text_contents():
                return []

        class FakePage:
            waited_ms = 0

            @staticmethod
            def locator(_selector: str):
                return FakeLocator()

            def wait_for_timeout(self, interval_ms: int):
                self.waited_ms += interval_ms

        page = FakePage()

        posts, script_count = wait_for_profile_posts(page, [], wait_ms=750)

        self.assertEqual(posts, [])
        self.assertEqual(script_count, 0)
        self.assertEqual(page.waited_ms, 750)

    def test_post_detail_wait_keeps_pumping_until_carousel_children_arrive(self):
        response_payloads: list[dict] = []
        detail_payload = {
            "media": {
                "code": "CAROUSEL",
                "media_type": 8,
                "carousel_media": [
                    {"display_uri": "https://cdn.example/cover.jpg"},
                    {"display_uri": "https://cdn.example/two.jpg"},
                ],
            }
        }

        class FakeLocator:
            @staticmethod
            def all_text_contents():
                return []

        class FakePage:
            waited_ms = 0

            @staticmethod
            def locator(selector: str):
                self.assertEqual(selector, 'script[type="application/json"]')
                return FakeLocator()

            def wait_for_timeout(self, interval_ms: int):
                self.waited_ms += interval_ms
                if self.waited_ms == 500:
                    response_payloads.append(detail_payload)

        page = FakePage()

        detail = wait_for_post_detail(
            page,
            response_payloads,
            "CAROUSEL",
            payload_start=0,
            wait_ms=1000,
        )

        self.assertIsNotNone(detail)
        self.assertEqual(len(extract_images(detail or {}, "CAROUSEL")), 2)
        self.assertEqual(page.waited_ms, 500)

    def test_auto_fetch_uses_embedded_browser_profile_without_direct_api_request(self):
        payload = {"data": {"user": {"edge_owner_to_timeline_media": {"edges": []}}}}

        with (
            patch("scraper.instagram.instagram.fetch_profile_browser", return_value=(200, payload)) as browser,
            patch("scraper.instagram.instagram.fetch_profile") as direct,
        ):
            status, result = fetch_profile_resilient(
                "blocked.shop",
                timeout=30,
                user_agent="test-agent",
                fetch_mode="auto",
                browser="chromium",
                headless=True,
                browser_wait_ms=2500,
            )

        self.assertEqual(status, 200)
        self.assertEqual(result, payload)
        browser.assert_called_once()
        direct.assert_not_called()

    def test_auto_fetch_does_not_fall_back_to_direct_api_after_browser_block(self):
        with (
            patch(
                "scraper.instagram.instagram.fetch_profile_browser",
                side_effect=InstagramFetchError("Instagram browser HTTP 429", status=429),
            ),
            patch("scraper.instagram.instagram.fetch_profile") as direct,
        ):
            with self.assertRaises(InstagramFetchError):
                fetch_profile_resilient(
                    "missing.shop",
                    timeout=30,
                    user_agent="test-agent",
                    fetch_mode="auto",
                    browser="chromium",
                    headless=True,
                    browser_wait_ms=2500,
                )

        direct.assert_not_called()

    def test_embedded_profile_posts_sort_by_numeric_pk_and_normalize_relay_fields(self):
        payload = {
            "props": {
                "polaris_ordered_timeline_connection": {
                    "edges": [
                        {
                            "node": {
                                "code": "OLDER",
                                "pk": "100",
                                "caption": {"text": "Harga Rp1.000.000\nLokasi Jakarta"},
                                "display_uri": "https://cdn.example/older.jpg",
                                "media_type": 1,
                            }
                        },
                        {
                            "node": {
                                "code": "NEWER",
                                "pk": "200",
                                "caption": {"text": "Harga Rp2.000.000\nKondisi mulus"},
                                "display_uri": "https://cdn.example/newer.jpg",
                                "media_type": 1,
                            }
                        },
                    ]
                }
            }
        }

        posts = extract_profile_posts(["{}", json.dumps(payload)])

        self.assertEqual([post["shortcode"] for post in posts], ["NEWER", "OLDER"])
        self.assertEqual(posts[0]["edge_media_to_caption"]["edges"][0]["node"]["text"], "Harga Rp2.000.000\nKondisi mulus")
        self.assertEqual(posts[0]["display_url"], "https://cdn.example/newer.jpg")

    def test_embedded_profile_posts_deduplicate_same_shortcode(self):
        connection = {
            "polaris_ordered_timeline_connection": {
                "edges": [
                    {"node": {"code": "SAME", "pk": "300", "caption": {"text": "Harga Rp3.000.000"}}}
                ]
            }
        }

        posts = extract_profile_posts([json.dumps(connection), json.dumps(connection)])

        self.assertEqual([post["shortcode"] for post in posts], ["SAME"])

    def test_embedded_and_network_posts_merge_complementary_fields_by_shortcode(self):
        embedded = {
            "polaris_ordered_timeline_connection": {
                "edges": [
                    {
                        "node": {
                            "code": "SAME",
                            "pk": "500",
                            "caption": {"text": "Harga Rp5.000.000"},
                            "display_uri": "https://cdn.example/primary.jpg",
                            "media_type": 8,
                            "product_type": "carousel_container",
                        }
                    }
                ]
            }
        }
        network = {
            "data": {
                "user": {
                    "edge_owner_to_timeline_media": {
                        "edges": [
                            {
                                "node": {
                                    "shortcode": "SAME",
                                    "id": "500",
                                    "taken_at_timestamp": 1_800_000_000,
                                    "edge_media_to_caption": {"edges": []},
                                    "edge_sidecar_to_children": {
                                        "edges": [
                                            {"node": {"display_url": "https://cdn.example/sidecar.jpg"}}
                                        ]
                                    },
                                }
                            }
                        ]
                    }
                }
            }
        }

        [post] = extract_profile_posts([json.dumps(embedded), json.dumps(network)])

        self.assertEqual(post["shortcode"], "SAME")
        self.assertEqual(post["taken_at_timestamp"], 1_800_000_000)
        self.assertEqual(post["product_type"], "carousel_container")
        self.assertEqual(post["display_url"], "https://cdn.example/primary.jpg")
        self.assertEqual(post["edge_media_to_caption"]["edges"][0]["node"]["text"], "Harga Rp5.000.000")
        self.assertEqual(
            [edge["node"]["display_url"] for edge in post["edge_sidecar_to_children"]["edges"]],
            ["https://cdn.example/sidecar.jpg"],
        )

    def test_timeline_response_capture_accepts_shape_not_document_id(self):
        class FakeResponse:
            status = 200
            url = "https://www.instagram.com/some/future/bootstrap/path"
            headers = {"content-type": "application/json; charset=utf-8"}

            @staticmethod
            def json():
                return {
                    "data": {
                        "user": {
                            "edge_owner_to_timeline_media": {
                                "edges": [{"node": {"shortcode": "NETWORK", "id": "600"}}]
                            }
                        }
                    }
                }

        captured: list[dict] = []

        capture_timeline_response(FakeResponse(), captured)

        self.assertEqual(len(captured), 1)
        self.assertEqual(
            captured[0]["data"]["user"]["edge_owner_to_timeline_media"]["edges"][0]["node"]["shortcode"],
            "NETWORK",
        )

    def test_timeline_response_capture_rejects_unrelated_or_cross_origin_json(self):
        class FakeResponse:
            status = 200
            headers = {"content-type": "application/json"}

            def __init__(self, url: str, payload: dict):
                self.url = url
                self.payload = payload

            def json(self):
                return self.payload

        captured: list[dict] = []

        capture_timeline_response(FakeResponse("https://example.test/graphql", {"data": {}}), captured)
        capture_timeline_response(FakeResponse("https://www.instagram.com/graphql/query", {"data": {}}), captured)

        self.assertEqual(captured, [])

    def test_embedded_parser_supports_legacy_edges_timestamps_and_carousels(self):
        payload = {
            "edge_owner_to_timeline_media": {
                "edges": [
                    None,
                    {"node": "invalid"},
                    {"node": {"pk": "missing-shortcode"}},
                    {
                        "node": {
                            "shortcode": "LEGACY",
                            "id": "400",
                            "taken_at_timestamp": 1_700_000_000,
                            "edge_media_to_caption": {"edges": [{"node": {"text": "Harga Rp4.000.000"}}]},
                            "image_versions2": {
                                "candidates": [None, {"url": "https://cdn.example/primary.jpg"}]
                            },
                            "carousel_media": [
                                None,
                                {"display_url": "https://cdn.example/sidecar.jpg"},
                                {"image_versions2": {"candidates": [{"url": "https://cdn.example/sidecar-2.jpg"}]}},
                            ],
                        }
                    },
                ]
            },
            "ignored": {"polaris_ordered_timeline_connection": {"edges": "not-a-list"}},
        }

        posts = extract_profile_posts(["not-json", json.dumps(payload)])

        self.assertEqual([post["shortcode"] for post in posts], ["LEGACY"])
        self.assertEqual(posts[0]["taken_at_timestamp"], 1_700_000_000)
        self.assertEqual(posts[0]["display_url"], "https://cdn.example/primary.jpg")
        self.assertEqual(
            [edge["node"]["display_url"] for edge in posts[0]["edge_sidecar_to_children"]["edges"]],
            ["https://cdn.example/sidecar.jpg", "https://cdn.example/sidecar-2.jpg"],
        )


if __name__ == "__main__":
    unittest.main()
