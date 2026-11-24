"""SQLite persistence for daily application update checks."""

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


SCHEMA = """
CREATE TABLE IF NOT EXISTS application_updates (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_checked_date TEXT NOT NULL DEFAULT '',
    local_commit TEXT NOT NULL DEFAULT '',
    remote_commit TEXT NOT NULL DEFAULT '',
    update_available INTEGER NOT NULL DEFAULT 0,
    update_in_progress INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    last_update_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

STORE = SQLiteStore(
    "DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "cairnmark.db",
    schema=SCHEMA,
)


class UpdateStorage:
    """Read and update the singleton application-update record."""

    def __init__(self, store=STORE):
        self.store = store

    def status(self):
        """Return cached update state without performing network work."""
        if not self.store.path().exists():
            return self._defaults()
        row = self.store.fetch(
            """
            SELECT last_checked_date, local_commit, remote_commit,
                   update_available, update_in_progress, last_error,
                   last_update_at
            FROM application_updates WHERE id = 1
            """,
            one=True,
        )
        if not row:
            return self._defaults()
        return {
            "last_checked_date": row[0] or "",
            "local_commit": row[1] or "",
            "remote_commit": row[2] or "",
            "update_available": bool(row[3]),
            "update_in_progress": bool(row[4]),
            "last_error": row[5] or "",
            "last_update_at": row[6],
        }

    def record_check(self, checked_date, local_commit, remote_commit, error=""):
        """Persist one daily remote comparison."""
        available = bool(
            local_commit
            and remote_commit
            and local_commit != remote_commit
            and not error
        )
        self.store.execute(
            """
            INSERT INTO application_updates (
                id, last_checked_date, local_commit, remote_commit,
                update_available, update_in_progress, last_error
            ) VALUES (1, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_checked_date = excluded.last_checked_date,
                local_commit = excluded.local_commit,
                remote_commit = excluded.remote_commit,
                update_available = excluded.update_available,
                update_in_progress = 0,
                last_error = excluded.last_error,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                checked_date,
                local_commit,
                remote_commit,
                int(available),
                error,
            ),
        )
        return self.status()

    def mark_started(self):
        """Mark the cached update as handed to the detached updater."""
        self.store.execute(
            """
            UPDATE application_updates
            SET update_in_progress = 1,
                last_error = '',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )

    @staticmethod
    def _defaults():
        return {
            "last_checked_date": "",
            "local_commit": "",
            "remote_commit": "",
            "update_available": False,
            "update_in_progress": False,
            "last_error": "",
            "last_update_at": None,
        }


UPDATE_STORAGE = UpdateStorage()
