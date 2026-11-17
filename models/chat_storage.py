"""SQLite persistence for chat history and chat setup defaults.

Chat messages, saved chats, and saved system prompts live in the separate
``instance/chathistory.db``. The ``chat_settings`` row that supplies the chat
page defaults lives in the main ``instance/cairnmark.db``.
"""

import json
from contextlib import closing

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

CHAT_SETTINGS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS chat_settings ({CHAT_SETTINGS_COLUMNS_SQL});
"""

CHAT_ATTACHMENT_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_attachment_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    save_original_media INTEGER NOT NULL DEFAULT 0,
    attach_audio INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CHAT_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    model_name TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    response_time REAL NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    system_prompt TEXT NOT NULL DEFAULT '',
    saved_system_prompt_name TEXT NOT NULL DEFAULT '',
    request_body TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saved_chats (
    name TEXT PRIMARY KEY,
    messages TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saved_system_prompts (
    name TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _parse_preview_images(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return [part for part in str(value).split(",") if part.strip()]
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, str):
        return [parsed] if parsed else []
    return []


def _parse_preview_media(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return []
    if isinstance(parsed, list):
        return parsed
    return []


CHAT_MESSAGE_COLUMNS = {
    "model_name": "TEXT NOT NULL DEFAULT ''",
    "provider": "TEXT NOT NULL DEFAULT ''",
    "response_time": "REAL NOT NULL DEFAULT 0",
    "input_tokens": "INTEGER NOT NULL DEFAULT 0",
    "output_tokens": "INTEGER NOT NULL DEFAULT 0",
    "system_prompt": "TEXT NOT NULL DEFAULT ''",
    "saved_system_prompt_name": "TEXT NOT NULL DEFAULT ''",
    "request_body": "TEXT NOT NULL DEFAULT ''",
    "preview_images": "TEXT NOT NULL DEFAULT ''",
    "has_audio": "INTEGER NOT NULL DEFAULT 0",
    "preview_media": "TEXT NOT NULL DEFAULT ''",
}


def _migrate_chat_messages(connection):
    existing = {
        row[1] for row in connection.execute("PRAGMA table_info(chat_messages)")
    }
    for column, definition in CHAT_MESSAGE_COLUMNS.items():
        if column not in existing:
            connection.execute(
                f"ALTER TABLE chat_messages ADD COLUMN {column} {definition}"
            )


def _migrate_chat_settings(connection):
    """Rebuild chat settings so every numeric parameter can be unset."""
    existing = {
        row[1]: row for row in connection.execute("PRAGMA table_info(chat_settings)")
    }
    if not existing:
        return
    parameter_columns = tuple(CHAT_PARAMETER_DEFAULTS)
    # Also drop any parameters that used to exist but no longer do.
    extra_columns = {col for col in existing if col not in CHAT_SETTINGS_COLUMNS}
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


CHAT_STORE = SQLiteStore(
    "CHAT_DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "chathistory.db",
    schema=CHAT_SCHEMA,
    migrate=_migrate_chat_messages,
)

SETTINGS_STORE = SQLiteStore(
    "DATABASE_PATH",
    schema=CHAT_SETTINGS_SCHEMA + CHAT_ATTACHMENT_SETTINGS_SCHEMA,
    migrate=_migrate_chat_settings,
)


def _default_chat_settings():
    return {
        "model_name": "",
        "system_prompt": "",
        **CHAT_PARAMETER_DEFAULTS,
    }


def get_chat_settings():
    database_path = SETTINGS_STORE.path()
    if not database_path.exists():
        return _default_chat_settings()
    parameter_columns = tuple(CHAT_PARAMETER_DEFAULTS)
    with closing(SETTINGS_STORE.connect()) as connection:
        row = connection.execute(
            "SELECT model_name, system_prompt, "
            + ", ".join(parameter_columns)
            + " FROM chat_settings WHERE id = 1"
        ).fetchone()
    if not row:
        return _default_chat_settings()
    settings = {
        "model_name": row[0] or "",
        "system_prompt": row[1] or "",
    }
    for index, column in enumerate(parameter_columns, start=2):
        settings[column] = row[index]
    return settings


def _optional_number(value, converter):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return converter(value)


def save_chat_settings(settings):
    writable_columns = ("model_name", "system_prompt", *CHAT_PARAMETER_DEFAULTS)
    placeholders = ", ".join("?" for _ in writable_columns)
    values = [
        settings.get("model_name", ""),
        settings.get("system_prompt", ""),
        *(
            _optional_number(settings.get(key, CHAT_PARAMETER_DEFAULTS[key]), converter)
            for key, converter in CHAT_PARAMETER_CONVERTERS.items()
        ),
    ]
    with closing(SETTINGS_STORE.connect()) as connection:
        connection.execute(
            f"""
            INSERT INTO chat_settings
                (id, {', '.join(writable_columns)})
            VALUES (1, {placeholders})
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
        connection.commit()


