"""Expose enabled MCP tools to chat models and execute selected calls."""

import hashlib
import json
import logging
import re
from contextlib import nullcontext
from dataclasses import dataclass

from models.mcp_settings import DEFAULT_TOOL_GLOBAL_SETTINGS, MCP_SETTINGS
from services.chat_previews import ChatPreviewStore
from services.mcp_services import McpServiceRegistry


LOGGER = logging.getLogger(__name__)


MAX_TOOL_ROUNDS = DEFAULT_TOOL_GLOBAL_SETTINGS["max_rounds"]
MAX_TOOL_CALLS = DEFAULT_TOOL_GLOBAL_SETTINGS["max_total_calls"]
MAX_TOOL_RESULT_CHARS = DEFAULT_TOOL_GLOBAL_SETTINGS["max_result_chars"]
TOOL_COMPLETION_TIMEOUT_SECONDS = 300
LOCAL_TOOL_COMPLETION_TIMEOUT_SECONDS = 900
DEPENDENCY_DISPLAY_NAMES = {
    "comfyui": "ComfyUI",
    "searxng": "SearXNG",
}
CONNECTION_SETTING_KEYS = {
    "endpoint",
    "password",
    "timeout_ms",
    "user",
}
TOOL_PREVIEW_PATTERN = re.compile(
    r"!\[[^\]]*\]\((/chat/preview/[A-Za-z0-9._-]+)\)"
)
PROMPT_ID_PATTERN = re.compile(
    r"[\"']?prompt_id[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9-]{1,64})",
    re.IGNORECASE,
)
COMFYUI_PROMPT_UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
COMFYUI_TOOL_DESCRIPTIONS = {
    "generate_image": (
        "Generate media with ComfyUI. For text-to-image use action='image' and "
        "prompt; checkpoint, negative_prompt, width, height, steps, cfg, sampler, "
        "scheduler, seed and batch_size are optional. Returns a prompt_id. CairnMark "
        "waits for the image and attaches it automatically."
    ),
    "get_image": (
        "Retrieve ComfyUI output. Use action='get' with filename, action='view' "
        "with asset_id, or action='list_assets' to list recent registered images."
    ),
    "list_local_models": (
        "Inspect installed ComfyUI models. Use action='list' and optionally set "
        "model_type such as 'checkpoints'; other actions manage model search paths."
    ),
    "queue": (
        "Inspect or manage the ComfyUI queue. Use action='status' with prompt_id "
        "for one job or action='list' for running and pending jobs."
    ),
}


@dataclass(frozen=True)
class ChatToolBinding:
    """Map one model-visible function name to a trusted tool executor."""

    alias: str
    source: str
    service: str
    tool: str
    definition: dict
    settings: dict


