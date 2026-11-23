"""SQLite persistence for chat-scoped local media and external links."""

import re

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


TRAILING_PERCENT_ENCODING = re.compile(r"(?:%[0-9A-F]{2})+$", re.IGNORECASE)
FILE_PERCENT_POSTFIX = re.compile(
    r"(\.(?:avif|bmp|gif|jpe?g|png|svg|tiff?|webp|aac|flac|m4a|mp3|ogg|"
    r"opus|wav|avi|m4v|mkv|mov|mp4|webm|csv|docx?|xlsx?|pdf|pptx?|txt|zip))%.*$",
    re.IGNORECASE,
)


def normalize_external_locator(value):
    """Clean trailing encoded or Markdown punctuation from an external URL."""
    locator = str(value or "").strip().rstrip("`.,;:!?)]}")
    locator = FILE_PERCENT_POSTFIX.sub(r"\1", locator)
    return TRAILING_PERCENT_ENCODING.sub("", locator)


MEDIA_SCHEMA = """
CREATE TABLE IF NOT EXISTS media_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL CHECK (source IN ('preview', 'generated', 'external')),
    locator TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (
        category IN ('image', 'audio', 'video', 'document', 'external')
    ),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, locator)
);

CREATE TABLE IF NOT EXISTS media_references (
    media_id INTEGER NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('active', 'saved')),
    scope_name TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (media_id, scope_type, scope_name)
);

CREATE TABLE IF NOT EXISTS media_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS media_references_scope
ON media_references(scope_type, scope_name);
"""


MEDIA_STORE = SQLiteStore(
    "MEDIA_DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "media.db",
    schema=MEDIA_SCHEMA,
)


class MediaRepository:
    """Store canonical media items and references from active or saved chats."""

    def __init__(self, store=MEDIA_STORE):
        self.store = store

    @staticmethod
    def _scope(scope_type, scope_name=""):
        if scope_type not in {"active", "saved"}:
            raise ValueError("Media scope must be active or saved.")
        return scope_type, str(scope_name or "") if scope_type == "saved" else ""

    @staticmethod
    def _record(item):
        source = str(item.get("source") or "").strip()
        locator = str(item.get("locator") or "").strip()
        name = str(item.get("name") or locator).strip()
        category = str(item.get("category") or "document").strip()
        if source not in {"preview", "generated", "external"}:
            return None
        if source == "external":
            locator = normalize_external_locator(locator)
            name = locator
            category = "external"
        if not locator or not name:
            return None
        if category not in {"image", "audio", "video", "document", "external"}:
            category = "document"
        return source, locator, name, category

    def list(self, scope_type="active", scope_name=""):
        """Return the media records referenced by one chat scope."""
        scope_type, scope_name = self._scope(scope_type, scope_name)
        if not self.store.path().exists():
            return []
        rows = self.store.fetch(
            """
            SELECT item.source, item.locator, item.name, item.category
            FROM media_references AS reference
            JOIN media_items AS item ON item.id = reference.media_id
            WHERE reference.scope_type = ? AND reference.scope_name = ?
            ORDER BY item.id
            """,
            (scope_type, scope_name),
        )
        return [
            {
                "source": row[0],
                "locator": row[1],
                "name": row[2],
                "category": row[3],
            }
            for row in rows
        ]

    def add(self, records, scope_type="active", scope_name=""):
        """Add media references to a chat without replacing existing ones."""
        scope_type, scope_name = self._scope(scope_type, scope_name)
        normalized = [self._record(item) for item in records or []]
        normalized = [item for item in normalized if item is not None]
        if not normalized:
            return
        with self.store.transaction() as connection:
            self._add(connection, normalized, scope_type, scope_name)

    def replace(self, records, scope_type="active", scope_name=""):
        """Replace one chat's references and return orphaned preview locators."""
        scope_type, scope_name = self._scope(scope_type, scope_name)
        normalized = [self._record(item) for item in records or []]
        normalized = [item for item in normalized if item is not None]
        with self.store.transaction() as connection:
            previous = connection.execute(
                """
                SELECT item.id, item.source, item.locator
                FROM media_references AS reference
                JOIN media_items AS item ON item.id = reference.media_id
                WHERE reference.scope_type = ? AND reference.scope_name = ?
                """,
                (scope_type, scope_name),
            ).fetchall()
            connection.execute(
                "DELETE FROM media_references WHERE scope_type = ? AND scope_name = ?",
                (scope_type, scope_name),
            )
            self._add(connection, normalized, scope_type, scope_name)
            orphaned_previews = []
            for media_id, source, locator in previous:
                reference = connection.execute(
                    "SELECT 1 FROM media_references WHERE media_id = ? LIMIT 1",
                    (media_id,),
                ).fetchone()
                if reference:
                    continue
                if source == "preview":
                    orphaned_previews.append(locator)
                connection.execute("DELETE FROM media_items WHERE id = ?", (media_id,))
        return orphaned_previews

    def copy(self, source_type, source_name, target_type, target_name):
        """Replace a target chat's references with another chat's references."""
        return self.replace(
            self.list(source_type, source_name),
            target_type,
            target_name,
        )

    def delete(self, scope_type="active", scope_name=""):
        """Delete one chat's references and return orphaned preview locators."""
        return self.replace([], scope_type, scope_name)

    @staticmethod
    def _add(connection, records, scope_type, scope_name):
        for source, locator, name, category in records:
            connection.execute(
                """
                INSERT INTO media_items (source, locator, name, category)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source, locator) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category
                """,
                (source, locator, name, category),
            )
            media_id = connection.execute(
                "SELECT id FROM media_items WHERE source = ? AND locator = ?",
                (source, locator),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT OR IGNORE INTO media_references
                    (media_id, scope_type, scope_name)
                VALUES (?, ?, ?)
                """,
                (media_id, scope_type, scope_name),
            )

    def metadata(self, key, value=None):
        """Read a metadata value, or persist it when value is supplied."""
        if value is not None:
            self.store.execute(
                """
                INSERT INTO media_metadata (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )
            return str(value)
        if not self.store.path().exists():
            return None
        row = self.store.fetch(
            "SELECT value FROM media_metadata WHERE key = ?",
            (key,),
            one=True,
        )
        return row[0] if row else None


MEDIA = MediaRepository()
