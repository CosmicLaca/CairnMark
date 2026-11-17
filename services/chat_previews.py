"""Filesystem persistence for chat attachment previews."""

import base64
import io
import json
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image


class ChatPreviewStore:
    """Save preview media and remove files no conversation references."""

    def directory(self):
        database_path = Path(current_app.config["CHAT_DATABASE_PATH"])
        directory = database_path.parent / "preview"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def save(self, data, extension, *, image_height=300, image_quality=60):
        """Save decoded media, optionally normalizing an image to JPEG."""
        try:
            decoded = base64.b64decode(data, validate=True)
            if not decoded:
                return None
            extension = extension.lstrip(".").lower()
            if extension == "jpg":
                with Image.open(io.BytesIO(decoded)) as image:
                    if image.height <= 0:
                        return None
                    width = max(1, int(image.width * image_height / image.height))
                    image = image.resize((width, image_height), Image.LANCZOS)
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")
                    filename = f"preview-{uuid.uuid4().hex}.jpg"
                    image.save(
                        self.directory() / filename,
                        format="JPEG",
                        quality=image_quality,
                    )
                    return filename
            if extension not in {"mp3", "mp4", "wav"}:
                extension = "bin"
            filename = f"preview-{uuid.uuid4().hex}.{extension}"
            (self.directory() / filename).write_bytes(decoded)
            return filename
        except Exception:  # noqa: BLE001
            current_app.logger.exception("Chat preview could not be saved")
            return None

    @staticmethod
    def filenames(messages):
        """Return safe preview filenames referenced by message dictionaries."""
        names = []
        for message in messages or []:
            if not isinstance(message, dict):
                continue
            images = message.get("preview_images") or []
            if isinstance(images, str):
                try:
                    images = json.loads(images)
                except (TypeError, ValueError):
                    images = [
                        part.strip() for part in images.split(",") if part.strip()
                    ]
            if not isinstance(images, list):
                images = [images]
            names.extend(str(item) for item in images if item)
            media = message.get("preview_media") or []
            if isinstance(media, str):
                try:
                    media = json.loads(media)
                except (TypeError, ValueError):
                    media = []
            if isinstance(media, list):
                names.extend(
                    str(item["filename"])
                    for item in media
                    if isinstance(item, dict) and item.get("filename")
                )
        return [Path(name).name for name in names]

    def delete_unreferenced(self, candidates, *referenced_message_groups):
        """Delete candidate files absent from every supplied message group."""
        in_use = {
            filename
            for messages in referenced_message_groups
            for filename in self.filenames(messages)
        }
        directory = self.directory().resolve()
        for filename in {Path(str(name)).name for name in candidates if name} - in_use:
            path = (directory / filename).resolve()
            if path.parent != directory:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                current_app.logger.exception(
                    "Preview file could not be deleted: %s", path
                )
