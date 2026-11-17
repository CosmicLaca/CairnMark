"""Provider catalog access and provider-configuration business rules."""

import base64
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import anthropic
import grpc
import httpx2
import openai
from google import genai
from google.genai import errors as google_errors
from google.genai import types as google_types
from mistralai.client import Mistral
from mistralai.client import errors as mistral_errors
from openrouter import OpenRouter
from openrouter.errors import NoResponseError, ResponseValidationError
from openrouter.errors.openroutererror import OpenRouterError
from xai_sdk import Client as XaiClient
from xai_sdk.chat import assistant as xai_assistant
from xai_sdk.chat import system as xai_system
from xai_sdk.chat import user as xai_user

from models.model_storage import (
    get_active_model_configurations,
    get_model_configuration_summary,
    get_provider_configuration,
    get_saved_model_configuration,
    save_model_list,
    save_provider_configuration,
    set_provider_enabled,
)
from models.parameter_storage import (
    delete_model_parameters,
    get_model_parameters,
    save_model_parameters,
)


class ProviderValidationError(ValueError):
    """Raised when provider input cannot form a valid configuration."""


class ProviderConflictError(ValueError):
    """Raised when provider state conflicts with its saved configuration."""


class ProviderOfflineError(ConnectionError):
    """Raised when a configured provider cannot currently be reached."""


class ProviderCatalogError(OSError):
    """Raised when a provider returns a safe, user-actionable HTTP failure."""


CATALOG_ERRORS = (
    OSError,
    ValueError,
)

GIB_BYTES = 1024 ** 3


def rounded_size_gb(size_bytes):
    """Round a byte count to the nearest whole gigabyte."""
    if not isinstance(size_bytes, (int, float)) or size_bytes <= 0:
        return None
    return int(size_bytes / GIB_BYTES + 0.5)


SDK_ERRORS = (
    anthropic.AnthropicError,
    google_errors.APIError,
    grpc.RpcError,
    httpx2.RequestError,
    mistral_errors.MistralError,
    NoResponseError,
    openai.OpenAIError,
    OpenRouterError,
    ResponseValidationError,
)


@dataclass(frozen=True)
class ProviderSpec:
    """Describe behavior that differs between supported providers."""

    name: str
    display_name: str
    fixed_endpoint: str | None = None
    fixed_port: int | None = None
    requires_api_key: bool = False
    local: bool = False
    single_live_model: bool = False
    catalog_endpoint: str | None = None
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer "
    catalog_headers: tuple[tuple[str, str], ...] = ()
    sdk_client: str | None = None
    rejected_api_key_prefixes: tuple[str, ...] = ()
    rejected_api_key_message: str | None = None
    extra_body_parameters: tuple[tuple[str, str], ...] = ()


PROVIDER_SPECS = {
    spec.name: spec
    for spec in (
        ProviderSpec(
            "llama.cpp",
            "llama.cpp",
            local=True,
            sdk_client="openai",
            extra_body_parameters=(
                ("top_k", "top_k"),
                ("min_p", "min_p"),
                ("repeat_penalty", "repeat_penalty"),
                ("repeat_last_n", "repeat_last_n"),
                ("dry_multiplier", "dry_multiplier"),
            ),
        ),
        ProviderSpec(
            "vllm",
            "vLLM",
            local=True,
            single_live_model=True,
            sdk_client="openai",
            extra_body_parameters=(
                ("top_k", "top_k"),
                ("min_p", "min_p"),
                ("repeat_penalty", "repetition_penalty"),
            ),
        ),
        ProviderSpec(
            "openrouter",
            "OpenRouter",
            fixed_endpoint="https://openrouter.ai/api/v1",
            fixed_port=443,
            requires_api_key=True,
            sdk_client="openrouter",
        ),
        ProviderSpec(
            "openai",
            "OpenAI",
            fixed_endpoint="https://api.openai.com/v1",
            fixed_port=443,
            requires_api_key=True,
            sdk_client="openai",
        ),
        ProviderSpec(
            "google",
            "Google Gemini",
            fixed_endpoint="https://generativelanguage.googleapis.com/v1beta",
            fixed_port=443,
            requires_api_key=True,
            api_key_header="x-goog-api-key",
            api_key_prefix="",
            sdk_client="google",
        ),
        ProviderSpec(
            "anthropic",
            "Anthropic",
            fixed_endpoint="https://api.anthropic.com",
            fixed_port=443,
            requires_api_key=True,
            api_key_header="x-api-key",
            api_key_prefix="",
            catalog_headers=(("anthropic-version", "2023-06-01"),),
            sdk_client="anthropic",
        ),
        ProviderSpec(
            "mistral",
            "Mistral",
            fixed_endpoint="https://api.mistral.ai/v1",
            fixed_port=443,
            requires_api_key=True,
            sdk_client="mistral",
        ),
        ProviderSpec(
            "deepseek",
            "DeepSeek",
            fixed_endpoint="https://api.deepseek.com/v1",
            fixed_port=443,
            requires_api_key=True,
            sdk_client="openai",
        ),
        ProviderSpec(
            "opencode",
            "OpenCode",
            fixed_endpoint="https://opencode.ai/inference/openai/v1",
            fixed_port=443,
            requires_api_key=True,
            catalog_endpoint="https://opencode.ai/inference/v1",
            catalog_headers=(("User-Agent", "Cairnmark/1.0"),),
            sdk_client="openai",
            extra_body_parameters=(("top_k", "top_k"),),
        ),
        ProviderSpec(
            "opencode-zen",
            "OpenCode-ZEN",
            fixed_endpoint="https://opencode.ai/zen/v1",
            fixed_port=443,
            requires_api_key=True,
            catalog_headers=(("User-Agent", "Cairnmark/1.0"),),
            sdk_client="openai",
            extra_body_parameters=(("top_k", "top_k"),),
        ),
        ProviderSpec(
            "zai",
            "Z.ai",
            fixed_endpoint="https://api.z.ai/api/paas/v4",
            fixed_port=443,
            requires_api_key=True,
            sdk_client="openai",
        ),
        ProviderSpec(
            "grok",
            "Grok",
            fixed_endpoint="https://api.x.ai/v1",
            fixed_port=443,
            requires_api_key=True,
            sdk_client="xai",
            rejected_api_key_prefixes=("gsk_",),
            rejected_api_key_message=(
                "Grok requires an xAI API key. Keys starting with gsk_ belong "
                "to Groq, which is a different provider."
            ),
        ),
    )
}

# Sampling fields reported by local providers that may be forwarded as request
# body overrides from the chat parameter modal.
LOCAL_MODEL_PARAMETER_KEYS = frozenset(
    {
        "dry_allowed_length",
        "dry_base",
        "dry_multiplier",
        "dry_penalty_last_n",
        "dynatemp_exponent",
        "dynatemp_range",
        "frequency_penalty",
        "ignore_eos",
        "max_tokens",
        "min_keep",
        "min_p",
        "mirostat",
        "mirostat_eta",
        "mirostat_tau",
        "n_discard",
        "n_keep",
        "n_predict",
        "presence_penalty",
        "repeat_last_n",
        "repeat_penalty",
        "stop",
        "top_n_sigma",
        "typical_p",
        "xtc_probability",
        "xtc_threshold",
    }
)


