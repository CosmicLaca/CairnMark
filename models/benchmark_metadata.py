"""SQLite persistence for benchmark organization metadata."""

import sqlite3
from contextlib import closing
from pathlib import Path

from flask import current_app


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


def _add_missing_columns(connection):
    """Add metadata columns introduced after the original schema."""
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(benchmark_metadata)")
    }
    for column, definition in LATER_COLUMNS.items():
        if column not in existing_columns:
            connection.execute(
                f"ALTER TABLE benchmark_metadata "
                f"ADD COLUMN {column} {definition}"
            )


def _database_path():
    """Return the configured database as a concrete filesystem path."""
    return Path(current_app.config["DATABASE_PATH"])


def _connect():
    """Open a configured SQLite connection with named-column rows."""
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_database(app):
    """Create the instance database and metadata table for an application."""
    database_path = Path(app.config["DATABASE_PATH"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA)
        _add_missing_columns(connection)
        connection.commit()


def get_benchmark_metadata(filename):
    """Return saved metadata for one benchmark, or ``None`` when unsaved."""
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT filename, category, difficulty, notes,
                   generation_prompt, model_name, updated_at
            FROM benchmark_metadata
            WHERE filename = ?
            """,
            (filename,),
        ).fetchone()
    return dict(row) if row else None


def get_metadata_for_files(filenames):
    """Return metadata indexed by filename for the requested benchmarks."""
    filenames = tuple(filenames)
    if not filenames:
        return {}

    placeholders = ", ".join("?" for _filename in filenames)
    with closing(_connect()) as connection:
        rows = connection.execute(
            f"""
            SELECT filename, category, difficulty, notes,
                   generation_prompt, model_name, updated_at
            FROM benchmark_metadata
            WHERE filename IN ({placeholders})
            """,
            filenames,
        ).fetchall()
    return {row["filename"]: dict(row) for row in rows}


def list_categories():
    """Return saved category names in case-insensitive order."""
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT name AS category
            FROM benchmark_categories
            UNION
            SELECT category
            FROM benchmark_metadata
            WHERE category != 'Uncategorized'
            """
        ).fetchall()
    unique = {}
    for row in rows:
        unique.setdefault(row["category"].casefold(), row["category"])
    return sorted(unique.values(), key=str.casefold)


def save_category(name):
    """Persist one category and return its stored spelling."""
    with closing(_connect()) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO benchmark_categories (name) VALUES (?)",
            (name,),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT name
            FROM benchmark_categories
            WHERE name COLLATE NOCASE = ?
            """,
            (name,),
        ).fetchone()
    return row["name"]


def save_benchmark_metadata(
    filename,
    category,
    difficulty,
    notes,
    generation_prompt,
    model_name,
):
    """Create or replace the editable metadata for one benchmark file."""
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO benchmark_metadata (
                filename,
                category,
                difficulty,
                notes,
                generation_prompt,
                model_name
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
                category,
                difficulty,
                notes,
                generation_prompt,
                model_name,
            ),
        )
        connection.commit()