def get_chat_attachment_settings():
    """Return the last-used media attachment switch values."""
    database_path = SETTINGS_STORE.path()
    if not database_path.exists():
        return {"save_original_media": False, "attach_audio": False}
    with closing(SETTINGS_STORE.connect()) as connection:
        row = connection.execute(
            "SELECT save_original_media, attach_audio "
            "FROM chat_attachment_settings WHERE id = 1"
        ).fetchone()
    if not row:
        return {"save_original_media": False, "attach_audio": False}
    return {
        "save_original_media": bool(row[0]),
        "attach_audio": bool(row[1]),
    }


def save_chat_attachment_settings(settings):
    """Persist both media attachment switch values."""
    with closing(SETTINGS_STORE.connect()) as connection:
        connection.execute(
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
                1 if settings.get("save_original_media") else 0,
                1 if settings.get("attach_audio") else 0,
            ),
        )
        connection.commit()


def list_chat_messages():
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return []
    with closing(CHAT_STORE.connect()) as connection:
        rows = connection.execute(
            "SELECT id, role, content, model_name, provider, response_time, "
            "input_tokens, output_tokens, system_prompt, saved_system_prompt_name, "
            "request_body, preview_images, has_audio, preview_media, created_at FROM chat_messages ORDER BY id"
        ).fetchall()
    return [
        {
            "id": row[0],
            "role": row[1],
            "content": row[2],
            "model_name": row[3] or "",
            "provider": row[4] or "",
            "response_time": row[5] or 0,
            "input_tokens": row[6] or 0,
            "output_tokens": row[7] or 0,
            "system_prompt": row[8] or "",
            "saved_system_prompt_name": row[9] or "",
            "request_body": row[10] or "",
            "preview_images": _parse_preview_images(row[11] or ""),
            "has_audio": bool(row[12]),
            "preview_media": _parse_preview_media(row[13] or ""),
            "created_at": row[14],
        }
        for row in rows
    ]


def add_chat_message(
    role,
    content,
    model_name="",
    provider="",
    response_time=0,
    input_tokens=0,
    output_tokens=0,
    system_prompt="",
    saved_system_prompt_name="",
    request_body="",
    preview_images=None,
    has_audio=0,
    preview_media=None,
):
    with closing(CHAT_STORE.connect()) as connection:
        if isinstance(preview_images, (list, tuple)):
            preview_value = json.dumps(list(preview_images), ensure_ascii=False)
        elif preview_images in (None, ""):
            preview_value = ""
        else:
            preview_value = str(preview_images)
        if isinstance(preview_media, (list, tuple)):
            preview_media_value = json.dumps(list(preview_media), ensure_ascii=False)
        elif preview_media in (None, ""):
            preview_media_value = ""
        else:
            preview_media_value = str(preview_media)
        cursor = connection.execute(
            "INSERT INTO chat_messages "
            "(role, content, model_name, provider, response_time, input_tokens, "
            "output_tokens, system_prompt, saved_system_prompt_name, request_body, "
            "preview_images, has_audio, preview_media) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                role,
                content,
                model_name,
                provider,
                response_time,
                input_tokens,
                output_tokens,
                system_prompt,
                saved_system_prompt_name,
                request_body,
                preview_value,
                1 if has_audio else 0,
                preview_media_value,
            ),
        )
        connection.commit()
        return cursor.lastrowid


