"""Provider catalog access and provider-configuration business rules."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

# (No process-wide cache: the browser caches the mode for one page load.)
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

from models.model_storage import MODEL_CONFIGURATIONS
from models.parameter_storage import MODEL_PARAMETERS


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
UUID_MODEL_PREFIX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}:(.+)$"
)


def rounded_size_gb(size_bytes):
    """Round a byte count to the nearest whole gigabyte."""
    if not isinstance(size_bytes, (int, float)) or size_bytes <= 0:
        return None
    return int(size_bytes / GIB_BYTES + 0.5)


def model_display_name(spec, model_id, reported_name=None):
    """Return a friendly custom-model label without changing its request ID."""
    match = UUID_MODEL_PREFIX.fullmatch(str(model_id))
    if spec.name.startswith("custom:") and match:
        provider_name = re.sub(r"\s+", "", spec.display_name)
        return f"{provider_name}:{match.group(1)}"
    return str(reported_name or model_id)


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
    supports_api_key: bool = False
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

CUSTOM_PROVIDER_SENTINEL = "__custom__"

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
        reported_name = str(
            getattr(model, "display_name", None)
            or getattr(model, "name", None)
            or model_id
        )
        display_name = model_display_name(spec, model_id, reported_name)
        entry = {"id": model_id, "name": display_name}
        size_gb = rounded_size_gb(cls._model_size_bytes(spec, model))
        if size_gb is not None:
            entry["size_gb"] = size_gb
        return entry

    @staticmethod
    def _google_model_name(model):
        """Return the model name expected by Google generation methods."""
        model_name = str(model or "").strip()
        if model_name.startswith("models/"):
            return model_name.removeprefix("models/")
        return model_name

    @classmethod
    def _google_interaction_request(cls, messages, parameters, attachments=None):
        """Build Interactions API input while preserving the chat transcript."""
        system_text, conversation = cls._system_and_messages(messages)
        input_steps = []
        for index, message in enumerate(conversation):
            is_assistant = message.get("role") == "assistant"
            content = [
                {
                    "type": "text",
                    "text": str(message.get("content", "")),
                }
            ]
            if not is_assistant and index == len(conversation) - 1:
                for item in attachments or []:
                    media_type = item.get("type")
                    if media_type not in ("image", "audio", "video"):
                        continue
                    content.append(
                        {
                            "type": media_type,
                            "data": item.get("data", ""),
                            "mime_type": item.get("mime_type", ""),
                        }
                    )
            input_steps.append(
                {
                    "type": "model_output" if is_assistant else "user_input",
                    "content": content,
                }
            )

        generation_config = cls._provided_parameters(
            parameters,
            {
                "temperature": "temperature",
                "top_p": "top_p",
                "max_tokens": "max_output_tokens",
            },
        )
        seed = parameters.get("seed") if parameters else None
        if seed is not None:
            seed = int(seed)
            generation_config["seed"] = (
                (seed + (2 ** 31)) % (2 ** 32)
            ) - (2 ** 31)
        return system_text, input_steps, generation_config

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
                        entry = self._model_entry(spec, model)
                        entry["id"] = self._google_model_name(entry["id"])
                        entries.append(entry)
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
        documents = [
            item for item in (attachments or [])
            if item.get("type") == "document"
        ]
        if not media and not documents:
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
        for item in documents:
            filename = item.get("original_name") or item.get("filename") or "document"
            content.append(
                {
                    "type": "text",
                    "text": f"Document: {filename}\n{item.get('data', '')}",
                }
            )
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
        extra_body=None, attachments=None, documents=None,
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
        combined_attachments = list(attachments or [])
        for document in (documents or []):
            combined_attachments.append(
                {
                    "type": "document",
                    "data": document.get("content", ""),
                    "mime_type": document.get("mime_type", "text/plain"),
                    "original_name": document.get("filename", "document"),
                }
            )
        if combined_attachments:
            messages = self._openai_messages_with_attachments(
                messages, combined_attachments
            )
        if body_parameters:
            kwargs["extra_body"] = body_parameters
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
        system_text, input_steps, generation_config = (
            self._google_interaction_request(messages, parameters, attachments)
        )
        model = self._google_model_name(model)
        options = google_types.HttpOptions(
            api_version="v1beta",
            timeout=int(timeout * 1000),
        )
        kwargs = {
            "model": model,
            "input": input_steps,
            "generation_config": generation_config,
            "store": False,
        }
        if system_text:
            kwargs["system_instruction"] = system_text
        with self.google_factory(
            api_key=api_key,
            http_options=options,
        ) as client:
            response = client.interactions.create(**kwargs)
        usage = getattr(response, "usage", None)
        return str(getattr(response, "output_text", "") or ""), {
            "prompt_tokens": getattr(usage, "total_input_tokens", 0),
            "completion_tokens": getattr(usage, "total_output_tokens", 0),
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
        documents=None,
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
                    documents=documents,
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
        provider_spec=None,
    ):
        """Return normalized model entries reported by a provider SDK."""
        spec = provider_spec or PROVIDER_SPECS.get(provider)
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

    def __init__(
        self,
        catalog_client=None,
        model_repository=None,
        parameter_repository=None,
    ):
        self.catalog_client = catalog_client or ProviderCatalogClient()
        self.models = model_repository or MODEL_CONFIGURATIONS
        self.parameters = parameter_repository or MODEL_PARAMETERS

    def spec(self, provider):
        """Return a supported provider definition."""
        declared = PROVIDER_SPECS.get(provider)
        if declared is not None:
            return declared
        configuration = self.models.provider(provider)
        if configuration and configuration.get("custom"):
            return self._custom_provider_spec(
                provider,
                configuration["display_name"],
            )
        raise ProviderValidationError("A valid provider is required")

    def provider_label(self, provider):
        """Return the user-facing label for a provider name."""
        try:
            return self.spec(provider).display_name
        except ProviderValidationError:
            return provider

    @staticmethod
    def _custom_provider_spec(provider, display_name):
        """Build OpenAI-compatible rules for one saved custom provider."""
        return ProviderSpec(
            provider,
            display_name,
            supports_api_key=True,
            local=True,
            sdk_client="openai",
        )

    def _custom_provider_identity(self, raw_name):
        """Validate a new custom name and return its stable storage key."""
        display_name = " ".join(str(raw_name or "").split())
        if not display_name or len(display_name) > 80:
            raise ProviderValidationError(
                "Provider name is required and must be 80 characters or fewer"
            )
        reserved_names = {
            value.casefold()
            for spec in PROVIDER_SPECS.values()
            for value in (spec.name, spec.display_name)
        }
        if display_name.casefold() in reserved_names:
            raise ProviderValidationError(
                "Choose a provider name that is not already built in"
            )
        slug = re.sub(r"[^\w]+", "-", display_name.casefold()).strip("-_")
        if not slug:
            raise ProviderValidationError(
                "Provider name must contain letters or numbers"
            )
        provider = f"custom:{slug}"
        if self.models.provider(provider):
            raise ProviderValidationError(
                "A custom provider with this name already exists"
            )
        return provider, display_name

    def custom_providers(self):
        """Return saved custom-provider identities for setup-page rendering."""
        return self.models.custom_providers()

    def setup_selection(self):
        """Return the saved setup-page provider filter when it remains valid."""
        provider = self.models.setup_selection()
        if provider == "all":
            return provider
        try:
            self.spec(provider)
        except ProviderValidationError:
            return "all"
        return provider

    def save_setup_selection(self, provider):
        """Validate and persist the setup-page provider filter."""
        if provider != "all":
            self.spec(provider)
        self.models.setup_selection(provider)
        return provider

    def model_selector_filter(self, page="all"):
        """Return the saved model-selector provider filter when valid."""
        provider = self.models.model_selector_filter(page)
        active = {entry["provider"] for entry in self.active_models()}
        if provider != "all" and provider not in active:
            return "all"
        return provider

    def save_model_selector_filter(self, page, provider):
        """Validate and persist the model-selector provider filter."""
        page = str(page or "all").strip() or "all"
        provider = str(provider or "all").strip()
        if provider != "all":
            active = {entry["provider"] for entry in self.active_models()}
            if provider not in active:
                raise ProviderValidationError(
                    "A valid online provider is required"
                )
        self.models.model_selector_filter(page, provider)
        return provider

    def saved_provider_overview(self, provider):
        """Return persisted connection and model counts for setup-page views."""
        self.spec(provider)
        return {
            "configuration": self.models.provider(provider),
            "summary": self.models.summary(provider),
        }

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

    def _selector_entry(self, provider, model_name, size_gb=None):
        """Build one active-model selector entry with its size marker."""
        try:
            spec = self.spec(provider)
        except ProviderValidationError:
            spec = None
        display_name = spec.display_name if spec else provider
        displayed_model = (
            model_display_name(spec, model_name) if spec else model_name
        )
        label = f"{display_name}::{displayed_model}"
        if spec is not None and not spec.local:
            label = f"{label} (API)"
        elif size_gb is not None:
            label = f"{label} ({size_gb} GB)"
        entry = {
            "provider": provider,
            "provider_label": display_name,
            "model": model_name,
            "size_gb": size_gb,
            "label": label,
        }
        saved = self.parameters.value(f"{provider}::{model_name}")
        if isinstance(saved, dict):
            modalities = ModelProviderService._display_field(
                saved, "modalities"
            )
            if modalities:
                entry["modalities"] = modalities
            caps = ModelProviderService._display_field(
                saved, "chat_template_caps"
            )
            if caps:
                entry["chat_template_caps"] = caps
        return entry

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
            for configuration in self.models.active()
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
        configuration = self.models.provider(provider)
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

    def connection(self, provider, data=None, spec=None):
        """Resolve and validate a submitted or saved provider connection."""
        spec = spec or self.spec(provider)
        data = data or {}
        saved = (
            None
            if provider == CUSTOM_PROVIDER_SENTINEL
            else self.models.provider(provider)
        )
        if spec.fixed_endpoint:
            submitted_key = str(data.get("api_key", "")).strip()
            api_key = submitted_key or (saved["api_key"] if saved else None)
            address = spec.fixed_endpoint
            port = spec.fixed_port
        else:
            address = str(data.get("ip", "")).strip()
            port = data.get("port", "")
            submitted_key = str(data.get("api_key", "")).strip()
            api_key = (
                submitted_key or (saved["api_key"] if saved else None)
                if spec.supports_api_key
                else None
            )

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
        configuration = self.models.provider(provider)
        if not configuration:
            return None
        if not spec.fixed_endpoint:
            return configuration
        return {
            **configuration,
            "ip": spec.fixed_endpoint,
            "port": spec.fixed_port,
        }

    def _fetch_catalog(self, provider, connection, timeout=5, spec=None):
        """Fetch a catalog using the provider's discovery endpoint and headers."""
        spec = spec or self.spec(provider)
        return self.catalog_client.fetch_catalog(
            connection["ip"],
            connection["port"],
            timeout=timeout,
            api_key=connection.get("api_key"),
            provider=provider,
            catalog_address=spec.catalog_endpoint,
            provider_spec=spec,
        )

    def fetch_models(self, provider, data):
        """Read a live model catalog without changing saved data."""
        spec = None
        if provider == CUSTOM_PROVIDER_SENTINEL:
            custom_provider, display_name = self._custom_provider_identity(
                data.get("provider_name")
            )
            spec = self._custom_provider_spec(custom_provider, display_name)
        connection = self.connection(provider, data, spec=spec)
        return self._fetch_catalog(provider, connection, spec=spec)

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
        saved = self.models.models(provider)
        changed = False
        merged = []
        for model in saved:
            size_gb = discovered.get(model["name"])
            if size_gb is not None and size_gb != model.get("size_gb"):
                model = {**model, "size_gb": size_gb}
                changed = True
            merged.append(model)
        if changed:
            self.models.models(provider, merged)

    def _models_with_sizes(
        self,
        provider,
        connection,
        models,
        timeout=5,
        spec=None,
    ):
        """Attach authoritative sizes to submitted models for a local provider.

        The catalog is read again so the stored size matches the served file.
        When the server is unreachable the previously saved sizes are reused.
        """
        sizes = {
            model["name"]: model["size_gb"]
            for model in self.models.models(provider)
            if model.get("size_gb") is not None
        }
        try:
            live_models = self._fetch_catalog(
                provider,
                connection,
                timeout=timeout,
                spec=spec,
            )
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
        custom_display_name = None
        if provider == CUSTOM_PROVIDER_SENTINEL:
            provider, custom_display_name = self._custom_provider_identity(
                data.get("provider_name")
            )
            spec = self._custom_provider_spec(provider, custom_display_name)
        else:
            spec = self.spec(provider)
        models = data.get("models")
        if not isinstance(models, list):
            raise ProviderValidationError("Models must be a list")
        if any(not isinstance(model, dict) for model in models):
            raise ProviderValidationError("Every model must be an object")
        connection = self.connection(provider, data, spec=spec)

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
            self.models.models(provider, [])
            summary = {"total": 1, "enabled": 1}
        else:
            if not models:
                raise ProviderValidationError("Read and select models first")
            if spec.local:
                models = self._models_with_sizes(
                    provider,
                    connection,
                    models,
                    spec=spec,
                )
            else:
                models = [{**model, "size_gb": None} for model in models]
            self.models.models(provider, models)
            summary = self.models.summary(provider)

        self.models.provider(
            provider,
            {
                "ip": connection["ip"],
                "port": connection["port"],
                "api_key": connection["api_key"],
                "display_name": custom_display_name,
                "custom": custom_display_name is not None,
            },
        )
        configuration = self.saved_connection(provider)
        return {
            "message": "Model configuration saved successfully",
            "models_count": summary["total"],
            "enabled_count": summary["enabled"],
            "model_name": model_name,
            "provider_enabled": configuration["enabled"],
            "has_api_key": bool(configuration.get("api_key")),
            "provider": provider,
        }

    def load_configuration(self, provider):
        """Return browser-safe saved state for one provider."""
        spec = self.spec(provider)
        configuration = self.models.provider(provider)
        models = (
            []
            if spec is not None and spec.single_live_model
            else self.models.models(provider)
        )
        if (
            spec is not None
            and spec.local
            and configuration
            and not configuration.get("custom")
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
                self.models.models(provider, merged)
            models = merged
        if configuration and configuration.get("custom"):
            models = [
                {
                    **model,
                    "id": model["name"],
                    "name": model_display_name(spec, model["name"]),
                }
                for model in models
            ]
        else:
            models = self._attach_saved_capabilities(provider, models)
        summary = self.models.summary(provider)
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

    def detect_ctx_mode(self, provider):
        """Detect the llama.cpp router-mode context setting (--ctx-size/--fit)."""
        if provider != "llama.cpp":
            return None
        # No process-wide cache: the browser caches the mode for one page load.
        configuration = self.models.provider(provider)
        if not configuration:
            return None
        ip = (configuration.get("ip") or "").rstrip("/")
        port = configuration.get("port")
        if not ip or not port:
            return None
        mode = None
        try:
            with urllib.request.urlopen(f"{ip}:{port}/models", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or not data:
            return None
        entry = None
        for item in data:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if isinstance(status, dict) and isinstance(status.get("args"), list):
                entry = item
                break
        if entry is None:
            entry = data[0]
        status = entry.get("status") if isinstance(entry, dict) else None
        args = status.get("args") if isinstance(status, dict) else None
        if not isinstance(args, list):
            args = []
        index = 0
        while index < len(args):
            token = str(args[index])
            if token == "--ctx-size" and index + 1 < len(args):
                mode = "n_ctx"
                break
            if token == "--fit" and index + 1 < len(args):
                value = str(args[index + 1]).strip().lower()
                if value == "on":
                    mode = "fit_on"
                elif value == "off":
                    mode = "fit_off"
                break
            index += 1
        return mode

    def check_props_available(self, provider):
        """Quickly check whether a local provider exposes the props endpoint."""
        if provider not in ("llama.cpp", "vllm"):
            return False
        configuration = self.models.provider(provider)
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

    def fetch_model_params(self, provider, model):
        """Return cached defaults, otherwise read them from the local model."""
        parameter_key = f"{provider}::{model}"
        if provider not in ("llama.cpp", "vllm"):
            self.spec(provider)
            saved = self.parameters.value(parameter_key)
            tier = "Free"
            if isinstance(saved, dict) and saved.get("tier"):
                tier = str(saved.get("tier"))
            ctx_mode = f"API::{tier}"
            return {
                "params": {},
                "modalities": ModelProviderService._display_field(
                    saved, "modalities"
                ),
                "chat_template_caps": ModelProviderService._display_field(
                    saved, "chat_template_caps"
                ),
                "n_ctx": ModelProviderService._display_n_ctx(saved, ctx_mode),
                "ctx_mode": ctx_mode,
                "tier": tier,
                "source": "database",
            }
        ctx_mode = (
            self.detect_ctx_mode(provider)
            if provider == "llama.cpp"
            else None
        )
        saved_params = self.parameters.value(parameter_key)
        if saved_params is not None and ctx_mode is not None:
            saved_n_ctx = ModelProviderService._display_n_ctx(saved_params, ctx_mode)
            if saved_n_ctx is not None:
                return {
                    "params": ModelProviderService._display_params(saved_params),
                    "modalities": ModelProviderService._display_field(
                        saved_params, "modalities"
                    ),
                    "n_ctx": saved_n_ctx,
                    "ctx_mode": ctx_mode,
                    "source": "database",
                }
        if saved_params is not None and ctx_mode is None:
            return {
                "params": ModelProviderService._display_params(saved_params),
                "modalities": ModelProviderService._display_field(
                    saved_params, "modalities"
                ),
                "n_ctx": ModelProviderService._display_n_ctx(saved_params),
                "ctx_mode": None,
                "source": "database",
            }

        configuration = self.models.provider(provider)
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
                    "modalities": ModelProviderService._display_field(
                        saved_params, "modalities"
                    ),
                    "n_ctx": ModelProviderService._display_n_ctx(
                        saved_params, ctx_mode
                    ),
                    "ctx_mode": ctx_mode,
                    "source": "database",
                }
            raise ProviderCatalogError(
                "Could not read model parameters"
            ) from error

        # Default generation settings (existing behaviour).
        settings = payload.get("default_generation_settings") or {}
        params = settings.get("params") if isinstance(settings, dict) else None
        if isinstance(params, dict):
            params = {
                key: ModelProviderService._round_model_param_value(value)
                for key, value in params.items()
            }

        # New capability fields.
        modalities = payload.get("modalities") if isinstance(payload, dict) else None
        chat_template_caps = payload.get("chat_template_caps") if isinstance(payload, dict) else None
        n_ctx = None
        if isinstance(settings, dict):
            n_ctx = settings.get("n_ctx")
        if n_ctx is None and isinstance(payload, dict):
            n_ctx = payload.get("n_ctx")

        # When only the context size for a new mode is needed, keep the
        # previously saved parameters/modalities and just add that mode.
        updating_mode_only = (
            saved_params is not None
            and ctx_mode is not None
            and ModelProviderService._display_n_ctx(saved_params, ctx_mode)
            is None
        )
        if updating_mode_only:
            merged = dict(saved_params) if isinstance(saved_params, dict) else {}
            modes = merged.get("n_ctx_modes")
            if not isinstance(modes, dict):
                modes = {}
            modes = dict(modes)
            if n_ctx is not None:
                modes[ctx_mode] = n_ctx
                merged["n_ctx_modes"] = modes
            self.parameters.value(parameter_key, merged)
            return {
                "params": ModelProviderService._display_params(merged),
                "modalities": ModelProviderService._display_field(merged, "modalities"),
                "n_ctx": n_ctx,
                "ctx_mode": ctx_mode,
                "source": "provider",
            }

        # Store everything together so callers can read any subset.
        full = {}
        if params is not None:
            full["params"] = params
        if modalities is not None:
            full["modalities"] = modalities
        if chat_template_caps is not None:
            full["chat_template_caps"] = chat_template_caps
        if ctx_mode is not None and n_ctx is not None:
            modes = {}
            if isinstance(saved_params, dict):
                existing = saved_params.get("n_ctx_modes")
                if isinstance(existing, dict):
                    modes = dict(existing)
            modes[ctx_mode] = n_ctx
            full["n_ctx_modes"] = modes

        if not full:
            raise ProviderCatalogError("Unexpected parameter response")

        self.parameters.value(parameter_key, full)
        return {
            "params": params if isinstance(params, dict) else {},
            "modalities": modalities if isinstance(modalities, dict) else {},
            "n_ctx": n_ctx,
            "ctx_mode": ctx_mode,
            "source": "provider",
        }

    def model_params_status(self, provider, model):
        """Return saved parameter/context state without reading ``/props``."""
        self.spec(provider)
        saved = self.parameters.value(f"{provider}::{model}")
        if provider == "llama.cpp":
            ctx_mode = self.detect_ctx_mode(provider)
            tier = None
        elif provider == "vllm":
            ctx_mode = None
            tier = None
        else:
            tier = "Free"
            if isinstance(saved, dict) and saved.get("tier"):
                tier = str(saved.get("tier"))
            ctx_mode = f"API::{tier}"
        params_saved = self._has_saved_params(saved)
        n_ctx = self._display_n_ctx(saved, ctx_mode)
        has_capabilities = isinstance(saved, dict) and (
            bool(saved.get("modalities"))
            or bool(saved.get("chat_template_caps"))
            or saved.get("n_ctx") is not None
        )
        if not params_saved and not has_capabilities:
            state = "missing_params"
        elif provider == "llama.cpp" and n_ctx is None and not has_capabilities:
            state = "missing_ctx"
        else:
            state = "complete"
        return {
            "state": state,
            "params_saved": params_saved,
            "modalities": self._display_field(saved, "modalities"),
            "chat_template_caps": self._display_field(saved, "chat_template_caps"),
            "ctx_mode": ctx_mode,
            "n_ctx": n_ctx,
            "tier": tier,
        }

    @staticmethod
    def _round_model_param_value(value):
        """Round a model parameter to the nearest 0.005 (3 decimals)."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            rounded = round(value / 0.005) * 0.005
            rounded = round(rounded, 3)
            if isinstance(value, int) and float(rounded).is_integer():
                return int(rounded)
            return rounded
        if isinstance(value, dict):
            return {
                key: ModelProviderService._round_model_param_value(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                ModelProviderService._round_model_param_value(item)
                for item in value
            ]
        return value

    # Backwards/alternative names for the same rounding helper.
    _round_param_value = _round_model_param_value
    _round_params = _round_model_param_value
    _round_to_accuracy = _round_model_param_value
    round_model_param = _round_model_param_value

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
    def _has_saved_params(saved_params):
        """Return whether a cache row contains generation parameters."""
        if not isinstance(saved_params, dict):
            return False
        if "params" in saved_params:
            return isinstance(saved_params["params"], dict)
        metadata_keys = {"modalities", "chat_template_caps", "n_ctx_modes", "n_ctx"}
        return any(key not in metadata_keys for key in saved_params)

    @staticmethod
    def _display_field(saved_params, field):
        """Return one nested capability field (modalities, chat_template_caps)."""
        if isinstance(saved_params, dict) and isinstance(saved_params.get(field), dict):
            return saved_params[field]
        return {}

    @staticmethod
    def _display_n_ctx(saved_params, mode=None):
        """Return the saved context size for *mode*, if present.

        For providers without a router-mode context setting (or when a manual
        override was saved), fall back to a top-level ``n_ctx`` value.
        """
        if not isinstance(saved_params, dict):
            return None
        modes = saved_params.get("n_ctx_modes")
        if isinstance(modes, dict) and mode:
            value = modes.get(mode)
            if isinstance(value, bool):
                pass
            elif isinstance(value, (int, float)):
                return int(value)
            elif isinstance(value, str) and value.strip():
                try:
                    return int(float(value.strip()))
                except ValueError:
                    pass
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

    def _attach_saved_modalities(self, models):
        """Attach locally saved modality flags to each model, if any."""
        return self._attach_saved_capabilities("llama.cpp", models)

    def _attach_saved_capabilities(self, provider, models):
        """Attach saved modality and tool-capability flags to each model."""
        updated = []
        for model in models:
            entry = dict(model)
            model_name = entry.get("id") or entry.get("name")
            if model_name:
                saved = self.parameters.value(f"{provider}::{model_name}")
                modalities = (
                    ModelProviderService._display_field(saved, "modalities")
                    if saved else {}
                )
                if modalities:
                    entry["modalities"] = modalities
                caps = (
                    ModelProviderService._display_field(
                        saved, "chat_template_caps"
                    )
                    if saved else {}
                )
                if caps:
                    entry["chat_template_caps"] = caps
            updated.append(entry)
        return updated

    def delete_model_params(self, provider, model):
        """Remove cached defaults for one local provider model."""
        if provider not in ("llama.cpp", "vllm"):
            raise ProviderValidationError(
                "Additional parameters are only available for local providers"
            )
        return self.parameters.delete(f"{provider}::{model}")

    def save_model_params(self, provider, model, params):
        """Persist custom default parameters for one provider model."""
        self.spec(provider)
        if not isinstance(params, dict):
            raise ProviderValidationError("Parameters must be an object")
        parameter_key = f"{provider}::{model}"
        existing = self.parameters.value(parameter_key)
        full = existing if isinstance(existing, dict) else {}
        capability_keys = {"n_ctx", "modalities", "chat_template_caps", "tier"}
        capability_data = {
            key: params[key] for key in capability_keys if key in params
        }
        other = {
            key: value for key, value in params.items()
            if key not in capability_keys
        }
        if capability_data:
            if other:
                full["params"] = other
        else:
            full["params"] = params
        if "n_ctx" in capability_data:
            value = capability_data["n_ctx"]
            if value is None:
                full.pop("n_ctx", None)
            else:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    value = None
                if value is not None and provider not in ("llama.cpp", "vllm") and value < 1024:
                    value = 1024
                if value is None:
                    full.pop("n_ctx", None)
                else:
                    full["n_ctx"] = value
                    modes = full.get("n_ctx_modes")
                    modes = dict(modes) if isinstance(modes, dict) else {}
                    if provider == "llama.cpp":
                        mode = self.detect_ctx_mode(provider)
                        if mode:
                            modes[mode] = value
                    elif provider != "vllm":
                        tier = full.get("tier")
                        if not tier and "tier" in capability_data:
                            tier = capability_data.get("tier")
                        tier = str(tier or "Free")
                        full["tier"] = tier
                        modes[f"API::{tier}"] = value
                    if modes:
                        full["n_ctx_modes"] = modes
        if "modalities" in capability_data:
            full["modalities"] = capability_data["modalities"] or {}
        if "chat_template_caps" in capability_data:
            full["chat_template_caps"] = capability_data["chat_template_caps"] or {}
        if "tier" in capability_data:
            full["tier"] = capability_data["tier"] or "Free"
        self.parameters.value(parameter_key, full)
        return full

    def status(self, provider):
        """Return live reachability and persisted state for one provider."""
        spec = self.spec(provider)
        configuration = self.models.provider(provider)
        summary = self.models.summary(provider)
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
            self.models.set_enabled(provider, False)

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

    def llama_managed_tools(self, timeout=3):
        """Read live MCP tools from the configured llama.cpp server."""
        configuration = self.saved_connection("llama.cpp")
        if not configuration:
            return {
                "configured": False,
                "online": False,
                "tools_available": False,
                "status_code": None,
                "tools": [],
            }

        models_url = self.catalog_client.models_url(
            configuration["ip"],
            configuration["port"],
        )
        parsed = urllib.parse.urlsplit(models_url)
        tools_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, "/tools", "", "")
        )
        tools_request = urllib.request.Request(
            tools_url,
            headers={"Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(tools_request, timeout=timeout) as response:
                status_code = int(getattr(response, "status", 0) or 0)
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            return {
                "configured": True,
                "online": True,
                "tools_available": False,
                "status_code": error.code,
                "tools": [],
            }
        except (OSError, TimeoutError, json.JSONDecodeError, ValueError):
            return {
                "configured": True,
                "online": False,
                "tools_available": False,
                "status_code": None,
                "tools": [],
            }

        tools = payload if isinstance(payload, list) else []
        return {
            "configured": True,
            "online": status_code == 200,
            "tools_available": status_code == 200 and bool(tools),
            "status_code": status_code,
            "tools": tools,
        }

    def call_llama_managed_tool(self, tool_name, arguments, timeout=30):
        """Invoke one llama.cpp-managed tool through its server endpoint."""
        configuration = self.saved_connection("llama.cpp")
        if not configuration:
            raise ProviderValidationError("llama.cpp is not configured")
        if not isinstance(arguments, dict):
            raise ProviderValidationError("Tool arguments must be an object")
        models_url = self.catalog_client.models_url(
            configuration["ip"],
            configuration["port"],
        )
        parsed = urllib.parse.urlsplit(models_url)
        tools_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, "/tools", "", "")
        )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        api_key = configuration.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        tool_request = urllib.request.Request(
            tools_url,
            data=json.dumps(
                {"tool": tool_name, "params": arguments}
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(tool_request, timeout=timeout) as response:
                payload = json.load(response)
        except (OSError, TimeoutError, urllib.error.URLError, ValueError) as error:
            raise ProviderValidationError(
                f"llama.cpp tool {tool_name} failed"
            ) from error
        if not isinstance(payload, dict):
            raise ProviderValidationError(
                f"llama.cpp tool {tool_name} returned an invalid result"
            )
        if payload.get("error"):
            raise ProviderValidationError(str(payload["error"]))
        return payload

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
        documents=None,
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
            documents=documents,
        )

    def chat_completion_with_tools(
        self,
        provider,
        model,
        messages,
        tools,
        temperature,
        top_p,
        top_k,
        max_tokens=None,
        min_p=None,
        repeat_penalty=None,
        repeat_last_n=None,
        dry_multiplier=None,
        seed=None,
        timeout=300,
        extra_parameters=None,
        attachments=None,
        documents=None,
    ):
        """Return one OpenAI-compatible completion with structured tool calls."""
        spec, configuration, base_url = self._completion_context(provider)
        if spec.sdk_client != "openai":
            raise ProviderValidationError(
                f"{spec.display_name} does not support CairnMark MCP tool calls"
            )
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
        sdk = self.catalog_client.sdk_client
        kwargs = sdk._provided_parameters(
            parameters,
            {
                "temperature": "temperature",
                "top_p": "top_p",
                "max_tokens": "max_tokens",
            },
        )
        body_parameters = {
            **sdk._extra_body(spec, parameters),
            **self.local_extra_parameters(provider, extra_parameters),
        }
        combined_attachments = list(attachments or [])
        for document in (documents or []):
            combined_attachments.append(
                {
                    "type": "document",
                    "data": document.get("content", ""),
                    "mime_type": document.get("mime_type", "text/plain"),
                    "original_name": document.get("filename", "document"),
                }
            )
        if combined_attachments:
            messages = sdk._openai_messages_with_attachments(
                messages,
                combined_attachments,
            )
        if body_parameters:
            kwargs["extra_body"] = body_parameters
        with sdk.openai_factory(
            api_key=configuration.get("api_key") or "not-needed",
            base_url=base_url,
            timeout=timeout,
            default_headers=dict(spec.catalog_headers) or None,
        ) as client:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                **kwargs,
            )

        message = response.choices[0].message
        normalized_calls = []
        for index, tool_call in enumerate(
            getattr(message, "tool_calls", None) or []
        ):
            function = getattr(tool_call, "function", None)
            normalized_calls.append(
                {
                    "id": str(
                        getattr(tool_call, "id", None) or f"call_{index}"
                    ),
                    "type": "function",
                    "function": {
                        "name": str(getattr(function, "name", "")),
                        "arguments": str(
                            getattr(function, "arguments", "{}") or "{}"
                        ),
                    },
                }
            )
        usage = response.usage
        return {
            "role": "assistant",
            "content": sdk._message_text(message.content),
            "tool_calls": normalized_calls,
        }, {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": (
                getattr(usage, "completion_tokens", 0) if usage else 0
            ),
        }

    def chat_completion_with_params_stream(
        self, provider, model, messages, temperature, top_p, top_k, max_tokens=None,
        min_p=None, repeat_penalty=None, repeat_last_n=None,
        dry_multiplier=None, seed=None, timeout=300, extra_parameters=None,
        attachments=None,
        documents=None,
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
            combined_attachments = list(attachments or [])
            for document in (documents or []):
                combined_attachments.append(
                    {
                        "type": "document",
                        "data": document.get("content", ""),
                        "mime_type": document.get("mime_type", "text/plain"),
                        "original_name": document.get("filename", "document"),
                    }
                )
            if combined_attachments:
                messages = self.catalog_client.sdk_client._openai_messages_with_attachments(
                    messages, combined_attachments
                )
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
                sdk = self.catalog_client.sdk_client
                google_system, google_input, generation_config = (
                    sdk._google_interaction_request(
                        messages,
                        parameters,
                        attachments,
                    )
                )
                options = google_types.HttpOptions(
                    api_version="v1beta",
                    timeout=int(timeout * 1000),
                )
                kwargs = {
                    "model": sdk._google_model_name(model),
                    "input": google_input,
                    "generation_config": generation_config,
                    "store": False,
                    "stream": True,
                }
                if google_system:
                    kwargs["system_instruction"] = google_system
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
                with sdk.google_factory(
                    api_key=api_key,
                    http_options=options,
                ) as client:
                    for event in client.interactions.create(**kwargs):
                        event_type = getattr(event, "event_type", "")
                        delta = getattr(event, "delta", None)
                        if (
                            event_type == "step.delta"
                            and getattr(delta, "type", "") == "text"
                        ):
                            text = str(getattr(delta, "text", "") or "")
                            if text:
                                accumulated += text
                                yield {"type": "chunk", "text": text}
                        elif event_type == "interaction.completed":
                            interaction = getattr(event, "interaction", None)
                            usage_meta = getattr(interaction, "usage", None)
                            usage = {
                                "prompt_tokens": getattr(
                                    usage_meta, "total_input_tokens", 0
                                ),
                                "completion_tokens": getattr(
                                    usage_meta, "total_output_tokens", 0
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
                self.models.set_enabled(provider, False)
                raise ProviderConflictError("Provider server is offline") from error

            summary = self.models.summary(provider)
            valid_models = (
                len(live_models) == 1
                if spec.single_live_model
                else summary["total"] > 0
            )
            if not valid_models:
                self.models.set_enabled(provider, False)
                raise ProviderConflictError("Save a valid model configuration first")

        self.models.set_enabled(provider, enabled)
        return {"provider": provider, "enabled": enabled}
