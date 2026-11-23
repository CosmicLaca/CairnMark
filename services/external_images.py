"""Validate and download public image URLs selected from chat output."""

import ipaddress
import mimetypes
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


MAX_EXTERNAL_IMAGE_BYTES = 25 * 1024 * 1024


class ExternalImageError(ValueError):
    """Report an invalid or unavailable external image."""


@dataclass(frozen=True)
class DownloadedImage:
    """Hold a validated external image response."""

    content: bytes
    content_type: str
    filename: str


@dataclass(frozen=True)
class ExternalDocumentInfo:
    """Describe the response metadata for a validated public URL."""

    content_type: str
    filename: str


class _ValidatedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, validator):
        self.validator = validator
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.validator(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ExternalImageService:
    """Fetch public images while rejecting local-network and oversized URLs."""

    def __init__(self, opener=None, resolver=None):
        self.resolver = resolver or socket.getaddrinfo
        self.opener = opener

    def _validated_url(self, value):
        raw_url = str(value or "").strip()
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ExternalImageError("A public HTTP image URL is required.")
        if parsed.username or parsed.password:
            raise ExternalImageError("Image URLs cannot contain credentials.")

        try:
            addresses = self.resolver(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except (OSError, ValueError) as error:
            raise ExternalImageError("The image host could not be resolved.") from error
        if not addresses:
            raise ExternalImageError("The image host could not be resolved.")
        for address in addresses:
            host = str(address[4][0]).split("%", 1)[0]
            try:
                ip_address = ipaddress.ip_address(host)
            except ValueError as error:
                raise ExternalImageError("The image host is invalid.") from error
            if not ip_address.is_global:
                raise ExternalImageError(
                    "Local or private image addresses are not allowed."
                )
        return raw_url

    @staticmethod
    def _content_type(headers):
        if hasattr(headers, "get_content_type"):
            return headers.get_content_type().lower()
        return str(headers.get("Content-Type", "")).split(";", 1)[0].lower()

    @staticmethod
    def _filename(url, content_type):
        raw_name = unquote(Path(urlsplit(url).path).name)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._")
        if not safe_name:
            safe_name = "external-image"
        if not Path(safe_name).suffix:
            safe_name += mimetypes.guess_extension(content_type) or ".img"
        return safe_name[:160]

    def _open(self, request, timeout):
        if self.opener is not None:
            return self.opener(request, timeout=timeout)
        opener = urllib.request.build_opener(
            _ValidatedRedirectHandler(self._validated_url)
        )
        return opener.open(request, timeout=timeout)

    def inspect(self, url):
        """Return response MIME metadata without downloading the document body."""
        safe_url = self._validated_url(url)
        request = urllib.request.Request(
            safe_url,
            headers={
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.5",
                "User-Agent": "CairnMark/1.0",
            },
            method="HEAD",
        )
        try:
            with self._open(request, timeout=8) as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                if status != 200:
                    raise ExternalImageError(
                        "The document server did not return HTTP 200."
                    )
                final_url = self._validated_url(response.geturl())
                content_type = self._content_type(response.headers)
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_EXTERNAL_IMAGE_BYTES:
                    raise ExternalImageError("The document is larger than 25 MB.")
        except ExternalImageError:
            raise
        except (OSError, urllib.error.URLError, ValueError) as error:
            raise ExternalImageError(
                "The external document could not be inspected."
            ) from error

        return ExternalDocumentInfo(
            content_type=content_type,
            filename=self._filename(final_url, content_type),
        )

    def download(self, url):
        """Return a bounded public image download."""
        safe_url = self._validated_url(url)
        request = urllib.request.Request(
            safe_url,
            headers={
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.5",
                "User-Agent": "CairnMark/1.0",
            },
            method="GET",
        )
        try:
            response_context = self._open(request, timeout=20)
            with response_context as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                if status != 200:
                    raise ExternalImageError(
                        "The image server did not return HTTP 200."
                    )
                final_url = self._validated_url(response.geturl())
                content_type = self._content_type(response.headers)
                if not content_type.startswith("image/"):
                    raise ExternalImageError("The URL did not return an image.")
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_EXTERNAL_IMAGE_BYTES:
                    raise ExternalImageError("The image is larger than 25 MB.")
                content = response.read(MAX_EXTERNAL_IMAGE_BYTES + 1)
        except ExternalImageError:
            raise
        except (OSError, urllib.error.URLError, ValueError) as error:
            raise ExternalImageError(
                "The external image could not be downloaded."
            ) from error

        if len(content) > MAX_EXTERNAL_IMAGE_BYTES:
            raise ExternalImageError("The image is larger than 25 MB.")
        return DownloadedImage(
            content=content,
            content_type=content_type,
            filename=self._filename(final_url, content_type),
        )
