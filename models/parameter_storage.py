"""SQLite persistence for cached model generation parameters."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import current_app

from config import PROJECT_ROOT


PARAMETER_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_parameters (
    parameter_key TEXT PRIMARY KEY,
    parameters TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def _database_path():
    """Return the parameter database configured for the active application."""
    configured = current_app.config.get("PARAMETER_DATABASE_PATH")
    if configured:
        path = Path(configured)
    else:
        path = PROJECT_ROOT / "instance" / "parameters.db"
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _connect():
    """Open the parameter database, creating it and its table on first use."""
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.executescript(PARAMETER_SCHEMA)
    connection.commit()
    return connection


def init_parameter_storage(app):
    """Record the parameter database path without creating the file."""
    database_path = Path(
        app.config.get(
            "PARAMETER_DATABASE_PATH",
            str(PROJECT_ROOT / "instance" / "parameters.db"),
        )
    )
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path
    app.config["PARAMETER_DATABASE_PATH"] = str(database_path)


def get_model_parameters(parameter_key):
    """Return saved default parameters for one ``provider::model`` key."""
    database_path = _database_path()
    if not database_path.exists():
        return None
    with closing(_connect()) as connection:
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
    with closing(_connect()) as connection:
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
    database_path = _database_path()
    if not database_path.exists():
        return False
    with closing(_connect()) as connection:
        cursor = connection.execute(
            "DELETE FROM model_parameters WHERE parameter_key = ?",
            (parameter_key,),
        )
        connection.commit()
        return cursor.rowcount > 0
