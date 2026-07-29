"""Bounded Facebook Group image download and Cloudflare R2 upload."""

from __future__ import annotations

import hashlib
import ipaddress
import socket
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, build_opener

from scraper.media.instagram_r2 import (
    ALLOWED_CONTENT_TYPES,
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_TIMEOUT_SECONDS,
    CachedImage,
    DownloadedImage,
    MediaCacheError,
    NoRedirectHandler,
    R2Config,
    build_r2_client,
    object_exists,
    read_bounded,
)


ALLOWED_FACEBOOK_SOURCE_SUFFIXES = (".fbcdn.net",)


class FacebookGroupsR2Cache:
    def __init__(
        self,
        config: R2Config,
        *,
        s3_client: Any | None = None,
        downloader: Callable[[str], DownloadedImage] | None = None,
    ) -> None:
        self.config = config
        self.s3 = s3_client or build_r2_client(config)
        self.downloader = downloader or download_facebook_group_image

    def cache_image(self, source_url: str) -> CachedImage:
        downloaded = self.downloader(source_url)
        key = (
            f"{self.config.object_prefix}/facebook-groups/"
            f"{downloaded.content_hash[:2]}/{downloaded.content_hash}.{downloaded.extension}"
        )
        reused = object_exists(self.s3, self.config.bucket_name, key)
        if not reused:
            try:
                self.s3.put_object(
                    Bucket=self.config.bucket_name,
                    Key=key,
                    Body=downloaded.body,
                    ContentType=downloaded.content_type,
                    CacheControl="public, max-age=31536000, immutable",
                    Metadata={"sha256": downloaded.content_hash, "source": "facebook-groups"},
                )
            except Exception as exc:
                raise MediaCacheError(f"R2 upload failed: {type(exc).__name__}") from exc

        encoded_key = "/".join(quote(part, safe="") for part in key.split("/"))
        return CachedImage(
            cachedUrl=f"{self.config.public_base_url}/{encoded_key}",
            storageKey=key,
            contentHash=downloaded.content_hash,
            contentType=downloaded.content_type,
            byteSize=len(downloaded.body),
            cachedAt=datetime.now(timezone.utc).isoformat(),
            reused=reused,
        )


def download_facebook_group_image(
    source_url: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> DownloadedImage:
    opener = build_opener(NoRedirectHandler())
    current_url = source_url
    for redirect_count in range(max_redirects + 1):
        validate_facebook_source_url(current_url)
        request = Request(
            current_url,
            headers={
                "Accept": "image/avif,image/webp,image/png,image/jpeg",
                "Referer": "https://www.facebook.com/",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
                ),
            },
        )
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308} and redirect_count < max_redirects:
                location = exc.headers.get("Location")
                if not location:
                    raise MediaCacheError("Facebook image redirect omitted Location.") from exc
                current_url = urljoin(current_url, location)
                continue
            raise MediaCacheError(f"Facebook image request failed with HTTP {exc.code}.") from exc
        except (OSError, URLError) as exc:
            raise MediaCacheError(f"Facebook image request failed: {type(exc).__name__}") from exc

        with response:
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            declared_length = response.headers.get("Content-Length")
            if declared_length:
                try:
                    if int(declared_length) > max_bytes:
                        raise MediaCacheError("Facebook image exceeds the configured size limit.")
                except ValueError as exc:
                    raise MediaCacheError("Facebook image returned an invalid Content-Length.") from exc
            body = read_bounded(response, max_bytes)
        extension, signature_check = ALLOWED_CONTENT_TYPES.get(content_type, (None, None))
        if extension is None or signature_check is None or not signature_check(body):
            raise MediaCacheError("Facebook media response is not a supported image.")
        return DownloadedImage(
            body=body,
            content_type=content_type,
            extension=extension,
            content_hash=hashlib.sha256(body).hexdigest(),
        )
    raise MediaCacheError("Facebook image exceeded the redirect limit.")


def validate_facebook_source_url(value: str) -> None:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise MediaCacheError("Facebook image URL must use HTTPS without credentials.")
    if not any(
        hostname == suffix[1:] or hostname.endswith(suffix)
        for suffix in ALLOWED_FACEBOOK_SOURCE_SUFFIXES
    ):
        raise MediaCacheError("Facebook image host is not allowlisted.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise MediaCacheError("Facebook image host could not be resolved.") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise MediaCacheError("Facebook image host resolved to a non-public address.")
