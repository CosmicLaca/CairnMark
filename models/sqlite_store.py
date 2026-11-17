"""Shared SQLite connection and schema lifecycle support."""

import sqlite3
from pathlib import Path

from flask import current_app

from config import PROJECT_ROOT


class SQLiteStore:
    """Open one configured SQLite database and keep its schema current."""

    def __init__(
        self,
        config_key,
        *,
        schema="",
        migrate=None,
        default_path=None,
        row_factory=None,
    ):
        self.config_key = config_key
        self.schema = schema
        self.migrate = migrate
        self.default_path = default_path
        self.row_factory = row_factory

    def path(self, config=None):
        """Resolve this store's configured path against the project root."""
        if config is None:
            config = current_app.config
        configured = config.get(self.config_key) or self.default_path
        if configured is None:
            raise KeyError(f"Missing database configuration: {self.config_key}")
        path = Path(configured)
        return path if path.is_absolute() else PROJECT_ROOT / path

    def connect(self):
        """Open the database and safely apply idempotent schema updates."""
        return self._open(self.path())

    def configure(self, app, *, create=True):
        """Normalize the application path and optionally create the schema."""
        path = self.path(app.config)
        app.config[self.config_key] = str(path)
        if create:
            connection = self._open(path)
            connection.close()

    def _open(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA busy_timeout = 5000")
        if self.row_factory is not None:
            connection.row_factory = self.row_factory
        try:
            if self.schema:
                connection.executescript(self.schema)
            if self.migrate is not None:
                self.migrate(connection)
            connection.commit()
        except Exception:
            connection.close()
            raise
        return connection
