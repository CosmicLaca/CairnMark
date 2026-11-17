"""Chat interface context and message handling for the home page."""

import base64
import io
import json
import re
import time
from dataclasses import dataclass
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
    get_chat_attachment_settings,
    get_chat_settings,
    get_saved_chat,
    get_saved_system_prompt,
    list_chat_messages,
    list_saved_chats,
    list_saved_system_prompts,
    load_saved_chat,
    save_chat_attachment_settings,
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
AUDIO_ANALYSIS_PROMPT = (
    "Analyze the attached audio: transcribe any spoken words, and if there "
    "is no speech, describe the audio content (music, sounds, or noise)."
)
from services.chat_previews import ChatPreviewStore


class AttachmentProcessingError(RuntimeError):
    """Raised when media cannot be converted into a safe model attachment."""


@dataclass(frozen=True)
class ChatRequestData:
    """Validated values submitted for one chat turn."""

    raw: dict
    model_spec: str
    user_message: str
    system_prompt: str
    saved_prompt_name: str
    parameters: dict
    extra_parameters: dict
    attachments: list


@dataclass(frozen=True)
class AttachmentRequestPlan:
    """Converted attachments and messages for one or two model requests."""

    primary_attachments: list
    primary_messages: list
    audio_attachments: list
    audio_messages: list
    split: bool = False


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
            raise ValueError(
                "Attachment type must be image, document, video, or audio."
            )
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
                "original_name": str(
                    item.get("original_name") or item.get("name") or ""
                ).strip(),
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
    """Re-encode video to MP4 with a 480px maximum side and 2 fps.

    Audio is always removed. Conversion fails closed because returning the
    original file could silently send an audio track when Attach audio is off.
    """
    if not isinstance(attachment, dict) or attachment.get("type") != "video":
        return attachment
    try:
        import ffmpeg
    except ImportError as error:
        raise AttachmentProcessingError(
            "Video attachments require FFmpeg to remove the audio track."
        ) from error
    try:
        decoded = base64.b64decode(attachment["data"], validate=True)
    except Exception as error:  # noqa: BLE001
        raise AttachmentProcessingError("Video attachment data is invalid.") from error
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
                raise AttachmentProcessingError(
                    "The attachment does not contain a video track."
                )
            width = int(video_stream.get("width") or 0)
            height = int(video_stream.get("height") or 0)
            if width <= 0 or height <= 0:
                raise AttachmentProcessingError(
                    "The video dimensions could not be determined."
                )
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
                video,
                output_path,
                an=None,
                **output_args,
            ).overwrite_output().run(quiet=True)
            with open(output_path, "rb") as handle:
                converted = handle.read()
            if not converted:
                raise AttachmentProcessingError("The converted video is empty.")
            return {
                "type": "video",
                "data": base64.b64encode(converted).decode("ascii"),
                "mime_type": "video/mp4",
                "preview_data": attachment.get("preview_data"),
            }
    except AttachmentProcessingError:
        raise
    except Exception as error:  # noqa: BLE001
        current_app.logger.exception("Video attachment could not be converted")
        raise AttachmentProcessingError(
            "Video attachment could not be converted without audio."
        ) from error


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
                audio,
                output_path,
                acodec="libmp3lame",
                audio_bitrate="64k",
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
                audio,
                output_path,
                acodec="libmp3lame",
                audio_bitrate="64k",
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
                video_stream,
                audio_stream,
                output_path,
                vcodec="copy",
                acodec="aac",
                audio_bitrate="64k",
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
    for item in attachments or []:
        if isinstance(item, dict) and item.get("type") == "video":
            result.append(_convert_video_attachment(item))
        elif isinstance(item, dict) and item.get("type") == "image":
            result.append(_resize_image_attachment(item))
        elif isinstance(item, dict) and item.get("type") == "audio":
            result.append(_convert_audio_attachment(item))
        else:
            result.append(item)
    return result


def _requires_split_attachment_request(attachments):
    """Return whether video and extracted audio need separate requests."""
    return any(
        isinstance(item, dict)
        and item.get("type") == "video"
        and bool(item.get("attach_audio"))
        for item in (attachments or [])
    )


def _audio_analysis_messages(messages):
    """Copy a conversation and replace its final user prompt for audio."""
    audio_messages = [dict(message) for message in messages]
    for message in reversed(audio_messages):
        if message.get("role") == "user":
            message["content"] = AUDIO_ANALYSIS_PROMPT
            break
    return audio_messages


