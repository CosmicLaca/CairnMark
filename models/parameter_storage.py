"""SQLite persistence for cached model generation parameters."""

import json
from contextlib import closing

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


PARAMETER_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_parameters (
    parameter_key TEXT PRIMARY KEY,
    parameters TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


STORE = SQLiteStore(
    "PARAMETER_DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "parameters.db",
    schema=PARAMETER_SCHEMA,
)


def get_model_parameters(parameter_key):
    """Return saved default parameters for one ``provider::model`` key."""
    database_path = STORE.path()
    if not database_path.exists():
        return None
    with closing(STORE.connect()) as connection:
        row = connection.execute(
            "SELECT parameters FROM model_parameters WHERE parameter_key = ?",
            (parameter_key,),
        ).fetchone()
    if not row:
        return None
    try:
        parameters = json.loads(row[0])
    except (TypeError, ValueError):
        return None
    return parameters if isinstance(parameters, dict) else None


def save_model_parameters(parameter_key, parameters):
    """Store every default parameter for one ``provider::model`` key."""
    payload = json.dumps(parameters, ensure_ascii=False)
    with closing(STORE.connect()) as connection:
        connection.execute(
            """
            INSERT INTO model_parameters (parameter_key, parameters)
            VALUES (?, ?)
            ON CONFLICT(parameter_key) DO UPDATE SET
                parameters = excluded.parameters,
                updated_at = CURRENT_TIMESTAMP
            """,
            (parameter_key, payload),
        )
        connection.commit()


def delete_model_parameters(parameter_key):
    """Remove saved default parameters for one ``provider::model`` key."""
    database_path = STORE.path()
    if not database_path.exists():
        return False
    with closing(STORE.connect()) as connection:
        cursor = connection.execute(
            "DELETE FROM model_parameters WHERE parameter_key = ?",
            (parameter_key,),
        )
        connection.commit()
        return cursor.rowcount > 0
