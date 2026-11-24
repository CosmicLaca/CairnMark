"""SQLite persistence for benchmark-creator generation settings."""

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


CREATE_BENCHMARK_DEFAULTS = {
    "temperature": 0.7,
    "top_p": 1.0,
    "top_k": 40,
    "seed": 4294967295,
    "min_p": 0.05,
    "randomize_seed": False,
    "create_log": False,
}
_NUMERIC_FIELDS = {
    "temperature": float,
    "top_p": float,
    "top_k": int,
    "seed": int,
    "min_p": float,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS create_benchmark_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    temperature REAL,
    top_p REAL,
    top_k INTEGER,
    seed INTEGER,
    min_p REAL,
    randomize_seed INTEGER NOT NULL DEFAULT 0,
    create_log INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

STORE = SQLiteStore(
    "DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "cairnmark.db",
    schema=SCHEMA,
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
            SELECT temperature, top_p, top_k, seed, min_p,
                   randomize_seed, create_log
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
            "seed": row[3],
            "min_p": row[4],
            "randomize_seed": bool(row[5]),
            "create_log": bool(row[6]),
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
        saved["randomize_seed"] = bool(values.get("randomize_seed", False))
        saved["create_log"] = bool(values.get("create_log", False))
        self.store.execute(
            """
            INSERT INTO create_benchmark_settings (
                id, temperature, top_p, top_k, seed, min_p,
                randomize_seed, create_log
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                temperature = excluded.temperature,
                top_p = excluded.top_p,
                top_k = excluded.top_k,
                seed = excluded.seed,
                min_p = excluded.min_p,
                randomize_seed = excluded.randomize_seed,
                create_log = excluded.create_log,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                saved["temperature"], saved["top_p"], saved["top_k"],
                saved["seed"], saved["min_p"], int(saved["randomize_seed"]),
                int(saved["create_log"]),
            ),
        )
        return saved


CREATE_BENCHMARK_SETTINGS = CreateBenchmarkSettingsRepository()
