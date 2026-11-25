"""Chat interface context and message handling for the home page."""

import base64
import io
import json
import re
import time
import urllib.request
import zipfile
from dataclasses import replace
from functools import partialmethod
from pathlib import Path

from flask import (
    Response,
    current_app,
    jsonify,
    request,
    send_file,
    send_from_directory,
    stream_with_context,
)

from models.chat_settings import (
    AUTO_COMPACT_THRESHOLD_MAX,
    AUTO_COMPACT_THRESHOLD_MIN,
    CHAT_SETTINGS,
    DEFAULT_AUTO_COMPACT_THRESHOLD,
    DEFAULT_MINERU_TIMEOUT,
    MINERU_TIMEOUT_MAX,
    MINERU_TIMEOUT_MIN,
    VIDEO_FPS_VALUES,
)
from models.chat_storage import CHAT_HISTORY
from models.mcp_settings import MCP_SETTINGS
from services.chat_attachments import AttachmentProcessingError
from services.chat_exports import ChatExportRepository
from services.chat_media import CHAT_MEDIA
from services.chat_previews import ChatPreviewStore
from services.chat_requests import CHAT_PARAMETER_FIELDS, ChatRequestWorkflow
from services.chat_tools import ChatToolService
from services.document_previews import DOCUMENT_PREVIEWS, DocumentPreviewError
from services.external_images import ExternalImageError, ExternalImageService
from services.mcp_services import MCP_NAME_PATTERN, McpServiceRegistry
from services.model_providers import (
    ModelProviderService,
    ProviderOfflineError,
    ProviderValidationError,
)
from services.webpage_previews import WebpagePreviewService


