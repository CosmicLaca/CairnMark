"""SQLite persistence for the displayed application version."""

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


SCHEMA = """
CREATE TABLE IF NOT EXISTS application_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    major INTEGER NOT NULL,
    minor INTEGER NOT NULL,
    patch INTEGER NOT NULL,
    commit_hash TEXT NOT NULL DEFAULT '',
    last_update_date TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

STORE = SQLiteStore(
    "DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "cairnmark.db",
    schema=SCHEMA,
)


class ApplicationInfoStorage:
    """Persist version progress independently from tracked metadata."""

    def __init__(self, store=STORE):
        self.store = store

    def status(self):
        """Return the stored version row, if one has been initialized."""
        row = self.store.fetch(
            """
            SELECT major, minor, patch, commit_hash, last_update_date
            FROM application_version WHERE id = 1
            """,
            one=True,
        )
        if not row:
            return None
        return {
            "major": row[0],
            "minor": row[1],
            "patch": row[2],
            "commit_hash": row[3] or "",
            "last_update_date": row[4],
        }

    def synchronize(
        self,
        *,
        major,
        minor,
        initial_patch,
        commit_hash,
        commit_increment,
        metadata_date,
        commit_date,
    ):
        """Apply manual release changes and automatic commit increments."""
        with self.store.transaction() as connection:
            row = connection.execute(
                """
                SELECT major, minor, patch, commit_hash, last_update_date
                FROM application_version WHERE id = 1
                """
            ).fetchone()
            if row is None:
                patch = initial_patch
                effective_commit = commit_hash
                update_date = metadata_date
            else:
                old_major, old_minor, old_patch, old_commit, old_date = row
                effective_commit = commit_hash or old_commit
                update_date = old_date
                if (major, minor) != (old_major, old_minor):
                    patch = 0
                    update_date = metadata_date
                elif old_commit and commit_hash and old_commit != commit_hash:
                    patch = old_patch + max(1, commit_increment)
                    update_date = commit_date
                else:
                    patch = old_patch

            connection.execute(
                """
                INSERT INTO application_version (
                    id, major, minor, patch, commit_hash, last_update_date
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    major = excluded.major,
                    minor = excluded.minor,
                    patch = excluded.patch,
                    commit_hash = excluded.commit_hash,
                    last_update_date = excluded.last_update_date,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    major,
                    minor,
                    patch,
                    effective_commit,
                    update_date,
                ),
            )
        return self.status()


APPLICATION_INFO_STORAGE = ApplicationInfoStorage()
