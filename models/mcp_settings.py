"""SQLite persistence for MCP service and tool preferences."""

import json

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
)
"""
STORE = SQLiteStore(
    "DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "cairnmark.db",
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


MCP_SETTINGS = McpSettingsRepository()
