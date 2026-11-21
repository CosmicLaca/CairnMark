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


MCP_SETTINGS = McpSettingsRepository()