def _prepare_attachment_plan(attachments, messages):
    """Convert attachments into the model request layout they require."""
    attachments = attachments or []
    if not _requires_split_attachment_request(attachments):
        return AttachmentRequestPlan(
            primary_attachments=_process_attachments(attachments),
            primary_messages=messages,
            audio_attachments=[],
            audio_messages=[],
        )

    primary_attachments = []
    audio_attachments = []
    for item in attachments:
        if not isinstance(item, dict):
            primary_attachments.append(item)
        elif item.get("type") == "video":
            primary_attachments.append(_convert_video_attachment(item))
            if item.get("attach_audio") and _video_has_audio(item.get("data", "")):
                audio_attachment = _extract_video_audio_attachment(item)
                if audio_attachment is not None:
                    audio_attachments.append(audio_attachment)
        elif item.get("type") == "audio":
            audio_attachments.append(_convert_audio_attachment(item))
        else:
            primary_attachments.append(item)

    return AttachmentRequestPlan(
        primary_attachments=primary_attachments,
        primary_messages=messages,
        audio_attachments=audio_attachments,
        audio_messages=_audio_analysis_messages(messages),
        split=True,
    )


def _build_chat_request_body(
    service,
    provider,
    model,
    messages,
    request_parameters,
    extra_parameters,
    attachments=None,
):
    """Return the JSON-serializable body sent for an assistant chat turn."""
    body = {"model": model, "messages": messages}
    body.update(
        {
            key: value
            for key, value in (request_parameters or {}).items()
            if value is not None
        }
    )
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


def _build_plan_request_body(
    service,
    provider,
    model,
    plan,
    request_parameters,
    extra_parameters,
):
    """Build the persisted request body for an attachment plan."""
    primary_body = _build_chat_request_body(
        service,
        provider,
        model,
        plan.primary_messages,
        request_parameters,
        extra_parameters,
        attachments=plan.primary_attachments,
    )
    if not plan.audio_attachments:
        return primary_body
    audio_body = _build_chat_request_body(
        service,
        provider,
        model,
        plan.audio_messages,
        request_parameters,
        extra_parameters,
        attachments=plan.audio_attachments,
    )
    return {"video_request": primary_body, "audio_request": audio_body}


def _complete_attachment_plan(
    service,
    provider,
    model,
    plan,
    request_parameters,
    extra_parameters,
):
    """Run every request in an attachment plan and combine its result."""
    primary_text, primary_usage = service.chat_completion_with_params(
        provider,
        model,
        plan.primary_messages,
        **request_parameters,
        extra_parameters=extra_parameters,
        attachments=plan.primary_attachments,
    )
    audio_text = ""
    audio_usage = {}
    if plan.audio_attachments:
        audio_text, audio_usage = service.chat_completion_with_params(
            provider,
            model,
            plan.audio_messages,
            **request_parameters,
            extra_parameters=extra_parameters,
            attachments=plan.audio_attachments,
        )
    response_text = primary_text
    if audio_text:
        response_text = f"{primary_text}\n\nAudio transcription:\n{audio_text}"
    usage = {
        key: primary_usage.get(key, 0) + audio_usage.get(key, 0)
        for key in ("prompt_tokens", "completion_tokens")
    }
    return response_text, usage


def _conversation_messages(system_prompt, history, history_limit):
    """Build model messages while retaining complete recent chat turns."""
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    if history_limit is not None:
        current_turn = history[-1:]
        previous = history[:-1]
        if history_limit <= 0:
            history = current_turn
        else:
            kept_previous = history_limit * 2
            start = max(0, len(previous) - kept_previous)
            if start % 2:
                start += 1
            history = previous[start:] + current_turn
    messages.extend(
        {"role": message["role"], "content": message["content"]} for message in history
    )
    return messages


def _chat_result_payload(
    response_text,
    elapsed,
    usage,
    provider,
    model,
    chat_request,
    request_body,
    event_type=None,
):
    """Return the shared JSON result for regular and streaming chat."""
    payload = {
        "response": response_text,
        "response_html": render_markdown_html(response_text),
        "time": elapsed,
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "provider": provider,
        "model": model,
        "saved_system_prompt_name": chat_request.saved_prompt_name,
        "system_prompt": chat_request.system_prompt,
        "request_body": json.dumps(request_body),
    }
    if event_type:
        payload["type"] = event_type
    return payload


def render_markdown_html(text):
    """Render Markdown text to HTML using the same extensions as About."""
    return markdown.markdown(str(text or ""), extensions=MARKDOWN_EXTENSIONS)


