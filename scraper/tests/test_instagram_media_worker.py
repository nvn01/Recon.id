from __future__ import annotations

import unittest

from scraper.media.instagram_r2 import CachedImage, MediaCacheError
from scraper.media.worker import PendingImage, cache_pending_batch, cache_pending_images


def cached_image(*, reused: bool = False) -> CachedImage:
    return CachedImage(
        cachedUrl="https://media.app-pixel.com/production/instagram/aa/hash.jpg",
        storageKey="production/instagram/aa/hash.jpg",
        contentHash="a" * 64,
        contentType="image/jpeg",
        byteSize=100,
        cachedAt="2026-07-16T05:00:00+00:00",
        reused=reused,
    )


class FakeCache:
    def __init__(self, outcomes: list[CachedImage | Exception]):
        self.outcomes = outcomes
        self.urls: list[str] = []

    def cache_image(self, source_url: str) -> CachedImage:
        self.urls.append(source_url)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = -1
        self.rows: list[tuple[str, str]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.connection.executions.append((sql, params))
        if sql.lstrip().startswith("SELECT"):
            self.rows = list(self.connection.rows)
            return
        self.rowcount = 1

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[tuple[str, str]]):
        self.rows = rows
        self.executions: list[tuple[str, object]] = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


class InstagramMediaWorkerTests(unittest.TestCase):
    def test_database_query_is_an_instagram_only_durable_media_queue(self):
        connection = FakeConnection(
            [("image-1", "https://scontent.cdninstagram.com/one.jpg")],
        )
        cache = FakeCache([cached_image()])

        result = cache_pending_batch(
            "postgresql://scraper:test-placeholder@postgres:5432/recon",
            after_id="",
            batch_size=25,
            cache=cache,
            connect_fn=lambda _url: connection,
        )

        select_sql, select_params = connection.executions[0]
        update_sql, update_params = connection.executions[1]
        self.assertIn("listing.platform = 'instagram'::listing_platform", select_sql)
        self.assertIn("image.cached_url IS NULL", select_sql)
        self.assertEqual(select_params, ("", 25))
        self.assertIn("WHERE id = %(id)s AND cached_url IS NULL", update_sql)
        self.assertEqual(update_params["id"], "image-1")
        self.assertEqual(connection.commits, 1)
        self.assertEqual(result.updated, 1)

    def test_caches_pending_rows_after_database_ingestion_and_updates_only_successes(self):
        images = [
            PendingImage(id="image-1", source_url="https://scontent.cdninstagram.com/one.jpg"),
            PendingImage(id="image-2", source_url="https://scontent.cdninstagram.com/two.jpg"),
        ]
        cache = FakeCache([cached_image(), MediaCacheError("expired")])
        updates: list[tuple[str, dict[str, object]]] = []

        result = cache_pending_images(
            images,
            cache=cache,
            update_fn=lambda image_id, fields: updates.append((image_id, fields)) or True,
        )

        self.assertEqual(cache.urls, [image.source_url for image in images])
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][0], "image-1")
        self.assertEqual(updates[0][1]["cachedUrl"], "https://media.app-pixel.com/production/instagram/aa/hash.jpg")
        self.assertEqual(
            result.as_dict(),
            {"selected": 2, "updated": 1, "cached": 1, "reused": 0, "failed": 1, "skipped": 0},
        )
        self.assertEqual(result.next_cursor, "image-2")

    def test_database_race_does_not_overwrite_an_existing_cached_url(self):
        cache = FakeCache([cached_image(reused=True)])

        result = cache_pending_images(
            [PendingImage(id="image-1", source_url="https://scontent.cdninstagram.com/one.jpg")],
            cache=cache,
            update_fn=lambda _image_id, _fields: False,
        )

        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.cached, 0)
        self.assertEqual(result.reused, 0)


if __name__ == "__main__":
    unittest.main()
