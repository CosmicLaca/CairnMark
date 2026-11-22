"""SQLite persistence for benchmark organization metadata."""

import sqlite3

from models.sqlite_store import SQLiteStore


SCHEMA = """
CREATE TABLE IF NOT EXISTS benchmark_metadata (
    filename TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('Easy', 'Normal', 'Hard')),
    notes TEXT NOT NULL DEFAULT '',
    generation_prompt TEXT NOT NULL DEFAULT '',
    model_name TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS benchmark_categories (
    name TEXT PRIMARY KEY COLLATE NOCASE
)
"""

LATER_COLUMNS = {
    "generation_prompt": "TEXT NOT NULL DEFAULT ''",
    "model_name": "TEXT NOT NULL DEFAULT ''",
}


STORE = SQLiteStore(
    "DATABASE_PATH",
    schema=SCHEMA,
    columns={"benchmark_metadata": LATER_COLUMNS},
    row_factory=sqlite3.Row,
)


_UNSET = object()


class BenchmarkMetadataRepository:
    """Persist editable metadata and user-created category names."""

    def __init__(self, store=STORE):
        self.store = store

    def metadata(self, filename, values=_UNSET):
        """Read one metadata record, or save it when values are supplied."""
        if values is _UNSET:
            row = self.store.fetch(
                """
                SELECT filename, category, difficulty, notes,
                       generation_prompt, model_name, updated_at
                FROM benchmark_metadata
                WHERE filename = ?
                """,
                (filename,),
                one=True,
            )
            return dict(row) if row else None

        self.store.execute(
            """
            INSERT INTO benchmark_metadata (
                filename, category, difficulty, notes,
                generation_prompt, model_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                category = excluded.category,
                difficulty = excluded.difficulty,
                notes = excluded.notes,
                generation_prompt = excluded.generation_prompt,
                model_name = excluded.model_name,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                filename,
                values["category"],
                values["difficulty"],
                values.get("notes", ""),
                values.get("generation_prompt", ""),
                values.get("model_name", ""),
            ),
        )
        return {"filename": filename, **values}

    def for_files(self, filenames):
        """Return metadata indexed by filename for requested benchmark files."""
        filenames = tuple(filenames)
        if not filenames:
            return {}
        placeholders = ", ".join("?" for _filename in filenames)
        rows = self.store.fetch(
            f"""
            SELECT filename, category, difficulty, notes,
                   generation_prompt, model_name, updated_at
            FROM benchmark_metadata
            WHERE filename IN ({placeholders})
            """,
            filenames,
        )
        return {row["filename"]: dict(row) for row in rows}

    def categories(self):
        """Return saved category names in case-insensitive order."""
        rows = self.store.fetch(
            """
            SELECT name AS category FROM benchmark_categories
            UNION
            SELECT category FROM benchmark_metadata
            WHERE category != 'Uncategorized'
            """
        )
        unique = {}
        for row in rows:
            unique.setdefault(row["category"].casefold(), row["category"])
        return sorted(unique.values(), key=str.casefold)

    def category(self, name):
        """Persist one category and return its stored spelling."""
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO benchmark_categories (name) VALUES (?)",
                (name,),
            )
            row = connection.execute(
                """
                SELECT name FROM benchmark_categories
                WHERE name COLLATE NOCASE = ?
                """,
                (name,),
            ).fetchone()
        return row["name"]


BENCHMARK_METADATA = BenchmarkMetadataRepository()