class ProviderSdkClient:
    """Use provider-supported Python clients for catalogs and generation."""

    def __init__(
        self,
        anthropic_factory=anthropic.Anthropic,
        google_factory=genai.Client,
        mistral_factory=Mistral,
        openai_factory=openai.OpenAI,
        openrouter_factory=OpenRouter,
        xai_factory=XaiClient,
    ):
        self.anthropic_factory = anthropic_factory
        self.google_factory = google_factory
        self.mistral_factory = mistral_factory
        self.openai_factory = openai_factory
        self.openrouter_factory = openrouter_factory
        self.xai_factory = xai_factory

    @staticmethod
    def _field_value(container, key):
        """Read a catalog field from either a mapping or an SDK object."""
        if container is None:
            return None
        if isinstance(container, dict):
            return container.get(key)
        return getattr(container, key, None)

    @staticmethod
    def _path_size_bytes(raw_path):
        """Return a local file's size, or a local directory's contents size."""
        if not raw_path:
            return None
        try:
            path = Path(str(raw_path))
            if path.is_file():
                return path.stat().st_size
            if path.is_dir():
                return sum(
                    item.stat().st_size
                    for item in path.rglob("*")
                    if item.is_file()
                )
        except OSError:
            return None
        return None

    @staticmethod
    def _argument_value(args, flags):
        """Return the value that follows one of ``flags`` in an argument list."""
        if not isinstance(args, (list, tuple)):
            return None
        tokens = [str(token) for token in args]
        for index, token in enumerate(tokens):
            for flag in flags:
                if token == flag:
                    if index + 1 < len(tokens):
                        return tokens[index + 1]
                elif token.startswith(f"{flag}="):
                    return token[len(flag) + 1:]
        return None

    @classmethod
    def _model_size_bytes(cls, spec, model):
        """Return a local model's weight size in bytes when it can be found.

        llama.cpp reports ``meta.size`` for a loaded model and only the launch
        arguments for the rest, so the ``--model`` file path is used as a
        fallback. vLLM reports the served ``root`` path instead. Both paths
        are measured only when they exist on this machine.
        """
        if not spec.local:
            return None
        meta = cls._field_value(model, "meta")
        reported = cls._field_value(meta, "size")
        if isinstance(reported, (int, float)) and reported > 0:
            return int(reported)
        status = cls._field_value(model, "status")
        model_path = cls._argument_value(
            cls._field_value(status, "args"),
            ("--model", "-m"),
        )
        for candidate in (
            cls._field_value(model, "root"),
            cls._field_value(model, "path"),
            model_path,
        ):
            size = cls._path_size_bytes(candidate)
            if size:
                return size
        return None

    @classmethod
    def _model_entry(cls, spec, model):
        model_id = str(getattr(model, "id", None) or getattr(model, "name", ""))
        display_name = str(
            getattr(model, "display_name", None)
            or getattr(model, "name", None)
            or model_id
        )
        entry = {"id": model_id, "name": display_name}
        size_gb = rounded_size_gb(cls._model_size_bytes(spec, model))
        if size_gb is not None:
            entry["size_gb"] = size_gb
        return entry

    @staticmethod
    def _deduplicate_entries(entries):
        """Collapse provider aliases that share one display name."""
        seen = set()
        unique = []
        for entry in entries:
            key = entry["name"] or entry["id"]
            if key in seen:
                continue
            seen.add(key)
            unique.append(entry)
        return unique

    @staticmethod
    def _error_status(error):
        status = getattr(error, "status_code", None) or getattr(error, "code", None)
        if callable(status):
            status = status()
        if isinstance(status, grpc.StatusCode):
            status = {
                grpc.StatusCode.UNAUTHENTICATED: 401,
                grpc.StatusCode.PERMISSION_DENIED: 403,
                grpc.StatusCode.RESOURCE_EXHAUSTED: 429,
                grpc.StatusCode.INVALID_ARGUMENT: 400,
            }.get(status, status.name)
        if status:
            return status
        name = type(error).__name__.lower()
        return 401 if "unauthorized" in name else None

    @staticmethod
    def _status_suffix(status):
        if not status:
            return ""
        label = f"HTTP {status}" if isinstance(status, int) else status
        return f" ({label})"

    @classmethod
    def _catalog_error(cls, spec, error):
        status = cls._error_status(error)
        body = getattr(error, "body", None)
        error_detail = body.get("error", {}) if isinstance(body, dict) else {}
        if (
            isinstance(error_detail, dict)
            and error_detail.get("code") == "api_key_expired"
        ):
            return ProviderCatalogError(
                f"{spec.display_name} API key has expired; create a new key"
            )
        if status == 401:
            return ProviderCatalogError(
                f"{spec.display_name} rejected the API key (HTTP 401)"
            )
        if status == 403:
            return ProviderCatalogError(
                f"{spec.display_name} denied the request (HTTP 403); check key "
                "permissions, billing, and model access"
            )
        if status == 429:
            return ProviderCatalogError(
                f"{spec.display_name} rate limit was reached (HTTP 429)"
            )
        if status == 400:
            return ProviderCatalogError(
                f"{spec.display_name} rejected the request (HTTP 400); check "
                "the API key type and request settings"
            )
        suffix = cls._status_suffix(status)
        return ProviderCatalogError(
            f"{spec.display_name} model catalog request failed{suffix}"
        )

    def fetch_catalog(self, spec, api_key, timeout, base_url):
        """Return normalized model entries through the configured SDK."""
        try:
            if spec.sdk_client == "anthropic":
                with self.anthropic_factory(
                    api_key=api_key,
                    timeout=timeout,
                ) as client:
                    models = client.models.list(limit=1000)
                    return [self._model_entry(spec, model) for model in models]
            if spec.sdk_client == "google":
                options = google_types.HttpOptions(
                    api_version="v1beta",
                    timeout=int(timeout * 1000),
                )
                with self.google_factory(
                    api_key=api_key,
                    http_options=options,
                ) as client:
                    entries = []
                    for model in client.models.list():
                        actions = getattr(model, "supported_actions", None) or ()
                        if "generateContent" not in actions:
                            continue
                        entries.append(self._model_entry(spec, model))
                    return entries
            if spec.sdk_client == "openrouter":
                with self.openrouter_factory(
                    api_key=api_key,
                    timeout_ms=int(timeout * 1000),
                ) as client:
                    response = client.models.list(limit=500)
                    models = response.result.data if response else []
                    return [self._model_entry(spec, model) for model in models]
            if spec.sdk_client == "mistral":
                with self.mistral_factory(
                    api_key=api_key,
                    timeout_ms=int(timeout * 1000),
                ) as client:
                    response = client.models.list()
                    models = getattr(response, "data", response) or []
                    return self._deduplicate_entries(
                        [self._model_entry(spec, model) for model in models]
                    )
            if spec.sdk_client == "xai":
                client = self.xai_factory(api_key=api_key, timeout=timeout)
                try:
                    models = client.models.list_language_models()
                    return [self._model_entry(spec, model) for model in models]
                finally:
                    client.close()
            if spec.sdk_client == "openai":
                with self.openai_factory(
                    api_key=api_key or "not-needed",
                    base_url=base_url,
                    timeout=timeout,
                    default_headers=dict(spec.catalog_headers) or None,
                ) as client:
                    return [
                        self._model_entry(spec, model)
                        for model in client.models.list()
                    ]
        except SDK_ERRORS as error:
            raise self._catalog_error(spec, error) from error
        raise ProviderValidationError("A valid provider SDK is required")

    @staticmethod
    def _system_and_messages(messages):
        system_text = next(
            (
                str(message.get("content", ""))
                for message in messages
                if message.get("role") == "system"
            ),
            "",
        )
        conversation = [
            message for message in messages if message.get("role") != "system"
        ]
        return system_text, conversation

    @staticmethod
    def _message_text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                str(
                    item.get("text", "")
                    if isinstance(item, dict)
                    else getattr(item, "text", "")
                )
                for item in content
            )
        return str(content or "")

    @staticmethod
    def _openai_messages_with_attachments(messages, attachments):
        media = [
            item for item in (attachments or [])
            if item.get("type") in ("image", "audio", "video")
        ]
        if not media:
            return messages
        converted = [dict(message) if isinstance(message, dict) else message for message in (messages or [])]
        last_user = None
        for index in range(len(converted) - 1, -1, -1):
            if isinstance(converted[index], dict) and converted[index].get("role") == "user":
                last_user = index
                break
        if last_user is None:
            converted.append({"role": "user", "content": ""})
            last_user = len(converted) - 1
        original = converted[last_user].get("content", "")
        if not isinstance(original, str):
            original = str(original or "")
        content = [{"type": "text", "text": original}]
        for item in media:
            attachment_type = item.get("type")
            if attachment_type == "image":
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{item['mime_type']};base64,{item['data']}"
                        },
                    }
                )
            elif attachment_type == "audio":
                content.append(
                    {
                        "type": "input_audio",
                        "input_audio": {"data": item["data"]},
                    }
                )
            elif attachment_type == "video":
                content.append(
                    {
                        "type": "input_video",
                        "input_video": {"data": item["data"]},
                    }
                )
        converted[last_user]["content"] = content
        return converted

    @staticmethod
    def _anthropic_messages_with_attachments(conversation, attachments):
        images = [item for item in (attachments or []) if item.get("type") == "image"]
        if not images:
            return conversation
        converted = [dict(message) if isinstance(message, dict) else message for message in (conversation or [])]
        last_user = None
        for index in range(len(converted) - 1, -1, -1):
            if isinstance(converted[index], dict) and converted[index].get("role") == "user":
                last_user = index
                break
        if last_user is None:
            converted.append({"role": "user", "content": ""})
            last_user = len(converted) - 1
        original = converted[last_user].get("content", "")
        blocks = []
        if isinstance(original, list):
            blocks.extend(original)
        elif isinstance(original, str) and original.strip():
            blocks.append({"type": "text", "text": original})
        for item in images:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": item["mime_type"],
                        "data": item["data"],
                    },
                }
            )
        converted[last_user]["content"] = blocks
        return converted

    @staticmethod
    def _provided_parameters(parameters, mapping):
        """Return only parameters explicitly supplied by the caller."""
        if not parameters:
            return {}
        return {
            target: parameters.get(source)
            for source, target in mapping.items()
            if parameters.get(source) is not None
        }

    @classmethod
    def _extra_body(cls, spec, parameters):
        return cls._provided_parameters(
            parameters, dict(spec.extra_body_parameters)
        )

    def _openai_completion(
        self, spec, api_key, model, messages, parameters, timeout, base_url,
        extra_body=None, attachments=None,
    ):
        kwargs = self._provided_parameters(
            parameters,
            {
                "temperature": "temperature",
                "top_p": "top_p",
                "max_tokens": "max_tokens",
            },
        )
        body_parameters = {
            **self._extra_body(spec, parameters),
            **(extra_body or {}),
        }
        if body_parameters:
            kwargs["extra_body"] = body_parameters
        if attachments:
            messages = self._openai_messages_with_attachments(messages, attachments)
        with self.openai_factory(
            api_key=api_key or "not-needed",
            base_url=base_url,
            timeout=timeout,
            default_headers=dict(spec.catalog_headers) or None,
        ) as client:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
        content = self._message_text(response.choices[0].message.content)
        usage = response.usage
        return content, {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": (
                getattr(usage, "completion_tokens", 0) if usage else 0
            ),
        }

    def _mistral_completion(
        self, api_key, model, messages, parameters, timeout, attachments=None
    ):
        kwargs = self._provided_parameters(
            parameters,
            {
                "temperature": "temperature",
                "top_p": "top_p",
                "top_k": "top_k",
                "max_tokens": "max_tokens",
            },
        )
        if attachments:
            messages = self._openai_messages_with_attachments(messages, attachments)
        with self.mistral_factory(
            api_key=api_key,
            timeout_ms=int(timeout * 1000),
        ) as client:
            response = client.chat.complete(
                model=model,
                messages=messages,
                **kwargs,
            )
        content = self._message_text(response.choices[0].message.content)
        usage = response.usage
        return content, {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": (
                getattr(usage, "completion_tokens", 0) if usage else 0
            ),
        }

    def _anthropic_completion(
        self, api_key, model, messages, parameters, timeout, attachments=None
    ):
        system_text, conversation = self._system_and_messages(messages)
        if attachments:
            conversation = self._anthropic_messages_with_attachments(conversation, attachments)
        kwargs = self._provided_parameters(
            parameters,
            {
                "temperature": "temperature",
                "top_p": "top_p",
            },
        )
        max_tokens = (
            parameters.get("max_tokens") if parameters else None
        )
        with self.anthropic_factory(
            api_key=api_key,
            timeout=timeout,
        ) as client:
            response = client.messages.create(
                model=model,
                max_tokens=8192 if max_tokens is None else max_tokens,
                system=system_text,
                messages=conversation,
                **kwargs,
            )
        content = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        return content, {
            "prompt_tokens": getattr(response.usage, "input_tokens", 0),
            "completion_tokens": getattr(response.usage, "output_tokens", 0),
        }

    def _google_completion(
        self, api_key, model, messages, parameters, timeout, attachments=None
    ):
        system_text, conversation = self._system_and_messages(messages)
        image_attachments = [
            item for item in (attachments or []) if item.get("type") == "image"
        ]
        contents = []
        for index, message in enumerate(conversation):
            is_last_user = (
                message.get("role") != "assistant"
                and index == len(conversation) - 1
            )
            parts = [
                google_types.Part.from_text(
                    text=str(message.get("content", ""))
                )
            ]
            if is_last_user:
                for item in (attachments or []):
                    if item.get("type") not in ("image", "audio", "video"):
                        continue
                    try:
                        parts.append(
                            google_types.Part.from_bytes(
                                data=base64.b64decode(item["data"], validate=True),
                                mime_type=item["mime_type"],
                            )
                        )
                    except Exception:  # noqa: BLE001
                        continue
            contents.append(
                google_types.Content(
                    role=(
                        "model" if message.get("role") == "assistant" else "user"
                    ),
                    parts=parts,
                )
            )
        config_data = {"system_instruction": system_text}
        config_data.update(
            self._provided_parameters(
                parameters,
                {
                    "temperature": "temperature",
                    "top_p": "top_p",
                    "top_k": "top_k",
                    "max_tokens": "max_output_tokens",
                },
            )
        )
        config = google_types.GenerateContentConfig(**config_data)
        options = google_types.HttpOptions(
            api_version="v1beta",
            timeout=int(timeout * 1000),
        )
        with self.google_factory(
            api_key=api_key,
            http_options=options,
        ) as client:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        usage = response.usage_metadata
        return str(response.text or ""), {
            "prompt_tokens": getattr(usage, "prompt_token_count", 0),
            "completion_tokens": getattr(usage, "candidates_token_count", 0),
        }

    def _openrouter_completion(
        self, api_key, model, messages, parameters, timeout, attachments=None
    ):
        kwargs = self._provided_parameters(
            parameters,
            {
                "temperature": "temperature",
                "top_p": "top_p",
                "top_k": "top_k",
                "max_tokens": "max_tokens",
            },
        )
        if attachments:
            messages = self._openai_messages_with_attachments(messages, attachments)
        with self.openrouter_factory(
            api_key=api_key,
            timeout_ms=int(timeout * 1000),
        ) as client:
            response = client.chat.send(
                model=model,
                messages=messages,
                stream=False,
                **kwargs,
            )
        content = self._message_text(response.choices[0].message.content)
        usage = response.usage
        return content, {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": (
                getattr(usage, "completion_tokens", 0) if usage else 0
            ),
        }

    def _xai_completion(
        self, api_key, model, messages, parameters, timeout, attachments=None
    ):
        factories = {
            "system": xai_system,
            "user": xai_user,
            "assistant": xai_assistant,
        }
        native_messages = [
            factories[message.get("role", "user")](
                str(message.get("content", ""))
            )
            for message in messages
            if message.get("role", "user") in factories
        ]
        kwargs = self._provided_parameters(
            parameters,
            {
                "temperature": "temperature",
                "top_p": "top_p",
                "max_tokens": "max_tokens",
            },
        )
        client = self.xai_factory(api_key=api_key, timeout=timeout)
        try:
            chat = client.chat.create(
                model=model,
                messages=native_messages,
                **kwargs,
            )
            response = chat.sample()
        finally:
            client.close()
        usage = response.usage
        return str(response.content or ""), {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
        }

    def chat_completion(
        self,
        spec,
        api_key,
        model,
        messages,
        base_url,
        parameters=None,
        timeout=300,
        extra_body=None,
        attachments=None,
    ):
        """Send messages through the provider SDK and normalize the result."""
        try:
            if spec.sdk_client == "openai":
                return self._openai_completion(
                    spec,
                    api_key,
                    model,
                    messages,
                    parameters,
                    timeout,
                    base_url,
                    extra_body=extra_body,
                    attachments=attachments,
                )
            if spec.sdk_client == "anthropic":
                return self._anthropic_completion(
                    api_key, model, messages, parameters, timeout, attachments=attachments
                )
            if spec.sdk_client == "google":
                return self._google_completion(
                    api_key, model, messages, parameters, timeout, attachments=attachments
                )
            if spec.sdk_client == "openrouter":
                return self._openrouter_completion(
                    api_key, model, messages, parameters, timeout, attachments=attachments
                )
            if spec.sdk_client == "mistral":
                return self._mistral_completion(
                    api_key, model, messages, parameters, timeout, attachments=attachments
                )
            if spec.sdk_client == "xai":
                return self._xai_completion(
                    api_key, model, messages, parameters, timeout, attachments=attachments
                )
        except SDK_ERRORS as error:
            status = self._error_status(error)
            suffix = self._status_suffix(status)
            raise ProviderValidationError(
                f"{spec.display_name} model request failed{suffix}"
            ) from error
        raise ProviderValidationError("A valid provider SDK is required")


