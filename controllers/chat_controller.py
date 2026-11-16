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
ATTACHMENT_DATA_LIMIT = 20 * 1024 * 1024
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
        cleaned.append(
            {
                "type": attachment_type,
                "data": data,
                "mime_type": mime_type,
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


def _resize_attachments(attachments):
    return [_resize_image_attachment(item) for item in (attachments or [])]


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


def _save_preview_image(data):
    """Create a 100px-high JPEG preview and return its randomized filename."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        decoded = base64.b64decode(data, validate=True)
        with Image.open(io.BytesIO(decoded)) as image:
            if image.height <= 0:
                return None
            scale = 100 / image.height
            width = max(1, int(image.width * scale))
            resized = image.resize((width, 100), Image.LANCZOS)
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
            _resize_attachments(_attachment_values(data.get("attachments"))),
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

        preview_images = []
        for attachment in attachments or []:
            if attachment.get("type") == "image":
                filename = _save_preview_image(attachment.get("data", ""))
                if filename:
                    preview_images.append(filename)
        add_chat_message("user", user_message, preview_images=preview_images)

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

        # Build the JSON-serializable body sent with the assistant turn.
        request_body = _build_chat_request_body(
            self.service,
            provider,
            model,
            messages,
            request_parameters,
            extra_parameters,
            attachments=attachments,
        )

        if not stream_requested:
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
                    "request_body": request_body,
                    "messages": list_chat_messages(),
                }
            )

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
                    extra_parameters=extra_parameters,
                    attachments=attachments,
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
                    "request_body": request_body,
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
        clear_chat_messages()
        return jsonify({"message": "Chat cleared."})

    def abort(self):
        deleted = delete_last_chat_message()
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
        if not delete_saved_chat(name):
            return jsonify({"error": "Saved chat not found."}), 404
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