def clear_chat_messages():
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return
    with closing(CHAT_STORE.connect()) as connection:
        connection.execute("DELETE FROM chat_messages")
        connection.commit()


def delete_last_chat_message():
    """Remove the most recent chat message when it is an unanswered user request."""
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return False
    with closing(CHAT_STORE.connect()) as connection:
        row = connection.execute(
            "SELECT id, role FROM chat_messages ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row or row[1] != "user":
            return False
        connection.execute("DELETE FROM chat_messages WHERE id = ?", (row[0],))
        connection.commit()
        return True


def list_saved_system_prompts():
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return []
    with closing(CHAT_STORE.connect()) as connection:
        rows = connection.execute(
            "SELECT name FROM saved_system_prompts ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [row[0] for row in rows]


def save_saved_system_prompt(name, content):
    with closing(CHAT_STORE.connect()) as connection:
        connection.execute(
            """
            INSERT INTO saved_system_prompts (name, content)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET
                content = excluded.content,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, content),
        )
        connection.commit()


def get_saved_system_prompt(name):
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return None
    with closing(CHAT_STORE.connect()) as connection:
        row = connection.execute(
            "SELECT content FROM saved_system_prompts WHERE name = ?", (name,)
        ).fetchone()
    if not row:
        return None
    return row[0]


def delete_saved_system_prompt(name):
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return False
    with closing(CHAT_STORE.connect()) as connection:
        cursor = connection.execute(
            "DELETE FROM saved_system_prompts WHERE name = ?", (name,)
        )
        connection.commit()
        return cursor.rowcount > 0


def list_saved_chats():
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return []
    with closing(CHAT_STORE.connect()) as connection:
        rows = connection.execute(
            "SELECT name FROM saved_chats ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [row[0] for row in rows]


def save_saved_chat(name, messages):
    payload = json.dumps(messages, ensure_ascii=False)
    with closing(CHAT_STORE.connect()) as connection:
        connection.execute(
            """
            INSERT INTO saved_chats (name, messages)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET
                messages = excluded.messages,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, payload),
        )
        connection.commit()


def get_saved_chat(name):
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return None
    with closing(CHAT_STORE.connect()) as connection:
        row = connection.execute(
            "SELECT messages FROM saved_chats WHERE name = ?", (name,)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (ValueError, TypeError):
        return None


def delete_saved_chat(name):
    database_path = CHAT_STORE.path()
    if not database_path.exists():
        return False
    with closing(CHAT_STORE.connect()) as connection:
        cursor = connection.execute("DELETE FROM saved_chats WHERE name = ?", (name,))
        connection.commit()
        return cursor.rowcount > 0


def load_saved_chat(name):
    messages = get_saved_chat(name)
    if messages is None:
        return False
    with closing(CHAT_STORE.connect()) as connection:
        connection.execute("DELETE FROM chat_messages")
        for m in messages:
            preview_images = m.get("preview_images", [])
            if isinstance(preview_images, str):
                preview_images = _parse_preview_images(preview_images)
            connection.execute(
                "INSERT INTO chat_messages "
                "(role, content, model_name, provider, response_time, input_tokens, "
                "output_tokens, system_prompt, saved_system_prompt_name, request_body, "
                "preview_images, has_audio, preview_media) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    m.get("role", "user"),
                    m.get("content", ""),
                    m.get("model_name", ""),
                    m.get("provider", ""),
                    m.get("response_time", 0) or 0,
                    m.get("input_tokens", 0) or 0,
                    m.get("output_tokens", 0) or 0,
                    m.get("system_prompt", "") or "",
                    m.get("saved_system_prompt_name", "") or "",
                    m.get("request_body", "") or "",
                    json.dumps(preview_images, ensure_ascii=False)
                    if isinstance(preview_images, (list, tuple))
                    else str(preview_images or ""),
                    1 if m.get("has_audio") else 0,
                    json.dumps(m.get("preview_media", []), ensure_ascii=False)
                    if isinstance(m.get("preview_media"), (list, tuple))
                    else str(m.get("preview_media") or ""),
                ),
            )
        connection.commit()
    return True