class ProviderCatalogClient:
    """Read model catalogs through provider-supported Python clients."""

    def __init__(self, sdk_client=None):
        self.sdk_client = sdk_client or ProviderSdkClient()

    @staticmethod
    def models_url(server_address, port_value):
        """Validate an address and build its model-catalog URL."""
        if not server_address or not str(port_value):
            raise ProviderValidationError("Server address and port are required")
        port = int(port_value)
        if not 1 <= port <= 65535:
            raise ProviderValidationError("Port must be between 1 and 65535")

        if "://" not in server_address:
            server_address = f"http://{server_address}"
        parsed = urllib.parse.urlsplit(server_address)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ProviderValidationError("Use a valid HTTP or HTTPS server address")

        hostname = parsed.hostname
        if ":" in hostname:
            hostname = f"[{hostname}]"
        default_port = (parsed.scheme == "https" and port == 443) or (
            parsed.scheme == "http" and port == 80
        )
        authority = hostname if default_port else f"{hostname}:{port}"
        base_path = parsed.path.rstrip("/")
        models_path = f"{base_path}/models" if base_path else "/v1/models"
        return urllib.parse.urlunsplit((parsed.scheme, authority, models_path, "", ""))

    def fetch_catalog(
        self,
        server_address,
        port_value,
        timeout=5,
        api_key=None,
        provider=None,
        catalog_address=None,
    ):
        """Return normalized model entries reported by a provider SDK."""
        spec = PROVIDER_SPECS.get(provider)
        if not spec or not spec.sdk_client:
            raise ProviderValidationError("A valid provider SDK is required")
        models_url = self.models_url(
            catalog_address or server_address,
            port_value,
        )
        base_url = models_url[: -len("/models")]
        return self.sdk_client.fetch_catalog(
            spec,
            api_key,
            timeout,
            base_url,
        )

    @staticmethod
    def api_base_url(server_address, port_value):
        """Build the API root consumed by OpenAI-compatible SDK clients."""
        models_url = ProviderCatalogClient.models_url(server_address, port_value)
        return models_url[: -len("/models")]


