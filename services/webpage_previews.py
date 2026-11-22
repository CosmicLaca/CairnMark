"""Capture bounded screenshots for public webpage links in chat output."""

import ipaddress
import socket
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import current_app


MAX_WEBPAGE_PREVIEWS = 5
WEBPAGE_PREVIEW_HEIGHT = 320
WEBPAGE_PREVIEW_WIDTH = 568
DEFAULT_WEBPAGE_PREVIEW_TIMEOUT_SECONDS = 2


class WebpagePreviewService:
    """Create UUID-addressed screenshots without allowing private-network access."""

    def __init__(self, preview_store, resolver=None, playwright_factory=None):
        self.preview_store = preview_store
        self.resolver = resolver or socket.getaddrinfo
        self.playwright_factory = playwright_factory

    def _validated_url(self, value):
        url = str(value or "").strip()
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("A public HTTP(S) URL is required.")
        if parsed.username or parsed.password:
            raise ValueError("Webpage URLs cannot contain credentials.")
        addresses = self.resolver(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
        if not addresses:
            raise ValueError("The webpage host could not be resolved.")
        for address in addresses:
            host = str(address[4][0]).split("%", 1)[0]
            if not ipaddress.ip_address(host).is_global:
                raise ValueError("Local or private webpage addresses are not allowed.")
        return url

    def _playwright(self):
        if self.playwright_factory is not None:
            return self.playwright_factory()
        from playwright.sync_api import sync_playwright

        return sync_playwright()

    def _route(self, route):
        parsed = urlsplit(route.request.url)
        if parsed.scheme not in {"http", "https"}:
            route.continue_()
            return
        try:
            self._validated_url(route.request.url)
        except (OSError, ValueError):
            route.abort()
            return
        route.continue_()

    @staticmethod
    def _launch_browser(playwright):
        last_error = None
        for options in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
            try:
                return playwright.chromium.launch(headless=True, **options)
            except Exception as error:  # noqa: BLE001
                last_error = error
        raise last_error

    def capture(self, urls, *, timeout_seconds=DEFAULT_WEBPAGE_PREVIEW_TIMEOUT_SECONDS):
        """Capture successful HTTP 200 pages and silently skip failures."""
        timeout_ms = max(1, min(30, int(timeout_seconds))) * 1_000
        candidates = []
        for value in urls or []:
            try:
                url = self._validated_url(value)
            except (OSError, ValueError):
                continue
            if url not in candidates:
                candidates.append(url)
            if len(candidates) >= MAX_WEBPAGE_PREVIEWS:
                break
        if not candidates:
            return []

        previews = []
        try:
            with self._playwright() as playwright:
                browser = self._launch_browser(playwright)
                try:
                    for url in candidates:
                        preview = self._capture_one(browser, url, timeout_ms)
                        if preview:
                            previews.append(preview)
                finally:
                    browser.close()
        except Exception as error:  # noqa: BLE001
            current_app.logger.warning(
                "Webpage previews are unavailable: %s",
                error,
            )
        return previews

    def _capture_one(self, browser, url, timeout_ms):
        preview_id = uuid.uuid4().hex
        filename = f"webpage-preview-{preview_id}.png"
        destination = Path(self.preview_store.directory()) / filename
        page = browser.new_page(
            viewport={
                "width": WEBPAGE_PREVIEW_WIDTH,
                "height": WEBPAGE_PREVIEW_HEIGHT,
            }
        )
        page.route("**/*", self._route)
        page.set_default_timeout(timeout_ms)
        try:
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            if response is None or response.status != 200:
                return None
            self._validated_url(page.url)
            page.screenshot(path=str(destination), full_page=False, type="png")
            return {"id": preview_id, "url": url, "filename": filename}
        except Exception:  # noqa: BLE001
            destination.unlink(missing_ok=True)
            return None
        finally:
            page.close()
