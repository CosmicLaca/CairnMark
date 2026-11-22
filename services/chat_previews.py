"""Filesystem persistence for chat attachment previews."""

import base64
import io
import json
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image

from services.chat_attachments import (
    convert_audio_attachment,
    convert_video_attachment,
    extract_video_audio_attachment,
    merge_video_audio,
    video_has_audio,
)


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

    def save_attachments(
        self,
        attachments,
        *,
        save_original_media=False,
        video_fps=2,
    ):
        """Persist requested previews and return message metadata for them."""
        preview_images = []
        preview_media = []
        has_audio = False
        for attachment in attachments or []:
            attachment_type = attachment.get("type")
            if attachment_type == "image":
                filename = self.save(attachment.get("data", ""), "jpg")
                if filename:
                    preview_images.append(filename)
            elif attachment_type == "audio":
                has_audio = True
                if save_original_media:
                    converted = convert_audio_attachment(attachment)
                    filename = self.save(
                        converted.get("data", attachment.get("data", "")),
                        "mp3",
                    )
                    if filename:
                        preview_media.append(
                            self._media_record("audio", filename, attachment)
                        )
            elif attachment_type == "video" and save_original_media:
                converted = convert_video_attachment(attachment, fps=video_fps)
                data = converted["data"]
                if attachment.get("attach_audio") and video_has_audio(
                    attachment.get("data", "")
                ):
                    audio = extract_video_audio_attachment(attachment)
                    if audio is not None:
                        data = merge_video_audio(data, audio.get("data", "")) or data
                filename = self.save(data, "mp4")
                if filename:
                    preview_media.append(
                        self._media_record("video", filename, attachment)
                    )
            elif attachment_type == "video" and attachment.get("preview_data"):
                filename = self.save(attachment["preview_data"], "jpg")
                if filename:
                    preview_images.append(filename)
            elif attachment_type == "document":
                preview_media.append(
                    {
                        "type": "document",
                        "filename": "",
                        "original_name": attachment.get("original_name", ""),
                    }
                )
        return {
            "preview_images": preview_images,
            "preview_media": preview_media,
            "has_audio": has_audio and not save_original_media,
        }

    @staticmethod
    def _media_record(media_type, filename, attachment):
        return {
            "type": media_type,
            "filename": filename,
            "original_name": attachment.get("original_name", ""),
        }

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
            webpage_previews = message.get("webpage_previews") or []
            if isinstance(webpage_previews, str):
                try:
                    webpage_previews = json.loads(webpage_previews)
                except (TypeError, ValueError):
                    webpage_previews = []
            if isinstance(webpage_previews, list):
                names.extend(
                    str(item["filename"])
                    for item in webpage_previews
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