class ChatController:
    """Provide chat context and handle chat messages."""

    def __init__(
        self,
        service=None,
        preview_store=None,
        request_workflow=None,
        export_repository=None,
        tool_service=None,
        external_image_service=None,
        webpage_preview_service=None,
        history_repository=None,
        media_service=None,
        document_preview_service=None,
    ):
        self.service = service or ModelProviderService()
        self.history = history_repository or CHAT_HISTORY
        self.previews = preview_store or ChatPreviewStore()
        self.requests = request_workflow or ChatRequestWorkflow(
            self.service,
            history=self.history,
        )
        self.exports = export_repository or ChatExportRepository()
        self.mcp_settings = MCP_SETTINGS
        self.tools = tool_service
        self.external_images = external_image_service or ExternalImageService()
        self.webpages = webpage_preview_service or WebpagePreviewService(self.previews)
        self.media = media_service or CHAT_MEDIA
        self.document_previews = document_preview_service or DOCUMENT_PREVIEWS

    @staticmethod
    def _add_tools_to_request_body(request_body, bindings, transcript):
        """Record the model-visible tools and actual tool-loop messages."""
        target = request_body.get("video_request", request_body)
        target["tools"] = [binding.definition for binding in bindings]
        target["messages"] = transcript

    @staticmethod
    def _used_tools(bindings, transcript):
        """Return unique source-qualified tools actually called by the model."""
        by_alias = {binding.alias: binding for binding in bindings}
        used = []
        for message in transcript:
            for call in message.get("tool_calls", []):
                function = call.get("function", {})
                binding = by_alias.get(str(function.get("name") or ""))
                if binding is None:
                    continue
                identity = f"{binding.source}::{binding.tool}"
                if identity not in used:
                    used.append(identity)
        return used

    @staticmethod
    def _is_libreoffice_save_tool(name):
        """Recognize managed and Custom LibreOffice save aliases."""
        stable_name = re.sub(
            r"__[0-9a-f]{8}$",
            "",
            str(name or "").strip().lower(),
        )
        parts = stable_name.split("__")
        return (
            len(parts) >= 3
            and "libreoffice" in parts[-2]
            and parts[-1] in {"lo_save", "libreoffice_lo_save"}
        )

    @staticmethod
    def _generated_document_candidates(transcript):
        """Return safe LibreOffice save targets, including missing files."""
        output_directory = Path(
            current_app.config["GENERATED_DOCUMENT_DIRECTORY"]
        ).resolve()
        documents = []
        for message in transcript or []:
            if message.get("role") != "tool":
                continue
            if not ChatController._is_libreoffice_save_tool(
                message.get("name")
            ):
                continue
            try:
                result = json.loads(str(message.get("content") or ""))
                saved_path = Path(str(result.get("saved") or "")).resolve()
                relative_path = saved_path.relative_to(output_directory)
            except (AttributeError, json.JSONDecodeError, OSError, ValueError):
                continue
            name = relative_path.as_posix()
            if name not in {item["name"] for item in documents}:
                documents.append({
                    "name": name,
                    "exists": saved_path.is_file(),
                })
        return documents

    def _record_failed_response(
        self,
        error,
        elapsed,
        provider,
        model,
        chat_request,
        request_body,
    ):
        """Persist a failed model call with normal assistant metadata."""
        error_message = str(error).strip() or "The model request failed."
        response_text = f"Request failed: {error_message}"
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self.history.add(
            "assistant",
            response_text,
            model_name=model,
            provider=provider,
            response_time=elapsed,
            input_tokens=0,
            output_tokens=0,
            system_prompt=chat_request.system_prompt,
            saved_system_prompt_name=chat_request.saved_prompt_name,
            request_body=json.dumps(request_body),
            is_error=True,
        )
        payload = self.requests.result_payload(
            response_text,
            elapsed,
            usage,
            provider,
            model,
            chat_request,
            request_body,
            event_type="error",
        )
        payload["error"] = error_message
        payload["is_error"] = True
        return payload

    def context(self):
        settings = CHAT_SETTINGS.form()
        self.media.ensure_backfilled(self.history)
        messages = self.history.messages()
        attachment_settings = CHAT_SETTINGS.group("attachments")
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
            "chat_compact_settings": CHAT_SETTINGS.group("compact"),
            "mineru_settings": CHAT_SETTINGS.group("mineru"),
            "chat_messages": messages,
            "chat_local_attachments": self.media.list(),
            "active_models": self.service.active_models(),
            "saved_chats": self.history.saved("list", "chat"),
            "saved_system_prompts": self.history.saved("list", "system_prompt"),
        }

    def _parse_request(self):
        return self.requests.parse(request.get_json(silent=True) or {})

    def send(self):
        self.media.ensure_backfilled(self.history)
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
        attachment_settings = CHAT_SETTINGS.group("attachments")
        if "stream_responses" in chat_request.raw:
            stream_responses = chat_request.raw["stream_responses"]
            if not isinstance(stream_responses, bool):
                return jsonify(
                    {"error": "stream_responses must be a boolean."}
                ), 400
            attachment_settings["stream_responses"] = stream_responses
        attachment_settings["video_fps"] = chat_request.video_fps
        CHAT_SETTINGS.group("attachments", attachment_settings)
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
                "filename": str(document.get("local_filename") or ""),
                "original_name": str(document.get("filename") or "Document"),
            }
            for document in (chat_request.documents or [])
        ]
        if document_preview_media:
            preview_data.setdefault("preview_media", []).extend(
                document_preview_media
            )
        self.history.add(
            "user",
            chat_request.user_message,
            **preview_data,
        )
        self.media.add_active(
            self.media.records_from_messages([preview_data])
        )

        stream_requested = request.args.get("stream") == "1" or "text/event-stream" in (
            request.accept_mimetypes or ""
        )

        # Build messages list from the most recent turns kept by the user.
        history = self.requests.active_history(self.history.messages())
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
        tool_service = self.tools or ChatToolService(
            self.service,
            settings=self.mcp_settings,
            registry=self._mcp_registry(),
        )
        binding_started = time.monotonic()
        try:
            tool_bindings = tool_service.bindings(provider)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            current_app.logger.exception(
                "Could not load enabled MCP tools for provider=%s", provider
            )
            request_body = {"model": model, "messages": messages}
            elapsed = round(time.monotonic() - binding_started, 2)
            payload = self._record_failed_response(
                error,
                elapsed,
                provider,
                model,
                chat_request,
                request_body,
            )
            payload["local_attachments"] = self.media.list()
            payload["messages"] = self.history.messages()
            return jsonify(payload), 502

        allows_tools = getattr(tool_service, "request_allows_tools", None)
        if tool_bindings and callable(allows_tools) and not allows_tools(
            chat_request.raw,
            chat_request.user_message,
        ):
            tool_bindings = []
        effective_system_prompt = chat_request.system_prompt
        prompt_builder = getattr(tool_service, "system_prompt", None)
        if tool_bindings and callable(prompt_builder):
            effective_system_prompt = prompt_builder(
                chat_request.system_prompt,
                tool_bindings,
            )
        if effective_system_prompt != chat_request.system_prompt:
            chat_request = replace(
                chat_request,
                system_prompt=effective_system_prompt,
            )
            messages = self.requests.messages(
                effective_system_prompt,
                history,
                history_limit,
            )

        needs_conversion = any(
            isinstance(item, dict) and item.get("type") in ("video", "audio")
            for item in chat_request.attachments
        )

        if not stream_requested:
            started = time.monotonic()
            request_body = {"model": model, "messages": messages}
            used_tools = []
            transcript = []
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
                if tool_bindings:
                    response_text, usage, transcript = (
                        self.requests.complete_with_tools(
                            tool_service,
                            tool_bindings,
                            provider,
                            model,
                            plan,
                            request_parameters,
                            chat_request.extra_parameters,
                            documents=chat_request.documents,
                        )
                    )
                    self._add_tools_to_request_body(
                        request_body,
                        tool_bindings,
                        transcript,
                    )
                    used_tools = self._used_tools(tool_bindings, transcript)
                else:
                    response_text, usage = self.requests.complete(
                        provider,
                        model,
                        plan,
                        request_parameters,
                        chat_request.extra_parameters,
                        documents=chat_request.documents,
                    )
            except AttachmentProcessingError as error:
                elapsed = round(time.monotonic() - started, 2)
                payload = self._record_failed_response(
                    error,
                    elapsed,
                    provider,
                    model,
                    chat_request,
                    request_body,
                )
                payload["local_attachments"] = self.media.list()
                payload["messages"] = self.history.messages()
                return jsonify(payload), 422
            except Exception as error:  # noqa: BLE001
                current_app.logger.exception(
                    "Chat request failed for provider=%s model=%s",
                    provider,
                    model,
                )
                elapsed = round(time.monotonic() - started, 2)
                payload = self._record_failed_response(
                    error,
                    elapsed,
                    provider,
                    model,
                    chat_request,
                    request_body,
                )
                payload["local_attachments"] = self.media.list()
                payload["messages"] = self.history.messages()
                return jsonify(payload), 502
            elapsed = round(time.monotonic() - started, 2)
            document_candidates = self._generated_document_candidates(transcript)
            generated_documents = [
                {"name": document["name"]}
                for document in document_candidates
                if document["exists"]
            ]
            assistant_id = self.history.add(
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
                used_tools=used_tools,
                generated_documents=generated_documents,
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
            payload["used_tools"] = used_tools
            payload["generated_documents"] = generated_documents
            self.media.add_active(
                self.media.generated_records(transcript)
                + self.media.external_records(response_text)
            )
            payload["local_attachments"] = self.media.list()
            payload["message_id"] = assistant_id
            payload["messages"] = self.history.messages()
            return jsonify(payload)

        def generate():
            started = time.monotonic()
            usage = {"prompt_tokens": 0, "completion_tokens": 0}
            response_text = ""
            request_body = {"model": model, "messages": messages}
            used_tools = []
            transcript = []
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
                if tool_bindings:
                    transcript = []
                    for tool_event in self.requests.iter_complete_with_tools(
                        tool_service,
                        tool_bindings,
                        provider,
                        model,
                        plan,
                        request_parameters,
                        chat_request.extra_parameters,
                        documents=chat_request.documents,
                    ):
                        if tool_event.get("type") == "status":
                            yield f"data: {json.dumps(tool_event)}\n\n"
                            continue
                        response_text = tool_event["response"]
                        usage = tool_event["usage"]
                        transcript = tool_event["transcript"]
                    self._add_tools_to_request_body(
                        request_body,
                        tool_bindings,
                        transcript,
                    )
                    used_tools = self._used_tools(tool_bindings, transcript)
                    if response_text:
                        yield f"data: {json.dumps({'type': 'chunk', 'text': response_text})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'usage': usage})}\n\n"
                elif plan.split:
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
                document_candidates = self._generated_document_candidates(
                    transcript
                )
                generated_documents = [
                    {"name": document["name"]}
                    for document in document_candidates
                    if document["exists"]
                ]
                assistant_id = self.history.add(
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
                    used_tools=used_tools,
                    generated_documents=generated_documents,
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
                payload["used_tools"] = used_tools
                payload["generated_documents"] = generated_documents
                self.media.add_active(
                    self.media.generated_records(transcript)
                    + self.media.external_records(response_text)
                )
                payload["local_attachments"] = self.media.list()
                payload["message_id"] = assistant_id
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as error:  # noqa: BLE001
                current_app.logger.exception(
                    "Chat stream failed for provider=%s model=%s", provider, model
                )
                elapsed = round(time.monotonic() - started, 2)
                payload = self._record_failed_response(
                    error,
                    elapsed,
                    provider,
                    model,
                    chat_request,
                    request_body,
                )
                payload["local_attachments"] = self.media.list()
                yield f"data: {json.dumps(payload)}\n\n"

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
                for message in self.history.messages()
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
            assistant_id = self.history.add(
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
                "message_id": assistant_id,
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
                assistant_id = self.history.add(
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
                    "message_id": assistant_id,
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
        as_attachment = request.args.get("download") == "1"
        return send_from_directory(
            directory,
            safe_name,
            as_attachment=as_attachment,
            download_name=safe_name if as_attachment else None,
        )

    def download_generated_document(self, filename):
        """Download one document created by an application tool."""
        directory = Path(current_app.config["GENERATED_DOCUMENT_DIRECTORY"])
        safe_path = Path(filename)
        if safe_path.is_absolute() or ".." in safe_path.parts:
            return ("", 404)
        file_path = directory / safe_path
        if not file_path.is_file():
            return ("", 404)
        as_attachment = request.args.get("preview") != "1"
        return send_from_directory(
            directory,
            safe_path.as_posix(),
            as_attachment=as_attachment,
            download_name=safe_path.name if as_attachment else None,
        )

    def preview_generated_document(self, filename):
        """Create or reuse an independent cached document preview."""
        directory = Path(current_app.config["GENERATED_DOCUMENT_DIRECTORY"])
        safe_path = Path(filename)
        if safe_path.is_absolute() or ".." in safe_path.parts:
            return ("", 404)
        source_path = directory / safe_path
        if not source_path.is_file():
            return ("", 404)
        try:
            preview = self.document_previews.preview(source_path, safe_path)
        except DocumentPreviewError as error:
            return jsonify({"error": str(error)}), 422
        response = send_file(
            preview.path,
            mimetype=preview.mimetype,
            as_attachment=False,
            max_age=0,
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def download_external_image(self):
        """Download a validated public chat image through a same-origin route."""
        try:
            image = self.external_images.download(request.args.get("url", ""))
        except ExternalImageError as error:
            return jsonify({"error": str(error)}), 400
        return send_file(
            io.BytesIO(image.content),
            mimetype=image.content_type,
            as_attachment=request.args.get("preview") != "1",
            download_name=(
                image.filename if request.args.get("preview") != "1" else None
            ),
            max_age=0,
        )

    def inspect_external_image(self):
        """Report whether a validated public URL returns an image MIME type."""
        try:
            document = self.external_images.inspect(request.args.get("url", ""))
        except ExternalImageError as error:
            return jsonify({"error": str(error)}), 400
        response = jsonify(
            {
                "is_image": document.content_type.startswith("image/"),
                "content_type": document.content_type,
                "filename": document.filename,
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    def capture_webpage_previews(self):
        """Capture ordinary webpage links and persist their UUID mappings."""
        self.media.ensure_backfilled(self.history)
        data = request.get_json(silent=True) or {}
        try:
            message_id = int(data.get("message_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "A valid assistant message ID is required."}), 400
        urls = data.get("urls")
        if not isinstance(urls, list):
            return jsonify({"error": "Webpage preview URLs must be a list."}), 400
        if not any(
            message.get("id") == message_id and message.get("role") == "assistant"
            for message in self.history.messages()
        ):
            return jsonify({"error": "Assistant message not found."}), 404
        settings = self.mcp_settings.global_settings()
        if not settings["capture_webpage_preview"]:
            return jsonify({"previews": [], "disabled": True})
        previews = self.webpages.capture(
            urls,
            timeout_seconds=settings["webpage_preview_timeout"],
        )
        self.history.update_webpage_previews(message_id, previews)
        records = []
        for preview in previews:
            record = self.media.preview_record(
                preview.get("filename"),
                media_type="image",
            )
            if record:
                records.append(record)
        records.extend(self.media.external_records("\n".join(urls)))
        self.media.add_active(records)
        return jsonify({
            "previews": previews,
            "attachments": self.media.list(),
        })

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
        CHAT_SETTINGS.form(settings)
        return jsonify({"message": "Settings saved."})

    def save_attachment_settings(self):
        """Persist last-used media attachment switch values."""
        data = request.get_json(silent=True) or {}
        settings = CHAT_SETTINGS.group("attachments")
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
        CHAT_SETTINGS.group("attachments", settings)
        return jsonify({"message": "Attachment settings saved."})

    def save_compact_settings(self):
        """Validate and persist the automatic compaction threshold."""
        data = request.get_json(silent=True) or {}
        threshold = data.get("threshold", DEFAULT_AUTO_COMPACT_THRESHOLD)
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, int)
            or not AUTO_COMPACT_THRESHOLD_MIN
            <= threshold
            <= AUTO_COMPACT_THRESHOLD_MAX
        ):
            return jsonify({
                "error": "Auto compact threshold must be an integer from 5 to 100."
            }), 400
        return jsonify(CHAT_SETTINGS.group("compact", {"threshold": threshold}))

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

    def save_switch_setting(self, name, aliases=()):
        """Persist one compatible boolean chat-switch payload."""
        data = request.get_json(silent=True) or {}
        value = self._switch_value(data, name, *aliases)
        if value is None:
            return jsonify({"error": f"{name} must be a boolean."}), 400
        CHAT_SETTINGS.group("attachments", {name: value})
        return jsonify({"message": "Settings saved."})

    save_seed_settings = partialmethod(
        save_switch_setting,
        "randomize_seed",
        ("seed_randomize", "randomize"),
    )
    save_history_settings = partialmethod(
        save_switch_setting,
        "send_all_previous",
        (
            "send_all_previous_messages",
            "all_previous",
            "all_previous_messages",
            "history_all",
            "all_history",
        ),
    )

    def clear(self):
        self.media.ensure_backfilled(self.history)
        self.history.messages([])
        self.media.delete_scope("active")
        return jsonify({"message": "Chat cleared."})

    def export_chat(self):
        """Export the complete active chat or one selected saved chat."""
        data = request.get_json(silent=True) or {}
        name = str(data.get("name") or "").strip()
        messages = (
            self.history.saved("get", "chat", name)
            if name
            else self.history.messages()
        )
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

    def import_chat(self):
        """Validate and restore one exported chat as the active conversation."""
        data = request.get_json(silent=True) or {}
        try:
            messages = self.exports.import_messages(data.get("document"))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        self.media.ensure_backfilled(self.history)
        messages, _changed = self.media.enrich_generated_documents(messages)
        try:
            self.history.messages(messages)
        except Exception:  # noqa: BLE001
            current_app.logger.exception("Could not import chat")
            return jsonify({"error": "Chat import failed."}), 500

        restored = self.history.messages()
        self.media.replace_active_from_messages(restored)
        return jsonify({
            "message": "Chat imported.",
            "messages": restored,
            "attachments": self.media.list(),
        })

    def _mineru_check(
        self,
        endpoint,
        api_key=None,
        timeout=DEFAULT_MINERU_TIMEOUT,
    ):
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
                with urllib.request.urlopen(request_obj, timeout=timeout) as response:
                    if getattr(response, "status", None) == 200:
                        return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def mineru_available(self):
        """Report whether the local MinerU document service is reachable."""
        settings = CHAT_SETTINGS.group("mineru")
        endpoint = settings.get("endpoint", "http://127.0.0.1:8100")
        api_key = settings.get("api_key", "")
        timeout = settings.get("timeout", DEFAULT_MINERU_TIMEOUT)
        return jsonify(
            {"available": bool(self._mineru_check(endpoint, api_key, timeout))}
        )

    def mineru_settings_get(self):
        """Return the saved MinerU endpoint settings."""
        return jsonify(CHAT_SETTINGS.group("mineru"))

    def mcp_status(self):
        """Return the live status of one registered local MCP service."""
        name = request.args.get("name", "").strip()
        endpoint = request.args.get("endpoint", "").strip()
        timeout_ms = request.args.get("timeout_ms")
        if not name:
            return jsonify({"error": "MCP service name is required."}), 400
        saved_settings = next(
            (
                record["settings"]
                for record in self.mcp_settings.all()
                if record["source"] == "external" and record["service"] == name
            ),
            {},
        )
        try:
            return jsonify(
                self._mcp_registry().check(
                    name,
                    endpoint or saved_settings.get("endpoint"),
                    timeout_ms or saved_settings.get("timeout_ms"),
                    saved_settings.get("user", ""),
                    saved_settings.get("password", ""),
                )
            )
        except (OSError, json.JSONDecodeError):
            current_app.logger.exception("Could not read MCP configuration")
            return jsonify({"error": "Could not read MCP configuration."}), 500
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    def mcp_endpoint_test(self):
        """Test an endpoint declared by a service-specific setup schema."""
        payload = request.get_json(silent=True) or {}
        source = str(payload.get("source") or "").strip()
        name = str(payload.get("service") or "").strip()
        access_key = str(payload.get("access_key") or "").strip()
        submitted = payload.get("settings", {})
        if source not in {"external", "llama_service"}:
            return jsonify({"error": "A valid MCP source is required."}), 400
        if not MCP_NAME_PATTERN.fullmatch(name):
            return jsonify({"error": "A valid MCP service name is required."}), 400
        if not isinstance(submitted, dict):
            return jsonify({"error": "MCP settings must be an object."}), 400

        definitions, test_definition = self._mcp_endpoint_test_setup(
            name,
            allow_default=source != "llama_service",
        )
        if source == "llama_service" and definitions is None:
            return jsonify({"name": name, "online": True, "status_code": None})
        if definitions is None:
            return jsonify({"error": "Endpoint test setup is unavailable."}), 400
        if (
            test_definition is None
            or test_definition.get("access_key") != access_key
            or not isinstance(definitions.get(access_key), dict)
        ):
            return jsonify({"error": "Endpoint test setup is invalid."}), 400

        saved = next(
            (
                record["settings"]
                for record in self.mcp_settings.all()
                if record["source"] == source and record["service"] == name
            ),
            {},
        )
        settings = dict(saved)
        secret_fields = self._mcp_secret_fields(name) | {"password"}
        settings.update(
            {
                key: value
                for key, value in submitted.items()
                if key not in secret_fields or value not in (None, "")
            }
        )
        endpoint_definition = definitions[access_key]
        endpoint = settings.get(access_key)
        if endpoint in (None, ""):
            endpoint = endpoint_definition.get("default", "")
        try:
            result = self._mcp_registry().test_endpoint(
                name,
                endpoint,
                settings.get("timeout_ms"),
                settings.get("user", ""),
                settings.get("password", ""),
                managed=source == "llama_service",
            )
            return jsonify(result)
        except (OSError, json.JSONDecodeError):
            current_app.logger.exception("Could not test MCP endpoint")
            return jsonify({"error": "Could not test MCP endpoint."}), 500
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @staticmethod
    def _mcp_setup_definitions(name, *, allow_default=True):
        setup_names = (
            (name,)
            if name == "default" or not allow_default
            else (name, "default")
        )
        for setup_name in setup_names:
            setup_name = str(setup_name).strip().lower()
            setup_path = (
                Path(current_app.static_folder)
                / f"tool-setup-{setup_name}.json"
            )
            try:
                with setup_path.open("r", encoding="utf-8-sig") as setup_file:
                    definitions = json.load(setup_file)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(definitions, dict):
                return definitions
        return None

    @classmethod
    def _mcp_secret_fields(cls, name):
        """Return fields whose service schema declares password input."""
        definitions = cls._mcp_setup_definitions(name) or {}
        return {
            key
            for key, definition in definitions.items()
            if isinstance(definition, dict)
            and str(definition.get("type") or "").lower() == "password"
        }

    @classmethod
    def _mcp_endpoint_test_setup(cls, name, *, allow_default=True):
        definitions = cls._mcp_setup_definitions(
            name,
            allow_default=allow_default,
        )
        if definitions is None:
            return None, None
        test_definition = definitions.get("test")
        if (
            not isinstance(test_definition, dict)
            or str(test_definition.get("type") or "").lower() != "button"
        ):
            test_definition = None
        return definitions, test_definition

    def llama_managed_tools(self):
        """Return live MCP discovery state from the configured llama.cpp server."""
        return jsonify(self.service.llama_managed_tools())

    def llama_managed_mcp_status(self):
        """Return the API status required by one llama.cpp-managed service."""
        name = request.args.get("name", "").strip()
        endpoint = request.args.get("endpoint", "").strip()
        timeout_ms = request.args.get("timeout_ms", 3000)
        if not name:
            return jsonify({"error": "MCP service name is required."}), 400
        try:
            result = self._mcp_registry().check_managed_service(
                name,
                endpoint,
                timeout_ms,
            )
            return jsonify(result)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @staticmethod
    def _mcp_registry():
        return McpServiceRegistry(
            config_path=current_app.config["MCP_CONFIG_PATH"],
            opencode_path=current_app.config["OPENCODE_CONFIG_PATH"],
        )

    def mcp_configuration(self):
        """Return private MCP configuration and first-run discovery state."""
        try:
            return jsonify(self._mcp_registry().client_configuration())
        except (OSError, json.JSONDecodeError, ValueError):
            current_app.logger.exception("Could not read MCP configuration")
            return jsonify({"error": "Could not read MCP configuration."}), 500

    def import_opencode_mcp(self):
        """Import usable OpenCode MCP declarations after explicit approval."""
        try:
            servers = self._mcp_registry().import_opencode()
            return jsonify({"saved": True, "mcpServers": servers})
        except (OSError, json.JSONDecodeError):
            current_app.logger.exception("Could not import OpenCode MCP configuration")
            return jsonify({"error": "Could not import OpenCode MCP configuration."}), 500
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    def save_mcp_server(self):
        """Create or update one private local MCP server declaration."""
        data = request.get_json(silent=True) or {}
        settings = data.get("settings", {})
        if not isinstance(settings, dict):
            return jsonify({"error": "MCP settings must be an object."}), 400
        try:
            service_name = str(data.get("name") or "").strip()
            registry = self._mcp_registry()
            availability = registry.probe_local_server(
                service_name,
                data.get("command"),
                data.get("args"),
                data.get("timeout_ms"),
                settings.get("endpoint"),
                settings.get("user", ""),
                settings.get("password", ""),
                settings=settings,
            )
            if not availability.get("online"):
                return jsonify(
                    {"error": "MCP service is not accessible."}
                ), 400
            declaration = registry.save_local_server(
                service_name,
                data.get("command"),
                data.get("args"),
                data.get("timeout_ms"),
            )
            existing = next(
                (
                    record
                    for record in self.mcp_settings.all()
                    if record["source"] == "external"
                    and record["service"] == service_name
                    and not record["tool"]
                ),
                None,
            )
            saved_settings = dict(existing["settings"]) if existing else {}
            secret_fields = self._mcp_secret_fields(service_name) | {"password"}
            for field_name, value in settings.items():
                if (
                    field_name in secret_fields
                    and value in (None, "")
                    and saved_settings.get(field_name)
                ):
                    continue
                saved_settings[field_name] = value
            self.mcp_settings.upsert(
                [
                    {
                        "source": "external",
                        "service": service_name,
                        "tool": "",
                        "enabled": existing["enabled"] if existing else False,
                        "settings": saved_settings,
                        "secret_fields": sorted(secret_fields),
                    }
                ]
            )
            return jsonify(
                {
                    "saved": True,
                    "server": declaration,
                    "availability": availability,
                }
            )
        except OSError:
            current_app.logger.exception("Could not save MCP configuration")
            return jsonify({"error": "Could not save MCP configuration."}), 500
        except (json.JSONDecodeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400

    def mcp_settings_get(self):
        """Return saved MCP preferences keyed per service and tool."""
        records = self.mcp_settings.all()
        for record in records:
            settings = dict(record["settings"])
            secret_fields = self._mcp_secret_fields(record["service"]) | {
                "password"
            }
            saved_secret_fields = sorted(
                field_name
                for field_name in secret_fields
                if settings.pop(field_name, "")
            )
            record["settings"] = settings
            if saved_secret_fields:
                record["secret_fields_saved"] = saved_secret_fields
            if "password" in saved_secret_fields:
                record["password_saved"] = True
        return jsonify(
            {
                "records": records,
                "custom_tools": self.mcp_settings.cached_tools(),
            }
        )

    def mcp_global_state(self):
        """Read or save global tool behavior without probing services."""
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            enabled = payload.get("enabled")
            if not isinstance(enabled, bool):
                return jsonify({"error": "Tool state must be a boolean."}), 400
            try:
                settings = self.mcp_settings.set_global_settings(
                    payload.get("settings", self.mcp_settings.global_settings())
                )
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
            self.mcp_settings.set_tools_enabled(enabled)
        else:
            settings = self.mcp_settings.global_settings()
        return jsonify(
            {
                "enabled": self.mcp_settings.tools_enabled(),
                "enabled_services": self.mcp_settings.enabled_services(),
                "settings": settings,
            }
        )

    def mcp_tools_refresh(self):
        """Refresh cached tool definitions for accessible Custom MCP services."""
        registry = self._mcp_registry()
        saved_settings = {
            record["service"]: record["settings"]
            for record in self.mcp_settings.all()
            if record["source"] == "external"
        }
        refreshed = []
        skipped = []
        try:
            service_names = sorted(registry.services())
        except (OSError, ValueError, json.JSONDecodeError):
            current_app.logger.exception("Could not read MCP configuration")
            return jsonify({"error": "Could not read MCP configuration."}), 500

        for name in service_names:
            settings = saved_settings.get(name, {})
            try:
                result = registry.discover_tools(
                    name,
                    settings.get("endpoint"),
                    settings.get("timeout_ms"),
                    settings.get("user", ""),
                    settings.get("password", ""),
                )
            except (OSError, ValueError, json.JSONDecodeError):
                current_app.logger.exception(
                    "Could not refresh MCP tools for service=%s",
                    name,
                )
                result = {"online": False, "tools": []}
            if result.get("online"):
                count = self.mcp_settings.replace_cached_tools(
                    name,
                    result.get("tools", []),
                )
                refreshed.append({"service": name, "tools": count})
            else:
                skipped.append(name)

        return jsonify(
            {
                "refreshed": refreshed,
                "skipped": skipped,
                "custom_tools": self.mcp_settings.cached_tools(),
            }
        )

    @staticmethod
    def _managed_tool_identity(tool):
        definition = tool.get("definition") if isinstance(tool, dict) else None
        function = definition.get("function") if isinstance(definition, dict) else None
        tool_name = str(
            (tool.get("tool") if isinstance(tool, dict) else None)
            or (function.get("name") if isinstance(function, dict) else None)
            or ""
        ).strip()
        explicit_service = next(
            (
                value.strip()
                for value in (
                    tool.get("mcp_server") if isinstance(tool, dict) else None,
                    tool.get("mcp_service") if isinstance(tool, dict) else None,
                    tool.get("server") if isinstance(tool, dict) else None,
                    tool.get("service") if isinstance(tool, dict) else None,
                )
                if isinstance(value, str) and value.strip()
            ),
            "",
        )
        service_name = explicit_service or tool_name.split("_", 1)[0]
        return service_name, tool_name

    def mcp_settings_save(self):
        """Persist preferences only for currently accessible MCP entries."""
        payload = request.get_json(silent=True) or {}
        records = payload.get("records")
        if not isinstance(records, list):
            return jsonify({"error": "MCP records must be a list."}), 400

        saved_secrets = {}
        for saved_record in self.mcp_settings.all():
            secret_fields = self._mcp_secret_fields(saved_record["service"]) | {
                "password"
            }
            for field_name in secret_fields:
                secret = saved_record["settings"].get(field_name)
                if secret:
                    saved_secrets[
                        (
                            saved_record["source"],
                            saved_record["service"],
                            field_name,
                        )
                    ] = secret
        normalized = []
        for record in records:
            if not isinstance(record, dict):
                return jsonify({"error": "Each MCP record must be an object."}), 400
            source = str(record.get("source") or "").strip()
            service_name = str(record.get("service") or "").strip()
            tool_name = str(record.get("tool") or "").strip()
            enabled = record.get("enabled")
            settings = record.get("settings", {})
            if source not in {
                "external",
                "external_tool",
                "llama_service",
                "llama_tool",
            }:
                return jsonify({"error": "A valid MCP record source is required."}), 400
            if not service_name or not isinstance(enabled, bool):
                return jsonify({"error": "MCP service and boolean state are required."}), 400
            if source in {"external_tool", "llama_tool"} and not tool_name:
                return jsonify({"error": "A managed MCP tool name is required."}), 400
            if not isinstance(settings, dict):
                return jsonify({"error": "MCP settings must be an object."}), 400
            settings = dict(settings)
            secret_fields = self._mcp_secret_fields(service_name) | {"password"}
            for field_name in secret_fields:
                saved_secret = saved_secrets.get(
                    (source, service_name, field_name)
                )
                if settings.get(field_name) in (None, "") and saved_secret:
                    settings[field_name] = saved_secret
            normalized.append(
                {
                    "source": source,
                    "service": service_name,
                    "tool": tool_name,
                    "enabled": enabled,
                    "settings": settings,
                    "secret_fields": sorted(secret_fields),
                }
            )

        registry = self._mcp_registry()
        eligible = []
        skipped = []
        external_status = {}
        external_settings = {
            item["service"]: item["settings"]
            for item in normalized
            if item["source"] == "external"
        }
        external_enabled = {
            item["service"]: item["enabled"]
            for item in normalized
            if item["source"] == "external"
        }
        cached_external_tools = {
            (tool["service"], tool["tool"])
            for tool in self.mcp_settings.cached_tools()
        }
        for record in (
            item for item in normalized if item["source"].startswith("external")
        ):
            name = record["service"]
            service_enabled = external_enabled.get(name, False)
            if not record["enabled"] or not service_enabled:
                eligible.append(record)
                continue
            if name not in external_status:
                service_settings = external_settings.get(name, {})
                try:
                    external_status[name] = bool(
                        registry.check(
                            name,
                            service_settings.get("endpoint"),
                            service_settings.get("timeout_ms"),
                            service_settings.get("user", ""),
                            service_settings.get("password", ""),
                        ).get("online")
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    external_status[name] = False
            accessible = external_status[name]
            if record["source"] == "external_tool":
                accessible = accessible and (
                    name,
                    record["tool"],
                ) in cached_external_tools
            (eligible if accessible else skipped).append(record)

        managed_records = [
            item for item in normalized if item["source"].startswith("llama_")
        ]
        managed_enabled = {
            item["service"]: item["enabled"]
            for item in managed_records
            if item["source"] == "llama_service"
        }
        enabled_managed_records = [
            item
            for item in managed_records
            if item["enabled"] and managed_enabled.get(item["service"], False)
        ]
        if managed_records and not enabled_managed_records:
            eligible.extend(managed_records)
        elif enabled_managed_records:
            discovery = self.service.llama_managed_tools()
            live_tools = {}
            live_services = set()
            if discovery.get("online"):
                for tool in discovery.get("tools", []):
                    service_name, tool_name = self._managed_tool_identity(tool)
                    if service_name and tool_name:
                        live_services.add(service_name)
                        live_tools[tool_name] = service_name

            saved_records = self.mcp_settings.all()
            service_settings = {
                item["service"]: item["settings"]
                for item in saved_records
                if item["source"] == "llama_service"
            }
            service_settings.update(
                {
                    item["service"]: item["settings"]
                    for item in managed_records
                    if item["source"] == "llama_service"
                }
            )
            managed_status = {}
            enabled_services = {
                item["service"] for item in enabled_managed_records
            }
            for service_name in live_services & enabled_services:
                settings = service_settings.get(service_name, {})
                definitions, test_definition = self._mcp_endpoint_test_setup(
                    service_name,
                    allow_default=False,
                )
                if test_definition is None:
                    managed_status[service_name] = True
                    continue
                access_key = str(test_definition.get("access_key") or "")
                access_definition = definitions.get(access_key, {})
                endpoint = settings.get(access_key)
                if endpoint in (None, ""):
                    endpoint = access_definition.get("default", "")
                try:
                    managed_status[service_name] = bool(
                        registry.test_endpoint(
                            service_name,
                            endpoint,
                            settings.get("timeout_ms", 3000),
                            settings.get("user", ""),
                            settings.get("password", ""),
                            managed=True,
                        ).get("online")
                    )
                except (OSError, ValueError):
                    managed_status[service_name] = False

            for record in managed_records:
                service_name = record["service"]
                if (
                    not record["enabled"]
                    or not managed_enabled.get(service_name, False)
                ):
                    eligible.append(record)
                    continue
                accessible = managed_status.get(service_name, False)
                if record["source"] == "llama_tool":
                    accessible = (
                        accessible
                        and live_tools.get(record["tool"]) == service_name
                    )
                (eligible if accessible else skipped).append(record)

        self.mcp_settings.upsert(eligible)
        return jsonify(
            {
                "saved": len(eligible),
                "skipped": [
                    {
                        "source": item["source"],
                        "service": item["service"],
                        "tool": item["tool"],
                    }
                    for item in skipped
                ],
            }
        )

    def save_mineru_settings(self):
        """Validate and persist the MinerU endpoint settings."""
        data = request.get_json(silent=True) or {}
        endpoint = str(data.get("endpoint") or "").strip()
        api_key = str(data.get("api_key") or "").strip()
        timeout = data.get("timeout", DEFAULT_MINERU_TIMEOUT)
        if not endpoint:
            return jsonify({"error": "MinerU endpoint is required."}), 400
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, int)
            or not MINERU_TIMEOUT_MIN <= timeout <= MINERU_TIMEOUT_MAX
        ):
            return jsonify(
                {"error": "MinerU timeout must be an integer from 1 to 30."}
            ), 400
        if not self._mineru_check(endpoint, api_key, timeout):
            return jsonify({"error": "MinerU endpoint is not reachable."}), 400
        saved = CHAT_SETTINGS.group(
            "mineru",
            {"endpoint": endpoint, "api_key": api_key, "timeout": timeout}
        )
        return jsonify({"message": "MinerU settings saved.", **saved})

    def process_document(self):
        """Process a binary document through the configured MinerU service."""
        self.media.ensure_backfilled(self.history)
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

        local_filename = self.previews.save_original(raw_data.strip(), filename)
        if not local_filename:
            return jsonify({"error": "Document could not be saved locally."}), 500
        record = self.media.preview_record(
            local_filename,
            filename,
            "document",
        )
        if record:
            self.media.add_active([record])

        settings = CHAT_SETTINGS.group("mineru")
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
        return jsonify({
            "content": extracted,
            "local_filename": local_filename,
            "attachments": self.media.list(),
        })

    def abort(self):
        self.media.ensure_backfilled(self.history)
        deleted = self.history.delete_last()
        if deleted:
            self.media.replace_active_from_messages(self.history.messages())
        return jsonify({"message": "Request aborted.", "deleted": deleted})

    def saved_chat(self, action):
        """List, save, load, replace, or delete a named chat."""
        self.media.ensure_backfilled(self.history)
        if action == "list":
            return jsonify({"names": self.history.saved("list", "chat")})
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Chat name is required."}), 400
        if action == "save":
            self.history.saved("save", "chat", name, self.history.messages())
            self.media.copy_active_to_saved(name)
            return jsonify({"message": "Chat saved.", "name": name})
        if action == "load":
            if not self.history.load(name):
                return jsonify({"error": "Saved chat not found."}), 404
            self.media.copy_saved_to_active(name)
            messages = self.history.messages()
            return jsonify(
                {
                    "message": "Chat loaded.",
                    "name": name,
                    "messages": messages,
                    "attachments": self.media.list(),
                }
            )
        if action == "replace":
            if self.history.saved("get", "chat", name) is None:
                return jsonify({"error": "Saved chat not found."}), 404
            current_messages = self.history.messages()
            self.history.saved("save", "chat", name, current_messages)
            self.media.copy_active_to_saved(name)
            return jsonify({"message": "Chat replaced.", "name": name})

        saved = self.history.saved("get", "chat", name)
        if saved is None:
            return jsonify({"error": "Saved chat not found."}), 404
        if not self.history.saved("delete", "chat", name):
            return jsonify({"error": "Saved chat not found."}), 404
        self.history.messages([])
        self.media.delete_scope("saved", name)
        self.media.delete_scope("active")
        return jsonify({"message": "Chat deleted.", "name": name})

    def saved_system_prompt(self, action):
        """List, save, load, or delete a named system prompt."""
        if action == "list":
            return jsonify({
                "names": self.history.saved("list", "system_prompt")
            })
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name is required."}), 400
        if action == "save":
            self.history.saved(
                "save",
                "system_prompt",
                name,
                data.get("content", ""),
            )
            return jsonify({"message": "System prompt saved.", "name": name})
        if action == "load":
            content = self.history.saved("get", "system_prompt", name)
            if content is None:
                return jsonify({"error": "Saved system prompt not found."}), 404
            return jsonify(
                {
                    "message": "System prompt loaded.",
                    "name": name,
                    "content": content,
                }
            )
        if not self.history.saved("delete", "system_prompt", name):
            return jsonify({"error": "Saved system prompt not found."}), 404
        return jsonify({"message": "System prompt deleted.", "name": name})


chat_controller = ChatController()
