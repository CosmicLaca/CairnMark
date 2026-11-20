"""Chat interface context and message handling for the home page."""

import base64
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

from flask import (
    Response,
    current_app,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)

from models.chat_settings import (
    CHAT_SETTINGS,
    VIDEO_FPS_VALUES,
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
from services.chat_attachments import AttachmentProcessingError
from services.chat_exports import ChatExportRepository
from services.chat_previews import ChatPreviewStore
from services.chat_requests import CHAT_PARAMETER_FIELDS, ChatRequestWorkflow
from services.model_providers import (
    ModelProviderService,
    ProviderOfflineError,
    ProviderValidationError,
)



class ChatController:
    """Provide chat context and handle chat messages."""

    def __init__(
        self,
        service=None,
        preview_store=None,
        request_workflow=None,
        export_repository=None,
    ):
        self.service = service or ModelProviderService()
        self.previews = preview_store or ChatPreviewStore()
        self.requests = request_workflow or ChatRequestWorkflow(self.service)
        self.exports = export_repository or ChatExportRepository()

    def context(self):
        settings = CHAT_SETTINGS.form()
        messages = list_chat_messages()
        attachment_settings = CHAT_SETTINGS.attachments()
        return {
            "chat_settings": settings,
            "chat_attachment_settings": attachment_settings,
            "chat_video_fps_index": VIDEO_FPS_VALUES.index(
                attachment_settings["video_fps"]
            ),
            "chat_seed_settings": {
                "randomize_seed": CHAT_SETTINGS.switch("randomize_seed")
            },
            "chat_history_settings": {
                "send_all_previous": CHAT_SETTINGS.switch("send_all_previous")
            },
            "chat_compact_settings": {
                "auto_compact": CHAT_SETTINGS.switch("auto_compact")
            },
            "mineru_settings": CHAT_SETTINGS.mineru(),
            "chat_messages": messages,
            "active_models": self.service.active_models(),
            "saved_chats": list_saved("chat"),
            "saved_system_prompts": list_saved("system_prompt"),
        }

    def _parse_request(self):
        return self.requests.parse(request.get_json(silent=True) or {})

    def send(self):
        try:
            chat_request = self._parse_request()
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        if not chat_request.user_message:
            return jsonify({"error": "Message is required."}), 400
        if "auto_compact" in chat_request.raw:
            auto_compact = chat_request.raw["auto_compact"]
            if not isinstance(auto_compact, bool):
                return jsonify({"error": "auto_compact must be a boolean."}), 400
            CHAT_SETTINGS.switch("auto_compact", auto_compact)
        attachment_settings = CHAT_SETTINGS.attachments()
        if "stream_responses" in chat_request.raw:
            stream_responses = chat_request.raw["stream_responses"]
            if not isinstance(stream_responses, bool):
                return jsonify(
                    {"error": "stream_responses must be a boolean."}
                ), 400
            attachment_settings["stream_responses"] = stream_responses
        attachment_settings["video_fps"] = chat_request.video_fps
        CHAT_SETTINGS.attachments(attachment_settings)
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
        history = self.requests.active_history(
            [
                message
                for message in list_chat_messages()
                if message["role"] in ("user", "assistant")
            ]
        )
        history_limit = chat_request.parameters.get("history_limit")
        send_all_previous = self.requests.history_switch(chat_request.raw)
        if send_all_previous:
            history_limit = None
        messages = self.requests.messages(
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
                plan = self.requests.attachment_plan(
                    chat_request.attachments,
                    messages,
                    fps=chat_request.video_fps,
                )
                request_body = self.requests.request_body(
                    provider,
                    model,
                    plan,
                    request_parameters,
                    chat_request.extra_parameters,
                    documents=chat_request.documents,
                )
                response_text, usage = self.requests.complete(
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
            payload = self.requests.result_payload(
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
                plan = self.requests.attachment_plan(
                    chat_request.attachments,
                    messages,
                    fps=chat_request.video_fps,
                )
                if needs_conversion:
                    status = {"type": "status", "text": "thinking…"}
                    yield f"data: {json.dumps(status)}\n\n"
                request_body = self.requests.request_body(
                    provider,
                    model,
                    plan,
                    request_parameters,
                    chat_request.extra_parameters,
                    documents=chat_request.documents,
                )
                if plan.split:
                    response_text, usage = self.requests.complete(
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
                payload = self.requests.result_payload(
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

        settings = CHAT_SETTINGS.form()
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
            return (
                jsonify({"error": f"Could not read compaction prompts: {error}"}),
                500,
            )

        # Select the previous messages to compact.
        history = self.requests.active_history(
            [
                message
                for message in list_chat_messages()
                if message["role"] in ("user", "assistant")
            ]
        )
        history_limit = None
        send_all_previous = self.requests.history_switch(data)
        if not send_all_previous:
            try:
                history_limit = self.requests.number(
                    data.get("history_limit"), "Prev. messages", int
                )
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
        selected_previous = self.requests.selected_history(
            history,
            None if send_all_previous else history_limit,
        )

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
        settings = CHAT_SETTINGS.form()
        if model_name is not None:
            settings["model_name"] = str(model_name).strip()
        if "system_prompt" in data:
            settings["system_prompt"] = data["system_prompt"] or ""
        try:
            for key, (converter, label) in CHAT_PARAMETER_FIELDS.items():
                if key in data:
                    settings[key] = self.requests.number(data[key], label, converter)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        CHAT_SETTINGS.save_form(settings)
        return jsonify({"message": "Settings saved."})

    def save_attachment_settings(self):
        """Persist last-used media attachment switch values."""
        data = request.get_json(silent=True) or {}
        settings = CHAT_SETTINGS.attachments()
        for key in ("save_original_media", "attach_audio", "stream_responses"):
            if key in data:
                if not isinstance(data[key], bool):
                    return jsonify({"error": f"{key} must be a boolean."}), 400
                settings[key] = data[key]
        history_value = self._switch_value(
            data,
            "send_all_previous",
            "send_all_previous_messages",
            "all_previous",
            "all_previous_messages",
            "history_all",
            "all_history",
        )
        if history_value is not None:
            settings["send_all_previous"] = history_value
        if "video_fps" in data:
            try:
                settings["video_fps"] = self.requests.video_fps(data["video_fps"])
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
        seed_value = self._switch_value(
            data,
            "randomize_seed",
            "seed_randomize",
            "randomize",
        )
        if seed_value is not None:
            settings["randomize_seed"] = seed_value
        CHAT_SETTINGS.attachments(settings)
        return jsonify({"message": "Attachment settings saved."})

    @staticmethod
    def _switch_value(data, *names):
        """Read a boolean from compatible switch payload names."""
        if not isinstance(data, dict):
            return None
        for key in (*names, "value", "enabled", "state", "checked"):
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
        value = self._switch_value(
            data,
            "randomize_seed",
            "seed_randomize",
            "randomize",
        )
        if value is None:
            return jsonify({"error": "randomize_seed must be a boolean."}), 400
        CHAT_SETTINGS.attachments({"randomize_seed": value})
        return jsonify({"message": "Settings saved."})

    def save_history_settings(self):
        """Persist the history "send all previous" switch state."""
        data = request.get_json(silent=True) or {}
        value = self._switch_value(
            data,
            "send_all_previous",
            "send_all_previous_messages",
            "all_previous",
            "all_previous_messages",
            "history_all",
            "all_history",
        )
        if value is None:
            return jsonify({"error": "send_all_previous must be a boolean."}), 400
        CHAT_SETTINGS.attachments({"send_all_previous": value})
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

    def export_chat(self):
        """Export the complete active chat or one selected saved chat."""
        data = request.get_json(silent=True) or {}
        name = str(data.get("name") or "").strip()
        messages = get_saved("chat", name) if name else list_chat_messages()
        if name and messages is None:
            return jsonify({"error": "Saved chat not found."}), 404
        if not messages:
            return jsonify({"error": "No chat to export."}), 400
        try:
            filename = self.exports.export(
                messages,
                saved_chat_name=name or None,
            )
        except OSError:
            current_app.logger.exception("Could not export chat")
            return jsonify({"error": "Chat export failed."}), 500
        return jsonify({"message": "Chat exported.", "filename": filename})

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
        settings = CHAT_SETTINGS.mineru()
        endpoint = settings.get("endpoint", "http://127.0.0.1:8100")
        api_key = settings.get("api_key", "")
        return jsonify({"available": bool(self._mineru_check(endpoint, api_key))})

    def mineru_settings_get(self):
        """Return the saved MinerU endpoint settings."""
        return jsonify(CHAT_SETTINGS.mineru())

    def save_mineru_settings(self):
        """Validate and persist the MinerU endpoint settings."""
        data = request.get_json(silent=True) or {}
        endpoint = str(data.get("endpoint") or "").strip()
        api_key = str(data.get("api_key") or "").strip()
        if not endpoint:
            return jsonify({"error": "MinerU endpoint is required."}), 400
        if not self._mineru_check(endpoint, api_key):
            return jsonify({"error": "MinerU endpoint is not reachable."}), 400
        saved = CHAT_SETTINGS.mineru({"endpoint": endpoint, "api_key": api_key})
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

        settings = CHAT_SETTINGS.mineru()
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
