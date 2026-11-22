"""Validation and model-request planning shared by chat endpoints."""

import base64
import json
import re
from dataclasses import dataclass

from models.chat_settings import CHAT_SETTINGS, VIDEO_FPS_VALUES
from models.chat_storage import CHAT_HISTORY
from services.chat_attachments import (
    convert_audio_attachment,
    convert_video_attachment,
    extract_video_audio_attachment,
    resize_image_attachment,
    video_has_audio,
)


CHAT_PARAMETER_FIELDS = {
    "temperature": (float, "Temperature"),
    "top_p": (float, "Top P"),
    "top_k": (int, "Top K"),
    "seed": (int, "Seed"),
    "history_limit": (int, "Prev. messages"),
    "min_p": (float, "Min P"),
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
MIME_TYPES = {
    "txt": "text/plain",
    "md": "text/markdown",
    "doc": "application/msword",
    "rtf": "application/rtf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "mp4": "video/mp4",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
}
HISTORY_SWITCH_NAMES = (
    "send_all_previous",
    "send_all_previous_messages",
    "all_previous",
    "all_previous_messages",
    "history_all",
    "all_history",
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


class ChatRequestWorkflow:
    """Validate chat input and build provider-neutral model requests."""

    def __init__(self, service, settings=CHAT_SETTINGS, history=CHAT_HISTORY):
        self.service = service
        self.settings = settings
        self.history = history

    def parse(self, data):
        """Normalize one browser payload without depending on Flask request state."""
        data = data if isinstance(data, dict) else {}
        attachment_settings = self.settings.group("attachments")
        system_prompt = data.get("system_prompt") or ""
        saved_name_raw = (data.get("saved_system_prompt_name") or "").strip()
        saved_name = ""
        if saved_name_raw:
            stored = self.history.saved("get", "system_prompt", saved_name_raw)
            if stored is None and system_prompt.strip():
                self.history.saved(
                    "save",
                    "system_prompt",
                    saved_name_raw,
                    system_prompt,
                )
                stored = system_prompt
            if stored == system_prompt:
                saved_name = saved_name_raw

        parameters = {}
        for key, (converter, label) in CHAT_PARAMETER_FIELDS.items():
            parameters[key] = self.number(data.get(key), label, converter)
        return ChatRequestData(
            raw=data,
            model_spec=(data.get("model") or "").strip(),
            user_message=(data.get("message") or "").strip(),
            system_prompt=system_prompt,
            saved_prompt_name=saved_name,
            parameters=parameters,
            extra_parameters=self.model_parameters(data.get("model_params")),
            video_fps=self.video_fps(
                data.get("video_fps", attachment_settings["video_fps"])
            ),
            attachments=self.items(data.get("attachments"), "attachment"),
            documents=self.items(data.get("documents"), "document"),
        )

    @staticmethod
    def number(value, label, converter):
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

    @staticmethod
    def video_fps(value):
        """Validate one of the FPS values offered by the video slider."""
        try:
            fps = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Video FPS must be a valid number.") from error
        if fps not in VIDEO_FPS_VALUES:
            supported = ", ".join(str(item) for item in VIDEO_FPS_VALUES)
            raise ValueError(f"Video FPS must be one of: {supported}.")
        return fps

    @staticmethod
    def model_parameters(value):
        """Return validated JSON-safe values from the parameter modal."""
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
            valid_scalar = isinstance(item, (str, bool, int, float))
            valid_list = isinstance(item, list) and all(
                isinstance(entry, (str, bool, int, float)) for entry in item
            )
            if isinstance(item, str) and len(item) > MODEL_PARAMETER_TEXT_LIMIT:
                raise ValueError("A model parameter value is too long.")
            if isinstance(item, list) and len(item) > MODEL_PARAMETER_LIMIT:
                raise ValueError("A model parameter list is too long.")
            if not (valid_scalar or valid_list):
                raise ValueError(
                    "Model parameter values must be simple JSON values."
                )
            cleaned[key] = item
        return cleaned

    @staticmethod
    def items(value, kind):
        """Validate and normalize document or media attachment dictionaries."""
        label = "Documents" if kind == "document" else "Attachments"
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise ValueError(f"{label} must be a list.")
        if kind == "attachment" and len(value) > ATTACHMENT_LIMIT:
            raise ValueError("Too many attachments were supplied.")

        cleaned = []
        for item in value:
            if not isinstance(item, dict):
                raise ValueError(f"{label} must be objects.")
            filename = str(item.get("filename") or item.get("name") or "").strip()
            extension = str(item.get("extension") or "").strip().lower()
            if not extension and "." in filename:
                extension = filename.rsplit(".", 1)[-1].lower()
            mime_type = str(item.get("mime_type") or "").strip()
            mime_type = mime_type or MIME_TYPES.get(
                extension, "application/octet-stream"
            )
            if kind == "document":
                content = item.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Document content is required.")
                size = item.get("size")
                if not isinstance(size, int) or size < 0:
                    size = len(content.encode("utf-8"))
                cleaned.append(
                    {
                        "id": str(
                            item.get("id") or f"doc_{len(cleaned) + 1:03d}"
                        ).strip(),
                        "filename": filename,
                        "mime_type": mime_type,
                        "extension": extension,
                        "size": size,
                        "content": content,
                    }
                )
                continue

            attachment_type = str(item.get("type") or "").strip().lower()
            if attachment_type not in ATTACHMENT_TYPES:
                raise ValueError(
                    "Attachment type must be image, document, video, or audio."
                )
            data = item.get("data")
            if not isinstance(data, str) or not data.strip():
                raise ValueError("Attachment data is required.")
            data = data.strip()
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
            preview_data = item.get("preview_data")
            if isinstance(preview_data, str) and preview_data.strip():
                preview_data = preview_data.strip()
                try:
                    base64.b64decode(preview_data, validate=True)
                except Exception as error:  # noqa: BLE001
                    raise ValueError("Preview data must be valid base64.") from error
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

    def history_switch(self, data):
        """Read the compatible history switch names or its saved fallback."""
        for name in HISTORY_SWITCH_NAMES:
            if name not in data:
                continue
            value = data[name]
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes", "on"}
            return False
        return self.settings.switch("send_all_previous")

    @staticmethod
    def active_history(history):
        """Return the conversation beginning at its latest compacted summary."""
        latest_compaction = next(
            (
                index
                for index in range(len(history) - 1, -1, -1)
                if history[index].get("compacted")
            ),
            None,
        )
        if latest_compaction is None:
            return history[:]
        return history[latest_compaction:]

    @staticmethod
    def selected_history(history, limit, *, keep_current=False):
        """Select recent turns, optionally retaining the current user item."""
        if limit is None:
            return history[:]
        current = history[-1:] if keep_current else []
        previous = history[:-1] if keep_current else history
        if limit <= 0:
            return current
        return previous[max(0, len(previous) - (limit * 2)) :] + current

    def messages(self, system_prompt, history, history_limit):
        """Build provider messages while retaining complete recent chat turns."""
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(
            {"role": item["role"], "content": item["content"]}
            for item in self.selected_history(
                history, history_limit, keep_current=True
            )
        )
        return messages

    @staticmethod
    def attachment_plan(attachments, messages, fps=2):
        """Convert attachments into the one or two requests they require."""
        attachments = attachments or []
        split = any(
            isinstance(item, dict)
            and item.get("type") == "video"
            and bool(item.get("attach_audio"))
            for item in attachments
        )
        primary = []
        audio = []
        for item in attachments:
            if not isinstance(item, dict):
                primary.append(item)
            elif item.get("type") == "video":
                primary.append(convert_video_attachment(item, fps=fps))
                if split and item.get("attach_audio") and video_has_audio(
                    item.get("data", "")
                ):
                    extracted = extract_video_audio_attachment(item)
                    if extracted is not None:
                        audio.append(extracted)
            elif item.get("type") == "audio":
                converted = convert_audio_attachment(item)
                (audio if split else primary).append(converted)
            elif item.get("type") == "image":
                primary.append(resize_image_attachment(item))
            else:
                primary.append(item)

        audio_messages = []
        if split:
            audio_messages = [dict(message) for message in messages]
            for message in reversed(audio_messages):
                if message.get("role") == "user":
                    message["content"] = AUDIO_ANALYSIS_PROMPT
                    break
        return AttachmentRequestPlan(
            primary_attachments=primary,
            primary_messages=messages,
            audio_attachments=audio,
            audio_messages=audio_messages,
            split=split,
        )

    def request_body(
        self,
        provider,
        model,
        plan,
        request_parameters,
        extra_parameters,
        documents=None,
    ):
        """Build the persisted JSON body for an attachment request plan."""
        filtered_extra = self.service.local_extra_parameters(
            provider, extra_parameters
        )

        def one(messages, attachments):
            body = {"model": model, "messages": messages}
            body.update(
                {
                    key: value
                    for key, value in (request_parameters or {}).items()
                    if value is not None
                }
            )
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

        primary = one(plan.primary_messages, plan.primary_attachments)
        if not plan.audio_attachments:
            return primary
        return {
            "video_request": primary,
            "audio_request": one(plan.audio_messages, plan.audio_attachments),
        }

    def complete(
        self,
        provider,
        model,
        plan,
        request_parameters,
        extra_parameters,
        documents=None,
    ):
        """Run every request in an attachment plan and combine its result."""
        primary_text, primary_usage = self.service.chat_completion_with_params(
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
            audio_text, audio_usage = self.service.chat_completion_with_params(
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

    def complete_with_tools(
        self,
        tool_service,
        bindings,
        provider,
        model,
        plan,
        request_parameters,
        extra_parameters,
        documents=None,
    ):
        """Run tools for the primary request and preserve split-audio behavior."""
        primary_text, primary_usage, transcript = tool_service.complete(
            provider,
            model,
            plan.primary_messages,
            bindings,
            request_parameters,
            extra_parameters,
            attachments=plan.primary_attachments,
            documents=documents,
        )
        audio_text = ""
        audio_usage = {}
        if plan.audio_attachments:
            audio_text, audio_usage = self.service.chat_completion_with_params(
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
        return response_text, usage, transcript

    def iter_complete_with_tools(
        self,
        tool_service,
        bindings,
        provider,
        model,
        plan,
        request_parameters,
        extra_parameters,
        documents=None,
    ):
        """Yield tool statuses followed by the combined final result."""
        completed = None
        for event in tool_service.iter_complete(
            provider,
            model,
            plan.primary_messages,
            bindings,
            request_parameters,
            extra_parameters,
            attachments=plan.primary_attachments,
            documents=documents,
        ):
            if event.get("type") == "status":
                yield event
            elif event.get("type") == "complete":
                completed = event
        if completed is None:
            raise RuntimeError("The tool workflow ended without a response.")

        audio_text = ""
        audio_usage = {}
        if plan.audio_attachments:
            audio_text, audio_usage = self.service.chat_completion_with_params(
                provider,
                model,
                plan.audio_messages,
                **request_parameters,
                extra_parameters=extra_parameters,
                attachments=plan.audio_attachments,
                documents=documents,
            )
        response_text = completed["response"]
        if audio_text:
            response_text = f"{response_text}\n\nAudio transcription:\n{audio_text}"
        usage = {
            key: completed["usage"].get(key, 0) + audio_usage.get(key, 0)
            for key in ("prompt_tokens", "completion_tokens")
        }
        yield {
            "type": "complete",
            "response": response_text,
            "usage": usage,
            "transcript": completed["transcript"],
        }

    @staticmethod
    def result_payload(
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
