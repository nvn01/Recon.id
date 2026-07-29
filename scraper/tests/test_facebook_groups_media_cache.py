from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from scraper.media.facebook_groups_r2 import (
    FacebookGroupsR2Cache,
    download_facebook_group_image,
    validate_facebook_source_url,
)
from scraper.media.instagram_r2 import DownloadedImage, MediaCacheError, R2Config


JPEG = b"\xff\xd8\xff" + b"facebook-group-image"


class FakeNotFound(Exception):
    response = {
        "Error": {"Code": "404"},
        "ResponseMetadata": {"HTTPStatusCode": 404},
    }


class FakeS3:
    def __init__(self):
        self.exists = False
        self.put_calls: list[dict[str, object]] = []

    def head_object(self, **_kwargs):
        if not self.exists:
            raise FakeNotFound()
        return {}

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        self.exists = True


class FakeResponse:
    def __init__(self, body: bytes, content_type: str):
        self.body = body
        self.offset = 0
        self.headers = {"Content-Type": content_type, "Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int):
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class FakeOpener:
    def __init__(self, response: FakeResponse):
        self.response = response

    def open(self, request, timeout: int):
        self.request = request
        self.timeout = timeout
        return self.response


def config() -> R2Config:
    return R2Config(
        account_id="account",
        access_key_id="access",
        secret_access_key="secret",
        bucket_name="recon-media-production",
        public_base_url="https://media.app-pixel.com",
        object_prefix="production",
    )


class FacebookGroupsMediaCacheTests(unittest.TestCase):
    def test_content_addressed_images_use_a_separate_r2_prefix(self):
        downloaded = DownloadedImage(
            body=JPEG,
            content_type="image/jpeg",
            extension="jpg",
            content_hash=hashlib.sha256(JPEG).hexdigest(),
        )
        s3 = FakeS3()
        cache = FacebookGroupsR2Cache(config(), s3_client=s3, downloader=lambda _url: downloaded)

        first = cache.cache_image("https://scontent-test.fbcdn.net/photo.jpg")
        second = cache.cache_image("https://scontent-test.fbcdn.net/photo.jpg?token=changed")

        self.assertFalse(first.reused)
        self.assertTrue(second.reused)
        self.assertIn("/production/facebook-groups/", first.cachedUrl)
        self.assertEqual(len(s3.put_calls), 1)
        self.assertEqual(s3.put_calls[0]["Metadata"]["source"], "facebook-groups")

    def test_download_uses_facebook_referer_and_rejects_untrusted_hosts(self):
        response = FakeResponse(JPEG, "image/jpeg")
        opener = FakeOpener(response)
        with (
            patch("scraper.media.facebook_groups_r2.build_opener", return_value=opener),
            patch(
                "scraper.media.facebook_groups_r2.socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("1.1.1.1", 443))],
            ),
        ):
            downloaded = download_facebook_group_image("https://scontent-test.fbcdn.net/photo.jpg")

        self.assertEqual(downloaded.content_hash, hashlib.sha256(JPEG).hexdigest())
        self.assertEqual(opener.request.headers["Referer"], "https://www.facebook.com/")
        with self.assertRaises(MediaCacheError):
            validate_facebook_source_url("https://example.com/photo.jpg")


if __name__ == "__main__":
    unittest.main()
