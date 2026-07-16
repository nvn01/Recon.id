"""Bounded Instagram image download and Cloudflare R2 upload boundary."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


ALLOWED_SOURCE_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": ("webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
    "image/avif": ("avif", lambda data: len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis"}),
}
REQUIRED_ENV_KEYS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_PUBLIC_BASE_URL",
)
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_REDIRECTS = 3


class MediaCacheError(RuntimeError):
    """Raised when an image cannot be cached safely."""


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    public_base_url: str
    object_prefix: str = "production"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> R2Config | None:
        values = env if env is not None else os.environ
        populated = {key: str(values.get(key) or "").strip() for key in REQUIRED_ENV_KEYS}
        if not any(populated.values()):
            return None
        missing = [key for key, value in populated.items() if not value]
        if missing:
            raise MediaCacheError(f"Incomplete R2 configuration; missing: {', '.join(missing)}")

        public_url = populated["R2_PUBLIC_BASE_URL"].rstrip("/")
        parsed = urlsplit(public_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise MediaCacheError("R2_PUBLIC_BASE_URL must be an HTTPS URL without credentials.")

        prefix = str(values.get("R2_OBJECT_PREFIX") or "production").strip().strip("/")
        if not prefix or any(part in {".", ".."} for part in prefix.split("/")):
            raise MediaCacheError("R2_OBJECT_PREFIX must be a non-empty object path.")
        return cls(
            account_id=populated["R2_ACCOUNT_ID"],
            access_key_id=populated["R2_ACCESS_KEY_ID"],
            secret_access_key=populated["R2_SECRET_ACCESS_KEY"],
            bucket_name=populated["R2_BUCKET_NAME"],
            public_base_url=public_url,
            object_prefix=prefix,
        )


@dataclass(frozen=True)
class DownloadedImage:
    body: bytes
    content_type: str
    extension: str
    content_hash: str


@dataclass(frozen=True)
class CachedImage:
    cachedUrl: str
    storageKey: str
    contentHash: str
    contentType: str
    byteSize: int
    cachedAt: str
    reused: bool

    def image_fields(self) -> dict[str, Any]:
        fields = asdict(self)
        fields.pop("reused")
        return fields


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


class InstagramR2Cache:
    def __init__(
        self,
        config: R2Config,
        *,
        s3_client: Any | None = None,
        downloader: Callable[[str], DownloadedImage] | None = None,
    ) -> None:
        self.config = config
        self.s3 = s3_client or build_r2_client(config)
        self.downloader = downloader or download_instagram_image

    def cache_image(self, source_url: str) -> CachedImage:
        downloaded = self.downloader(source_url)
        key = (
            f"{self.config.object_prefix}/instagram/"
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
                    Metadata={"sha256": downloaded.content_hash, "source": "instagram"},
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


def build_r2_client(config: R2Config) -> Any:
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:  # pragma: no cover - verified in the scraper image.
        raise MediaCacheError("Install scraper dependencies before enabling R2 media caching.") from exc
    return boto3.client(
        "s3",
        endpoint_url=f"https://{config.account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=20,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def object_exists(client: Any, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as exc:
        error = getattr(exc, "response", {}).get("Error", {})
        code = str(error.get("Code") or "")
        status = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
            return False
        raise MediaCacheError(f"R2 object check failed: {type(exc).__name__}") from exc


def download_instagram_image(
    source_url: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> DownloadedImage:
    opener = build_opener(NoRedirectHandler())
    current_url = source_url
    for redirect_count in range(max_redirects + 1):
        validate_source_url(current_url)
        request = Request(
            current_url,
            headers={
                "Accept": "image/avif,image/webp,image/png,image/jpeg",
                "Referer": "https://www.instagram.com/",
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
                    raise MediaCacheError("Instagram image redirect omitted Location.") from exc
                current_url = urljoin(current_url, location)
                continue
            raise MediaCacheError(f"Instagram image request failed with HTTP {exc.code}.") from exc
        except (OSError, URLError) as exc:
            raise MediaCacheError(f"Instagram image request failed: {type(exc).__name__}") from exc

        with response:
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            declared_length = response.headers.get("Content-Length")
            if declared_length:
                try:
                    if int(declared_length) > max_bytes:
                        raise MediaCacheError("Instagram image exceeds the configured size limit.")
                except ValueError as exc:
                    raise MediaCacheError("Instagram image returned an invalid Content-Length.") from exc
            body = read_bounded(response, max_bytes)
        extension, signature_check = ALLOWED_CONTENT_TYPES.get(content_type, (None, None))
        if extension is None or signature_check is None or not signature_check(body):
            raise MediaCacheError("Instagram media response is not a supported image.")
        return DownloadedImage(
            body=body,
            content_type=content_type,
            extension=extension,
            content_hash=hashlib.sha256(body).hexdigest(),
        )
    raise MediaCacheError("Instagram image exceeded the redirect limit.")


def read_bounded(response: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, max_bytes + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise MediaCacheError("Instagram image exceeds the configured size limit.")
        chunks.append(chunk)
    if total == 0:
        raise MediaCacheError("Instagram image response was empty.")
    return b"".join(chunks)


def validate_source_url(value: str) -> None:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise MediaCacheError("Instagram image URL must use HTTPS without credentials.")
    if not any(hostname == suffix[1:] or hostname.endswith(suffix) for suffix in ALLOWED_SOURCE_SUFFIXES):
        raise MediaCacheError("Instagram image host is not allowlisted.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise MediaCacheError("Instagram image host could not be resolved.") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise MediaCacheError("Instagram image host resolved to a non-public address.")
