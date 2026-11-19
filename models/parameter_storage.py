"""SQLite repository for cached model generation parameters."""

import json

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
_UNSET = object()


class ModelParameterRepository:
    """Read, update, and remove cached model parameters."""

    def __init__(self, store=STORE):
        self.store = store

    def value(self, key, parameters=_UNSET):
        """Read one parameter dictionary, or save it when supplied."""
        if parameters is _UNSET:
            if not self.store.path().exists():
                return None
            row = self.store.fetch(
                "SELECT parameters FROM model_parameters WHERE parameter_key = ?",
                (key,),
                one=True,
            )
            if not row:
                return None
            try:
                value = json.loads(row[0])
            except (TypeError, ValueError):
                return None
            return value if isinstance(value, dict) else None

        self.store.execute(
            """
            INSERT INTO model_parameters (parameter_key, parameters)
            VALUES (?, ?)
            ON CONFLICT(parameter_key) DO UPDATE SET
                parameters = excluded.parameters,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, json.dumps(parameters, ensure_ascii=False)),
        )
        return parameters

    def delete(self, key):
        """Remove cached parameters for one provider/model key."""
        if not self.store.path().exists():
            return False
        rowcount, _lastrowid = self.store.execute(
            "DELETE FROM model_parameters WHERE parameter_key = ?",
            (key,),
        )
        return rowcount > 0


MODEL_PARAMETERS = ModelParameterRepository()
