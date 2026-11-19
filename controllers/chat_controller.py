"""Chat interface context and message handling for the home page."""

import base64
import io
import json
import time
import urllib.request
import zipfile
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from config import PROJECT_ROOT
from flask import (
    Response,
    current_app,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)

from models.chat_settings import (
    VIDEO_FPS_VALUES,
    chat_attachment_settings,
    chat_history_settings,
    chat_seed_settings,
    get_chat_settings,
    mineru_settings,
    save_chat_settings,
)
from models.chat_storage import (
    add_chat_message,
    clear_chat_messages,
    delete_last_chat_message,
    delete_saved,
    get_saved,
    list_chat_messages,
    list_saved,
    load_saved_chat,
    save_saved,
)
from services.model_providers import (
    ModelProviderService,
    ProviderOfflineError,
    ProviderValidationError,
)

CHAT_PARAMETER_CONVERTERS = {
    "temperature": (float, "Temperature"),
    "top_p": (float, "Top P"),
    "top_k": (int, "Top K"),
    "seed": (int, "Seed"),
    "history_limit": (int, "Prev. messages"),
    "min_p": (float, "Min P"),
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
AUDIO_ANALYSIS_PROMPT = (
    "Analyze the attached audio: transcribe any spoken words, and if there "
    "is no speech, describe the audio content (music, sounds, or noise)."
)
from services.chat_previews import ChatPreviewStore
from services.chat_attachments import (
    AttachmentProcessingError,
    convert_audio_attachment as _convert_audio_attachment,
    convert_video_attachment as _convert_video_attachment,
    extract_video_audio_attachment as _extract_video_audio_attachment,
    resize_image_attachment as _resize_image_attachment,
    video_has_audio as _video_has_audio,
)


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
    video_fps: float
    attachments: list
    documents: list


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


def _video_fps_value(value):
    """Validate one of the FPS values offered by the video slider."""
    try:
        fps = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Video FPS must be a valid number.") from error
    if fps not in VIDEO_FPS_VALUES:
        supported = ", ".join(str(value) for value in VIDEO_FPS_VALUES)
        raise ValueError(f"Video FPS must be one of: {supported}.")
    return fps


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


def _document_values(value):
    """Validate and normalize chat documents submitted by the browser."""
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("Documents must be a list.")
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Documents must be objects.")
        filename = str(item.get("filename") or item.get("name") or "").strip()
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Document content is required.")
        mime_type = str(item.get("mime_type") or "").strip()
        if not mime_type:
            mime_type = _mime_for_name(filename)
        extension = str(item.get("extension") or "").strip()
        if not extension and "." in filename:
            extension = filename.rsplit(".", 1)[-1].lower()
        size = item.get("size")
        if not isinstance(size, int) or size < 0:
            size = len(content.encode("utf-8"))
        cleaned.append(
            {
                "id": str(item.get("id") or f"doc_{len(cleaned) + 1:03d}").strip(),
                "filename": filename,
                "mime_type": mime_type,
                "extension": extension,
                "size": size,
                "content": content,
            }
        )
    return cleaned


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
        attachment_type = str(item.get("type") or "").strip().lower()
        if attachment_type == "document":
            if len(data) > ATTACHMENT_DATA_LIMIT:
                raise ValueError("Attachment data is too large.")
        else:
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


def _process_attachments(attachments, fps=2):
    result = []
    for item in attachments or []:
        if isinstance(item, dict) and item.get("type") == "video":
            result.append(_convert_video_attachment(item, fps=fps))
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


def _prepare_attachment_plan(attachments, messages, fps=2):
    """Convert attachments into the model request layout they require."""
    attachments = attachments or []
    if not _requires_split_attachment_request(attachments):
        return AttachmentRequestPlan(
            primary_attachments=_process_attachments(attachments, fps=fps),
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
            primary_attachments.append(_convert_video_attachment(item, fps=fps))
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
    documents=None,
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
    if documents:
        body["documents"] = documents
    return body


def _build_plan_request_body(
    service,
    provider,
    model,
    plan,
    request_parameters,
    extra_parameters,
    documents=None,
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
        documents=documents,
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
        documents=documents,
    )
    return {"video_request": primary_body, "audio_request": audio_body}


def _complete_attachment_plan(
    service,
    provider,
    model,
    plan,
    request_parameters,
    extra_parameters,
    documents=None,
):
    """Run every request in an attachment plan and combine its result."""
    primary_text, primary_usage = service.chat_completion_with_params(
        provider,
        model,
        plan.primary_messages,
        **request_parameters,
        extra_parameters=extra_parameters,
        attachments=plan.primary_attachments,
        documents=documents,
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
            documents=documents,
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


class ChatController:
    """Provide chat context and handle chat messages."""

    def __init__(self, service=None, preview_store=None):
        self.service = service or ModelProviderService()
        self.previews = preview_store or ChatPreviewStore()

    def context(self):
        settings = get_chat_settings()
        messages = list_chat_messages()
        attachment_settings = chat_attachment_settings()
        return {
            "chat_settings": settings,
            "chat_attachment_settings": attachment_settings,
            "chat_video_fps_index": VIDEO_FPS_VALUES.index(
                attachment_settings["video_fps"]
            ),
            "chat_seed_settings": chat_seed_settings(),
            "chat_history_settings": chat_history_settings(),
            "mineru_settings": mineru_settings(),
            "chat_messages": messages,
            "active_models": self.service.active_models(),
            "saved_chats": list_saved("chat"),
            "saved_system_prompts": list_saved("system_prompt"),
        }

    def _parse_request(self):
        data = request.get_json(silent=True) or {}
        attachment_settings = chat_attachment_settings()
        model_spec = (data.get("model") or "").strip()
        user_message = (data.get("message") or "").strip()
        system_prompt = data.get("system_prompt") or ""
        saved_name_raw = (data.get("saved_system_prompt_name") or "").strip()
        saved_name = ""
        if saved_name_raw:
            stored = get_saved("system_prompt", saved_name_raw)
            if stored is None and system_prompt.strip():
                save_saved("system_prompt", saved_name_raw, system_prompt)
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
            video_fps=_video_fps_value(
                data.get("video_fps", attachment_settings["video_fps"])
            ),
            attachments=_attachment_values(data.get("attachments")),
            documents=_document_values(data.get("documents")),
        )

    def send(self):
        try:
            chat_request = self._parse_request()
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        if not chat_request.user_message:
            return jsonify({"error": "Message is required."}), 400
        attachment_settings = chat_attachment_settings()
        attachment_settings["video_fps"] = chat_request.video_fps
        chat_attachment_settings(attachment_settings)
        try:
            provider, model = self.service.resolve_online_model(chat_request.model_spec)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderOfflineError as error:
            return jsonify({"error": str(error)}), 503

        save_original_media = bool(chat_request.raw.get("save_original_media"))
        try:
            preview_data = self.previews.save_attachments(
                chat_request.attachments,
                save_original_media=save_original_media,
                video_fps=chat_request.video_fps,
            )
        except AttachmentProcessingError as error:
            return jsonify({"error": str(error)}), 422
        document_preview_media = [
            {
                "type": "document",
                "filename": "",
                "original_name": str(document.get("filename") or "Document"),
            }
            for document in (chat_request.documents or [])
        ]
        if document_preview_media:
            preview_data.setdefault("preview_media", []).extend(
                document_preview_media
            )
        add_chat_message(
            "user",
            chat_request.user_message,
            **preview_data,
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
        history_limit = chat_request.parameters.get("history_limit")
        send_all_previous = False
        raw = chat_request.raw or {}
        for key in (
            "send_all_previous",
            "send_all_previous_messages",
            "all_previous",
            "all_previous_messages",
            "history_all",
            "all_history",
        ):
            if key in raw:
                value = raw.get(key)
                if isinstance(value, bool):
                    send_all_previous = value
                elif isinstance(value, (int, float)):
                    send_all_previous = bool(value)
                elif isinstance(value, str):
                    send_all_previous = value.strip().lower() in {
                        "true",
                        "1",
                        "yes",
                        "on",
                    }
                break
        else:
            send_all_previous = bool(
                chat_history_settings().get("send_all_previous", False)
            )
        if send_all_previous:
            history_limit = None
        messages = _conversation_messages(
            chat_request.system_prompt,
            history,
            history_limit,
        )

        request_parameters = {
            key: chat_request.parameters.get(key)
            for key in (
                "temperature",
                "top_p",
                "top_k",
                "seed",
                "min_p",
            )
        }

        needs_conversion = any(
            isinstance(item, dict) and item.get("type") in ("video", "audio")
            for item in chat_request.attachments
        )

        if not stream_requested:
            started = time.monotonic()
            try:
                plan = _prepare_attachment_plan(
                    chat_request.attachments,
                    messages,
                    fps=chat_request.video_fps,
                )
                request_body = _build_plan_request_body(
                    self.service,
                    provider,
                    model,
                    plan,
                    request_parameters,
                    chat_request.extra_parameters,
                    documents=chat_request.documents,
                )
                response_text, usage = _complete_attachment_plan(
                    self.service,
                    provider,
                    model,
                    plan,
                    request_parameters,
                    chat_request.extra_parameters,
                    documents=chat_request.documents,
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
                plan = _prepare_attachment_plan(
                    chat_request.attachments,
                    messages,
                    fps=chat_request.video_fps,
                )
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
                    documents=chat_request.documents,
                )
                if plan.split:
                    response_text, usage = _complete_attachment_plan(
                        self.service,
                        provider,
                        model,
                        plan,
                        request_parameters,
                        chat_request.extra_parameters,
                        documents=chat_request.documents,
                    )
                else:
                    for event in self.service.chat_completion_with_params_stream(
                        provider,
                        model,
                        plan.primary_messages,
                        **request_parameters,
                        extra_parameters=chat_request.extra_parameters,
                        attachments=plan.primary_attachments,
                        documents=chat_request.documents,
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

    def compact(self):
        data = request.get_json(silent=True) or {}
        model_spec = (data.get("model") or "").strip()
        try:
            provider, model = self.service.resolve_online_model(model_spec)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderOfflineError as error:
            return jsonify({"error": str(error)}), 503

        settings = get_chat_settings()
        request_parameters = {
            "temperature": settings.get("temperature"),
            "top_p": settings.get("top_p"),
            "top_k": settings.get("top_k"),
            "seed": settings.get("seed"),
            "min_p": settings.get("min_p"),
        }

        # Read the compaction prompts from disk.
        try:
            prompt_directory = Path(current_app.config["SYSTEM_PROMPT_DIRECTORY"])
            system_prompt = (
                prompt_directory / "compress_system.md"
            ).read_text(encoding="utf-8")
            user_prompt = (
                prompt_directory / "compress_user.md"
            ).read_text(encoding="utf-8")
        except OSError as error:
            return jsonify({"error": f"Could not read compaction prompts: {error}"}), 500

        # Select the previous messages to compact.
        history = [
            message
            for message in list_chat_messages()
            if message["role"] in ("user", "assistant")
        ]
        history_limit = None
        raw = data or {}
        send_all_previous = False
        for key in (
            "send_all_previous",
            "send_all_previous_messages",
            "all_previous",
            "all_previous_messages",
            "history_all",
            "all_history",
        ):
            if key in raw:
                value = raw.get(key)
                if isinstance(value, bool):
                    send_all_previous = value
                elif isinstance(value, (int, float)):
                    send_all_previous = bool(value)
                elif isinstance(value, str):
                    send_all_previous = value.strip().lower() in {
                        "true",
                        "1",
                        "yes",
                        "on",
                    }
                break
        else:
            send_all_previous = bool(
                chat_history_settings().get("send_all_previous", False)
            )
        if not send_all_previous:
            try:
                history_limit = _optional_parameter(
                    data.get("history_limit"), "Prev. messages", int
                )
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
        if history_limit is None and not send_all_previous:
            # Empty input means full history.
            history_limit = None
        if send_all_previous:
            selected_previous = history
        else:
            if history_limit is None:
                selected_previous = history
            elif history_limit <= 0:
                selected_previous = []
            else:
                kept_previous = history_limit * 2
                start = max(0, len(history) - kept_previous)
                if start % 2:
                    start += 1
                selected_previous = history[start:]

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            {"role": message["role"], "content": message["content"]}
            for message in selected_previous
        )
        messages.append({"role": "user", "content": user_prompt})

        stream_requested = request.args.get("stream") == "1" or "text/event-stream" in (
            request.accept_mimetypes or ""
        )

        if not stream_requested:
            started = time.monotonic()
            try:
                response_text, usage = self.service.chat_completion_with_params(
                    provider,
                    model,
                    messages,
                    **request_parameters,
                )
            except Exception as error:  # noqa: BLE001
                current_app.logger.exception(
                    "Compact request failed for provider=%s model=%s",
                    provider,
                    model,
                )
                return jsonify({"error": str(error)}), 502
            elapsed = round(time.monotonic() - started, 2)
            request_body = json.dumps({"model": model, "messages": messages})
            add_chat_message(
                "assistant",
                response_text,
                model_name=model,
                provider=provider,
                response_time=elapsed,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                system_prompt=system_prompt,
                request_body=request_body,
                compacted=True,
            )
            payload = {
                "response": response_text,
                "time": elapsed,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "provider": provider,
                "model": model,
                "system_prompt": system_prompt,
                "request_body": request_body,
                "compacted": True,
            }
            return jsonify(payload)

        def generate():
            started = time.monotonic()
            usage = {"prompt_tokens": 0, "completion_tokens": 0}
            response_text = ""
            try:
                for event in self.service.chat_completion_with_params_stream(
                    provider,
                    model,
                    messages,
                    **request_parameters,
                ):
                    if event.get("type") == "chunk":
                        response_text += event.get("text", "")
                        yield f"data: {json.dumps(event)}\n\n"
                    elif event.get("type") == "done":
                        usage = event.get("usage", usage) or usage
                        yield f"data: {json.dumps(event)}\n\n"
                elapsed = round(time.monotonic() - started, 2)
                request_body = json.dumps({"model": model, "messages": messages})
                add_chat_message(
                    "assistant",
                    response_text,
                    model_name=model,
                    provider=provider,
                    response_time=elapsed,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    system_prompt=system_prompt,
                    request_body=request_body,
                    compacted=True,
                )
                payload = {
                    "response": response_text,
                    "time": elapsed,
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "provider": provider,
                    "model": model,
                    "system_prompt": system_prompt,
                    "request_body": request_body,
                    "compacted": True,
                    "type": "result",
                }
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as error:  # noqa: BLE001
                current_app.logger.exception(
                    "Compact stream failed for provider=%s model=%s", provider, model
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
        settings = chat_attachment_settings()
        for key in ("save_original_media", "attach_audio"):
            if key in data:
                if not isinstance(data[key], bool):
                    return jsonify({"error": f"{key} must be a boolean."}), 400
                settings[key] = data[key]
        history_value = self._history_switch_value(data)
        if history_value is not None:
            settings["send_all_previous"] = history_value
            chat_history_settings({"send_all_previous": history_value})
        if "video_fps" in data:
            try:
                settings["video_fps"] = _video_fps_value(data["video_fps"])
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
        seed_value = self._seed_switch_value(data)
        if seed_value is not None:
            settings["randomize_seed"] = seed_value
            chat_seed_settings({"randomize_seed": seed_value})
        chat_attachment_settings(settings)
        return jsonify({"message": "Attachment settings saved."})

    def _seed_switch_value(self, data):
        if not isinstance(data, dict):
            return None
        for key in ("randomize_seed", "seed_randomize", "randomize", "value", "enabled", "state", "checked"):
            if key in data:
                value = data[key]
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return bool(value)
                if isinstance(value, str):
                    return value.strip().lower() in {"true", "1", "yes", "on"}
        return None

    def _history_switch_value(self, data):
        if not isinstance(data, dict):
            return None
        for key in (
            "send_all_previous",
            "send_all_previous_messages",
            "all_previous",
            "all_previous_messages",
            "history_all",
            "all_history",
            "value",
            "enabled",
            "state",
            "checked",
        ):
            if key in data:
                value = data[key]
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return bool(value)
                if isinstance(value, str):
                    return value.strip().lower() in {"true", "1", "yes", "on"}
        return None

    def save_seed_settings(self):
        """Persist the seed randomizer switch state."""
        data = request.get_json(silent=True) or {}
        value = self._seed_switch_value(data)
        if value is None:
            return jsonify({"error": "randomize_seed must be a boolean."}), 400
        chat_seed_settings({"randomize_seed": value})
        chat_attachment_settings({"randomize_seed": value})
        return jsonify({"message": "Settings saved."})

    def save_history_settings(self):
        """Persist the history "send all previous" switch state."""
        data = request.get_json(silent=True) or {}
        value = self._history_switch_value(data)
        if value is None:
            return jsonify({"error": "send_all_previous must be a boolean."}), 400
        chat_history_settings({"send_all_previous": value})
        chat_attachment_settings({"send_all_previous": value})
        return jsonify({"message": "Settings saved."})

    def clear(self):
        current_messages = list_chat_messages()
        filenames = self.previews.filenames(current_messages)
        saved_messages = [
            get_saved("chat", name) or [] for name in list_saved("chat")
        ]
        clear_chat_messages()
        self.previews.delete_unreferenced(filenames, *saved_messages)
        return jsonify({"message": "Chat cleared."})

    def _mineru_check(self, endpoint, api_key=None):
        endpoint = str(endpoint or "").strip().rstrip("/")
        if not endpoint:
            return False
        urls = (
            f"{endpoint}/v1/health",
            f"{endpoint}/",
        )
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        for url in urls:
            try:
                request_obj = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request_obj, timeout=3) as response:
                    if getattr(response, "status", None) == 200:
                        return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def mineru_available(self):
        """Report whether the local MinerU document service is reachable."""
        settings = mineru_settings()
        endpoint = settings.get("endpoint", "http://127.0.0.1:8100")
        api_key = settings.get("api_key", "")
        return jsonify({"available": bool(self._mineru_check(endpoint, api_key))})

    def mineru_settings_get(self):
        """Return the saved MinerU endpoint settings."""
        return jsonify(mineru_settings())

    def save_mineru_settings(self):
        """Validate and persist the MinerU endpoint settings."""
        data = request.get_json(silent=True) or {}
        endpoint = str(data.get("endpoint") or "").strip()
        api_key = str(data.get("api_key") or "").strip()
        if not endpoint:
            return jsonify({"error": "MinerU endpoint is required."}), 400
        if not self._mineru_check(endpoint, api_key):
            return jsonify({"error": "MinerU endpoint is not reachable."}), 400
        saved = mineru_settings({"endpoint": endpoint, "api_key": api_key})
        return jsonify({"message": "MinerU settings saved.", **saved})

    def process_document(self):
        """Process a binary document through the configured MinerU service."""
        data = request.get_json(silent=True) or {}
        filename = str(data.get("filename") or data.get("name") or "document").strip()
        raw_data = data.get("data")
        if not isinstance(raw_data, str) or not raw_data.strip():
            return jsonify({"error": "Document data is required."}), 400
        try:
            file_bytes = base64.b64decode(raw_data.strip(), validate=True)
        except Exception as error:  # noqa: BLE001
            return jsonify({"error": "Document data must be valid base64."}), 400
        if not file_bytes:
            return jsonify({"error": "Document data is empty."}), 400

        settings = mineru_settings()
        endpoint = str(settings.get("endpoint") or "").strip().rstrip("/")
        api_key = str(settings.get("api_key") or "").strip()
        if not endpoint:
            return jsonify({"error": "MinerU endpoint is not configured."}), 400

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Create task.
        try:
            create_payload = {"files": [{"file_name": filename, "bytes": len(file_bytes)}]}
            create_request = urllib.request.Request(
                f"{endpoint}/v1/tasks",
                data=json.dumps(create_payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(create_request, timeout=30) as response:
                created = json.loads(response.read().decode("utf-8"))
        except Exception as error:  # noqa: BLE001
            return jsonify({"error": f"MinerU task creation failed: {error}"}), 502

        task_id = created.get("task_id")
        files = created.get("files") or []
        if not task_id or not files:
            return jsonify({"error": "MinerU did not return a task."}), 502
        file_info = files[0]
        file_id = file_info.get("file_id")
        upload = file_info.get("upload") or {}
        upload_url = upload.get("url")
        upload_headers = dict(upload.get("headers") or {})
        if api_key:
            upload_headers.setdefault("Authorization", f"Bearer {api_key}")

        # Upload file.
        try:
            upload_request = urllib.request.Request(
                upload_url,
                data=file_bytes,
                headers=upload_headers,
                method="PUT",
            )
            with urllib.request.urlopen(upload_request, timeout=60):
                pass
        except Exception as error:  # noqa: BLE001
            return jsonify({"error": f"MinerU upload failed: {error}"}), 502

        # Poll task status.
        deadline = time.monotonic() + 120
        status = created.get("status")
        detail = None
        while time.monotonic() < deadline:
            try:
                status_request = urllib.request.Request(
                    f"{endpoint}/v1/tasks/{task_id}",
                    headers=headers,
                    method="GET",
                )
                with urllib.request.urlopen(status_request, timeout=30) as response:
                    detail = json.loads(response.read().decode("utf-8"))
                status = detail.get("status")
                if status in {"completed", "partial", "failed", "canceled"}:
                    break
            except Exception as error:  # noqa: BLE001
                return jsonify({"error": f"MinerU status check failed: {error}"}), 502
            time.sleep(1)

        if not detail or status not in {"completed", "partial"}:
            file_error = None
            if detail and detail.get("files"):
                file_error = detail["files"][0].get("error")
            message = "MinerU processing failed."
            if file_error:
                message = f"{message} {file_error.get('message', '')}".strip()
            return jsonify({"error": message}), 502

        file_detail = (detail.get("files") or [{}])[0]
        result_url = file_detail.get("result_url")
        if not result_url:
            return jsonify({"error": "MinerU did not return a result."}), 502

        # Download result ZIP and extract text.
        try:
            result_request = urllib.request.Request(result_url, headers=headers, method="GET")
            with urllib.request.urlopen(result_request, timeout=60) as response:
                result_bytes = response.read()
        except Exception as error:  # noqa: BLE001
            return jsonify({"error": f"MinerU result download failed: {error}"}), 502

        extracted = ""
        try:
            archive = zipfile.ZipFile(io.BytesIO(result_bytes))
            if "markdown.md" in archive.namelist():
                extracted = archive.read("markdown.md").decode("utf-8", errors="replace").strip()
            if not extracted and "middle_json.json" in archive.namelist():
                middle = json.loads(archive.read("middle_json.json").decode("utf-8"))
                texts = []
                for page in middle.get("pages", []) or []:
                    for block in page.get("blocks", []) or []:
                        if block.get("type") != "text":
                            continue
                        for content_item in block.get("content", []) or []:
                            if isinstance(content_item, dict) and content_item.get("type") == "text":
                                value = content_item.get("content")
                                if isinstance(value, str) and value.strip():
                                    texts.append(value.strip())
                extracted = "\n\n".join(texts).strip()
        except Exception as error:  # noqa: BLE001
            return jsonify({"error": f"MinerU result parsing failed: {error}"}), 502

        if not extracted:
            return jsonify({"error": "MinerU did not return text content."}), 502
        return jsonify({"content": extracted})

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
            get_saved("chat", name) or [] for name in list_saved("chat")
        ]
        deleted = delete_last_chat_message()
        if deleted:
            self.previews.delete_unreferenced(filenames, *referenced)
        return jsonify({"message": "Request aborted.", "deleted": deleted})

    def saved_chat(self, action):
        """List, save, load, replace, or delete a named chat."""
        if action == "list":
            return jsonify({"names": list_saved("chat")})
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Chat name is required."}), 400
        if action == "save":
            save_saved("chat", name, list_chat_messages())
            return jsonify({"message": "Chat saved.", "name": name})
        if action == "load":
            if not load_saved_chat(name):
                return jsonify({"error": "Saved chat not found."}), 404
            return jsonify(
                {
                    "message": "Chat loaded.",
                    "name": name,
                    "messages": list_chat_messages(),
                }
            )
        if action == "replace":
            saved = get_saved("chat", name)
            if saved is None:
                return jsonify({"error": "Saved chat not found."}), 404
            current_messages = list_chat_messages()
            replaced_filenames = self.previews.filenames(saved)
            save_saved("chat", name, current_messages)
            referenced = [current_messages] + [
                get_saved("chat", other) or []
                for other in list_saved("chat")
                if other != name
            ]
            self.previews.delete_unreferenced(replaced_filenames, *referenced)
            return jsonify({"message": "Chat replaced.", "name": name})

        saved = get_saved("chat", name)
        if saved is None:
            return jsonify({"error": "Saved chat not found."}), 404
        current_messages = list_chat_messages()
        filenames = self.previews.filenames(saved) + self.previews.filenames(
            current_messages
        )
        referenced = [
            get_saved("chat", other) or []
            for other in list_saved("chat")
            if other != name
        ]
        if not delete_saved("chat", name):
            return jsonify({"error": "Saved chat not found."}), 404
        clear_chat_messages()
        self.previews.delete_unreferenced(filenames, *referenced)
        return jsonify({"message": "Chat deleted.", "name": name})

    def saved_system_prompt(self, action):
        """List, save, load, or delete a named system prompt."""
        if action == "list":
            return jsonify({"names": list_saved("system_prompt")})
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name is required."}), 400
        if action == "save":
            save_saved("system_prompt", name, data.get("content", ""))
            return jsonify({"message": "System prompt saved.", "name": name})
        if action == "load":
            content = get_saved("system_prompt", name)
            if content is None:
                return jsonify({"error": "Saved system prompt not found."}), 404
            return jsonify(
                {
                    "message": "System prompt loaded.",
                    "name": name,
                    "content": content,
                }
            )
        if not delete_saved("system_prompt", name):
            return jsonify({"error": "Saved system prompt not found."}), 404
        return jsonify({"message": "System prompt deleted.", "name": name})


chat_controller = ChatController()
