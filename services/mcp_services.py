"""Manage private MCP server declarations and OpenCode imports."""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import PROJECT_ROOT


DEFAULT_MCP_TIMEOUT_MS = 10000
MCP_CONFIG_PATH = PROJECT_ROOT / "services" / "mcv.json"
OPENCODE_CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
MCP_HEALTH_URLS = {
    "searxng": "http://127.0.0.1:8888/search?q=AxelRudiPell&format=json",
}
MCP_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


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
                "mcpServers": self.services(),
                "opencode_import_available": False,
                "opencode_server_names": [],
            }
        discovered = self.opencode_services()
        return {
            "configured": False,
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

    def check(self, name):
        """Check one registered service using its configured timeout."""
        services = self.services()
        if name not in services:
            raise ValueError("Unknown MCP service.")
        health_url = MCP_HEALTH_URLS.get(name)
        if not health_url:
            return {"name": name, "online": False, "status_code": None}

        raw_timeout = services[name].get("timeout_ms", DEFAULT_MCP_TIMEOUT_MS)
        if isinstance(raw_timeout, bool):
            timeout_ms = DEFAULT_MCP_TIMEOUT_MS
        else:
            try:
                timeout_ms = int(raw_timeout)
            except (TypeError, ValueError):
                timeout_ms = DEFAULT_MCP_TIMEOUT_MS
        timeout_ms = max(1, timeout_ms)
        request = urllib.request.Request(
            health_url,
            headers={"Accept": "application/json"},
        )
        try:
            with self.opener(request, timeout=timeout_ms / 1000) as response:
                status_code = int(getattr(response, "status", 0) or 0)
        except (OSError, TimeoutError, urllib.error.URLError):
            return {"name": name, "online": False, "status_code": None}
        return {
            "name": name,
            "online": status_code == 200,
            "status_code": status_code,
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