class ChatController:
    """Provide chat context and handle chat messages."""

    def __init__(self, service=None, preview_store=None):
        self.service = service or ModelProviderService()
        self.previews = preview_store or ChatPreviewStore()

    def context(self):
        settings = get_chat_settings()
        messages = list_chat_messages()
        return {
            "chat_settings": settings,
            "chat_attachment_settings": get_chat_attachment_settings(),
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
        return ChatRequestData(
            raw=data,
            model_spec=model_spec,
            user_message=user_message,
            system_prompt=system_prompt,
            saved_prompt_name=saved_name,
            parameters=_parameter_values(data),
            extra_parameters=_model_parameter_values(data.get("model_params")),
            attachments=_attachment_values(data.get("attachments")),
        )

    def send(self):
        try:
            chat_request = self._parse_request()
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        if not chat_request.user_message:
            return jsonify({"error": "Message is required."}), 400
        try:
            provider, model = self.service.resolve_online_model(chat_request.model_spec)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderOfflineError as error:
            return jsonify({"error": str(error)}), 503

        save_original_media = bool(chat_request.raw.get("save_original_media"))
        preview_images = []
        preview_media = []
        has_audio_attachment = False
        try:
            for attachment in chat_request.attachments:
                attachment_type = attachment.get("type")
                if attachment_type == "image":
                    filename = self.previews.save(attachment.get("data", ""), "jpg")
                    if filename:
                        preview_images.append(filename)
                elif attachment_type == "audio":
                    has_audio_attachment = True
                    if save_original_media:
                        converted = _convert_audio_attachment(attachment)
                        data = converted.get("data", attachment.get("data", ""))
                        filename = self.previews.save(data, "mp3")
                        if filename:
                            preview_media.append(
                                {
                                    "type": "audio",
                                    "filename": filename,
                                    "original_name": attachment.get(
                                        "original_name", ""
                                    ),
                                }
                            )
                elif attachment_type == "video":
                    if save_original_media:
                        converted = _convert_video_attachment(attachment)
                        data = converted["data"]
                        if attachment.get("attach_audio") and _video_has_audio(
                            attachment.get("data", "")
                        ):
                            audio_att = _extract_video_audio_attachment(attachment)
                            if audio_att is not None:
                                merged = _merge_video_audio(
                                    converted["data"], audio_att.get("data", "")
                                )
                                if merged:
                                    data = merged
                        filename = self.previews.save(data, "mp4")
                        if filename:
                            preview_media.append(
                                {
                                    "type": "video",
                                    "filename": filename,
                                    "original_name": attachment.get(
                                        "original_name", ""
                                    ),
                                }
                            )
                    elif attachment.get("preview_data"):
                        filename = self.previews.save(
                            attachment.get("preview_data", ""), "jpg"
                        )
                        if filename:
                            preview_images.append(filename)
        except AttachmentProcessingError as error:
            return jsonify({"error": str(error)}), 422
        add_chat_message(
            "user",
            chat_request.user_message,
            preview_images=preview_images,
            has_audio=has_audio_attachment and not save_original_media,
            preview_media=preview_media,
        )

        stream_requested = request.args.get("stream") == "1" or "text/event-stream" in (
            request.accept_mimetypes or ""
        )

        # Build messages list from the most recent turns kept by the user.
        history = [
            message
            for message in list_chat_messages()
            if message["role"] in ("user", "assistant")
        ]
        messages = _conversation_messages(
            chat_request.system_prompt,
            history,
            chat_request.parameters.get("history_limit"),
        )

        request_parameters = {
            key: chat_request.parameters.get(key)
            for key in (
                "temperature",
                "top_p",
                "top_k",
                "seed",
            )
        }

        needs_conversion = any(
            isinstance(item, dict) and item.get("type") in ("video", "audio")
            for item in chat_request.attachments
        )

        if not stream_requested:
            started = time.monotonic()
            try:
                plan = _prepare_attachment_plan(chat_request.attachments, messages)
                request_body = _build_plan_request_body(
                    self.service,
                    provider,
                    model,
                    plan,
                    request_parameters,
                    chat_request.extra_parameters,
                )
                response_text, usage = _complete_attachment_plan(
                    self.service,
                    provider,
                    model,
                    plan,
                    request_parameters,
                    chat_request.extra_parameters,
                )
            except AttachmentProcessingError as error:
                return jsonify({"error": str(error)}), 422
            except Exception as error:  # noqa: BLE001
                current_app.logger.exception(
                    "Chat request failed for provider=%s model=%s",
                    provider,
                    model,
                )
                return jsonify({"error": str(error)}), 502
            elapsed = round(time.monotonic() - started, 2)
            add_chat_message(
                "assistant",
                response_text,
                model_name=model,
                provider=provider,
                response_time=elapsed,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                system_prompt=chat_request.system_prompt,
                saved_system_prompt_name=chat_request.saved_prompt_name,
                request_body=json.dumps(request_body),
            )
            payload = _chat_result_payload(
                response_text,
                elapsed,
                usage,
                provider,
                model,
                chat_request,
                request_body,
            )
            payload["messages"] = list_chat_messages()
            return jsonify(payload)

        def generate():
            started = time.monotonic()
            usage = {"prompt_tokens": 0, "completion_tokens": 0}
            response_text = ""
            try:
                if needs_conversion:
                    status = {
                        "type": "status",
                        "text": "Converting attachment…",
                    }
                    yield f"data: {json.dumps(status)}\n\n"
                plan = _prepare_attachment_plan(chat_request.attachments, messages)
                if needs_conversion:
                    status = {"type": "status", "text": "thinking…"}
                    yield f"data: {json.dumps(status)}\n\n"
                request_body = _build_plan_request_body(
                    self.service,
                    provider,
                    model,
                    plan,
                    request_parameters,
                    chat_request.extra_parameters,
                )
                if plan.split:
                    response_text, usage = _complete_attachment_plan(
                        self.service,
                        provider,
                        model,
                        plan,
                        request_parameters,
                        chat_request.extra_parameters,
                    )
                else:
                    for event in self.service.chat_completion_with_params_stream(
                        provider,
                        model,
                        plan.primary_messages,
                        **request_parameters,
                        extra_parameters=chat_request.extra_parameters,
                        attachments=plan.primary_attachments,
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
                    system_prompt=chat_request.system_prompt,
                    saved_system_prompt_name=chat_request.saved_prompt_name,
                    request_body=json.dumps(request_body),
                )
                payload = _chat_result_payload(
                    response_text,
                    elapsed,
                    usage,
                    provider,
                    model,
                    chat_request,
                    request_body,
                    event_type="result",
                )
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
        directory = self.previews.directory()
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
                    settings[key] = _optional_parameter(data[key], label, converter)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        save_chat_settings(settings)
        return jsonify({"message": "Settings saved."})

    def save_attachment_settings(self):
        """Persist last-used media attachment switch values."""
        data = request.get_json(silent=True) or {}
        settings = get_chat_attachment_settings()
        for key in ("save_original_media", "attach_audio"):
            if key in data:
                if not isinstance(data[key], bool):
                    return jsonify({"error": f"{key} must be a boolean."}), 400
                settings[key] = data[key]
        save_chat_attachment_settings(settings)
        return jsonify({"message": "Attachment settings saved."})

    def clear(self):
        current_messages = list_chat_messages()
        filenames = self.previews.filenames(current_messages)
        saved_messages = [get_saved_chat(name) or [] for name in list_saved_chats()]
        clear_chat_messages()
        self.previews.delete_unreferenced(filenames, *saved_messages)
        return jsonify({"message": "Chat cleared."})

    def abort(self):
        messages = list_chat_messages()
        filenames = []
        if (
            messages
            and isinstance(messages[-1], dict)
            and messages[-1].get("role") == "user"
        ):
            filenames = self.previews.filenames([messages[-1]])
        referenced = [messages[:-1]] + [
            get_saved_chat(name) or [] for name in list_saved_chats()
        ]
        deleted = delete_last_chat_message()
        if deleted:
            self.previews.delete_unreferenced(filenames, *referenced)
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
        return jsonify(
            {"message": "Chat loaded.", "name": name, "messages": list_chat_messages()}
        )

    def delete_chat(self):
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Chat name is required."}), 400
        saved = get_saved_chat(name)
        if saved is None:
            return jsonify({"error": "Saved chat not found."}), 404

        current_messages = list_chat_messages()
        filenames = self.previews.filenames(saved) + self.previews.filenames(
            current_messages
        )
        referenced = [
            get_saved_chat(other) or [] for other in list_saved_chats() if other != name
        ]
        if not delete_saved_chat(name):
            return jsonify({"error": "Saved chat not found."}), 404
        clear_chat_messages()
        self.previews.delete_unreferenced(filenames, *referenced)
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
        return jsonify(
            {"message": "System prompt loaded.", "name": name, "content": content}
        )

    def delete_system_prompt(self):
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name is required."}), 400
        if not delete_saved_system_prompt(name):
            return jsonify({"error": "Saved system prompt not found."}), 404
        return jsonify({"message": "System prompt deleted.", "name": name})


chat_controller = ChatController()
