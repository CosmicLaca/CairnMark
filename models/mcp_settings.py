"""SQLite persistence for MCP service and tool preferences."""

import json
import sqlite3
from pathlib import Path

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


MCP_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_settings (
    source TEXT NOT NULL,
    service_name TEXT NOT NULL,
    tool_name TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 0,
    settings TEXT NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source, service_name, tool_name)
);
CREATE TABLE IF NOT EXISTS mcp_tool_cache (
    service_name TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    definition TEXT NOT NULL DEFAULT '{}',
    refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (service_name, tool_name)
)
"""


class McpSettingsStore(SQLiteStore):
    """Keep MCP preferences isolated and migrate the legacy main-DB table."""

    def configure(self, app, *, create=True):
        """Create the tools database and move legacy MCP rows into it once."""
        super().configure(app, create=create)
        if create:
            self._migrate_legacy_table(app.config)

    def _migrate_legacy_table(self, config):
        target_path = self.path(config)
        legacy_path = Path(config["DATABASE_PATH"])
        if target_path == legacy_path or not legacy_path.is_file():
            return

        with sqlite3.connect(legacy_path) as legacy_connection:
            table_exists = legacy_connection.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = 'mcp_settings'"
            ).fetchone()
            if table_exists is None:
                return
            rows = legacy_connection.execute(
                """
                SELECT source, service_name, tool_name, enabled, settings,
                       updated_at
                FROM mcp_settings
                """
            ).fetchall()
            with sqlite3.connect(target_path) as target_connection:
                target_connection.executemany(
                    """
                    INSERT INTO mcp_settings (
                        source, service_name, tool_name, enabled, settings,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, service_name, tool_name) DO NOTHING
                    """,
                    rows,
                )
            legacy_connection.execute("DROP TABLE mcp_settings")


STORE = McpSettingsStore(
    "TOOLS_DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "tools.db",
    schema=MCP_SETTINGS_SCHEMA,
)


class McpSettingsRepository:
    """Read and upsert independently keyed MCP preferences."""

    def __init__(self, store=STORE):
        self.store = store

    def all(self):
        """Return every saved service and tool preference."""
        rows = self.store.fetch(
            """
            SELECT source, service_name, tool_name, enabled, settings
            FROM mcp_settings
            ORDER BY source, service_name, tool_name
            """
        )
        records = []
        for source, service_name, tool_name, enabled, settings_text in rows:
            try:
                settings = json.loads(settings_text)
            except (TypeError, ValueError):
                settings = {}
            records.append(
                {
                    "source": source,
                    "service": service_name,
                    "tool": tool_name,
                    "enabled": bool(enabled),
                    "settings": settings if isinstance(settings, dict) else {},
                }
            )
        return records

    def upsert(self, records):
        """Insert or update the supplied accessible MCP records."""
        if not records:
            return 0
        values = [
            (
                record["source"],
                record["service"],
                record.get("tool", ""),
                int(record["enabled"]),
                json.dumps(record.get("settings", {}), ensure_ascii=False),
            )
            for record in records
        ]
        rowcount, _lastrowid = self.store.execute(
            """
            INSERT INTO mcp_settings (
                source, service_name, tool_name, enabled, settings
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source, service_name, tool_name) DO UPDATE SET
                enabled = excluded.enabled,
                settings = excluded.settings,
                updated_at = CURRENT_TIMESTAMP
            """,
            values,
            many=True,
        )
        return rowcount

    def cached_tools(self, service_name=None):
        """Return cached Custom MCP tool definitions."""
        statement = (
            "SELECT service_name, tool_name, definition "
            "FROM mcp_tool_cache"
        )
        parameters = ()
        if service_name:
            statement += " WHERE service_name = ?"
            parameters = (service_name,)
        statement += " ORDER BY service_name, tool_name"
        rows = self.store.fetch(statement, parameters)
        tools = []
        for service, tool_name, definition_text in rows:
            try:
                definition = json.loads(definition_text)
            except (TypeError, ValueError):
                definition = {}
            tools.append(
                {
                    "service": service,
                    "tool": tool_name,
                    "definition": (
                        definition if isinstance(definition, dict) else {}
                    ),
                }
            )
        return tools

    def replace_cached_tools(self, service_name, tools):
        """Atomically replace one accessible service's cached tool snapshot."""
        values = [
            (
                service_name,
                tool["name"],
                json.dumps(tool, ensure_ascii=False),
            )
            for tool in tools
            if isinstance(tool, dict) and str(tool.get("name") or "").strip()
        ]
        with self.store.transaction() as connection:
            connection.execute(
                "DELETE FROM mcp_tool_cache WHERE service_name = ?",
                (service_name,),
            )
            if values:
                connection.executemany(
                    """
                    INSERT INTO mcp_tool_cache (
                        service_name, tool_name, definition
                    ) VALUES (?, ?, ?)
                    """,
                    values,
                )
        return len(values)


MCP_SETTINGS = McpSettingsRepository()
