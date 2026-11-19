"""SQLite persistence for chat form and attachment defaults."""

import sqlite3

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


CHAT_PARAMETER_DEFAULTS = {
    "temperature": 0.7,
    "top_p": 1.0,
    "top_k": 40,
    "seed": 4294967295,
    "history_limit": 4,
    "min_p": 0.05,
}

CHAT_PARAMETER_CONVERTERS = {
    "temperature": float,
    "top_p": float,
    "top_k": int,
    "seed": int,
    "history_limit": int,
    "min_p": float,
}

VIDEO_FPS_VALUES = (0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
DEFAULT_VIDEO_FPS = 2.0

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
    min_p REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
"""

CHAT_SETTINGS_DEFAULT_SQL = {
    **{
        key: ("NULL" if value is None else repr(value))
        for key, value in CHAT_PARAMETER_DEFAULTS.items()
    },
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
    video_fps REAL NOT NULL DEFAULT 2,
    send_all_previous INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_seed_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    randomize_seed INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    send_all_previous INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_compact_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    auto_compact INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mineru_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    endpoint TEXT NOT NULL DEFAULT 'http://127.0.0.1:8100',
    api_key TEXT,
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
        # Still ensure optional MinerU columns exist for older databases.
        try:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(mineru_settings)")
            }
            if columns and "api_key" not in columns:
                connection.execute("ALTER TABLE mineru_settings ADD COLUMN api_key TEXT")
        except sqlite3.Error:
            pass
        # Ensure video_fps exists for older databases.
        try:
            attachment_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(chat_attachment_settings)")
            }
            if attachment_columns and "video_fps" not in attachment_columns:
                connection.execute(
                    "ALTER TABLE chat_attachment_settings ADD COLUMN video_fps REAL NOT NULL DEFAULT 2"
                )
            if attachment_columns and "send_all_previous" not in attachment_columns:
                connection.execute(
                    "ALTER TABLE chat_attachment_settings ADD COLUMN send_all_previous INTEGER NOT NULL DEFAULT 0"
                )
        except sqlite3.Error:
            pass
        # Ensure min_p exists for older databases.
        try:
            chat_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(chat_settings)")
            }
            if chat_columns and "min_p" not in chat_columns:
                connection.execute("ALTER TABLE chat_settings ADD COLUMN min_p REAL")
        except sqlite3.Error:
            pass
        # Ensure the history settings table exists for older databases.
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS chat_history_settings ("
                "id INTEGER PRIMARY KEY CHECK (id = 1), "
                "send_all_previous INTEGER NOT NULL DEFAULT 0, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        except sqlite3.Error:
            pass
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
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(mineru_settings)")
        }
        if columns and "api_key" not in columns:
            connection.execute("ALTER TABLE mineru_settings ADD COLUMN api_key TEXT")
    except sqlite3.Error:
        pass
    # Ensure video_fps exists for older databases.
    try:
        attachment_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(chat_attachment_settings)")
        }
        if attachment_columns and "video_fps" not in attachment_columns:
            connection.execute(
                "ALTER TABLE chat_attachment_settings ADD COLUMN video_fps REAL NOT NULL DEFAULT 2"
            )
        if attachment_columns and "send_all_previous" not in attachment_columns:
            connection.execute(
                "ALTER TABLE chat_attachment_settings ADD COLUMN send_all_previous INTEGER NOT NULL DEFAULT 0"
            )
    except sqlite3.Error:
        pass
    # Ensure min_p exists for older databases.
    try:
        chat_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(chat_settings)")
        }
        if chat_columns and "min_p" not in chat_columns:
            connection.execute("ALTER TABLE chat_settings ADD COLUMN min_p REAL")
    except sqlite3.Error:
        pass
    # Ensure the history settings table exists for older databases.
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS chat_history_settings ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "send_all_previous INTEGER NOT NULL DEFAULT 0, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
    except sqlite3.Error:
        pass

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
    result = {
        "model_name": row[0] or "",
        "system_prompt": row[1] or "",
        **{
            column: row[index]
            for index, column in enumerate(parameter_columns, start=2)
        },
    }
    if result.get("min_p") is None:
        result["min_p"] = CHAT_PARAMETER_DEFAULTS.get("min_p", 0.05)
    return result


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
            min_p = excluded.min_p,
            updated_at = CURRENT_TIMESTAMP
        """,
        values,
    )


def chat_seed_settings(updates=None):
    """Read or partially update the seed randomizer switch state."""
    defaults = {"randomize_seed": False}
    if updates is None:
        if not SETTINGS_STORE.path().exists():
            return defaults
        row = SETTINGS_STORE.fetch(
            "SELECT randomize_seed FROM chat_seed_settings WHERE id = 1",
            one=True,
        )
        return defaults if not row else {
            "randomize_seed": bool(row[0]),
        }

    values = {**defaults, **updates}
    randomize_seed = bool(values.get("randomize_seed", defaults["randomize_seed"]))
    SETTINGS_STORE.execute(
        """
        INSERT INTO chat_seed_settings
            (id, randomize_seed)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET
            randomize_seed = excluded.randomize_seed,
            updated_at = CURRENT_TIMESTAMP
        """,
        (1 if randomize_seed else 0,),
    )
    return {"randomize_seed": randomize_seed}