class ChatToolService:
    """Coordinate model tool calls across Custom and provider-managed MCP."""

    def __init__(
        self,
        provider_service,
        settings=None,
        registry=None,
        preview_store=None,
    ):
        self.provider_service = provider_service
        self.settings = settings or MCP_SETTINGS
        self.registry = registry or McpServiceRegistry()
        self.previews = preview_store or ChatPreviewStore()

    @staticmethod
    def _alias(source, service, tool):
        raw = f"{source}__{service}__{tool}"
        normalized = re.sub(r"[^A-Za-z0-9_-]", "_", raw).strip("_")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
        return f"{normalized[:54]}__{digest}"

    @staticmethod
    def _compact_schema_descriptions(value):
        if isinstance(value, dict):
            compacted = {}
            for key, child in value.items():
                if key == "description" and isinstance(child, str):
                    compacted[key] = (
                        child if len(child) <= 300 else child[:297].rstrip() + "..."
                    )
                else:
                    compacted[key] = ChatToolService._compact_schema_descriptions(
                        child
                    )
            return compacted
        if isinstance(value, list):
            return [
                ChatToolService._compact_schema_descriptions(child)
                for child in value
            ]
        return value

    @staticmethod
    def _function_definition(
        alias,
        description,
        parameters,
        compact_descriptions=False,
    ):
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}}
        if compact_descriptions:
            parameters = ChatToolService._compact_schema_descriptions(parameters)
        return {
            "type": "function",
            "function": {
                "name": alias,
                "description": str(description or "MCP tool"),
                "parameters": parameters,
            },
        }

    @staticmethod
    def _managed_identity(tool):
        definition = tool.get("definition") if isinstance(tool, dict) else None
        function = (
            definition.get("function")
            if isinstance(definition, dict)
            else None
        )
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
        return explicit_service or tool_name.split("_", 1)[0], tool_name

    def bindings(self, provider):
        """Return only globally, service, and individually enabled tools."""
        if self.settings.tools_enabled() is not True:
            return []
        records = self.settings.all()
        main_records = {
            (record["source"], record["service"]): record
            for record in records
            if not record["tool"]
        }
        tool_records = {
            (record["source"], record["service"], record["tool"]): record
            for record in records
            if record["tool"]
        }
        bindings = []
        external_availability = {}
        dependency_check = getattr(self.registry, "dependency_online", None)
        dependency_managed = getattr(self.registry, "dependency_managed", None)

        def dependency_available(service, service_settings):
            managed = (
                dependency_managed(service_settings)
                if callable(dependency_managed)
                else bool(
                    str(
                        service_settings.get("dependency_start_command", "")
                    ).strip()
                )
            )
            if managed:
                return True
            if not callable(dependency_check):
                return True
            result = dependency_check(service, service_settings)
            if isinstance(result, dict):
                return bool(result.get("online"))
            return bool(result)

        for cached in self.settings.cached_tools():
            service = cached["service"]
            tool_name = cached["tool"]
            main = main_records.get(("external", service))
            tool_record = tool_records.get(
                ("external_tool", service, tool_name)
            )
            if not main or not main["enabled"] or not tool_record:
                continue
            if not tool_record["enabled"]:
                continue
            if service not in external_availability:
                external_availability[service] = dependency_available(
                    service,
                    dict(main.get("settings") or {}),
                )
            if not external_availability[service]:
                continue
            definition = cached["definition"]
            alias = self._alias("custom", service, tool_name)
            parameters = definition.get("inputSchema")
            if not isinstance(parameters, dict):
                parameters = definition.get("input_schema")
            bindings.append(
                ChatToolBinding(
                    alias=alias,
                    source="custom",
                    service=service,
                    tool=tool_name,
                    definition=self._function_definition(
                        alias,
                        COMFYUI_TOOL_DESCRIPTIONS.get(
                            tool_name,
                            definition.get("description"),
                        ) if service.casefold() == "comfyui" else definition.get(
                            "description"
                        ),
                        parameters,
                        compact_descriptions=service.casefold() == "comfyui",
                    ),
                    settings=dict(main.get("settings") or {}),
                )
            )

        if provider != "llama.cpp":
            return bindings
        managed = self.provider_service.llama_managed_tools()
        if not managed.get("online"):
            return bindings
        managed_availability = {}
        for live_tool in managed.get("tools", []):
            service, tool_name = self._managed_identity(live_tool)
            main = main_records.get(("llama_service", service))
            tool_record = tool_records.get(
                ("llama_tool", service, tool_name)
            )
            if not main or not main["enabled"] or not tool_record:
                continue
            if not tool_record["enabled"]:
                continue
            if service not in managed_availability:
                managed_availability[service] = dependency_available(
                    service,
                    dict(main.get("settings") or {}),
                )
            if not managed_availability[service]:
                continue
            live_definition = live_tool.get("definition", {})
            function = (
                live_definition.get("function", {})
                if isinstance(live_definition, dict)
                else {}
            )
            alias = self._alias("llama", service, tool_name)
            bindings.append(
                ChatToolBinding(
                    alias=alias,
                    source="llama",
                    service=service,
                    tool=tool_name,
                    definition=self._function_definition(
                        alias,
                        function.get("description"),
                        function.get("parameters"),
                    ),
                    settings=dict(main.get("settings") or {}),
                )
            )
        return bindings

    def global_settings(self):
        """Return global execution settings from new or legacy repositories."""
        getter = getattr(self.settings, "global_settings", None)
        if callable(getter):
            return getter()
        return dict(DEFAULT_TOOL_GLOBAL_SETTINGS)

    @staticmethod
    def completion_timeout(provider):
        """Allow slow local reasoning models to finish tool-call rounds."""
        if provider in {"llama.cpp", "vllm"}:
            return LOCAL_TOOL_COMPLETION_TIMEOUT_SECONDS
        return TOOL_COMPLETION_TIMEOUT_SECONDS

    def request_allows_tools(self, raw_request, user_message):
        """Enforce the saved automatic, confirmation, or manual policy."""
        policy = self.global_settings()["tool_policy"]
        if policy == "automatic":
            return True
        if policy == "ask":
            return raw_request.get("tools_allowed") is True
        normalized = str(user_message or "").lstrip().lower()
        return normalized.startswith(("/tool ", "/tools "))

    def _quick_scope_bindings(self, bindings):
        """Apply the saved provider-free quick scope to enabled bindings."""
        getter = getattr(self.settings, "automatic_scope_selection", None)
        selection = getter() if callable(getter) else None
        if selection is None:
            return bindings
        selected = {
            (
                str(item.get("service") or "").casefold(),
                str(item.get("tool") or "").casefold(),
            )
            for item in selection
            if isinstance(item, dict)
        }
        return [
            binding
            for binding in bindings
            if (binding.service.casefold(), binding.tool.casefold()) in selected
        ]

    def scope_bindings(self, bindings, system_prompt):
        """Use only automatic-scope tools named in the system prompt."""
        if not self.global_settings().get("automatic_tool_scope", False):
            return bindings
        prompt = str(system_prompt or "")
        candidates = self._quick_scope_bindings(bindings)
        return [
            binding
            for binding in candidates
            if re.search(
                rf"(?<![A-Za-z0-9_-]){re.escape(binding.service)}"
                rf"\s*:\s*{re.escape(binding.tool)}"
                rf"(?![A-Za-z0-9_-])",
                prompt,
                flags=re.IGNORECASE,
            )
        ]

    def system_prompt(self, system_prompt, bindings):
        """Append runtime-only tool guidance for the enabled bindings."""
        settings = self.global_settings()
        if not bindings or not settings["guidance_enabled"]:
            return system_prompt
        if settings.get("automatic_tool_scope", False):
            prompt_bindings = self._quick_scope_bindings(bindings)
            names = sorted(
                {
                    f"{binding.service}: {binding.tool}"
                    for binding in prompt_bindings
                },
                key=str.casefold,
            )
        else:
            names = sorted(
                {
                    f"{binding.source}::{binding.service}::{binding.tool}"
                    for binding in bindings
                },
                key=str.casefold,
            )
        tool_list = "\n".join(f"- {name}" for name in names)
        template = settings["guidance_template"].strip()
        guidance = template.replace("{tools}", tool_list)
        if "{tools}" not in template:
            guidance = f"{guidance}\n\nAvailable tools:\n{tool_list}".strip()
        policy = settings["tool_policy"]
        if policy == "ask":
            guidance += (
                "\n\nTool use was approved by the user for this response."
            )
        elif policy == "manual":
            guidance += (
                "\n\nThe user explicitly requested tool use for this response."
            )
        base = str(system_prompt or "").rstrip()
        return f"{base}\n\n{guidance}".strip()

    @staticmethod
    def _coerce_setting(value, property_schema):
        """Coerce modal values to the MCP tool's declared JSON type."""
        if not isinstance(property_schema, dict):
            return value
        value_type = property_schema.get("type")
        if value_type is None:
            candidate_types = {
                option.get("type")
                for option in property_schema.get("anyOf", [])
                if isinstance(option, dict)
            }
            if len(candidate_types) == 1:
                value_type = candidate_types.pop()
        if value_type == "array" and not isinstance(value, list):
            if isinstance(value, str):
                return [item.strip() for item in value.split(",") if item.strip()]
            return [value]
        if value_type == "integer" and not isinstance(value, bool):
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        if value_type == "number" and not isinstance(value, bool):
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        if value_type == "boolean" and isinstance(value, str):
            if value.lower() in {"true", "1", "yes", "on"}:
                return True
            if value.lower() in {"false", "0", "no", "off"}:
                return False
        return value

    @classmethod
    def _arguments_with_defaults(cls, binding, arguments):
        function = binding.definition.get("function", {})
        schema = function.get("parameters", {})
        properties = (
            schema.get("properties", {}) if isinstance(schema, dict) else {}
        )
        merged = {
            key: cls._coerce_setting(value, properties[key])
            for key, value in binding.settings.items()
            if (
                key in properties
                and key not in CONNECTION_SETTING_KEYS
                and value not in (None, "", [])
            )
        }
        normalized_arguments = dict(arguments)
        if (
            str(binding.service).casefold() == "comfyui"
            and binding.tool == "get_image"
            and normalized_arguments.get("action") == "view"
            and normalized_arguments.get("filename")
            and not normalized_arguments.get("asset_id")
        ):
            normalized_arguments["action"] = "get"
        if (
            "path" in properties
            and "file_path" not in properties
            and "path" not in normalized_arguments
        ):
            for alias in ("file_path", "file_name", "filename"):
                if alias in normalized_arguments:
                    normalized_arguments["path"] = normalized_arguments.pop(alias)
                    break
        merged.update(normalized_arguments)
        return merged

    def _result_text(self, result, max_chars=MAX_TOOL_RESULT_CHARS):
        preview_markdown = []
        if not isinstance(result, dict):
            text = str(result)
        elif result.get("error"):
            text = str(result["error"])
            if not (
                "Unresponsive engines:" in text
                and "No results." in text
            ):
                raise RuntimeError(text)
        elif "plain_text_response" in result:
            text = str(result.get("plain_text_response") or "")
        else:
            parts = []
            for item in result.get("content", []):
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                elif item.get("type") == "image" and item.get("data"):
                    filename = self.previews.save_inline_image(
                        item.get("data"),
                        item.get("mimeType") or item.get("mime_type"),
                    )
                    if filename:
                        preview_markdown.append(
                            f"![Generated image](/chat/preview/{filename})"
                        )
            structured = result.get("structuredContent")
            if structured is None:
                structured = result.get("structured_content")
            if structured is not None:
                parts.append(json.dumps(structured, ensure_ascii=False))
            text = "\n".join(part for part in parts if part)
            if result.get("isError") and not (
                "Unresponsive engines:" in text
                and "No results." in text
            ):
                raise RuntimeError(text or "MCP tool returned an error")
            if not text:
                text = json.dumps(result, ensure_ascii=False)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[Tool result truncated]"
        if preview_markdown:
            text = "\n\n".join(
                part for part in (text, *preview_markdown) if part
            )
        return text

    @staticmethod
    def _with_tool_previews(response, transcript):
        """Append MCP images when the model omits them from its final answer."""
        text = str(response or "")
        existing = set(TOOL_PREVIEW_PATTERN.findall(text))
        previews = []
        for message in transcript or []:
            if not isinstance(message, dict) or message.get("role") != "tool":
                continue
            for preview_url in TOOL_PREVIEW_PATTERN.findall(
                str(message.get("content") or "")
            ):
                if preview_url in existing:
                    continue
                existing.add(preview_url)
                previews.append(f"![Generated image]({preview_url})")
        return "\n\n".join(part for part in (text, *previews) if part)

    def _ensure_dependency(self, binding):
        """Start and validate an API required by one selected binding."""
        dependency_owned = getattr(self.registry, "dependency_owned", None)
        owned_before = (
            bool(dependency_owned(binding.service))
            if callable(dependency_owned)
            else False
        )
        ensure_dependency = getattr(self.registry, "ensure_dependency", None)
        if callable(ensure_dependency):
            dependency = ensure_dependency(binding.service, binding.settings)
            online = (
                dependency.get("online")
                if isinstance(dependency, dict)
                else dependency
            )
            if not online:
                raise RuntimeError(
                    f"Required API for {binding.service} is not available."
                )
            owned_after = (
                bool(dependency_owned(binding.service))
                if callable(dependency_owned)
                else False
            )
            return not owned_before and owned_after
        return False

    def _stop_started_dependencies(self, dependencies):
        """Stop only APIs first launched for the completed chat request."""
        stop_dependency = getattr(self.registry, "stop_dependency", None)
        if not callable(stop_dependency):
            return
        for service, settings in reversed(list(dependencies.items())):
            try:
                stop_dependency(service, settings)
            except Exception:  # noqa: BLE001
                LOGGER.warning(
                    "Could not stop request-owned MCP dependency %s",
                    service,
                    exc_info=True,
                )

    def _dependency_start_status(self, binding):
        """Return a visible status when a managed API needs lazy startup."""
        dependency_managed = getattr(self.registry, "dependency_managed", None)
        dependency_status = getattr(self.registry, "dependency_status", None)
        if (
            not callable(dependency_managed)
            or not dependency_managed(binding.settings)
            or not callable(dependency_status)
        ):
            return None
        status = dependency_status(binding.service, binding.settings)
        if not status.get("required") or status.get("online"):
            return None
        service_name = str(binding.service or "").strip()
        display_name = DEPENDENCY_DISPLAY_NAMES.get(
            service_name.casefold(),
            service_name,
        )
        return f"Starting {display_name}..."

    def _execute(
        self,
        binding,
        arguments,
        max_result_chars=MAX_TOOL_RESULT_CHARS,
        dependency_ready=False,
    ):
        if not dependency_ready:
            self._ensure_dependency(binding)
        arguments = self._arguments_with_defaults(binding, arguments)
        if binding.source == "llama":
            timeout = binding.settings.get("timeout_ms", 30_000)
            try:
                timeout = max(1, int(timeout)) / 1000
            except (TypeError, ValueError):
                timeout = 30
            result = self.provider_service.call_llama_managed_tool(
                binding.tool,
                arguments,
                timeout=timeout,
            )
        else:
            result = self.registry.call_tool(
                binding.service,
                binding.tool,
                arguments,
                binding.settings,
            )
        result_text = self._result_text(result, max_result_chars)
        if (
            str(binding.service).casefold() == "comfyui"
            and binding.tool == "generate_image"
        ):
            match = PROMPT_ID_PATTERN.search(result_text)
            if match is None:
                match = COMFYUI_PROMPT_UUID_PATTERN.search(result_text)
            wait_for_image = getattr(
                self.registry,
                "wait_for_comfyui_image",
                None,
            )
            if match and callable(wait_for_image):
                completed = wait_for_image(
                    match.group(1),
                    binding.settings,
                )
                if completed:
                    completed_text = self._result_text(
                        completed,
                        max_result_chars,
                    )
                    result_text = "\n\n".join(
                        part for part in (result_text, completed_text) if part
                    )
        return result_text

    @staticmethod
    def _is_degraded_search_result(result_text):
        """Recognize an empty SearXNG response caused by engine failures."""
        return (
            "Unresponsive engines:" in result_text
            and "No results." in result_text
        )

    @staticmethod
    def _relaxed_search_call(binding, arguments):
        """Remove optional search constraints for one bounded retry."""
        relaxed_settings = dict(binding.settings)
        relaxed_arguments = dict(arguments)
        for key in ("categories", "engines", "time_range"):
            relaxed_settings.pop(key, None)
            relaxed_arguments.pop(key, None)
        relaxed_settings["pageno"] = 1
        relaxed_arguments["pageno"] = 1
        return ChatToolBinding(
            alias=binding.alias,
            source=binding.source,
            service=binding.service,
            tool=binding.tool,
            definition=binding.definition,
            settings=relaxed_settings,
        ), relaxed_arguments

    def iter_complete(
        self,
        provider,
        model,
        messages,
        bindings,
        request_parameters,
        extra_parameters,
        attachments=None,
        documents=None,
    ):
        """Yield one completion while retaining stateful Custom MCP sessions."""
        session_scope = getattr(
            self.registry,
            "persistent_tool_sessions",
            None,
        )
        context = session_scope() if callable(session_scope) else nullcontext()
        started_dependencies = {}
        try:
            with context:
                yield from self._iter_complete(
                    provider,
                    model,
                    messages,
                    bindings,
                    request_parameters,
                    extra_parameters,
                    attachments,
                    documents,
                    started_dependencies,
                )
        finally:
            self._stop_started_dependencies(started_dependencies)

    def _iter_complete(
        self,
        provider,
        model,
        messages,
        bindings,
        request_parameters,
        extra_parameters,
        attachments=None,
        documents=None,
        started_dependencies=None,
    ):
        """Yield live tool statuses and one bounded final completion."""
        started_dependencies = (
            started_dependencies if started_dependencies is not None else {}
        )
        by_alias = {binding.alias: binding for binding in bindings}
        tools = [binding.definition for binding in bindings]
        transcript = [dict(message) for message in messages]
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        global_settings = self.global_settings()
        max_rounds = global_settings["max_rounds"]
        max_total_calls = global_settings["max_total_calls"]
        max_failures = global_settings["max_consecutive_failures"]
        max_result_chars = global_settings["max_result_chars"]
        completion_timeout = self.completion_timeout(provider)
        tool_round_count = 0
        tool_call_count = 0
        consecutive_failures = 0

        while True:
            assistant, round_usage = (
                self.provider_service.chat_completion_with_tools(
                    provider,
                    model,
                    transcript,
                    tools,
                    **request_parameters,
                    timeout=completion_timeout,
                    extra_parameters=extra_parameters,
                    attachments=attachments,
                    documents=documents,
                )
            )
            for key in usage:
                usage[key] += int(round_usage.get(key, 0) or 0)
            tool_calls = assistant.get("tool_calls") or []
            if not tool_calls:
                yield {
                    "type": "complete",
                    "response": self._with_tool_previews(
                        assistant.get("content", ""),
                        transcript,
                    ),
                    "usage": usage,
                    "transcript": transcript,
                }
                return

            tool_round_count += 1
            remaining_calls = max_total_calls - tool_call_count
            tool_calls = tool_calls[:remaining_calls]
            assistant = dict(assistant)
            assistant["tool_calls"] = tool_calls
            transcript.append(assistant)
            processed_tool_calls = []
            for call in tool_calls:
                if (
                    tool_call_count >= max_total_calls
                    or consecutive_failures >= max_failures
                ):
                    break
                processed_tool_calls.append(call)
                function = call.get("function", {})
                alias = str(function.get("name") or "")
                binding = by_alias.get(alias)
                tool_call_count += 1
                provider_name = binding.source if binding else "unknown"
                tool_name = binding.tool if binding else alias
                call_status = (
                    f"{provider_name}::{tool_name} call... "
                    f"[{tool_call_count}]"
                )
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be a JSON object.")
                    if binding is None:
                        raise ValueError("The requested tool is not enabled.")
                    start_status = self._dependency_start_status(binding)
                    if start_status:
                        yield {"type": "status", "text": start_status}
                    if self._ensure_dependency(binding):
                        started_dependencies.setdefault(
                            binding.service,
                            dict(binding.settings),
                        )
                    yield {"type": "status", "text": call_status}
                    result_text = self._execute(
                        binding,
                        arguments,
                        max_result_chars,
                        dependency_ready=True,
                    )
                    consecutive_failures = 0
                    if (
                        self._is_degraded_search_result(result_text)
                        and tool_call_count < max_total_calls
                    ):
                        tool_call_count += 1
                        yield {
                            "type": "status",
                            "text": (
                                f"{binding.source}::{binding.tool} call... "
                                f"[{tool_call_count}]"
                            ),
                        }
                        relaxed_binding, relaxed_arguments = (
                            self._relaxed_search_call(binding, arguments)
                        )
                        result_text = self._execute(
                            relaxed_binding,
                            relaxed_arguments,
                            max_result_chars,
                            dependency_ready=True,
                        )
                        consecutive_failures = 0
                except Exception as error:  # noqa: BLE001
                    result_text = f"Tool call failed: {error}"
                    consecutive_failures += 1
                transcript.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id") or ""),
                        "name": alias,
                        "content": result_text,
                    }
                )
            assistant["tool_calls"] = processed_tool_calls
            yield {"type": "status", "text": "thinking…"}

            if (
                tool_round_count < max_rounds
                and tool_call_count < max_total_calls
                and consecutive_failures < max_failures
            ):
                continue

            final_text, final_usage = (
                self.provider_service.chat_completion_with_params(
                    provider,
                    model,
                    transcript,
                    **request_parameters,
                    timeout=completion_timeout,
                    extra_parameters=extra_parameters,
                    attachments=attachments,
                    documents=documents,
                )
            )
            for key in usage:
                usage[key] += int(final_usage.get(key, 0) or 0)
            yield {
                "type": "complete",
                "response": self._with_tool_previews(final_text, transcript),
                "usage": usage,
                "transcript": transcript,
            }
            return

    def complete(
        self,
        provider,
        model,
        messages,
        bindings,
        request_parameters,
        extra_parameters,
        attachments=None,
        documents=None,
    ):
        """Consume tool events and return the final non-streaming result."""
        completed = None
        for event in self.iter_complete(
            provider,
            model,
            messages,
            bindings,
            request_parameters,
            extra_parameters,
            attachments=attachments,
            documents=documents,
        ):
            if event.get("type") == "complete":
                completed = event
        if completed is None:
            raise RuntimeError("The tool workflow ended without a response.")
        return (
            completed["response"],
            completed["usage"],
            completed["transcript"],
        )
