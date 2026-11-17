"""SQLite persistence for chat form and attachment defaults."""

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


CHAT_PARAMETER_DEFAULTS = {
    "temperature": 0.7,
    "top_p": 1.0,
    "top_k": 40,
    "seed": 4294967295,
    "history_limit": 4,
}

CHAT_PARAMETER_CONVERTERS = {
    "temperature": float,
    "top_p": float,
    "top_k": int,
    "seed": int,
    "history_limit": int,
}

CHAT_SETTINGS_COLUMNS = (
    "id",
    "model_name",
    "system_prompt",
    *CHAT_PARAMETER_DEFAULTS,
    "updated_at",
)

CHAT_SETTINGS_COLUMNS_SQL = """
    id INTEGER PRIMARY KEY CHECK (id = 1),
    model_name TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    temperature REAL,
    top_p REAL,
    top_k INTEGER,
    seed INTEGER,
    history_limit INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
"""

CHAT_SETTINGS_DEFAULT_SQL = {
    **{key: repr(value) for key, value in CHAT_PARAMETER_DEFAULTS.items()},
    "model_name": "''",
    "system_prompt": "''",
    "updated_at": "CURRENT_TIMESTAMP",
}

SETTINGS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS chat_settings ({CHAT_SETTINGS_COLUMNS_SQL});

CREATE TABLE IF NOT EXISTS chat_attachment_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    save_original_media INTEGER NOT NULL DEFAULT 0,
    attach_audio INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _migrate_chat_settings(connection):
    """Rebuild chat settings so every numeric parameter can be unset."""
    existing = {
        row[1]: row for row in connection.execute("PRAGMA table_info(chat_settings)")
    }
    if not existing:
        return
    parameter_columns = tuple(CHAT_PARAMETER_DEFAULTS)
    extra_columns = {column for column in existing if column not in CHAT_SETTINGS_COLUMNS}
    needs_rebuild = (
        any(column not in existing for column in CHAT_SETTINGS_COLUMNS)
        or any(existing[column][3] for column in parameter_columns)
        or bool(extra_columns)
    )
    if not needs_rebuild:
        return

    select_columns = ", ".join(
        column if column in existing else CHAT_SETTINGS_DEFAULT_SQL[column]
        for column in CHAT_SETTINGS_COLUMNS
    )
    connection.execute("DROP TABLE IF EXISTS chat_settings_new")
    connection.execute(f"CREATE TABLE chat_settings_new ({CHAT_SETTINGS_COLUMNS_SQL})")
    connection.execute(
        f"INSERT INTO chat_settings_new ({', '.join(CHAT_SETTINGS_COLUMNS)}) "
        f"SELECT {select_columns} FROM chat_settings"
    )
    connection.execute("DROP TABLE chat_settings")
    connection.execute("ALTER TABLE chat_settings_new RENAME TO chat_settings")


SETTINGS_STORE = SQLiteStore(
    "DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "cairnmark.db",
    schema=SETTINGS_SCHEMA,
    migrate=_migrate_chat_settings,
)


def _optional_number(value, converter):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return converter(value)


def get_chat_settings():
    """Return the saved chat form values or first-run defaults."""
    defaults = {"model_name": "", "system_prompt": "", **CHAT_PARAMETER_DEFAULTS}
    if not SETTINGS_STORE.path().exists():
        return defaults
    parameter_columns = tuple(CHAT_PARAMETER_DEFAULTS)
    row = SETTINGS_STORE.fetch(
        "SELECT model_name, system_prompt, "
        + ", ".join(parameter_columns)
        + " FROM chat_settings WHERE id = 1",
        one=True,
    )
    if not row:
        return defaults
    return {
        "model_name": row[0] or "",
        "system_prompt": row[1] or "",
        **{
            column: row[index]
            for index, column in enumerate(parameter_columns, start=2)
        },
    }


def save_chat_settings(settings):
    """Persist only the supported chat setup fields in the singleton row."""
    writable_columns = ("model_name", "system_prompt", *CHAT_PARAMETER_DEFAULTS)
    values = [
        settings.get("model_name", ""),
        settings.get("system_prompt", ""),
        *(
            _optional_number(settings.get(key, CHAT_PARAMETER_DEFAULTS[key]), converter)
            for key, converter in CHAT_PARAMETER_CONVERTERS.items()
        ),
    ]
    SETTINGS_STORE.execute(
        f"""
        INSERT INTO chat_settings
            (id, {', '.join(writable_columns)})
        VALUES (1, {', '.join('?' for _column in writable_columns)})
        ON CONFLICT(id) DO UPDATE SET
            model_name = excluded.model_name,
            system_prompt = excluded.system_prompt,
            temperature = excluded.temperature,
            top_p = excluded.top_p,
            top_k = excluded.top_k,
            seed = excluded.seed,
            history_limit = excluded.history_limit,
            updated_at = CURRENT_TIMESTAMP
        """,
        values,
    )


def chat_attachment_settings(updates=None):
    """Read or partially update the two last-used attachment switches."""
    defaults = {"save_original_media": False, "attach_audio": False}
    if updates is None:
        if not SETTINGS_STORE.path().exists():
            return defaults
        row = SETTINGS_STORE.fetch(
            "SELECT save_original_media, attach_audio "
            "FROM chat_attachment_settings WHERE id = 1",
            one=True,
        )
        return defaults if not row else {
            "save_original_media": bool(row[0]),
            "attach_audio": bool(row[1]),
        }

    values = {**defaults, **updates}
    SETTINGS_STORE.execute(
        """
        INSERT INTO chat_attachment_settings
            (id, save_original_media, attach_audio)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            save_original_media = excluded.save_original_media,
            attach_audio = excluded.attach_audio,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            1 if values["save_original_media"] else 0,
            1 if values["attach_audio"] else 0,
        ),
    )
    return values
