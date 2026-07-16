from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from scraper.media.instagram_r2 import (
    DownloadedImage,
    InstagramR2Cache,
    MediaCacheError,
    R2Config,
    download_instagram_image,
    validate_source_url,
)


JPEG = b"\xff\xd8\xff" + b"recon-image"


class FakeNotFound(Exception):
    response = {
        "Error": {"Code": "404"},
        "ResponseMetadata": {"HTTPStatusCode": 404},
    }


class FakeS3:
    def __init__(self, *, exists: bool = False):
        self.exists = exists
        self.put_calls: list[dict[str, object]] = []

    def head_object(self, **_kwargs):
        if not self.exists:
            raise FakeNotFound()
        return {}

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        self.exists = True


class FakeResponse:
    def __init__(self, body: bytes, content_type: str, content_length: str | None = None):
        self.body = body
        self.offset = 0
        self.headers = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = content_length

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

    def open(self, _request, timeout: int):
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


class InstagramMediaCacheTests(unittest.TestCase):
    def test_content_addressed_upload_is_immutable_and_reused(self):
        downloaded = DownloadedImage(
            body=JPEG,
            content_type="image/jpeg",
            extension="jpg",
            content_hash=hashlib.sha256(JPEG).hexdigest(),
        )
        s3 = FakeS3()
        cache = InstagramR2Cache(config(), s3_client=s3, downloader=lambda _url: downloaded)

        first = cache.cache_image("https://scontent.cdninstagram.com/image.jpg")
        second = cache.cache_image("https://scontent.cdninstagram.com/image.jpg?token=changed")

        self.assertFalse(first.reused)
        self.assertTrue(second.reused)
        self.assertEqual(first.cachedUrl, second.cachedUrl)
        self.assertEqual(len(s3.put_calls), 1)
        self.assertEqual(s3.put_calls[0]["CacheControl"], "public, max-age=31536000, immutable")

    def test_source_validation_rejects_untrusted_and_private_hosts(self):
        with self.assertRaises(MediaCacheError):
            validate_source_url("https://example.com/image.jpg")
        with patch("scraper.media.instagram_r2.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(MediaCacheError):
                validate_source_url("https://scontent.cdninstagram.com/image.jpg")

    def test_download_requires_supported_mime_and_magic_signature(self):
        response = FakeResponse(JPEG, "image/jpeg", str(len(JPEG)))
        with (
            patch("scraper.media.instagram_r2.build_opener", return_value=FakeOpener(response)),
            patch("scraper.media.instagram_r2.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]),
        ):
            downloaded = download_instagram_image("https://scontent.cdninstagram.com/image.jpg")
        self.assertEqual(downloaded.content_hash, hashlib.sha256(JPEG).hexdigest())

        bad_response = FakeResponse(b"<html>blocked</html>", "image/jpeg")
        with (
            patch("scraper.media.instagram_r2.build_opener", return_value=FakeOpener(bad_response)),
            patch("scraper.media.instagram_r2.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]),
        ):
            with self.assertRaises(MediaCacheError):
                download_instagram_image("https://scontent.cdninstagram.com/image.jpg")


if __name__ == "__main__":
    unittest.main()
