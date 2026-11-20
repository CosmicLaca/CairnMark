"""Atomic JSON export support for active and saved chats."""

import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app


EXPORT_FORMAT = "cairnmark-chat"
EXPORT_VERSION = 1
SQL_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
FILENAME_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def normalize_chat_filename(value):
    """Return a readable cross-platform filename component."""
    normalized = unicodedata.normalize("NFKC", str(value or "").strip())
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip(" ._")
    normalized = normalized[:80].rstrip(" ._") or "chat"
    if normalized.upper() in WINDOWS_RESERVED_NAMES:
        normalized = f"chat_{normalized}"
    return normalized


class ChatExportRepository:
    """Write import-ready chat documents to the configured export folder."""

    def __init__(self, directory=None):
        self._directory = Path(directory) if directory else None

    @property
    def directory(self):
        """Return the explicit or application-configured export directory."""
        if self._directory is not None:
            return self._directory
        return Path(current_app.config["CHAT_EXPORT_DIRECTORY"])

    def export(self, messages, *, saved_chat_name=None, now=None):
        """Atomically export one complete active or saved conversation."""
        moment = now or datetime.now(timezone.utc)
        source_type = "saved" if saved_chat_name else "active"
        source_name = str(saved_chat_name).strip() if saved_chat_name else None
        stem_name = normalize_chat_filename(source_name) if source_name else "main"
        filename = (
            f"Exported-{stem_name}-{moment.strftime(FILENAME_TIMESTAMP_FORMAT)}.json"
        )
        payload = {
            "format": EXPORT_FORMAT,
            "version": EXPORT_VERSION,
            "exported_at": moment.strftime(SQL_TIMESTAMP_FORMAT),
            "source": {"type": source_type, "name": source_name},
            "messages": messages,
        }
        self._atomic_write(
            self.directory / filename,
            json.dumps(payload, indent=2, ensure_ascii=False),
        )
        return filename

    @staticmethod
    def import_messages(document):
        """Validate an exported document and return its complete message list."""
        if not isinstance(document, dict):
            raise ValueError("Invalid chat export document.")
        if document.get("format") != EXPORT_FORMAT:
            raise ValueError("Unsupported chat export format.")
        if document.get("version") != EXPORT_VERSION:
            raise ValueError("Unsupported chat export version.")
        messages = document.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("The exported chat contains no messages.")
        validated = []
        for index, message in enumerate(messages, start=1):
            if not isinstance(message, dict):
                raise ValueError(f"Message {index} is invalid.")
            if message.get("role") not in {"user", "assistant", "system"}:
                raise ValueError(f"Message {index} has an invalid role.")
            if not isinstance(message.get("content"), str):
                raise ValueError(f"Message {index} has invalid content.")
            created_at = message.get("created_at")
            if not isinstance(created_at, str):
                raise ValueError(f"Message {index} has no creation date.")
            try:
                datetime.strptime(created_at, SQL_TIMESTAMP_FORMAT)
            except ValueError as error:
                raise ValueError(
                    f"Message {index} has an invalid creation date."
                ) from error
            validated.append(dict(message))
        return validated

    @staticmethod
    def _atomic_write(target, content):
        """Write UTF-8 content beside the target before replacing it."""
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, target)
        except Exception:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)
            raise