class ModelProviderService:
    """Coordinate provider rules, catalog access, and SQLite persistence."""

    def __init__(self, catalog_client=None):
        self.catalog_client = catalog_client or ProviderCatalogClient()

    @staticmethod
    def spec(provider):
        """Return a supported provider definition."""
        try:
            return PROVIDER_SPECS[provider]
        except KeyError as error:
            raise ProviderValidationError("A valid provider is required") from error

    @staticmethod
    def provider_label(provider):
        """Return the user-facing label for a provider name."""
        spec = PROVIDER_SPECS.get(provider)
        return spec.display_name if spec else provider

    def resolve_online_model(self, model_spec):
        """Validate a provider/model selector and require live reachability."""
        value = str(model_spec or "").strip()
        if "::" not in value:
            raise ProviderValidationError("Model is required.")
        provider, model = value.split("::", 1)
        if not provider or not model:
            raise ProviderValidationError("Model is required.")
        self.spec(provider)
        if not self.is_online(provider):
            raise ProviderOfflineError("The selected model server is offline.")
        return provider, model

    @staticmethod
    def _selector_entry(provider, model_name, size_gb=None):
        """Build one active-model selector entry with its size marker."""
        spec = PROVIDER_SPECS.get(provider)
        display_name = spec.display_name if spec else provider
        label = f"{display_name}::{model_name}"
        if spec is not None and not spec.local:
            label = f"{label} (API)"
        elif size_gb is not None:
            label = f"{label} ({size_gb} GB)"
        return {
            "provider": provider,
            "provider_label": display_name,
            "model": model_name,
            "size_gb": size_gb,
            "label": label,
        }

    def active_models(self):
        """Return enabled provider models ready for selection.

        Saved model switches come from the database. Providers that report
        one live model (vLLM) contribute that model only while the provider
        is enabled and its server is reachable.
        """
        models = [
            self._selector_entry(
                configuration["provider"],
                configuration["model"],
                configuration.get("size_gb"),
            )
            for configuration in get_active_model_configurations()
        ]
        for provider, spec in PROVIDER_SPECS.items():
            if not spec.single_live_model:
                continue
            live_model = self._live_single_model(provider)
            if live_model:
                models.append(
                    self._selector_entry(
                        provider,
                        live_model["model"],
                        live_model.get("size_gb"),
                    )
                )
        return models

    def _live_single_model(self, provider):
        """Return the live model entry of an enabled single-model provider."""
        configuration = get_provider_configuration(provider)
        if not configuration or not configuration.get("enabled"):
            return None
        try:
            live_models = self._fetch_catalog(provider, configuration, timeout=2)
        except CATALOG_ERRORS:
            return None
        if len(live_models) != 1:
            return None
        entry = live_models[0]
        return {
            "model": self.model_name(entry),
            "size_gb": entry.get("size_gb") if isinstance(entry, dict) else None,
        }

    @staticmethod
    def model_name(model):
        """Return a stable display name from a provider response."""
        if isinstance(model, str):
            return model
        if isinstance(model, dict):
            return str(model.get("id") or model.get("name") or "Unknown model")
        return str(model)

    def connection(self, provider, data=None):
        """Resolve and validate a submitted or saved provider connection."""
        spec = self.spec(provider)
        data = data or {}
        saved = get_provider_configuration(provider)
        if spec.fixed_endpoint:
            submitted_key = str(data.get("api_key", "")).strip()
            api_key = submitted_key or (saved["api_key"] if saved else None)
            address = spec.fixed_endpoint
            port = spec.fixed_port
        else:
            address = str(data.get("ip", "")).strip()
            port = data.get("port", "")
            api_key = None

        if spec.requires_api_key and not api_key:
            raise ProviderValidationError(
                f"Enter a {spec.display_name} API key first"
            )
        normalized_key = str(api_key or "").lower()
        if any(
            normalized_key.startswith(prefix.lower())
            for prefix in spec.rejected_api_key_prefixes
        ):
            raise ProviderValidationError(spec.rejected_api_key_message)
        self.catalog_client.models_url(address, port)
        return {"ip": address, "port": int(port), "api_key": api_key}

    def saved_connection(self, provider):
        """Return saved credentials with the current provider endpoint metadata."""
        spec = self.spec(provider)
        configuration = get_provider_configuration(provider)
        if not configuration:
            return None
        if not spec.fixed_endpoint:
            return configuration
        return {
            **configuration,
            "ip": spec.fixed_endpoint,
            "port": spec.fixed_port,
        }

    def _fetch_catalog(self, provider, connection, timeout=5):
        """Fetch a catalog using the provider's discovery endpoint and headers."""
        spec = self.spec(provider)
        return self.catalog_client.fetch_catalog(
            connection["ip"],
            connection["port"],
            timeout=timeout,
            api_key=connection.get("api_key"),
            provider=provider,
            catalog_address=spec.catalog_endpoint,
        )

    def fetch_models(self, provider, data):
        """Read a live model catalog without changing saved data."""
        connection = self.connection(provider, data)
        return self._fetch_catalog(provider, connection)

    @staticmethod
    def _catalog_sizes(live_models):
        """Map discovered model names to their reported size in GB."""
        return {
            ModelProviderService.model_name(entry): entry["size_gb"]
            for entry in live_models
            if isinstance(entry, dict) and entry.get("size_gb") is not None
        }

    def _backfill_sizes(self, provider, live_models):
        """Persist sizes discovered from a live catalog for saved models.

        Rows saved before sizes were stored keep their enabled state; only a
        missing size is filled in, so no configuration re-save is required.
        """
        discovered = self._catalog_sizes(live_models)
        if not discovered:
            return
        saved = get_saved_model_configuration(provider)
        changed = False
        merged = []
        for model in saved:
            size_gb = discovered.get(model["name"])
            if size_gb is not None and size_gb != model.get("size_gb"):
                model = {**model, "size_gb": size_gb}
                changed = True
            merged.append(model)
        if changed:
            save_model_list(merged, provider)

    def _models_with_sizes(self, provider, connection, models, timeout=5):
        """Attach authoritative sizes to submitted models for a local provider.

        The catalog is read again so the stored size matches the served file.
        When the server is unreachable the previously saved sizes are reused.
        """
        sizes = {
            model["name"]: model["size_gb"]
            for model in get_saved_model_configuration(provider)
            if model.get("size_gb") is not None
        }
        try:
            live_models = self._fetch_catalog(provider, connection, timeout=timeout)
        except CATALOG_ERRORS:
            live_models = []
        sizes.update(self._catalog_sizes(live_models))
        return [
            {
                **model,
                "size_gb": sizes.get(
                    str(model.get("id") or model.get("name", ""))
                ),
            }
            for model in models
        ]

    def save_configuration(self, provider, data):
        """Validate and persist one provider configuration."""
        spec = self.spec(provider)
        models = data.get("models")
        if not isinstance(models, list):
            raise ProviderValidationError("Models must be a list")
        if any(not isinstance(model, dict) for model in models):
            raise ProviderValidationError("Every model must be an object")
        connection = self.connection(provider, data)

        live_models = None
        if spec.single_live_model or spec.requires_api_key:
            live_models = self._fetch_catalog(provider, connection)

        model_name = None
        if spec.single_live_model:
            if len(live_models) != 1:
                raise ProviderValidationError(
                    "vLLM must report exactly one loaded model"
                )
            model_name = self.model_name(live_models[0])
            save_model_list([], provider)
            summary = {"total": 1, "enabled": 1}
        else:
            if not models:
                raise ProviderValidationError("Read and select models first")
            if spec.local:
                models = self._models_with_sizes(provider, connection, models)
            else:
                models = [{**model, "size_gb": None} for model in models]
            save_model_list(models, provider)
            summary = get_model_configuration_summary(provider)

        save_provider_configuration(
            provider,
            connection["ip"],
            connection["port"],
            api_key=connection["api_key"],
        )
        configuration = self.saved_connection(provider)
        return {
            "message": "Model configuration saved successfully",
            "models_count": summary["total"],
            "enabled_count": summary["enabled"],
            "model_name": model_name,
            "provider_enabled": configuration["enabled"],
            "provider": provider,
        }

    def load_configuration(self, provider):
        """Return browser-safe saved state for one provider."""
        spec = PROVIDER_SPECS.get(provider)
        configuration = get_provider_configuration(provider)
        models = (
            []
            if spec is not None and spec.single_live_model
            else get_saved_model_configuration(provider)
        )
        if (
            spec is not None
            and spec.local
            and configuration
            and any(model.get("size_gb") is None for model in models)
        ):
            merged = self._models_with_sizes(
                provider,
                configuration,
                models,
                timeout=10,
            )
            if any(
                updated.get("size_gb") != saved.get("size_gb")
                for updated, saved in zip(merged, models)
            ):
                save_model_list(merged, provider)
            models = merged
        if provider == "llama.cpp":
            models = self._attach_saved_modalities(models)
        summary = get_model_configuration_summary(provider)
        return {
            "models": models,
            "models_count": summary["total"],
            "enabled_count": summary["enabled"],
            "ip": configuration["ip"] if configuration else None,
            "port": configuration["port"] if configuration else None,
            "provider_enabled": (configuration["enabled"] if configuration else False),
            "has_api_key": bool(configuration and configuration.get("api_key")),
            "provider": provider,
        }

    @staticmethod
    def check_props_available(provider):
        """Quickly check whether a local provider exposes the props endpoint."""
        if provider not in ("llama.cpp", "vllm"):
            return False
        configuration = get_provider_configuration(provider)
        if not configuration:
            return False
        ip = (configuration.get("ip") or "").rstrip("/")
        port = configuration.get("port")
        if not ip or not port:
            return False
        url = f"{ip}:{port}/props"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status == 200
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def fetch_model_params(provider, model):
        """Return cached defaults, otherwise read them from the local model."""
        if provider not in ("llama.cpp", "vllm"):
            raise ProviderValidationError(
                "Additional parameters are only available for local providers"
            )
        parameter_key = f"{provider}::{model}"
        saved_params = get_model_parameters(parameter_key)
        if saved_params is not None and ModelProviderService._display_n_ctx(
            saved_params
        ) is not None:
            return {
                "params": ModelProviderService._display_params(saved_params),
                "modalities": ModelProviderService._display_field(saved_params, "modalities"),
                "n_ctx": ModelProviderService._display_n_ctx(saved_params),
                "source": "database",
            }

        configuration = get_provider_configuration(provider)
        if not configuration:
            raise ProviderValidationError("Provider is not configured")
        ip = (configuration.get("ip") or "").rstrip("/")
        port = configuration.get("port")
        if not ip or not port:
            raise ProviderValidationError("Provider connection is incomplete")
        url = (
            f"{ip}:{port}/props?model="
            f"{urllib.parse.quote(str(model), safe='')}"
        )
        try:
            with urllib.request.urlopen(url) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:  # noqa: BLE001
            if saved_params is not None:
                return {
                    "params": ModelProviderService._display_params(saved_params),
                    "modalities": ModelProviderService._display_field(saved_params, "modalities"),
                    "n_ctx": ModelProviderService._display_n_ctx(saved_params),
                    "source": "database",
                }
            raise ProviderCatalogError(
                "Could not read model parameters"
            ) from error

        # Default generation settings (existing behaviour).
        settings = payload.get("default_generation_settings") or {}
        params = settings.get("params") if isinstance(settings, dict) else None

        # New capability fields.
        modalities = payload.get("modalities") if isinstance(payload, dict) else None
        chat_template_caps = payload.get("chat_template_caps") if isinstance(payload, dict) else None
        n_ctx = None
        if isinstance(settings, dict):
            n_ctx = settings.get("n_ctx")
        if n_ctx is None and isinstance(payload, dict):
            n_ctx = payload.get("n_ctx")

        # Store everything together so callers can read any subset.
        full = {}
        if params is not None:
            full["params"] = params
        if modalities is not None:
            full["modalities"] = modalities
        if chat_template_caps is not None:
            full["chat_template_caps"] = chat_template_caps
        if n_ctx is not None:
            full["n_ctx"] = n_ctx

        if not full:
            raise ProviderCatalogError("Unexpected parameter response")

        save_model_parameters(parameter_key, full)
        return {
            "params": params if isinstance(params, dict) else {},
            "modalities": modalities if isinstance(modalities, dict) else {},
            "n_ctx": n_ctx,
            "source": "provider",
        }

    @staticmethod
    def _display_params(saved_params):
        """Return only the generation parameters for the modal.

        The stored payload may wrap generation params under ``params``
        together with ``modalities`` and ``chat_template_caps``, or it may
        be an older flat parameters object. Only ``params`` is shown in the
        modal; ``modalities`` and ``chat_template_caps`` stay in the DB.
        """
        if isinstance(saved_params, dict):
            params = saved_params.get("params")
            if isinstance(params, dict):
                return params
        return saved_params if isinstance(saved_params, dict) else {}

    @staticmethod
    def _display_field(saved_params, field):
        """Return one nested capability field (modalities, chat_template_caps)."""
        if isinstance(saved_params, dict) and isinstance(saved_params.get(field), dict):
            return saved_params[field]
        return {}

    @staticmethod
    def _display_n_ctx(saved_params):
        """Return the saved context size, if present."""
        if isinstance(saved_params, dict):
            value = saved_params.get("n_ctx")
            if isinstance(value, bool):
                return None
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.strip():
                try:
                    return int(float(value.strip()))
                except ValueError:
                    return None
        return None

    @staticmethod
    def _attach_saved_modalities(models):
        """Attach locally saved modality flags to each model, if any.

        Reads only the parameter database; the provider server is never
        contacted. Models without saved modalities are left untouched.
        """
        updated = []
        for model in models:
            entry = dict(model)
            model_name = entry.get("id") or entry.get("name")
            if model_name:
                saved = get_model_parameters(f"llama.cpp::{model_name}")
                modalities = (
                    ModelProviderService._display_field(saved, "modalities")
                    if saved else {}
                )
                if modalities:
                    entry["modalities"] = modalities
            updated.append(entry)
        return updated

    @staticmethod
    def delete_model_params(provider, model):
        """Remove cached defaults for one local provider model."""
        if provider not in ("llama.cpp", "vllm"):
            raise ProviderValidationError(
                "Additional parameters are only available for local providers"
            )
        return delete_model_parameters(f"{provider}::{model}")

    def status(self, provider):
        """Return live reachability and persisted state for one provider."""
        spec = self.spec(provider)
        configuration = get_provider_configuration(provider)
        summary = get_model_configuration_summary(provider)
        if not configuration:
            return {
                "provider": provider,
                "configured": False,
                "online": False,
                "enabled": False,
                "can_enable": False,
                "models_count": summary["total"],
                "enabled_count": summary["enabled"],
                "model_name": None,
                "size_gb": None,
            }

        try:
            live_models = self._fetch_catalog(
                provider,
                configuration,
                timeout=8 if spec.local else 2,
            )
            online = True
        except CATALOG_ERRORS:
            live_models = []
            online = False

        model_name = None
        size_gb = None
        if spec.single_live_model:
            can_enable = online and len(live_models) == 1
            if can_enable:
                entry = live_models[0]
                model_name = self.model_name(entry)
                size_gb = (
                    entry.get("size_gb") if isinstance(entry, dict) else None
                )
            models_count = 1 if can_enable else 0
            enabled_count = 1 if can_enable else 0
        else:
            if online and spec.local:
                self._backfill_sizes(provider, live_models)
            can_enable = online and summary["total"] > 0
            models_count = summary["total"]
            enabled_count = summary["enabled"]

        enabled = configuration["enabled"] and can_enable
        if configuration["enabled"] and not can_enable:
            set_provider_enabled(provider, False)

        return {
            "provider": provider,
            "configured": True,
            "online": online,
            "enabled": enabled,
            "can_enable": can_enable,
            "models_count": models_count,
            "enabled_count": enabled_count,
            "model_name": model_name,
            "size_gb": size_gb,
        }

    def is_online(self, provider):
        """Return whether a configured provider endpoint is reachable."""
        configuration = self.saved_connection(provider)
        if not configuration:
            return False
        try:
            self._fetch_catalog(provider, configuration, timeout=2)
            return True
        except CATALOG_ERRORS:
            return False

    def _completion_context(self, provider):
        """Return SDK inputs shared by all completion entry points."""
        configuration = self.saved_connection(provider)
        if not configuration:
            raise ProviderValidationError("Provider is not configured")
        base_url = self.catalog_client.api_base_url(
            configuration["ip"], configuration["port"]
        )
        return self.spec(provider), configuration, base_url

    @staticmethod
    def _stateless_prompt_messages(system_prompt, user_prompt):
        """Build a fresh system/user pair for benchmark generation and runs.

        Benchmark work is request-scoped: prior user requests and assistant
        answers must never be appended here, so every call starts clean.
        """
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def chat_completion(self, provider, model, system_prompt, user_prompt, timeout=300):
        """Send a chat completion request and return the assistant text."""
        spec, configuration, base_url = self._completion_context(provider)
        messages = self._stateless_prompt_messages(system_prompt, user_prompt)
        content, _usage = self.catalog_client.sdk_client.chat_completion(
            spec,
            configuration.get("api_key"),
            model,
            messages,
            base_url,
            timeout=timeout,
        )
        return content

    def chat_completion_stream(
        self, provider, model, system_prompt, user_prompt, timeout=300
    ):
        """Yield assistant text chunks while the provider writes the reply."""
        messages = self._stateless_prompt_messages(system_prompt, user_prompt)
        yield from self.chat_completion_with_params_stream(
            provider,
            model,
            messages,
            None,
            None,
            None,
            timeout=timeout,
        )

    @staticmethod
    def _sampling_parameters(
        temperature,
        top_p,
        top_k,
        max_tokens,
        min_p=None,
        repeat_penalty=None,
        repeat_last_n=None,
        dry_multiplier=None,
        seed=None,
    ):
        parameters = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_tokens": max_tokens,
            "min_p": min_p,
            "repeat_penalty": repeat_penalty,
            "repeat_last_n": repeat_last_n,
            "dry_multiplier": dry_multiplier,
            "seed": seed,
        }
        return {
            key: value for key, value in parameters.items() if value is not None
        }

    @staticmethod
    def local_extra_parameters(provider, extra_parameters):
        """Return supported local sampling overrides mapped to request keys."""
        if provider not in ("llama.cpp", "vllm") or not extra_parameters:
            return {}
        spec = PROVIDER_SPECS[provider]
        mapping = dict(spec.extra_body_parameters)
        return {
            mapping.get(key, key): value
            for key, value in extra_parameters.items()
            if key in LOCAL_MODEL_PARAMETER_KEYS and value is not None
        }

    def chat_completion_with_params(
        self, provider, model, messages, temperature, top_p, top_k, max_tokens=None,
        min_p=None, repeat_penalty=None, repeat_last_n=None,
        dry_multiplier=None, seed=None, timeout=300, extra_parameters=None,
        attachments=None,
    ):
        """Send a chat history with provider-specific parameter handling."""
        spec, configuration, base_url = self._completion_context(provider)
        parameters = self._sampling_parameters(
            temperature,
            top_p,
            top_k,
            max_tokens,
            min_p=min_p,
            repeat_penalty=repeat_penalty,
            repeat_last_n=repeat_last_n,
            dry_multiplier=dry_multiplier,
            seed=seed,
        )
        return self.catalog_client.sdk_client.chat_completion(
            spec,
            configuration.get("api_key"),
            model,
            messages,
            base_url,
            parameters=parameters,
            timeout=timeout,
            extra_body=self.local_extra_parameters(provider, extra_parameters),
            attachments=attachments,
        )

    def chat_completion_with_params_stream(
        self, provider, model, messages, temperature, top_p, top_k, max_tokens=None,
        min_p=None, repeat_penalty=None, repeat_last_n=None,
        dry_multiplier=None, seed=None, timeout=300, extra_parameters=None,
        attachments=None,
    ):
        """Yield chat response chunks as they are produced by the provider."""
        spec, configuration, base_url = self._completion_context(provider)
        extra_body = self.local_extra_parameters(provider, extra_parameters)
        parameters = self._sampling_parameters(
            temperature,
            top_p,
            top_k,
            max_tokens,
            min_p=min_p,
            repeat_penalty=repeat_penalty,
            repeat_last_n=repeat_last_n,
            dry_multiplier=dry_multiplier,
            seed=seed,
        )
        api_key = configuration.get("api_key")
        system_text, conversation = self.catalog_client.sdk_client._system_and_messages(
            messages
        )
        accumulated = ""

        def finish(usage, fallback=False):
            if not usage:
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
            if not usage.get("completion_tokens") and accumulated:
                usage = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": max(1, len(accumulated) // 4),
                }
            return usage

        # OpenAI-compatible providers.
        if spec.sdk_client == "openai":
            if attachments:
                messages = self.catalog_client.sdk_client._openai_messages_with_attachments(
                    messages, attachments
                )
            kwargs = self.catalog_client.sdk_client._provided_parameters(
                parameters,
                {
                    "temperature": "temperature",
                    "top_p": "top_p",
                    "max_tokens": "max_tokens",
                },
            )
            body_parameters = {
                **self.catalog_client.sdk_client._extra_body(spec, parameters),
                **extra_body,
            }
            if body_parameters:
                kwargs["extra_body"] = body_parameters
            factory = self.catalog_client.sdk_client.openai_factory
            try:
                with factory(
                    api_key=api_key or "not-needed",
                    base_url=base_url,
                    timeout=timeout,
                    default_headers=dict(spec.catalog_headers) or None,
                ) as client:
                    usage = {"prompt_tokens": 0, "completion_tokens": 0}
                    stream = None
                    try:
                        stream = client.chat.completions.create(
                            model=model,
                            messages=messages,
                            stream=True,
                            stream_options={"include_usage": True},
                            **kwargs,
                        )
                    except Exception:  # noqa: BLE001
                        stream = client.chat.completions.create(
                            model=model,
                            messages=messages,
                            stream=True,
                            **kwargs,
                        )
                    for chunk in stream:
                        choices = getattr(chunk, "choices", None) or []
                        if choices:
                            delta = getattr(
                                choices[0].delta, "content", None
                            )
                            if delta:
                                accumulated += delta
                                yield {"type": "chunk", "text": delta}
                        chunk_usage = getattr(chunk, "usage", None)
                        if chunk_usage is not None:
                            usage = {
                                "prompt_tokens": getattr(
                                    chunk_usage, "prompt_tokens", 0
                                ),
                                "completion_tokens": getattr(
                                    chunk_usage, "completion_tokens", 0
                                ),
                            }
                    yield {"type": "done", "usage": finish(usage)}
                    return
            except Exception:  # noqa: BLE001
                pass

        # Anthropic.
        if spec.sdk_client == "anthropic":
            try:
                kwargs = self.catalog_client.sdk_client._provided_parameters(
                    parameters,
                    {
                        "temperature": "temperature",
                        "top_p": "top_p",
                    },
                )
                max_tokens = (
                    parameters.get("max_tokens") if parameters else None
                )
                with self.catalog_client.sdk_client.anthropic_factory(
                    api_key=api_key,
                    timeout=timeout,
                ) as client:
                    usage = {"prompt_tokens": 0, "completion_tokens": 0}
                    stream_conversation = conversation
                    if attachments:
                        stream_conversation = (
                            self.catalog_client.sdk_client._anthropic_messages_with_attachments(
                                conversation, attachments
                            )
                        )
                    with client.messages.stream(
                        model=model,
                        max_tokens=8192 if max_tokens is None else max_tokens,
                        system=system_text,
                        messages=stream_conversation,
                        **kwargs,
                    ) as stream:
                        for text in stream.text_stream:
                            if text:
                                accumulated += text
                                yield {"type": "chunk", "text": text}
                        final = stream.get_final_message()
                        usage = {
                            "prompt_tokens": getattr(
                                getattr(final, "usage", None),
                                "input_tokens",
                                0,
                            ),
                            "completion_tokens": getattr(
                                getattr(final, "usage", None),
                                "output_tokens",
                                0,
                            ),
                        }
                    yield {"type": "done", "usage": finish(usage)}
                    return
            except Exception:  # noqa: BLE001
                pass

        # Google Gemini.
        if spec.sdk_client == "google":
            try:
                config_data = {"system_instruction": system_text}
                config_data.update(
                    self.catalog_client.sdk_client._provided_parameters(
                        parameters,
                        {
                            "temperature": "temperature",
                            "top_p": "top_p",
                            "top_k": "top_k",
                            "max_tokens": "max_output_tokens",
                        },
                    )
                )
                config = google_types.GenerateContentConfig(**config_data)
                options = google_types.HttpOptions(
                    api_version="v1beta",
                    timeout=int(timeout * 1000),
                )
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
                with self.catalog_client.sdk_client.google_factory(
                    api_key=api_key,
                    http_options=options,
                ) as client:
                    for chunk in client.models.generate_content_stream(
                        model=model,
                        contents=[
                            google_types.Content(
                                role=(
                                    "model"
                                    if m.get("role") == "assistant"
                                    else "user"
                                ),
                                parts=(
                                    [google_types.Part.from_text(text=str(m.get("content", "")))]
                                    + (
                                        [
                                            google_types.Part.from_bytes(
                                                data=base64.b64decode(
                                                    item["data"], validate=True
                                                ),
                                                mime_type=item["mime_type"],
                                            )
                                            for item in (attachments or [])
                                            if item.get("type") in ("image", "audio", "video")
                                            and m.get("role") != "assistant"
                                            and m is conversation[-1]
                                        ]
                                    )
                                ),
                            )
                            for m in conversation
                        ],
                        config=config,
                    ):
                        text = getattr(chunk, "text", None)
                        if text:
                            accumulated += text
                            yield {"type": "chunk", "text": text}
                        usage_meta = getattr(chunk, "usage_metadata", None)
                        if usage_meta is not None:
                            usage = {
                                "prompt_tokens": getattr(
                                    usage_meta, "prompt_token_count", 0
                                ),
                                "completion_tokens": getattr(
                                    usage_meta, "candidates_token_count", 0
                                ),
                            }
                yield {"type": "done", "usage": finish(usage)}
                return
            except Exception:  # noqa: BLE001
                pass

        # Mistral.
        if spec.sdk_client == "mistral":
            try:
                kwargs = self.catalog_client.sdk_client._provided_parameters(
                    parameters,
                    {
                        "temperature": "temperature",
                        "top_p": "top_p",
                        "top_k": "top_k",
                        "max_tokens": "max_tokens",
                    },
                )
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
                if attachments:
                    messages = self.catalog_client.sdk_client._openai_messages_with_attachments(
                        messages, attachments
                    )
                with self.catalog_client.sdk_client.mistral_factory(
                    api_key=api_key,
                    timeout_ms=int(timeout * 1000),
                ) as client:
                    for chunk in client.chat.stream(
                        model=model,
                        messages=messages,
                        **kwargs,
                    ):
                        data = getattr(chunk, "data", chunk)
                        choices = getattr(data, "choices", None) or []
                        if choices:
                            delta = getattr(
                                getattr(choices[0], "delta", None),
                                "content",
                                None,
                            )
                            if delta:
                                accumulated += delta
                                yield {"type": "chunk", "text": delta}
                        chunk_usage = getattr(data, "usage", None)
                        if chunk_usage is not None:
                            usage = {
                                "prompt_tokens": getattr(
                                    chunk_usage, "prompt_tokens", 0
                                ),
                                "completion_tokens": getattr(
                                    chunk_usage, "completion_tokens", 0
                                ),
                            }
                yield {"type": "done", "usage": finish(usage)}
                return
            except Exception:  # noqa: BLE001
                pass

        # OpenRouter.
        if spec.sdk_client == "openrouter":
            try:
                kwargs = self.catalog_client.sdk_client._provided_parameters(
                    parameters,
                    {
                        "temperature": "temperature",
                        "top_p": "top_p",
                        "top_k": "top_k",
                        "max_tokens": "max_tokens",
                    },
                )
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
                if attachments:
                    messages = self.catalog_client.sdk_client._openai_messages_with_attachments(
                        messages, attachments
                    )
                with self.catalog_client.sdk_client.openrouter_factory(
                    api_key=api_key,
                    timeout_ms=int(timeout * 1000),
                ) as client:
                    response = client.chat.send(
                        model=model,
                        messages=messages,
                        stream=True,
                        **kwargs,
                    )
                    for chunk in response:
                        choices = getattr(chunk, "choices", None) or []
                        if choices:
                            delta = getattr(
                                getattr(choices[0], "delta", None),
                                "content",
                                None,
                            )
                            if delta:
                                accumulated += delta
                                yield {"type": "chunk", "text": delta}
                        chunk_usage = getattr(chunk, "usage", None)
                        if chunk_usage is not None:
                            usage = {
                                "prompt_tokens": getattr(
                                    chunk_usage, "prompt_tokens", 0
                                ),
                                "completion_tokens": getattr(
                                    chunk_usage, "completion_tokens", 0
                                ),
                            }
                yield {"type": "done", "usage": finish(usage)}
                return
            except Exception:  # noqa: BLE001
                pass

        # xAI Grok.
        if spec.sdk_client == "xai":
            try:
                factories = {
                    "system": xai_system,
                    "user": xai_user,
                    "assistant": xai_assistant,
                }
                native_messages = [
                    factories[m.get("role", "user")](str(m.get("content", "")))
                    for m in messages
                    if m.get("role", "user") in factories
                ]
                kwargs = self.catalog_client.sdk_client._provided_parameters(
                    parameters,
                    {
                        "temperature": "temperature",
                        "top_p": "top_p",
                        "max_tokens": "max_tokens",
                    },
                )
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
                client = self.catalog_client.sdk_client.xai_factory(
                    api_key=api_key, timeout=timeout
                )
                try:
                    chat = client.chat.create(
                        model=model,
                        messages=native_messages,
                        **kwargs,
                    )
                    for response, chunk in chat.stream():
                        text = getattr(chunk, "content", None)
                        if text:
                            accumulated += text
                            yield {"type": "chunk", "text": text}
                        if getattr(response, "usage", None) is not None:
                            usage = {
                                "prompt_tokens": getattr(
                                    response.usage, "prompt_tokens", 0
                                ),
                                "completion_tokens": getattr(
                                    response.usage, "completion_tokens", 0
                                ),
                            }
                finally:
                    client.close()
                yield {"type": "done", "usage": finish(usage)}
                return
            except Exception:  # noqa: BLE001
                pass

        # Fallback to the non-streaming implementation.
        content, usage = self.catalog_client.sdk_client.chat_completion(
            spec,
            api_key,
            model,
            messages,
            base_url,
            parameters=parameters,
            timeout=timeout,
        )
        if content:
            accumulated = content
            yield {"type": "chunk", "text": content}
        yield {"type": "done", "usage": finish(usage or {})}

    def update_state(self, provider, enabled):
        """Persist an enabled state after validating live availability."""
        spec = self.spec(provider)
        if not isinstance(enabled, bool):
            raise ProviderValidationError("Valid provider state is required")
        configuration = self.saved_connection(provider)
        if not configuration:
            raise ProviderConflictError("Set up and save this provider first")

        if enabled:
            try:
                live_models = self._fetch_catalog(provider, configuration, timeout=2)
            except CATALOG_ERRORS as error:
                set_provider_enabled(provider, False)
                raise ProviderConflictError("Provider server is offline") from error

            summary = get_model_configuration_summary(provider)
            valid_models = (
                len(live_models) == 1
                if spec.single_live_model
                else summary["total"] > 0
            )
            if not valid_models:
                set_provider_enabled(provider, False)
                raise ProviderConflictError("Save a valid model configuration first")

        set_provider_enabled(provider, enabled)
        return {"provider": provider, "enabled": enabled}
