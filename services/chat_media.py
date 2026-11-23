"""Chat media registration, backfill, availability, and file cleanup."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from flask import current_app

from models.media_storage import MEDIA, normalize_external_locator


URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
RAW_FILE_PATTERN = re.compile(
    r"(?:file_name|file_path|filename):<\|\"\|>([^<>]+)<\|\"\|>",
    re.IGNORECASE,
)
PATH_KEYS = {
    "file", "file_name", "file_path", "filename", "output", "output_file",
    "path", "saved", "saved_path",
}
BACKFILL_KEY = "chat_media_backfill_v1"


class ChatMediaService:
    """Coordinate media records with active and named saved chats."""

    def __init__(self, repository=MEDIA):
        self.repository = repository

    @staticmethod
    def category(filename, media_type=None):
        """Classify a local file using explicit media type then extension."""
        if media_type in {"image", "audio", "video", "document"}:
            return media_type
        suffix = Path(str(filename or "")).suffix.lower()
        if suffix in {
            ".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg",
            ".tif", ".tiff", ".webp",
        }:
            return "image"
        if suffix in {
            ".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav",
        }:
            return "audio"
        if suffix in {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}:
            return "video"
        return "document"

    @staticmethod
    def preview_record(filename, name=None, media_type=None):
        """Create a safe preview-directory record."""
        locator = Path(str(filename or "")).name
        if not locator or locator != str(filename or ""):
            return None
        display_name = str(name or locator).strip() or locator
        return {
            "source": "preview",
            "locator": locator,
            "name": display_name,
            "category": ChatMediaService.category(display_name, media_type),
        }

    @staticmethod
    def external_records(content):
        """Extract unique HTTP(S) links from one assistant response."""
        records = []
        seen = set()
        for match in URL_PATTERN.findall(str(content or "")):
            url = ChatMediaService.normalize_external_url(match)
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if url in seen:
                continue
            seen.add(url)
            records.append({
                "source": "external",
                "locator": url,
                "name": url,
                "category": "external",
            })
        return records

    @staticmethod
    def normalize_external_url(value):
        """Remove trailing Markdown punctuation accidentally captured in URLs."""
        return normalize_external_locator(value)

    @staticmethod
    def generated_records(transcript):
        """Extract safe Generated-documents paths from MCP tool results."""
        directory = Path(
            current_app.config["GENERATED_DOCUMENT_DIRECTORY"]
        ).resolve()
        records = []
        seen = set()

        def add(value, key=""):
            raw = str(value or "").strip()
            if not raw or raw.startswith(("http://", "https://")):
                return
            candidate = Path(raw)
            try:
                if candidate.is_absolute():
                    resolved = candidate.resolve()
                    relative = resolved.relative_to(directory)
                elif key.lower() in PATH_KEYS and ".." not in candidate.parts:
                    relative = candidate
                else:
                    return
            except (OSError, ValueError):
                return
            locator = relative.as_posix()
            if not locator or locator in seen:
                return
            seen.add(locator)
            records.append({
                "source": "generated",
                "locator": locator,
                "name": relative.name,
                "category": ChatMediaService.category(relative.name),
            })

        def walk(value, key=""):
            if isinstance(value, dict):
                for child_key, child in value.items():
                    walk(child, str(child_key))
            elif isinstance(value, list):
                for child in value:
                    walk(child, key)
            elif isinstance(value, str):
                add(value, key)

        for message in transcript or []:
            if not isinstance(message, dict) or message.get("role") != "tool":
                continue
            content = message.get("content")
            try:
                content = json.loads(str(content or ""))
            except (TypeError, ValueError):
                content = str(content or "")
            walk(content)
        return records

    @staticmethod
    def raw_generated_records(content):
        """Recover safe relative output names from legacy raw tool calls."""
        records = []
        seen = set()
        for match in RAW_FILE_PATTERN.findall(str(content or "")):
            candidate = Path(match.strip())
            if candidate.is_absolute() or ".." in candidate.parts:
                continue
            locator = candidate.as_posix()
            if not locator or locator in seen:
                continue
            seen.add(locator)
            records.append({
                "source": "generated",
                "locator": locator,
                "name": candidate.name,
                "category": ChatMediaService.category(candidate.name),
            })
        return records

    def records_from_messages(self, messages):
        """Extract media records for the one-time migration or scope rebuild."""
        records = []
        for message in messages or []:
            if not isinstance(message, dict):
                continue
            for filename in message.get("preview_images") or []:
                record = self.preview_record(filename, media_type="image")
                if record:
                    records.append(record)
            for media in message.get("preview_media") or []:
                if not isinstance(media, dict):
                    continue
                record = self.preview_record(
                    media.get("filename"),
                    media.get("original_name"),
                    media.get("type"),
                )
                if record:
                    records.append(record)
            for preview in message.get("webpage_previews") or []:
                if not isinstance(preview, dict):
                    continue
                record = self.preview_record(
                    preview.get("filename"),
                    media_type="image",
                )
                if record:
                    records.append(record)
            if message.get("role") != "assistant":
                continue
            records.extend(self.external_records(message.get("content")))
            try:
                request_body = json.loads(message.get("request_body") or "{}")
                transcript = request_body.get("messages") or []
            except (AttributeError, TypeError, ValueError):
                transcript = []
            records.extend(self.generated_records(transcript))
            records.extend(self.raw_generated_records(message.get("content")))
        return records

    def enrich_generated_documents(self, messages):
        """Persist legacy MCP document cards during migration or import."""
        directory = Path(
            current_app.config["GENERATED_DOCUMENT_DIRECTORY"]
        ).resolve()
        enriched = []
        changed = False
        for message in messages or []:
            item = dict(message)
            if item.get("role") != "assistant" or item.get("generated_documents"):
                enriched.append(item)
                continue
            try:
                request_body = json.loads(item.get("request_body") or "{}")
                transcript = request_body.get("messages") or []
            except (AttributeError, TypeError, ValueError):
                transcript = []
            documents = []
            generated = self.generated_records(transcript)
            generated.extend(self.raw_generated_records(item.get("content")))
            for record in generated:
                safe_path = Path(record["locator"])
                if (
                    not safe_path.is_absolute()
                    and ".." not in safe_path.parts
                    and (directory / safe_path).is_file()
                ):
                    documents.append({"name": safe_path.as_posix()})
            if documents:
                item["generated_documents"] = documents
                changed = True
            enriched.append(item)
        return enriched, changed

    def ensure_backfilled(self, history):
        """Populate media.db once from existing active and saved conversations."""
        if self.repository.metadata(BACKFILL_KEY) == "complete":
            return
        active_messages, active_changed = self.enrich_generated_documents(
            history.messages()
        )
        if active_changed:
            history.messages(active_messages)
        self.repository.replace(
            self.records_from_messages(active_messages),
            "active",
        )
        for name in history.saved("list", "chat"):
            messages = history.saved("get", "chat", name) or []
            messages, changed = self.enrich_generated_documents(messages)
            if changed:
                history.saved("save", "chat", name, messages)
            self.repository.replace(
                self.records_from_messages(messages),
                "saved",
                name,
            )
        self.repository.metadata(BACKFILL_KEY, "complete")

    def list(self, scope_type="active", scope_name=""):
        """Return accordion-ready records with current local availability."""
        preview_directory = (
            Path(current_app.config["CHAT_DATABASE_PATH"]).parent / "preview"
        ).resolve()
        generated_directory = Path(
            current_app.config["GENERATED_DOCUMENT_DIRECTORY"]
        ).resolve()
        items = []
        for record in self.repository.list(scope_type, scope_name):
            source = record["source"]
            locator = record["locator"]
            if source == "preview":
                exists = (preview_directory / Path(locator).name).is_file()
                kind = "preview"
            elif source == "generated":
                safe_path = Path(locator)
                exists = (
                    not safe_path.is_absolute()
                    and ".." not in safe_path.parts
                    and (generated_directory / safe_path).is_file()
                )
                kind = "generated"
            else:
                exists = True
                kind = "external"
                locator = self.normalize_external_url(locator)
            items.append({
                "kind": kind,
                "filename": locator,
                "name": locator if source == "external" else record["name"],
                "exists": exists,
                "category": record["category"],
            })
        return items

    def add_active(self, records):
        """Register records for the current unsaved conversation."""
        self.repository.add(records, "active")

    def replace_active_from_messages(self, messages):
        """Rebuild active references after import or abort."""
        orphaned = self.repository.replace(
            self.records_from_messages(messages),
            "active",
        )
        self.delete_preview_files(orphaned)

    def copy_active_to_saved(self, name):
        """Replace a named saved chat's references from the active chat."""
        orphaned = self.repository.copy("active", "", "saved", name)
        self.delete_preview_files(orphaned)

    def copy_saved_to_active(self, name):
        """Replace active references from a named saved chat."""
        orphaned = self.repository.copy("saved", name, "active", "")
        self.delete_preview_files(orphaned)

    def delete_scope(self, scope_type, scope_name=""):
        """Drop one chat reference set and delete newly orphaned previews."""
        orphaned = self.repository.delete(scope_type, scope_name)
        self.delete_preview_files(orphaned)

    @staticmethod
    def delete_preview_files(locators):
        """Delete only safe orphaned files from instance/preview."""
        directory = (
            Path(current_app.config["CHAT_DATABASE_PATH"]).parent / "preview"
        ).resolve()
        for locator in locators or []:
            safe_name = Path(str(locator or "")).name
            if not safe_name or safe_name != str(locator or ""):
                continue
            try:
                (directory / safe_name).unlink(missing_ok=True)
            except OSError:
                current_app.logger.exception(
                    "Orphaned chat media could not be deleted: %s",
                    safe_name,
                )


CHAT_MEDIA = ChatMediaService()
