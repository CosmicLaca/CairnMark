"""Expose enabled MCP tools to chat models and execute selected calls."""

import hashlib
import json
import re
from dataclasses import dataclass

from models.mcp_settings import MCP_SETTINGS
from services.mcp_services import McpServiceRegistry


MAX_TOOL_CALLS = 6
MAX_TOOL_RESULT_CHARS = 100_000
CONNECTION_SETTING_KEYS = {
    "endpoint",
    "password",
    "timeout_ms",
    "user",
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

    def __init__(self, provider_service, settings=None, registry=None):
        self.provider_service = provider_service
        self.settings = settings or MCP_SETTINGS
        self.registry = registry or McpServiceRegistry()

    @staticmethod
    def _alias(source, service, tool):
        raw = f"{source}__{service}__{tool}"
        normalized = re.sub(r"[^A-Za-z0-9_-]", "_", raw).strip("_")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
        return f"{normalized[:54]}__{digest}"

    @staticmethod
    def _function_definition(alias, description, parameters):
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}}
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
                        definition.get("description"),
                        parameters,
                    ),
                    settings=dict(main.get("settings") or {}),
                )
            )

        if provider != "llama.cpp":
            return bindings
        managed = self.provider_service.llama_managed_tools()
        if not managed.get("online"):
            return bindings
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
        merged.update(arguments)
        return merged

    @staticmethod
    def _result_text(result):
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
        if len(text) > MAX_TOOL_RESULT_CHARS:
            return text[:MAX_TOOL_RESULT_CHARS] + "\n[Tool result truncated]"
        return text

    def _execute(self, binding, arguments):
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
        return self._result_text(result)

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
        """Yield live tool statuses and one bounded final completion."""
        by_alias = {binding.alias: binding for binding in bindings}
        tools = [binding.definition for binding in bindings]
        transcript = [dict(message) for message in messages]
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        tool_call_count = 0

        while True:
            assistant, round_usage = (
                self.provider_service.chat_completion_with_tools(
                    provider,
                    model,
                    transcript,
                    tools,
                    **request_parameters,
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
                    "response": assistant.get("content", ""),
                    "usage": usage,
                    "transcript": transcript,
                }
                return

            remaining_calls = MAX_TOOL_CALLS - tool_call_count
            tool_calls = tool_calls[:remaining_calls]
            assistant = dict(assistant)
            assistant["tool_calls"] = tool_calls
            transcript.append(assistant)
            processed_tool_calls = []
            for call in tool_calls:
                if tool_call_count >= MAX_TOOL_CALLS:
                    break
                processed_tool_calls.append(call)
                function = call.get("function", {})
                alias = str(function.get("name") or "")
                binding = by_alias.get(alias)
                tool_call_count += 1
                provider_name = binding.source if binding else "unknown"
                tool_name = binding.tool if binding else alias
                yield {
                    "type": "status",
                    "text": (
                        f"{provider_name}::{tool_name} call... "
                        f"[{tool_call_count}]"
                    ),
                }
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be a JSON object.")
                    if binding is None:
                        raise ValueError("The requested tool is not enabled.")
                    result_text = self._execute(binding, arguments)
                    if (
                        self._is_degraded_search_result(result_text)
                        and tool_call_count < MAX_TOOL_CALLS
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
                        )
                except Exception as error:  # noqa: BLE001
                    result_text = f"Tool call failed: {error}"
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

            if tool_call_count < MAX_TOOL_CALLS:
                continue

            final_text, final_usage = (
                self.provider_service.chat_completion_with_params(
                    provider,
                    model,
                    transcript,
                    **request_parameters,
                    extra_parameters=extra_parameters,
                    attachments=attachments,
                    documents=documents,
                )
            )
            for key in usage:
                usage[key] += int(final_usage.get(key, 0) or 0)
            yield {
                "type": "complete",
                "response": final_text,
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
