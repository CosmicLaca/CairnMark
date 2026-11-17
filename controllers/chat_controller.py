"""Chat interface context and message handling for the home page."""

import base64
import io
import json
import re
import time
import uuid
from pathlib import Path

import markdown
from flask import (
    Response,
    current_app,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)

from models.chat_storage import (
    add_chat_message,
    clear_chat_messages,
    delete_last_chat_message,
    delete_saved_chat,
    delete_saved_system_prompt,
    get_chat_settings,
    get_saved_chat,
    get_saved_system_prompt,
    list_chat_messages,
    list_saved_chats,
    list_saved_system_prompts,
    load_saved_chat,
    save_chat_settings,
    save_saved_chat,
    save_saved_system_prompt,
)
from services.model_providers import (
    ModelProviderService,
    ProviderOfflineError,
    ProviderValidationError,
)

MARKDOWN_EXTENSIONS = ("fenced_code", "tables", "sane_lists")

CHAT_PARAMETER_CONVERTERS = {
    "temperature": (float, "Temperature"),
    "top_p": (float, "Top P"),
    "top_k": (int, "Top K"),
    "seed": (int, "Seed"),
    "history_limit": (int, "Recent messages kept"),
}


def _optional_parameter(value, label, converter):
    """Convert a numeric field, treating blank values as unset."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        return converter(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a valid number.") from error


def _parameter_values(data):
    return {
        key: _optional_parameter(data.get(key), label, converter)
        for key, (converter, label) in CHAT_PARAMETER_CONVERTERS.items()
    }


MODEL_PARAMETER_NAME = re.compile(r"[A-Za-z0-9_.]{1,64}")
MODEL_PARAMETER_LIMIT = 128
MODEL_PARAMETER_TEXT_LIMIT = 4096

ATTACHMENT_TYPES = {"image", "document", "video", "audio"}
ATTACHMENT_LIMIT = 8
ATTACHMENT_DATA_LIMIT = 100 * 1024 * 1024
MAX_IMAGE_PIXELS = 1_200_000


def _model_parameter_values(value):
    """Validate model parameters submitted from the chat parameter modal."""
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError("Model parameters must be an object.")
    if len(value) > MODEL_PARAMETER_LIMIT:
        raise ValueError("Too many model parameters were supplied.")
    cleaned = {}
    for raw_key, item in value.items():
        key = str(raw_key).strip()
        if not MODEL_PARAMETER_NAME.fullmatch(key):
            raise ValueError("Model parameter names must be simple identifiers.")
        cleaned[key] = _model_parameter_value(item)
    return cleaned


def _model_parameter_value(item):
    """Return one JSON-safe model parameter value or raise a validation error."""
    if isinstance(item, bool) or isinstance(item, (int, float)):
        return item
    if isinstance(item, str):
        if len(item) > MODEL_PARAMETER_TEXT_LIMIT:
            raise ValueError("A model parameter value is too long.")
        return item
    if isinstance(item, list):
        if len(item) > MODEL_PARAMETER_LIMIT:
            raise ValueError("A model parameter list is too long.")
        if all(
            isinstance(entry, str) or isinstance(entry, (bool, int, float))
            for entry in item
        ):
            return item
    raise ValueError("Model parameter values must be simple JSON values.")


def _mime_for_name(name):
    lower = str(name or "").lower()
    if lower.endswith(".txt"):
        return "text/plain"
    if lower.endswith(".md"):
        return "text/markdown"
    if lower.endswith(".doc"):
        return "application/msword"
    if lower.endswith(".rtf"):
        return "application/rtf"
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".mp4"):
        return "video/mp4"
    if lower.endswith(".mp3"):
        return "audio/mpeg"
    if lower.endswith(".wav"):
        return "audio/wav"
    return "application/octet-stream"


def _attachment_values(value):
    """Validate and normalize chat attachments submitted by the browser."""
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("Attachments must be a list.")
    if len(value) > ATTACHMENT_LIMIT:
        raise ValueError("Too many attachments were supplied.")
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Attachments must be objects.")
        attachment_type = str(item.get("type") or "").strip().lower()
        if attachment_type not in ATTACHMENT_TYPES:
            raise ValueError("Attachment type must be image, document, video, or audio.")
        data = item.get("data")
        if not isinstance(data, str) or not data.strip():
            raise ValueError("Attachment data is required.")
        data = data.strip()
        try:
            decoded = base64.b64decode(data, validate=True)
        except Exception as error:  # noqa: BLE001
            raise ValueError("Attachment data must be valid base64.") from error
        if not decoded or len(decoded) > ATTACHMENT_DATA_LIMIT:
            raise ValueError("Attachment data is too large.")
        mime_type = str(item.get("mime_type") or "").strip()
        if not mime_type:
            mime_type = _mime_for_name(item.get("name"))
        preview_data = item.get("preview_data")
        if isinstance(preview_data, str):
            preview_data = preview_data.strip()
            if preview_data:
                try:
                    base64.b64decode(preview_data, validate=True)
                except Exception as error:  # noqa: BLE001
                    raise ValueError("Preview data must be valid base64.") from error
            else:
                preview_data = None
        else:
            preview_data = None
        cleaned.append(
            {
                "type": attachment_type,
                "data": data,
                "mime_type": mime_type,
                "preview_data": preview_data,
                "attach_audio": bool(item.get("attach_audio")),
                "original_name": str(item.get("original_name") or item.get("name") or "").strip(),
            }
        )
    return cleaned


def _resize_image_attachment(attachment):
    """Resize an image attachment above 1.2 megapixels when Pillow is available."""
    if not isinstance(attachment, dict) or attachment.get("type") != "image":
        return attachment
    try:
        from PIL import Image
    except ImportError:
        return attachment
    try:
        decoded = base64.b64decode(attachment["data"], validate=True)
        with Image.open(io.BytesIO(decoded)) as image:
            pixels = image.width * image.height
            if pixels <= MAX_IMAGE_PIXELS:
                return attachment
            scale = (MAX_IMAGE_PIXELS / pixels) ** 0.5
            size = (
                max(1, int(image.width * scale)),
                max(1, int(image.height * scale)),
            )
            resized = image.resize(size, Image.LANCZOS)
            if resized.mode in ("RGBA", "P"):
                resized = resized.convert("RGB")
            output = io.BytesIO()
            resized.save(output, format="JPEG", quality=90)
            return {
                "type": "image",
                "data": base64.b64encode(output.getvalue()).decode("ascii"),
                "mime_type": "image/jpeg",
            }
    except Exception:  # noqa: BLE001
        return attachment


def _convert_video_attachment(attachment):
    """Resize/re-encode a video attachment to max 640px side, 2 fps, lower quality, mp4.

    Returns the original attachment unchanged when ffmpeg-python or ffmpeg is
    unavailable or conversion fails, so chat still works without the toolchain.
    """
    if not isinstance(attachment, dict) or attachment.get("type") != "video":
        return attachment
    try:
        import ffmpeg
    except ImportError:
        return attachment
    try:
        decoded = base64.b64decode(attachment["data"], validate=True)
    except Exception:  # noqa: BLE001
        return attachment
    import os
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input")
            with open(input_path, "wb") as handle:
                handle.write(decoded)
            probe = ffmpeg.probe(input_path)
            streams = probe.get("streams", []) if isinstance(probe, dict) else []
            video_stream = next(
                (s for s in streams if s.get("codec_type") == "video"), None
            )
            if video_stream is None:
                return attachment
            width = int(video_stream.get("width") or 0)
            height = int(video_stream.get("height") or 0)
            if width <= 0 or height <= 0:
                return attachment
            stream = ffmpeg.input(input_path)
            video = stream.video
            if max(width, height) > 480:
                if width >= height:
                    video = video.filter("scale", 480, -2)
                else:
                    video = video.filter("scale", -2, 480)
            video = video.filter("fps", fps=2)
            output_path = os.path.join(tmpdir, "output.mp4")
            output_args = {
                "vcodec": "libx264",
                "crf": 28,
                "preset": "fast",
                "pix_fmt": "yuv420p",
                "movflags": "+faststart",
            }
            # Always strip audio: audio is sent separately when attach_audio is on.
            ffmpeg.output(
                video, output_path, **output_args,
            ).overwrite_output().run(quiet=True)
            with open(output_path, "rb") as handle:
                converted = handle.read()
            if not converted:
                return attachment
            return {
                "type": "video",
                "data": base64.b64encode(converted).decode("ascii"),
                "mime_type": "video/mp4",
                "preview_data": attachment.get("preview_data"),
            }
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Video attachment could not be converted")
        return attachment


def _convert_audio_attachment(attachment):
    """Convert an audio attachment to a 64 kbit/s MP3."""
    if not isinstance(attachment, dict) or attachment.get("type") != "audio":
        return attachment
    try:
        import ffmpeg
    except ImportError:
        return attachment
    try:
        decoded = base64.b64decode(attachment["data"], validate=True)
    except Exception:  # noqa: BLE001
        return attachment
    import os
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input")
            with open(input_path, "wb") as handle:
                handle.write(decoded)
            probe = ffmpeg.probe(input_path)
            streams = probe.get("streams", []) if isinstance(probe, dict) else []
            if not any(s.get("codec_type") == "audio" for s in streams):
                return attachment
            stream = ffmpeg.input(input_path)
            audio = stream.audio
            output_path = os.path.join(tmpdir, "output.mp3")
            ffmpeg.output(
                audio, output_path,
                acodec="libmp3lame", audio_bitrate="64k",
            ).overwrite_output().run(quiet=True)
            with open(output_path, "rb") as handle:
                converted = handle.read()
            if not converted:
                return attachment
            return {
                "type": "audio",
                "data": base64.b64encode(converted).decode("ascii"),
                "mime_type": "audio/mpeg",
                "preview_data": attachment.get("preview_data"),
            }
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Audio attachment could not be converted")
        return attachment


def _probe_audio_duration(path):
    """Return the audio stream duration in seconds, or None if unavailable."""
    try:
        import ffmpeg
    except ImportError:
        return None
    try:
        probe = ffmpeg.probe(path)
        streams = probe.get("streams", []) if isinstance(probe, dict) else []
        audio_stream = next(
            (s for s in streams if s.get("codec_type") == "audio"), None
        )
        if audio_stream is None:
            return None
        duration = audio_stream.get("duration")
        if duration is None and isinstance(probe, dict):
            duration = probe.get("format", {}).get("duration")
        if duration is None:
            return None
        return float(duration)
    except Exception:  # noqa: BLE001
        return None


def _video_has_audio(data):
    import os
    import tempfile

    try:
        decoded = base64.b64decode(data, validate=True)
    except Exception:  # noqa: BLE001
        return False
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input")
            with open(input_path, "wb") as handle:
                handle.write(decoded)
            return _probe_audio_duration(input_path) is not None
    except Exception:  # noqa: BLE001
        return False


def _extract_video_audio_attachment(attachment):
    """Extract the audio track of a video as a 64 kbit/s MP3 attachment."""
    if not isinstance(attachment, dict) or attachment.get("type") != "video":
        return None
    try:
        import ffmpeg
    except ImportError:
        return None
    try:
        decoded = base64.b64decode(attachment["data"], validate=True)
    except Exception:  # noqa: BLE001
        return None
    import os
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input")
            with open(input_path, "wb") as handle:
                handle.write(decoded)
            if _probe_audio_duration(input_path) is None:
                return None
            stream = ffmpeg.input(input_path)
            audio = stream.audio
            output_path = os.path.join(tmpdir, "output.mp3")
            ffmpeg.output(
                audio, output_path,
                acodec="libmp3lame", audio_bitrate="64k",
            ).overwrite_output().run(quiet=True)
            with open(output_path, "rb") as handle:
                converted = handle.read()
            if not converted:
                return None
            return {
                "type": "audio",
                "data": base64.b64encode(converted).decode("ascii"),
                "mime_type": "audio/mpeg",
            }
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Video audio could not be extracted")
        return None


def _merge_video_audio(video_data, audio_data):
    """Mux a converted (audio-less) video with a separate audio track into one MP4."""
    if not video_data or not audio_data:
        return None
    try:
        import ffmpeg
    except ImportError:
        return None
    import os
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            audio_path = os.path.join(tmpdir, "audio.mp3")
            output_path = os.path.join(tmpdir, "merged.mp4")
            with open(video_path, "wb") as handle:
                handle.write(base64.b64decode(video_data, validate=True))
            with open(audio_path, "wb") as handle:
                handle.write(base64.b64decode(audio_data, validate=True))
            video_stream = ffmpeg.input(video_path).video
            audio_stream = ffmpeg.input(audio_path).audio
            ffmpeg.output(
                video_stream, audio_stream, output_path,
                vcodec="copy", acodec="aac", audio_bitrate="64k",
                movflags="+faststart",
            ).overwrite_output().run(quiet=True)
            with open(output_path, "rb") as handle:
                merged = handle.read()
            if not merged:
                return None
            return base64.b64encode(merged).decode("ascii")
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Video and audio could not be merged")
        return None


def _process_attachments(attachments):
    result = []
    for item in (attachments or []):
        if isinstance(item, dict) and item.get("type") == "video":
            result.append(_convert_video_attachment(item))
        elif isinstance(item, dict) and item.get("type") == "image":
            result.append(_resize_image_attachment(item))
        elif isinstance(item, dict) and item.get("type") == "audio":
            result.append(_convert_audio_attachment(item))
        else:
            result.append(item)
    return result


def _build_chat_request_body(service, provider, model, messages, request_parameters, extra_parameters, attachments=None):
    """Return the JSON-serializable body sent for an assistant chat turn."""
    body = {"model": model, "messages": messages}
    body.update({key: value for key, value in (request_parameters or {}).items() if value is not None})
    filtered_extra = service.local_extra_parameters(provider, extra_parameters)
    body.update(filtered_extra)
    if attachments:
        body["attachments"] = [
            {
                "type": item["type"],
                "data": item["data"],
                "mime_type": item["mime_type"],
            }
            for item in attachments
        ]
    return body


def render_markdown_html(text):
    """Render Markdown text to HTML using the same extensions as About."""
    return markdown.markdown(str(text or ""), extensions=MARKDOWN_EXTENSIONS)


def _preview_directory():
    database_path = Path(current_app.config.get("CHAT_DATABASE_PATH", ""))
    if not database_path.is_absolute():
        database_path = Path(current_app.root_path).parent / database_path
    directory = database_path.parent / "preview"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _save_preview_media(data, extension):
    """Save converted media bytes to instance/preview and return the filename."""
    if not data:
        return None
    try:
        decoded = base64.b64decode(data, validate=True)
    except Exception:  # noqa: BLE001
        return None
    if not decoded:
        return None
    safe_ext = (extension or "").lstrip(".").lower()
    if safe_ext not in {"mp3", "mp4", "wav"}:
        safe_ext = "bin"
    filename = f"preview-{uuid.uuid4().hex}.{safe_ext}"
    try:
        (_preview_directory() / filename).write_bytes(decoded)
        return filename
    except OSError:  # noqa: BLE001
        current_app.logger.exception("Preview media could not be saved")
        return None


def _preview_filenames_from_messages(messages):
    """Collect preview filenames referenced by a list of message dicts."""
    names = []
    for message in (messages or []):
        if not isinstance(message, dict):
            continue
        value = message.get("preview_images")
        if isinstance(value, list):
            names.extend(str(item) for item in value if item)
        elif isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    names.extend(str(item) for item in parsed if item)
                elif parsed:
                    names.append(str(parsed))
            except (ValueError, TypeError):
                names.extend(part.strip() for part in value.split(",") if part.strip())
        media_value = message.get("preview_media")
        if isinstance(media_value, list):
            for item in media_value:
                if isinstance(item, dict) and item.get("filename"):
                    names.append(str(item["filename"]))
        elif isinstance(media_value, str) and media_value.strip():
            try:
                parsed = json.loads(media_value)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and item.get("filename"):
                            names.append(str(item["filename"]))
                        elif item:
                            names.append(str(item))
            except (ValueError, TypeError):
                pass
    return names


def _preview_filenames_in_use():
    """Collect preview filenames still referenced by any chat (current or saved)."""
    in_use = set()
    try:
        for message in list_chat_messages():
            for name in _preview_filenames_from_messages([message]):
                in_use.add(Path(str(name)).name)
    except Exception:  # noqa: BLE001
        pass
    try:
        from models.chat_storage import list_saved_chats, get_saved_chat

        for name in list_saved_chats():
            saved = get_saved_chat(name)
            for ref in _preview_filenames_from_messages(saved or []):
                in_use.add(Path(str(ref)).name)
    except Exception:  # noqa: BLE001
        pass
    return in_use


def _delete_preview_files(filenames, in_use=None):
    """Delete preview image files, ignoring missing or unsafe names.

    Files in the ``in_use`` set (still referenced elsewhere) are kept.
    """
    if in_use is None:
        in_use = _preview_filenames_in_use()
    in_use = {Path(str(name)).name for name in (in_use or set())}
    directory = _preview_directory()
    for name in (filenames or []):
        safe_name = Path(str(name)).name
        if not safe_name or safe_name in in_use:
            continue
        target = directory / safe_name
        try:
            target.unlink(missing_ok=True)
        except OSError:  # noqa: BLE001
            current_app.logger.exception("Preview file could not be deleted: %s", safe_name)


def _save_preview_image(data):
    """Create a 300px-high JPEG preview and return its randomized filename."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        decoded = base64.b64decode(data, validate=True)
        with Image.open(io.BytesIO(decoded)) as image:
            if image.height <= 0:
                return None
            scale = 300 / image.height
            width = max(1, int(image.width * scale))
            resized = image.resize((width, 300), Image.LANCZOS)
            if resized.mode in ("RGBA", "P"):
                resized = resized.convert("RGB")
            filename = f"preview-{uuid.uuid4().hex}.jpg"
            resized.save(_preview_directory() / filename, format="JPEG", quality=60)
            return filename
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Preview image could not be saved")
        return None


