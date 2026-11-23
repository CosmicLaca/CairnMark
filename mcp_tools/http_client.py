"""Small standard-library HTTP client shared by the custom MCP services."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RemoteServiceError(RuntimeError):
    """Report a remote data-service failure without exposing request secrets."""


def get_json(
    endpoint: str,
    params: dict[str, object],
    *,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Fetch a JSON object from an HTTP GET endpoint."""
    query = urlencode(params)
    request = Request(
        f"{endpoint}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "Cairnmark-MCP/1.0",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(response.read().decode(charset))
    except HTTPError as exc:
        raise RemoteServiceError(
            f"The remote service returned HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise RemoteServiceError(
            "The remote service could not be reached."
        ) from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RemoteServiceError(
            "The remote service returned an invalid response."
        ) from exc

    if not isinstance(payload, dict):
        raise RemoteServiceError(
            "The remote service returned an unexpected response shape."
        )
    return payload
