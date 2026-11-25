"""SQLite persistence for benchmark-creator form settings."""

import json

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


CREATE_BENCHMARK_DEFAULTS = {
    "temperature": 0.7,
    "top_p": 1.0,
    "top_k": 40,
    "min_p": 0.05,
    "create_log": False,
}
_NUMERIC_FIELDS = {
    "temperature": float,
    "top_p": float,
    "top_k": int,
    "min_p": float,
}

SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS create_benchmark_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    temperature REAL,
    top_p REAL,
    top_k INTEGER,
    min_p REAL,
    create_log INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA = SETTINGS_SCHEMA + """
CREATE TABLE IF NOT EXISTS create_benchmark_topics (
    category TEXT PRIMARY KEY COLLATE NOCASE,
    topics_json TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _remove_saved_seed_columns(connection):
    """Rebuild legacy creator settings without user-configurable seeds."""
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(create_benchmark_settings)"
        )
    }
    if not {"seed", "randomize_seed"} & columns:
        return
    connection.execute(
        "ALTER TABLE create_benchmark_settings "
        "RENAME TO create_benchmark_settings_legacy"
    )
    connection.executescript(SETTINGS_SCHEMA)
    connection.execute(
        """
        INSERT INTO create_benchmark_settings (
            id, temperature, top_p, top_k, min_p, create_log, updated_at
        )
        SELECT id, temperature, top_p, top_k, min_p, create_log, updated_at
        FROM create_benchmark_settings_legacy
        """
    )
    connection.execute("DROP TABLE create_benchmark_settings_legacy")

STORE = SQLiteStore(
    "DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "cairnmark.db",
    schema=SCHEMA,
    migrate=_remove_saved_seed_columns,
)


class CreateBenchmarkSettingsRepository:
    """Read and replace the creator-only singleton configuration."""

    def __init__(self, store=STORE):
        self.store = store

    def get(self):
        """Return saved creator settings or independent defaults."""
        if not self.store.path().exists():
            return dict(CREATE_BENCHMARK_DEFAULTS)
        row = self.store.fetch(
            """
            SELECT temperature, top_p, top_k, min_p, create_log
            FROM create_benchmark_settings WHERE id = 1
            """,
            one=True,
        )
        if not row:
            return dict(CREATE_BENCHMARK_DEFAULTS)
        return {
            "temperature": row[0],
            "top_p": row[1],
            "top_k": row[2],
            "min_p": row[3],
            "create_log": bool(row[4]),
        }

    def save(self, values):
        """Validate and replace the creator-only settings row."""
        saved = {}
        for name, converter in _NUMERIC_FIELDS.items():
            value = values.get(name, CREATE_BENCHMARK_DEFAULTS[name])
            if isinstance(value, str):
                value = value.strip() or None
            try:
                saved[name] = None if value is None else converter(value)
            except (TypeError, ValueError) as error:
                label = name.replace("_", " ").title()
                raise ValueError(f"{label} is invalid.") from error
        saved["create_log"] = bool(values.get("create_log", False))
        self.store.execute(
            """
            INSERT INTO create_benchmark_settings (
                id, temperature, top_p, top_k, min_p, create_log
            ) VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                temperature = excluded.temperature,
                top_p = excluded.top_p,
                top_k = excluded.top_k,
                min_p = excluded.min_p,
                create_log = excluded.create_log,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                saved["temperature"], saved["top_p"], saved["top_k"],
                saved["min_p"], int(saved["create_log"]),
            ),
        )
        return saved


class CreateBenchmarkTopicsRepository:
    """Store the latest benchmark topic rows for each category."""

    def __init__(self, store=STORE):
        self.store = store

    def get(self, category):
        """Return saved topic rows for a category, if any."""
        row = self.store.fetch(
            """
            SELECT topics_json
            FROM create_benchmark_topics
            WHERE category = ? COLLATE NOCASE
            """,
            (category,),
            one=True,
        )
        if not row:
            return None
        topics = json.loads(row[0])
        return topics if isinstance(topics, list) else None

    def save(self, category, topics):
        """Insert or replace a category's ordered topic rows."""
        saved = [
            {
                "name": str(topic.get("name") or "").strip(),
                "pairs": str(topic.get("pairs") or "").strip(),
            }
            for topic in topics
        ]
        self.store.execute(
            """
            INSERT INTO create_benchmark_topics (category, topics_json)
            VALUES (?, ?)
            ON CONFLICT(category) DO UPDATE SET
                category = excluded.category,
                topics_json = excluded.topics_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (category, json.dumps(saved, ensure_ascii=False)),
        )
        return saved


CREATE_BENCHMARK_SETTINGS = CreateBenchmarkSettingsRepository()
CREATE_BENCHMARK_TOPICS = CreateBenchmarkTopicsRepository()
