"""Manage private MCP server declarations and OpenCode imports."""

import asyncio
import base64
import json
import logging
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from config import PROJECT_ROOT


DEFAULT_MCP_TIMEOUT_MS = 10000
MCP_CONFIG_PATH = PROJECT_ROOT / "services" / "mcv.json"
OPENCODE_CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
MCP_DEFAULT_ENDPOINTS = {
    "searxng": "http://127.0.0.1:8888",
    "comfyui": "http://127.0.0.1:8188",
    "postgres": "postgresql://127.0.0.1:5432",
}
MCP_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
LOGGER = logging.getLogger(__name__)


class McpServiceRegistry:
    """Read, import, update, and check private MCP server declarations."""

    def __init__(
        self,
        config_path=MCP_CONFIG_PATH,
        opencode_path=OPENCODE_CONFIG_PATH,
        opener=None,
    ):
        self.config_path = Path(config_path)
        self.opencode_path = Path(opencode_path)
        self.opener = opener or urllib.request.urlopen

    def configured(self):
        """Return whether the CairnMark MCP configuration already exists."""
        return self.config_path.is_file()

    @staticmethod
    def _read_json(path):
        with Path(path).open("r", encoding="utf-8-sig") as config_file:
            return json.load(config_file)

    def services(self):
        """Return validated declarations from ``services/mcv.json``."""
        if not self.configured():
            return {}
        document = self._read_json(self.config_path)
        servers = document.get("mcpServers") if isinstance(document, dict) else None
        if not isinstance(servers, dict):
            raise ValueError("mcv.json must contain an mcpServers object.")
        return {
            str(name): details
            for name, details in servers.items()
            if isinstance(details, dict)
        }

    @staticmethod
    def _opencode_server_entries(document):
        """Return current and legacy OpenCode MCP declarations."""
        mcp = document.get("mcp") if isinstance(document, dict) else None
        if not isinstance(mcp, dict):
            return {}
        entries = {
            str(name): details
            for name, details in mcp.items()
            if name not in {"servers", "timeout"} and isinstance(details, dict)
        }
        current = mcp.get("servers")
        if isinstance(current, dict):
            entries.update(
                {
                    str(name): details
                    for name, details in current.items()
                    if isinstance(details, dict)
                }
            )
        return entries

    @staticmethod
    def _normalize_opencode_server(details, global_timeout=None):
        """Convert one local OpenCode declaration to CairnMark's format."""
        if details.get("type", "local") != "local":
            return None
        raw_command = details.get("command")
        if isinstance(raw_command, list) and raw_command:
            command = str(raw_command[0]).strip()
            args = [str(value) for value in raw_command[1:]]
        elif isinstance(raw_command, str) and raw_command.strip():
            command = raw_command.strip()
            raw_args = details.get("args", [])
            if not isinstance(raw_args, list):
                return None
            args = [str(value) for value in raw_args]
        else:
            return None
        if not command:
            return None

        normalized = {
            "type": "local",
            "command": command,
            "args": args,
        }
        raw_timeout = details.get("timeout", global_timeout)
        if raw_timeout is not None and not isinstance(raw_timeout, bool):
            try:
                timeout_ms = int(raw_timeout)
            except (TypeError, ValueError):
                timeout_ms = None
            if timeout_ms is not None and timeout_ms > 0:
                normalized["timeout_ms"] = timeout_ms
        if isinstance(details.get("cwd"), str) and details["cwd"].strip():
            normalized["cwd"] = details["cwd"].strip()
        environment = details.get("environment")
        if isinstance(environment, dict):
            normalized["environment"] = {
                str(key): str(value) for key, value in environment.items()
            }
        if details.get("disabled") is True or details.get("enabled") is False:
            normalized["disabled"] = True
        return normalized

    def opencode_services(self):
        """Return usable local MCP declarations discovered in OpenCode."""
        if not self.opencode_path.is_file():
            return {}
        document = self._read_json(self.opencode_path)
        entries = self._opencode_server_entries(document)
        mcp = document.get("mcp", {}) if isinstance(document, dict) else {}
        global_timeout = mcp.get("timeout") if isinstance(mcp, dict) else None
        normalized = {}
        for name, details in entries.items():
            server = self._normalize_opencode_server(details, global_timeout)
            if server is not None:
                normalized[name] = server
        return normalized

    def client_configuration(self):
        """Return the modal configuration without unnecessary discovery."""
        if self.configured():
            return {
                "configured": True,
                "default_timeout_ms": DEFAULT_MCP_TIMEOUT_MS,
                "mcpServers": self.services(),
                "opencode_import_available": False,
                "opencode_server_names": [],
            }
        discovered = self.opencode_services()
        return {
            "configured": False,
            "default_timeout_ms": DEFAULT_MCP_TIMEOUT_MS,
            "mcpServers": {},
            "opencode_import_available": bool(discovered),
            "opencode_server_names": list(discovered),
        }

    def _write_services(self, servers):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.config_path.with_suffix(".json.tmp")
        with temporary_path.open("w", encoding="utf-8", newline="\n") as output:
            json.dump({"mcpServers": servers}, output, indent=2, ensure_ascii=False)
            output.write("\n")
        os.replace(temporary_path, self.config_path)

    def import_opencode(self):
        """Explicitly import usable OpenCode MCP declarations once."""
        if self.configured():
            raise ValueError("services/mcv.json already exists.")
        servers = self.opencode_services()
        if not servers:
            raise ValueError("No usable OpenCode MCP services were found.")
        self._write_services(servers)
        return servers

    def save_local_server(self, name, command, args, timeout_ms=None):
        """Create or update one local MCP server declaration."""
        name = str(name or "").strip()
        command = str(command or "").strip()
        if not name or not MCP_NAME_PATTERN.fullmatch(name):
            raise ValueError(
                "MCP service name may contain letters, numbers, dots, underscores, and hyphens."
            )
        if not command:
            raise ValueError("MCP command is required.")
        if not isinstance(args, list) or any(not isinstance(value, str) for value in args):
            raise ValueError("MCP args must be a JSON array of strings.")

        services = self.services()
        declaration = dict(services.get(name, {}))
        declaration.update({"type": "local", "command": command, "args": args})
        if timeout_ms in (None, ""):
            declaration.pop("timeout_ms", None)
        else:
            if isinstance(timeout_ms, bool):
                raise ValueError("MCP timeout must be a positive integer.")
            try:
                parsed_timeout = int(timeout_ms)
            except (TypeError, ValueError) as error:
                raise ValueError("MCP timeout must be a positive integer.") from error
            if parsed_timeout < 1:
                raise ValueError("MCP timeout must be a positive integer.")
            declaration["timeout_ms"] = parsed_timeout
        services[name] = declaration
        self._write_services(services)
        return declaration

    @staticmethod
    def _timeout_ms(details, override=None):
        raw_timeout = (
            override
            if override not in (None, "")
            else details.get("timeout_ms", DEFAULT_MCP_TIMEOUT_MS)
        )
        if isinstance(raw_timeout, bool):
            return DEFAULT_MCP_TIMEOUT_MS
        try:
            return max(1, int(raw_timeout))
        except (TypeError, ValueError):
            return DEFAULT_MCP_TIMEOUT_MS

    @staticmethod
    def _configured_endpoint(name, details, endpoint):
        endpoint = str(endpoint or "").strip()
        if endpoint:
            return endpoint
        if name == "postgres":
            for argument in reversed(details.get("args", [])):
                value = str(argument).strip()
                if value.startswith(("postgres://", "postgresql://")):
                    return value
        return MCP_DEFAULT_ENDPOINTS.get(name, "")

    def _check_http_endpoint(self, name, endpoint, timeout_ms):
        endpoint = str(endpoint or "").strip().rstrip("/")
        parsed = urllib.parse.urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False, None
        if name == "searxng":
            health_url = f"{endpoint}/search?q=AxelRudiPell&format=json"
        else:
            health_url = f"{endpoint}/system_stats"
        request = urllib.request.Request(
            health_url,
            headers={"Accept": "application/json"},
        )
        try:
            with self.opener(request, timeout=timeout_ms / 1000) as response:
                status_code = int(getattr(response, "status", 0) or 0)
        except (OSError, TimeoutError, urllib.error.URLError):
            return False, None
        return status_code == 200, status_code

    @staticmethod
    def _check_postgres_endpoint(endpoint, timeout_ms):
        parsed = urllib.parse.urlsplit(str(endpoint or "").strip())
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
            return False
        try:
            with socket.create_connection(
                (parsed.hostname, parsed.port or 5432),
                timeout=timeout_ms / 1000,
            ):
                return True
        except (OSError, TimeoutError):
            return False

    @staticmethod
    def _postgres_test_endpoint(endpoint, details, user, password):
        """Build a test URI without changing the saved MCP declaration."""
        existing_endpoint = ""
        for argument in reversed(details.get("args", [])):
            candidate = str(argument).strip()
            if candidate.startswith(("postgres://", "postgresql://")):
                existing_endpoint = candidate
                break
        parsed = urllib.parse.urlsplit(endpoint)
        existing = urllib.parse.urlsplit(existing_endpoint)
        username = str(user or parsed.username or existing.username or "")
        secret = str(password or parsed.password or existing.password or "")
        host = parsed.hostname or existing.hostname or ""
        port = parsed.port or existing.port
        userinfo = ""
        if username:
            userinfo = urllib.parse.quote(username, safe="")
            if secret:
                userinfo += f":{urllib.parse.quote(secret, safe='')}"
            userinfo += "@"
        netloc = f"{userinfo}{host}"
        if port:
            netloc += f":{port}"
        path = parsed.path if parsed.path not in {"", "/"} else existing.path
        query = parsed.query or existing.query
        return urllib.parse.urlunsplit(
            (parsed.scheme, netloc, path, query, "")
        )

    @classmethod
    def _details_with_postgres_endpoint(
        cls,
        details,
        endpoint,
        user="",
        password="",
    ):
        test_details = dict(details)
        connection_endpoint = cls._postgres_test_endpoint(
            endpoint,
            details,
            user,
            password,
        )
        args = []
        endpoint_replaced = False
        for argument in details.get("args", []):
            value = str(argument)
            if value.startswith(("postgres://", "postgresql://")):
                args.append(connection_endpoint)
                endpoint_replaced = True
            else:
                args.append(value)
        if not endpoint_replaced:
            args.append(connection_endpoint)
        test_details["args"] = args
        return test_details

    def test_endpoint(
        self,
        name,
        endpoint,
        timeout_ms=None,
        user="",
        password="",
        managed=False,
    ):
        """Test a schema-declared MCP endpoint without service-name rules."""
        name = str(name or "").strip()
        endpoint = str(endpoint or "").strip().rstrip("/")
        details = {}
        if not managed:
            services = self.services()
            if name not in services:
                raise ValueError("Unknown MCP service.")
            details = services[name]
        parsed_timeout = self._timeout_ms(details, timeout_ms)
        parsed = urllib.parse.urlsplit(endpoint)

        if parsed.scheme in {"http", "https"} and parsed.netloc:
            headers = {"Accept": "application/json, text/html;q=0.9, */*;q=0.8"}
            if user:
                credentials = base64.b64encode(
                    f"{user}:{password}".encode("utf-8")
                ).decode("ascii")
                headers["Authorization"] = f"Basic {credentials}"
            endpoint_request = urllib.request.Request(endpoint, headers=headers)
            try:
                with self.opener(
                    endpoint_request,
                    timeout=parsed_timeout / 1000,
                ) as response:
                    status_code = int(getattr(response, "status", 0) or 0)
            except (OSError, TimeoutError, urllib.error.URLError):
                return {"name": name, "online": False, "status_code": None}
            return {
                "name": name,
                "online": 200 <= status_code < 400,
                "status_code": status_code,
            }

        if parsed.scheme in {"postgres", "postgresql"} and parsed.hostname:
            if managed:
                online = self._check_postgres_endpoint(endpoint, parsed_timeout)
                return {"name": name, "online": online, "status_code": None}
            test_details = self._details_with_postgres_endpoint(
                details,
                endpoint,
                user,
                password,
            )
            tools_count = self._check_stdio(test_details, parsed_timeout)
            return {
                "name": name,
                "online": tools_count > 0,
                "status_code": None,
            }

        raise ValueError("A valid HTTP or PostgreSQL endpoint is required.")

    @staticmethod
    async def _discover_stdio_async(details, timeout_ms):
        command = str(details.get("command") or "").strip()
        args = details.get("args", [])
        if not command or not isinstance(args, list):
            return []
        environment = details.get("environment")
        if not isinstance(environment, dict):
            environment = None
        parameters = StdioServerParameters(
            command=command,
            args=[str(argument) for argument in args],
            env=environment,
            cwd=details.get("cwd") or None,
        )
        with open(os.devnull, "w", encoding="utf-8") as stderr:
            async with asyncio.timeout(timeout_ms / 1000):
                async with stdio_client(parameters, errlog=stderr) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        return [
                            tool.model_dump(
                                mode="json",
                                by_alias=True,
                                exclude_none=True,
                            )
                            for tool in result.tools
                        ]

    @staticmethod
    async def _discover_http_async(details, timeout_ms, endpoint=None):
        """Discover tools from an MCP streamable-HTTP declaration."""
        url = str(
            details.get("url")
            or details.get("endpoint")
            or endpoint
            or ""
        ).strip()
        if not url:
            return []
        headers = details.get("headers")
        if not isinstance(headers, dict):
            headers = None
        async with asyncio.timeout(timeout_ms / 1000):
            async with streamablehttp_client(
                url,
                headers=headers,
                timeout=timeout_ms / 1000,
            ) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [
                        tool.model_dump(
                            mode="json",
                            by_alias=True,
                            exclude_none=True,
                        )
                        for tool in result.tools
                    ]

    @classmethod
    async def _check_stdio_async(cls, details, timeout_ms):
        return len(await cls._discover_stdio_async(details, timeout_ms))

    def _check_stdio(self, details, timeout_ms):
        try:
            return asyncio.run(self._check_stdio_async(details, timeout_ms))
        except Exception as error:
            LOGGER.warning("MCP stdio health check failed: %s", error)
            return 0

    def _discover_stdio(self, details, timeout_ms):
        try:
            return asyncio.run(self._discover_stdio_async(details, timeout_ms))
        except Exception as error:
            LOGGER.warning("MCP stdio tool discovery failed: %s", error)
            return []

    @staticmethod
    def _uses_http_transport(details):
        transport = str(details.get("type") or "").lower()
        return bool(details.get("url")) or transport in {
            "http",
            "remote",
            "streamable_http",
            "streamable-http",
        }

    def _discover_transport(self, details, timeout_ms, endpoint=None):
        if not self._uses_http_transport(details):
            return self._discover_stdio(details, timeout_ms)
        try:
            return asyncio.run(
                self._discover_http_async(details, timeout_ms, endpoint)
            )
        except Exception as error:
            LOGGER.warning("MCP tool discovery failed: %s", error)
            return []

    @staticmethod
    async def _call_stdio_async(details, timeout_ms, tool_name, arguments):
        """Call one tool through a short-lived MCP stdio session."""
        command = str(details.get("command") or "").strip()
        args = details.get("args", [])
        if not command or not isinstance(args, list):
            raise ValueError("The MCP service has no usable command.")
        environment = details.get("environment")
        if not isinstance(environment, dict):
            environment = None
        parameters = StdioServerParameters(
            command=command,
            args=[str(argument) for argument in args],
            env=environment,
            cwd=details.get("cwd") or None,
        )
        with open(os.devnull, "w", encoding="utf-8") as stderr:
            async with asyncio.timeout(timeout_ms / 1000):
                async with stdio_client(parameters, errlog=stderr) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
        return result.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )

    @staticmethod
    async def _call_http_async(
        details,
        timeout_ms,
        tool_name,
        arguments,
        endpoint=None,
    ):
        """Call one tool through MCP streamable HTTP."""
        url = str(
            details.get("url")
            or details.get("endpoint")
            or endpoint
            or ""
        ).strip()
        if not url:
            raise ValueError("The MCP service has no streamable HTTP URL.")
        headers = details.get("headers")
        if not isinstance(headers, dict):
            headers = None
        async with asyncio.timeout(timeout_ms / 1000):
            async with streamablehttp_client(
                url,
                headers=headers,
                timeout=timeout_ms / 1000,
            ) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
        return result.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )

    def call_tool(
        self,
        name,
        tool_name,
        arguments,
        settings=None,
    ):
        """Execute a registered Custom MCP tool with saved service settings."""
        services = self.services()
        if name not in services:
            raise ValueError("Unknown MCP service.")
        details = services[name]
        if details.get("disabled") is True:
            raise ValueError("The MCP service is disabled.")
        if not isinstance(arguments, dict):
            raise ValueError("MCP tool arguments must be an object.")

        settings = settings if isinstance(settings, dict) else {}
        timeout_ms = self._timeout_ms(details, settings.get("timeout_ms"))
        endpoint = self._configured_endpoint(
            name,
            details,
            settings.get("endpoint"),
        )
        if name == "postgres":
            details = self._details_with_postgres_endpoint(
                details,
                endpoint,
                settings.get("user", ""),
                settings.get("password", ""),
            )
        try:
            if self._uses_http_transport(details):
                return asyncio.run(
                    self._call_http_async(
                        details,
                        timeout_ms,
                        tool_name,
                        arguments,
                        endpoint,
                    )
                )
            return asyncio.run(
                self._call_stdio_async(
                    details,
                    timeout_ms,
                    tool_name,
                    arguments,
                )
            )
        except Exception as error:
            LOGGER.warning(
                "MCP tool call failed for service=%s tool=%s: %s",
                name,
                tool_name,
                error,
            )
            raise RuntimeError(
                f"MCP tool {name}::{tool_name} failed: {error}"
            ) from error

    def check(
        self,
        name,
        endpoint=None,
        timeout_ms=None,
        user="",
        password="",
    ):
        """Check one registered service and any required local endpoint."""
        services = self.services()
        if name not in services:
            raise ValueError("Unknown MCP service.")
        details = services[name]
        if details.get("disabled") is True:
            return {"name": name, "online": False, "status_code": None}
        timeout_ms = self._timeout_ms(details, timeout_ms)
        configured_endpoint = self._configured_endpoint(name, details, endpoint)
        status_code = None
        if name in {"searxng", "comfyui"}:
            endpoint_online, status_code = self._check_http_endpoint(
                name,
                configured_endpoint,
                timeout_ms,
            )
            if not endpoint_online:
                return {"name": name, "online": False, "status_code": status_code}
        elif name == "postgres":
            if not self._check_postgres_endpoint(configured_endpoint, timeout_ms):
                return {"name": name, "online": False, "status_code": None}
            details = self._details_with_postgres_endpoint(
                details,
                configured_endpoint,
                user,
                password,
            )

        if self._uses_http_transport(details):
            tools_count = len(
                self._discover_transport(
                    details,
                    timeout_ms,
                    configured_endpoint,
                )
            )
        else:
            tools_count = self._check_stdio(details, timeout_ms)
        return {
            "name": name,
            "online": tools_count > 0,
            "status_code": status_code,
            "tools_count": tools_count,
        }

    def discover_tools(
        self,
        name,
        endpoint=None,
        timeout_ms=None,
        user="",
        password="",
    ):
        """Read full tool definitions from one accessible Custom MCP service."""
        services = self.services()
        if name not in services:
            raise ValueError("Unknown MCP service.")
        details = services[name]
        if details.get("disabled") is True:
            return {"name": name, "online": False, "tools": []}
        timeout_ms = self._timeout_ms(details, timeout_ms)
        configured_endpoint = self._configured_endpoint(name, details, endpoint)
        status_code = None
        if name in {"searxng", "comfyui"}:
            endpoint_online, status_code = self._check_http_endpoint(
                name,
                configured_endpoint,
                timeout_ms,
            )
            if not endpoint_online:
                return {
                    "name": name,
                    "online": False,
                    "status_code": status_code,
                    "tools": [],
                }
        elif name == "postgres":
            if not self._check_postgres_endpoint(configured_endpoint, timeout_ms):
                return {
                    "name": name,
                    "online": False,
                    "status_code": None,
                    "tools": [],
                }
            details = self._details_with_postgres_endpoint(
                details,
                configured_endpoint,
                user,
                password,
            )

        tools = self._discover_transport(
            details,
            timeout_ms,
            configured_endpoint,
        )
        return {
            "name": name,
            "online": bool(tools),
            "status_code": status_code,
            "tools": tools,
        }

    def check_managed_service(self, name, endpoint, timeout_ms=3000):
        """Check an API required by a provider-managed MCP service."""
        name = str(name or "").strip()
        endpoint = str(endpoint or "").strip().rstrip("/")
        if name != "searxng":
            return {"name": name, "online": True, "status_code": None}
        parsed = urllib.parse.urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("A valid SearXNG endpoint is required.")
        try:
            parsed_timeout = int(timeout_ms)
        except (TypeError, ValueError) as error:
            raise ValueError("MCP timeout must be a positive integer.") from error
        if parsed_timeout < 1:
            raise ValueError("MCP timeout must be a positive integer.")
        health_url = f"{endpoint}/search?q=AxelRudiPell&format=json"
        health_request = urllib.request.Request(
            health_url,
            headers={"Accept": "application/json"},
        )
        try:
            with self.opener(
                health_request,
                timeout=parsed_timeout / 1000,
            ) as response:
                status_code = int(getattr(response, "status", 0) or 0)
        except (OSError, TimeoutError, urllib.error.URLError):
            return {"name": name, "online": False, "status_code": None}
        return {
            "name": name,
            "online": status_code == 200,
            "status_code": status_code,
        }


MCP_SERVICES = McpServiceRegistry()
