"""SQLite repository for provider and model configurations."""

from models.sqlite_store import SQLiteStore
from services.token_encryption import decrypt_token, encrypt_token


SCHEMA = """
CREATE TABLE IF NOT EXISTS model_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    is_enabled BOOLEAN DEFAULT 1,
    size_gb INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_provider_model
ON model_configurations (provider_name, model_name);

CREATE TABLE IF NOT EXISTS provider_configurations (
    provider_name TEXT PRIMARY KEY,
    display_name TEXT,
    is_custom BOOLEAN NOT NULL DEFAULT 0,
    server_ip TEXT NOT NULL,
    server_port INTEGER NOT NULL,
    api_key TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS provider_setup_preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    selected_provider TEXT NOT NULL DEFAULT 'all',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_selector_preferences (
    page TEXT PRIMARY KEY,
    selected_provider TEXT NOT NULL DEFAULT 'all',
    selected_model TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


LATER_COLUMNS = {
    "provider_configurations": {
        "api_key": "TEXT",
        "display_name": "TEXT",
        "is_custom": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "model_configurations": {
        "size_gb": "INTEGER",
    },
    "model_selector_preferences": {
        "selected_model": "TEXT NOT NULL DEFAULT ''",
    },
}


def _migrate_model_selector_preferences(connection):
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(model_selector_preferences)"
        )
    }
    if columns and "page" not in columns:
        connection.execute("DROP TABLE model_selector_preferences")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS model_selector_preferences (
            page TEXT PRIMARY KEY,
            selected_provider TEXT NOT NULL DEFAULT 'all',
            selected_model TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


STORE = SQLiteStore(
    "DATABASE_PATH",
    schema=SCHEMA,
    columns=LATER_COLUMNS,
    migrate=_migrate_model_selector_preferences,
)
_UNSET = object()


class ModelConfigurationRepository:
    """Persist model lists and provider connections in one database boundary."""

    def __init__(self, store=STORE):
        self.store = store

    def models(self, provider="llama.cpp", values=_UNSET):
        """Read a provider's models, or replace them when values are supplied."""
        if values is _UNSET:
            rows = self.store.fetch(
                """
                SELECT model_name, is_enabled, size_gb
                FROM model_configurations
                WHERE provider_name = ?
                ORDER BY model_name
                """,
                (provider,),
            )
            return [
                {"name": name, "enabled": bool(enabled), "size_gb": size_gb}
                for name, enabled, size_gb in rows
            ]

        with self.store.transaction() as connection:
            connection.execute(
                "DELETE FROM model_configurations WHERE provider_name = ?",
                (provider,),
            )
            connection.executemany(
                """
                INSERT INTO model_configurations
                    (provider_name, model_name, is_enabled, size_gb)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (
                        provider,
                        model.get("id") or model.get("name") or "unknown",
                        bool(model.get("enabled", True)),
                        model.get("size_gb"),
                    )
                    for model in values
                ),
            )

    def active(self):
        """Return enabled models belonging to enabled providers."""
        rows = self.store.fetch(
            """
            SELECT models.provider_name, models.model_name, models.size_gb
            FROM model_configurations AS models
            JOIN provider_configurations AS providers
              ON providers.provider_name = models.provider_name
            WHERE providers.is_enabled = 1 AND models.is_enabled = 1
            ORDER BY models.provider_name COLLATE NOCASE,
                     models.model_name COLLATE NOCASE
            """
        )
        return [
            {"provider": provider, "model": model, "size_gb": size_gb}
            for provider, model, size_gb in rows
        ]

    def summary(self, provider="llama.cpp"):
        """Return total and enabled model counts for one provider."""
        total, enabled = self.store.fetch(
            """
            SELECT COUNT(*), COALESCE(SUM(is_enabled), 0)
            FROM model_configurations
            WHERE provider_name = ?
            """,
            (provider,),
            one=True,
        )
        return {"total": total, "enabled": enabled}

    def provider(self, name, values=_UNSET):
        """Read a provider connection, or save it when values are supplied."""
        if values is _UNSET:
            row = self.store.fetch(
                """
                SELECT provider_name, display_name, is_custom,
                       server_ip, server_port, api_key, is_enabled
                FROM provider_configurations
                WHERE provider_name = ?
                """,
                (name,),
                one=True,
            )
            if not row:
                return None
            return {
                "provider": row[0],
                "display_name": row[1] or row[0],
                "custom": bool(row[2]),
                "ip": row[3],
                "port": row[4],
                "api_key": decrypt_token(row[5]),
                "enabled": bool(row[6]),
            }

        self.store.execute(
            """
            INSERT INTO provider_configurations
                (provider_name, display_name, is_custom,
                 server_ip, server_port, api_key)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_name) DO UPDATE SET
                display_name = COALESCE(
                    excluded.display_name,
                    provider_configurations.display_name
                ),
                is_custom = MAX(
                    excluded.is_custom,
                    provider_configurations.is_custom
                ),
                server_ip = excluded.server_ip,
                server_port = excluded.server_port,
                api_key = COALESCE(excluded.api_key, provider_configurations.api_key),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                name,
                values.get("display_name"),
                bool(values.get("custom", False)),
                values["ip"],
                values["port"],
                encrypt_token(values.get("api_key")),
            ),
        )

    def custom_providers(self):
        """Return saved custom-provider identities in display order."""
        rows = self.store.fetch(
            """
            SELECT provider_name, display_name
            FROM provider_configurations
            WHERE is_custom = 1
            ORDER BY display_name COLLATE NOCASE, provider_name COLLATE NOCASE
            """
        )
        return [
            {"provider": provider, "display_name": display_name or provider}
            for provider, display_name in rows
        ]

    def set_enabled(self, provider, enabled):
        """Persist the overall enabled state for a configured provider."""
        rowcount, _lastrowid = self.store.execute(
            """
            UPDATE provider_configurations
            SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE provider_name = ?
            """,
            (bool(enabled), provider),
        )
        return rowcount > 0

    def setup_selection(self, provider=_UNSET):
        """Read or persist the provider selected in the setup workspace."""
        if provider is _UNSET:
            row = self.store.fetch(
                """
                SELECT selected_provider
                FROM provider_setup_preferences
                WHERE id = 1
                """,
                one=True,
            )
            return row[0] if row else "all"

        self.store.execute(
            """
            INSERT INTO provider_setup_preferences (id, selected_provider)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET
                selected_provider = excluded.selected_provider,
                updated_at = CURRENT_TIMESTAMP
            """,
            (provider,),
        )

    def model_selector_filter(self, page, provider=_UNSET):
        """Read or persist the provider selected in model selector dropdowns."""
        page = str(page or "all").strip() or "all"
        if provider is _UNSET:
            row = self.store.fetch(
                """
                SELECT selected_provider
                FROM model_selector_preferences
                WHERE page = ?
                """,
                (page,),
                one=True,
            )
            return row[0] if row else "all"

        self.store.execute(
            """
            INSERT INTO model_selector_preferences (page, selected_provider)
            VALUES (?, ?)
            ON CONFLICT(page) DO UPDATE SET
                selected_provider = excluded.selected_provider,
                updated_at = CURRENT_TIMESTAMP
            """,
            (page, provider),
        )

    def model_selector_model(self, page, model=_UNSET):
        """Read or persist the model selected in a page's model selector."""
        page = str(page or "all").strip() or "all"
        if model is _UNSET:
            row = self.store.fetch(
                """
                SELECT selected_model
                FROM model_selector_preferences
                WHERE page = ?
                """,
                (page,),
                one=True,
            )
            return row[0] if row else ""

        self.store.execute(
            """
            INSERT INTO model_selector_preferences (page, selected_model)
            VALUES (?, ?)
            ON CONFLICT(page) DO UPDATE SET
                selected_model = excluded.selected_model,
                updated_at = CURRENT_TIMESTAMP
            """,
            (page, model),
        )


MODEL_CONFIGURATIONS = ModelConfigurationRepository()
