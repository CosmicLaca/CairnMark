"""SQLite persistence for provider-specific model configurations."""

from contextlib import closing

from models.sqlite_store import SQLiteStore
from services.token_encryption import encrypt_token, decrypt_token


SCHEMA = """
        CREATE TABLE IF NOT EXISTS model_configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_name TEXT NOT NULL,
            model_name TEXT NOT NULL,
            is_enabled BOOLEAN DEFAULT 1,
            size_gb INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
"""

INDEX = """
        CREATE INDEX IF NOT EXISTS idx_provider_model 
        ON model_configurations (provider_name, model_name)
"""

PROVIDER_SCHEMA = """
        CREATE TABLE IF NOT EXISTS provider_configurations (
            provider_name TEXT PRIMARY KEY,
            server_ip TEXT NOT NULL,
            server_port INTEGER NOT NULL,
            api_key TEXT,
            is_enabled BOOLEAN NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
"""


def _migrate(connection):
    """Add provider columns introduced after the initial schema."""
    provider_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(provider_configurations)"
        ).fetchall()
    }
    if "api_key" not in provider_columns:
        connection.execute(
            "ALTER TABLE provider_configurations ADD COLUMN api_key TEXT"
        )
    model_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(model_configurations)"
        ).fetchall()
    }
    if "size_gb" not in model_columns:
        connection.execute(
            "ALTER TABLE model_configurations ADD COLUMN size_gb INTEGER"
        )


STORE = SQLiteStore(
    "DATABASE_PATH",
    schema=";\n".join((SCHEMA, INDEX, PROVIDER_SCHEMA)),
    migrate=_migrate,
)


def save_model_list(models, provider_name="llama.cpp"):
    """Save model list to database with their enabled states and sizes."""
    with closing(STORE.connect()) as connection:
        connection.execute(
            "DELETE FROM model_configurations WHERE provider_name = ?",
            (provider_name,),
        )
        connection.executemany(
            """
            INSERT INTO model_configurations
                (provider_name, model_name, is_enabled, size_gb)
            VALUES (?, ?, ?, ?)
            """,
            (
                (
                    provider_name,
                    model.get("id") or model.get("name") or "unknown",
                    bool(model.get("enabled", True)),
                    model.get("size_gb"),
                )
                for model in models
            ),
        )
        connection.commit()


def get_saved_model_configuration(provider_name="llama.cpp"):
    """Retrieve saved model configuration for a specific provider."""
    with closing(STORE.connect()) as connection:
        rows = connection.execute(
            """
            SELECT model_name, is_enabled, size_gb
            FROM model_configurations
            WHERE provider_name = ?
            ORDER BY model_name
            """,
            (provider_name,),
        ).fetchall()
    return [
        {
            "name": model_name,
            "enabled": bool(is_enabled),
            "size_gb": size_gb,
        }
        for model_name, is_enabled, size_gb in rows
    ]


def get_active_model_configurations():
    """Return enabled models that belong to enabled providers."""
    with closing(STORE.connect()) as connection:
        rows = connection.execute(
            """
            SELECT models.provider_name, models.model_name, models.size_gb
            FROM model_configurations AS models
            JOIN provider_configurations AS providers
              ON providers.provider_name = models.provider_name
            WHERE providers.is_enabled = 1
              AND models.is_enabled = 1
            ORDER BY models.provider_name COLLATE NOCASE,
                     models.model_name COLLATE NOCASE
            """
        ).fetchall()
    return [
        {
            "provider": provider_name,
            "model": model_name,
            "size_gb": size_gb,
        }
        for provider_name, model_name, size_gb in rows
    ]


def get_model_configuration_summary(provider_name="llama.cpp"):
    """Return total and enabled model counts for one provider."""
    with closing(STORE.connect()) as connection:
        total, enabled = connection.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(is_enabled), 0)
            FROM model_configurations
            WHERE provider_name = ?
            """,
            (provider_name,),
        ).fetchone()
    return {"total": total, "enabled": enabled}


def save_provider_configuration(
    provider_name,
    server_ip,
    server_port,
    api_key=None,
):
    """Save a provider connection, preserving an omitted API key."""
    with closing(STORE.connect()) as connection:
        connection.execute(
            """
            INSERT INTO provider_configurations
                (provider_name, server_ip, server_port, api_key)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(provider_name) DO UPDATE SET
                server_ip = excluded.server_ip,
                server_port = excluded.server_port,
                api_key = COALESCE(excluded.api_key, provider_configurations.api_key),
                updated_at = CURRENT_TIMESTAMP
            """,
            (provider_name, server_ip, server_port, encrypt_token(api_key)),
        )
        connection.commit()


def get_provider_configuration(provider_name):
    """Return one saved provider endpoint and its enabled state."""
    with closing(STORE.connect()) as connection:
        row = connection.execute(
            """
            SELECT provider_name, server_ip, server_port, api_key, is_enabled
            FROM provider_configurations
            WHERE provider_name = ?
            """,
            (provider_name,),
        ).fetchone()
    if not row:
        return None
    return {
        "provider": row[0],
        "ip": row[1],
        "port": row[2],
        "api_key": decrypt_token(row[3]),
        "enabled": bool(row[4]),
    }


def set_provider_enabled(provider_name, is_enabled):
    """Persist the overall enabled state for a configured provider."""
    with closing(STORE.connect()) as connection:
        cursor = connection.execute(
            """
            UPDATE provider_configurations
            SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE provider_name = ?
            """,
            (bool(is_enabled), provider_name),
        )
        connection.commit()
    return cursor.rowcount > 0