class ChatController:
    """Provide chat context and handle chat messages."""

    def __init__(self, service=None):
        self.service = service or ModelProviderService()

    def context(self):
        settings = get_chat_settings()
        messages = list_chat_messages()
        return {
            "chat_settings": settings,
            "chat_messages": messages,
            "active_models": self.service.active_models(),
            "saved_chats": list_saved_chats(),
            "saved_system_prompts": list_saved_system_prompts(),
        }

    def _parse_request(self):
        data = request.get_json(silent=True) or {}
        model_spec = (data.get("model") or "").strip()
        user_message = (data.get("message") or "").strip()
        system_prompt = data.get("system_prompt") or ""
        saved_name_raw = (data.get("saved_system_prompt_name") or "").strip()
        saved_name = ""
        if saved_name_raw:
            stored = get_saved_system_prompt(saved_name_raw)
            if stored is None and system_prompt.strip():
                save_saved_system_prompt(saved_name_raw, system_prompt)
                stored = system_prompt
            if stored == system_prompt:
                saved_name = saved_name_raw
        return (
            data,
            model_spec,
            user_message,
            system_prompt,
            saved_name,
            _parameter_values(data),
            _model_parameter_values(data.get("model_params")),
            _attachment_values(data.get("attachments")),
        )

    def send(self):
        try:
            (
                _data,
                model_spec,
                user_message,
                system_prompt,
                saved_name,
                parameters,
                extra_parameters,
                attachments,
            ) = self._parse_request()
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        if not user_message:
            return jsonify({"error": "Message is required."}), 400
        try:
            provider, model = self.service.resolve_online_model(model_spec)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderOfflineError as error:
            return jsonify({"error": str(error)}), 503

        save_original_media = bool(_data.get("save_original_media"))
        preview_images = []
        preview_media = []
        has_audio_attachment = False
        for attachment in attachments or []:
            attachment_type = attachment.get("type")
            if attachment_type == "image":
                filename = _save_preview_image(attachment.get("data", ""))
                if filename:
                    preview_images.append(filename)
            elif attachment_type == "audio":
                has_audio_attachment = True
                if save_original_media:
                    converted = _convert_audio_attachment(attachment)
                    data = converted.get("data", attachment.get("data", ""))
                    filename = _save_preview_media(data, "mp3")
                    if filename:
                        preview_media.append({"type": "audio", "filename": filename, "original_name": attachment.get("original_name", "")})
            elif attachment_type == "video":
                if save_original_media:
                    converted = _convert_video_attachment(attachment)
                    data = converted.get("data", attachment.get("data", ""))
                    if attachment.get("attach_audio") and _video_has_audio(attachment.get("data", "")):
                        audio_att = _extract_video_audio_attachment(attachment)
                        if audio_att is not None:
                            merged = _merge_video_audio(converted.get("data", ""), audio_att.get("data", ""))
                            if merged:
                                data = merged
                    filename = _save_preview_media(data, "mp4")
                    if filename:
                        preview_media.append({"type": "video", "filename": filename, "original_name": attachment.get("original_name", "")})
                elif attachment.get("preview_data"):
                    filename = _save_preview_image(attachment.get("preview_data", ""))
                    if filename:
                        preview_images.append(filename)
        add_chat_message(
            "user",
            user_message,
            preview_images=preview_images,
            has_audio=has_audio_attachment and not save_original_media,
            preview_media=preview_media,
        )

        stream_requested = (
            request.args.get("stream") == "1"
            or "text/event-stream" in (request.accept_mimetypes or "")
        )

        # Build messages list from the most recent turns kept by the user.
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt})
        history = [
            message
            for message in list_chat_messages()
            if message["role"] in ("user", "assistant")
        ]
        history_limit = parameters.get("history_limit")
        if history_limit is not None:
            current_turn = history[-1:]
            previous = history[:-1]
            if history_limit <= 0:
                history = current_turn
            else:
                # "Recent messages kept" counts complete user/assistant pairs,
                # not individual messages, so a kept unit is two messages.
                kept_previous = history_limit * 2
                start = max(0, len(previous) - kept_previous)
                # Keep pair boundaries: each retained block starts with a
                # user message rather than an orphaned assistant reply.
                if start % 2:
                    start += 1
                history = previous[start:] + current_turn
        messages.extend(
            {"role": message["role"], "content": message["content"]}
            for message in history
        )

        request_parameters = {
            key: parameters.get(key)
            for key in (
                "temperature",
                "top_p",
                "top_k",
                "seed",
            )
        }

        split_needed = any(
            isinstance(item, dict)
            and item.get("type") == "video"
            and bool(item.get("attach_audio"))
            for item in (attachments or [])
        )

        needs_conversion = any(
            isinstance(item, dict) and item.get("type") in ("video", "audio")
            for item in (attachments or [])
        )

        audio_request_body = None

        if not stream_requested:
            if split_needed:
                video_attachments = []
                audio_attachments = []
                for item in (attachments or []):
                    if not isinstance(item, dict):
                        video_attachments.append(item)
                        continue
                    if item.get("type") == "video":
                        video_attachments.append(_convert_video_attachment(item))
                        if item.get("attach_audio") and _video_has_audio(item.get("data", "")):
                            audio_att = _extract_video_audio_attachment(item)
                            if audio_att is not None:
                                audio_attachments.append(audio_att)
                    elif item.get("type") == "audio":
                        audio_attachments.append(_convert_audio_attachment(item))
                    else:
                        video_attachments.append(item)
                # Build audio_messages (modify user prompt) before building audio_request_body
                audio_messages = [dict(m) for m in messages]
                for index in range(len(audio_messages) - 1, -1, -1):
                    if audio_messages[index].get("role") == "user":
                        audio_messages[index]["content"] = "Analyze the attached audio: transcribe any spoken words, and if there is no speech, describe the audio content (music, sounds, or noise)."
                        break

                request_body = _build_chat_request_body(
                    self.service,
                    provider,
                    model,
                    messages,
                    request_parameters,
                    extra_parameters,
                    attachments=video_attachments,
                )
                audio_request_body = None
                if audio_attachments:
                    audio_request_body = _build_chat_request_body(
                        self.service,
                        provider,
                        model,
                        audio_messages,
                        request_parameters,
                        extra_parameters,
                        attachments=audio_attachments,
                    )
                started = time.monotonic()
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
                try:
                    text1, usage1 = self.service.chat_completion_with_params(
                        provider,
                        model,
                        messages,
                        **request_parameters,
                        extra_parameters=extra_parameters,
                        attachments=video_attachments,
                    )
                    text2 = ""
                    usage2 = {"prompt_tokens": 0, "completion_tokens": 0}
                    if audio_attachments:
                        text2, usage2 = self.service.chat_completion_with_params(
                            provider,
                            model,
                            audio_messages,
                            **request_parameters,
                            extra_parameters=extra_parameters,
                            attachments=audio_attachments,
                        )
                    response_text = text1
                    if text2:
                        response_text = f"{text1}\n\nAudio transcription:\n{text2}"
                    usage = {
                        "prompt_tokens": usage1.get("prompt_tokens", 0) + usage2.get("prompt_tokens", 0),
                        "completion_tokens": usage1.get("completion_tokens", 0) + usage2.get("completion_tokens", 0),
                    }
                except Exception as error:  # noqa: BLE001
                    current_app.logger.exception(
                        "Chat request failed for provider=%s model=%s", provider, model
                    )
                    return jsonify({"error": str(error)}), 502
            else:
                attachments = _process_attachments(attachments)
                request_body = _build_chat_request_body(
                    self.service,
                    provider,
                    model,
                    messages,
                    request_parameters,
                    extra_parameters,
                    attachments=attachments,
                )
                started = time.monotonic()
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
                try:
                    response_text, usage = self.service.chat_completion_with_params(
                        provider,
                        model,
                        messages,
                        **request_parameters,
                        extra_parameters=extra_parameters,
                        attachments=attachments,
                    )
                except Exception as error:  # noqa: BLE001
                    current_app.logger.exception(
                        "Chat request failed for provider=%s model=%s", provider, model
                    )
                    return jsonify({"error": str(error)}), 502
            if audio_request_body:
                request_body = {
                    "video_request": request_body,
                    "audio_request": audio_request_body,
                }

            elapsed = round(time.monotonic() - started, 2)

            add_chat_message(
                "assistant",
                response_text,
                model_name=model,
                provider=provider,
                response_time=elapsed,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                system_prompt=system_prompt,
                saved_system_prompt_name=saved_name,
                request_body=json.dumps(request_body),
            )
            return jsonify(
                {
                    "response": response_text,
                    "response_html": render_markdown_html(response_text),
                    "time": elapsed,
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "provider": provider,
                    "model": model,
                    "saved_system_prompt_name": saved_name,
                    "system_prompt": system_prompt,
                    "request_body": json.dumps(request_body),
                    "messages": list_chat_messages(),
                }
            )

        def generate():
            started = time.monotonic()
            usage = {"prompt_tokens": 0, "completion_tokens": 0}
            response_text = ""
            try:
                if split_needed:
                    yield f"data: {json.dumps({'type': 'status', 'text': 'Converting attachment…'})}\n\n"
                    video_attachments = []
                    audio_attachments = []
                    for item in (attachments or []):
                        if not isinstance(item, dict):
                            video_attachments.append(item)
                            continue
                        if item.get("type") == "video":
                            video_attachments.append(_convert_video_attachment(item))
                            if item.get("attach_audio") and _video_has_audio(item.get("data", "")):
                                audio_att = _extract_video_audio_attachment(item)
                                if audio_att is not None:
                                    audio_attachments.append(audio_att)
                        elif item.get("type") == "audio":
                            audio_attachments.append(_convert_audio_attachment(item))
                        else:
                            video_attachments.append(item)
                    yield f"data: {json.dumps({'type': 'status', 'text': 'thinking…'})}\n\n"
                    audio_messages = [dict(m) for m in messages]
                    for index in range(len(audio_messages) - 1, -1, -1):
                        if audio_messages[index].get("role") == "user":
                            audio_messages[index]["content"] = "Analyze the attached audio: transcribe any spoken words, and if there is no speech, describe the audio content (music, sounds, or noise)."
                            break
                    text1, usage1 = self.service.chat_completion_with_params(
                        provider,
                        model,
                        messages,
                        **request_parameters,
                        extra_parameters=extra_parameters,
                        attachments=video_attachments,
                    )
                    text2 = ""
                    usage2 = {"prompt_tokens": 0, "completion_tokens": 0}
                    if audio_attachments:
                        text2, usage2 = self.service.chat_completion_with_params(
                            provider,
                            model,
                            audio_messages,
                            **request_parameters,
                            extra_parameters=extra_parameters,
                            attachments=audio_attachments,
                        )
                    response_text = text1
                    if text2:
                        response_text = f"{text1}\n\nAudio transcription:\n{text2}"
                    usage = {
                        "prompt_tokens": usage1.get("prompt_tokens", 0) + usage2.get("prompt_tokens", 0),
                        "completion_tokens": usage1.get("completion_tokens", 0) + usage2.get("completion_tokens", 0),
                    }
                    request_body = _build_chat_request_body(
                        self.service,
                        provider,
                        model,
                        messages,
                        request_parameters,
                        extra_parameters,
                        attachments=video_attachments,
                    )
                    audio_request_body = None
                    if audio_attachments:
                        audio_request_body = _build_chat_request_body(
                            self.service,
                            provider,
                            model,
                            audio_messages,
                            request_parameters,
                            extra_parameters,
                            attachments=audio_attachments,
                        )
                    if audio_request_body:
                        request_body = {
                            "video_request": request_body,
                            "audio_request": audio_request_body,
                        }
                else:
                    converted_attachments = attachments
                    if needs_conversion:
                        yield f"data: {json.dumps({'type': 'status', 'text': 'Converting attachment…'})}\n\n"
                        converted_attachments = _process_attachments(attachments)
                        yield f"data: {json.dumps({'type': 'status', 'text': 'thinking…'})}\n\n"
                    request_body = _build_chat_request_body(
                        self.service,
                        provider,
                        model,
                        messages,
                        request_parameters,
                        extra_parameters,
                        attachments=converted_attachments,
                    )
                    for event in self.service.chat_completion_with_params_stream(
                        provider,
                        model,
                        messages,
                        **request_parameters,
                        extra_parameters=extra_parameters,
                        attachments=converted_attachments,
                    ):
                        if event.get("type") == "chunk":
                            response_text += event.get("text", "")
                            yield f"data: {json.dumps(event)}\n\n"
                        elif event.get("type") == "done":
                            usage = event.get("usage", usage) or usage
                            yield f"data: {json.dumps(event)}\n\n"
                elapsed = round(time.monotonic() - started, 2)
                add_chat_message(
                    "assistant",
                    response_text,
                    model_name=model,
                    provider=provider,
                    response_time=elapsed,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    system_prompt=system_prompt,
                    saved_system_prompt_name=saved_name,
                    request_body=json.dumps(request_body),
                )
                payload = {
                    "type": "result",
                    "response": response_text,
                    "response_html": render_markdown_html(response_text),
                    "time": elapsed,
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "provider": provider,
                    "model": model,
                    "saved_system_prompt_name": saved_name,
                    "system_prompt": system_prompt,
                    "request_body": json.dumps(request_body),
                }
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as error:  # noqa: BLE001
                current_app.logger.exception(
                    "Chat stream failed for provider=%s model=%s", provider, model
                )
                yield f"data: {json.dumps({'type': 'error', 'error': str(error)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
        )

    def preview(self, filename):
        directory = _preview_directory()
        safe_name = Path(filename).name
        if not safe_name or safe_name != filename:
            return ("", 404)
        file_path = directory / safe_name
        if not file_path.is_file():
            return ("", 404)
        return send_from_directory(directory, safe_name)

    def save_settings(self):
        """Persist only the model, system prompt, and generation controls.

        Additional model parameters from the chat modal are session-only and
        are intentionally ignored here.
        """
        data = request.get_json(silent=True) or {}
        model_name = data.get("model_name", data.get("model"))
        settings = get_chat_settings()
        if model_name is not None:
            settings["model_name"] = str(model_name).strip()
        if "system_prompt" in data:
            settings["system_prompt"] = data["system_prompt"] or ""
        try:
            for key, (converter, label) in CHAT_PARAMETER_CONVERTERS.items():
                if key in data:
                    settings[key] = _optional_parameter(
                        data[key], label, converter
                    )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        save_chat_settings(settings)
        return jsonify({"message": "Settings saved."})

    def clear(self):
        current_messages = list_chat_messages()
        filenames = _preview_filenames_from_messages(current_messages)
        in_use = set()
        for name in list_saved_chats():
            saved = get_saved_chat(name)
            for ref in _preview_filenames_from_messages(saved or []):
                in_use.add(Path(str(ref)).name)
        clear_chat_messages()
        _delete_preview_files(filenames, in_use=in_use)
        return jsonify({"message": "Chat cleared."})

    def abort(self):
        messages = list_chat_messages()
        filenames = []
        if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
            filenames = _preview_filenames_from_messages([messages[-1]])
        in_use = set()
        for message in messages[:-1]:
            for ref in _preview_filenames_from_messages([message]):
                in_use.add(Path(str(ref)).name)
        for name in list_saved_chats():
            saved = get_saved_chat(name)
            for ref in _preview_filenames_from_messages(saved or []):
                in_use.add(Path(str(ref)).name)
        deleted = delete_last_chat_message()
        if deleted:
            _delete_preview_files(filenames, in_use=in_use)
        return jsonify({"message": "Request aborted.", "deleted": deleted})

    def list_saved(self):
        return jsonify({"names": list_saved_chats()})

    def save_chat(self):
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Chat name is required."}), 400
        messages = list_chat_messages()
        save_saved_chat(name, messages)
        return jsonify({"message": "Chat saved.", "name": name})

    def load_chat(self):
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Chat name is required."}), 400
        if not load_saved_chat(name):
            return jsonify({"error": "Saved chat not found."}), 404
        return jsonify({"message": "Chat loaded.", "name": name, "messages": list_chat_messages()})

    def delete_chat(self):
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Chat name is required."}), 400
        saved = get_saved_chat(name)
        filenames = _preview_filenames_from_messages(saved) if saved else []
        in_use = set()
        for message in list_chat_messages():
            for ref in _preview_filenames_from_messages([message]):
                in_use.add(Path(str(ref)).name)
        for other in list_saved_chats():
            if other == name:
                continue
            other_saved = get_saved_chat(other)
            for ref in _preview_filenames_from_messages(other_saved or []):
                in_use.add(Path(str(ref)).name)
        if not delete_saved_chat(name):
            return jsonify({"error": "Saved chat not found."}), 404
        _delete_preview_files(filenames, in_use=in_use)
        return jsonify({"message": "Chat deleted.", "name": name})

    def list_saved_system_prompts(self):
        return jsonify({"names": list_saved_system_prompts()})

    def save_system_prompt(self):
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        content = data.get("content", "")
        if not name:
            return jsonify({"error": "Name is required."}), 400
        save_saved_system_prompt(name, content)
        return jsonify({"message": "System prompt saved.", "name": name})

    def load_system_prompt(self):
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name is required."}), 400
        content = get_saved_system_prompt(name)
        if content is None:
            return jsonify({"error": "Saved system prompt not found."}), 404
        return jsonify({"message": "System prompt loaded.", "name": name, "content": content})

    def delete_system_prompt(self):
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name is required."}), 400
        if not delete_saved_system_prompt(name):
            return jsonify({"error": "Saved system prompt not found."}), 404
        return jsonify({"message": "System prompt deleted.", "name": name})


chat_controller = ChatController()