def chat_history_settings(updates=None):
    """Read or partially update the history "send all previous" switch state."""
    defaults = {"send_all_previous": False}
    if updates is None:
        if not SETTINGS_STORE.path().exists():
            return defaults
        row = SETTINGS_STORE.fetch(
            "SELECT send_all_previous FROM chat_history_settings WHERE id = 1",
            one=True,
        )
        return defaults if not row else {
            "send_all_previous": bool(row[0]),
        }

    values = {**defaults, **updates}
    send_all_previous = bool(
        values.get("send_all_previous", defaults["send_all_previous"])
    )
    SETTINGS_STORE.execute(
        """
        INSERT INTO chat_history_settings
            (id, send_all_previous)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET
            send_all_previous = excluded.send_all_previous,
            updated_at = CURRENT_TIMESTAMP
        """,
        (1 if send_all_previous else 0,),
    )
    return {"send_all_previous": send_all_previous}


def chat_compact_settings(updates=None):
    """Read or update the automatic compaction switch state."""
    defaults = {"auto_compact": False}
    if updates is None:
        if not SETTINGS_STORE.path().exists():
            return defaults
        row = SETTINGS_STORE.fetch(
            "SELECT auto_compact FROM chat_compact_settings WHERE id = 1",
            one=True,
        )
        return defaults if not row else {"auto_compact": bool(row[0])}

    auto_compact = bool(updates.get("auto_compact", defaults["auto_compact"]))
    SETTINGS_STORE.execute(
        """
        INSERT INTO chat_compact_settings (id, auto_compact)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET
            auto_compact = excluded.auto_compact,
            updated_at = CURRENT_TIMESTAMP
        """,
        (1 if auto_compact else 0,),
    )
    return {"auto_compact": auto_compact}


def mineru_settings(updates=None):
    """Read or update the saved MinerU API endpoint."""
    defaults = {
        "endpoint": "http://127.0.0.1:8100",
        "api_key": "",
        "configured": False,
    }
    if updates is None:
        if not SETTINGS_STORE.path().exists():
            return defaults
        row = SETTINGS_STORE.fetch(
            "SELECT endpoint, api_key FROM mineru_settings WHERE id = 1",
            one=True,
        )
        if not row:
            return defaults
        return {
            "endpoint": str(row[0] or defaults["endpoint"]).strip()
            or defaults["endpoint"],
            "api_key": str(row[1] or "").strip(),
            "configured": True,
        }

    values = {**defaults, **updates}
    endpoint = str(values.get("endpoint") or "").strip().rstrip("/")
    if not endpoint:
        endpoint = defaults["endpoint"]
    api_key = str(values.get("api_key") or "").strip()
    SETTINGS_STORE.execute(
        """
        INSERT INTO mineru_settings (id, endpoint, api_key)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            endpoint = excluded.endpoint,
            api_key = excluded.api_key,
            updated_at = CURRENT_TIMESTAMP
        """,
        (endpoint, api_key or None),
    )
    return {
        "endpoint": endpoint,
        "api_key": api_key,
        "configured": True,
    }


def chat_attachment_settings(updates=None):
    """Read or partially update the last-used attachment and seed switches."""
    defaults = {
        "save_original_media": False,
        "attach_audio": False,
        "video_fps": DEFAULT_VIDEO_FPS,
        "randomize_seed": False,
        "send_all_previous": False,
    }
    seed_state = chat_seed_settings()
    defaults["randomize_seed"] = seed_state["randomize_seed"]
    history_state = chat_history_settings()
    defaults["send_all_previous"] = history_state["send_all_previous"]

    if updates is None:
        if not SETTINGS_STORE.path().exists():
            return defaults
        row = SETTINGS_STORE.fetch(
            "SELECT save_original_media, attach_audio, video_fps, send_all_previous "
            "FROM chat_attachment_settings WHERE id = 1",
            one=True,
        )
        result = defaults if not row else {
            "save_original_media": bool(row[0]),
            "attach_audio": bool(row[1]),
            "video_fps": _stored_video_fps(row[2]),
            "randomize_seed": chat_seed_settings()["randomize_seed"],
            "send_all_previous": bool(row[3]),
        }
        return result

    values = {**defaults, **updates}
    if "randomize_seed" in updates:
        chat_seed_settings({"randomize_seed": bool(updates.get("randomize_seed"))})
    if "send_all_previous" in updates:
        chat_history_settings(
            {"send_all_previous": bool(updates.get("send_all_previous"))}
        )
    SETTINGS_STORE.execute(
        """
        INSERT INTO chat_attachment_settings
            (id, save_original_media, attach_audio, video_fps, send_all_previous)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            save_original_media = excluded.save_original_media,
            attach_audio = excluded.attach_audio,
            video_fps = excluded.video_fps,
            send_all_previous = excluded.send_all_previous,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            1 if values["save_original_media"] else 0,
            1 if values["attach_audio"] else 0,
            _stored_video_fps(values["video_fps"]),
            1 if values["send_all_previous"] else 0,
        ),
    )
    return {
        "save_original_media": bool(values["save_original_media"]),
        "attach_audio": bool(values["attach_audio"]),
        "video_fps": _stored_video_fps(values["video_fps"]),
        "randomize_seed": chat_seed_settings()["randomize_seed"],
        "send_all_previous": chat_history_settings()["send_all_previous"],
    }


def _stored_video_fps(value):
    """Return a supported FPS value, falling back for corrupt saved data."""
    try:
        fps = float(value)
    except (TypeError, ValueError):
        return DEFAULT_VIDEO_FPS
    return fps if fps in VIDEO_FPS_VALUES else DEFAULT_VIDEO_FPS
