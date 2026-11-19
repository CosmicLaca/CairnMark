"""SQLite persistence for messages, saved chats, and saved prompts."""

import json
from functools import partial

from config import PROJECT_ROOT
from models.sqlite_store import SQLiteStore


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


def _parse_list(value, *, csv_fallback=False):
    """Decode a stored JSON list, optionally accepting legacy CSV text."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        if csv_fallback:
            return [part.strip() for part in str(value).split(",") if part.strip()]
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, str):
        return [parsed] if parsed else []
    return []


def _stored_list(value):
    """Serialize list-like preview metadata while retaining legacy strings."""
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), ensure_ascii=False)
    return "" if value in (None, "") else str(value)


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
    "compacted": "INTEGER NOT NULL DEFAULT 0",
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


CHAT_STORE = SQLiteStore(
    "CHAT_DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "chathistory.db",
    schema=CHAT_SCHEMA,
    migrate=_migrate_chat_messages,
)

def list_chat_messages():
    if not CHAT_STORE.path().exists():
        return []
    rows = CHAT_STORE.fetch(
        "SELECT id, role, content, model_name, provider, response_time, "
        "input_tokens, output_tokens, system_prompt, saved_system_prompt_name, "
        "request_body, preview_images, has_audio, preview_media, compacted, created_at "
        "FROM chat_messages ORDER BY id"
    )
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
            "preview_images": _parse_list(row[11] or "", csv_fallback=True),
            "has_audio": bool(row[12]),
            "preview_media": _parse_list(row[13] or ""),
            "compacted": bool(row[14]),
            "created_at": row[15],
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
    compacted=0,
):
    _rowcount, lastrowid = CHAT_STORE.execute(
        "INSERT INTO chat_messages "
        "(role, content, model_name, provider, response_time, input_tokens, "
        "output_tokens, system_prompt, saved_system_prompt_name, request_body, "
        "preview_images, has_audio, preview_media, compacted) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            _stored_list(preview_images),
            1 if has_audio else 0,
            _stored_list(preview_media),
            1 if compacted else 0,
        ),
    )
    return lastrowid


def clear_chat_messages():
    if not CHAT_STORE.path().exists():
        return
    CHAT_STORE.execute("DELETE FROM chat_messages")


def delete_last_chat_message():
    """Remove the most recent chat message when it is an unanswered user request."""
    if not CHAT_STORE.path().exists():
        return False
    with CHAT_STORE.transaction() as connection:
        row = connection.execute(
            "SELECT id, role FROM chat_messages ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row or row[1] != "user":
            return False
        connection.execute("DELETE FROM chat_messages WHERE id = ?", (row[0],))
        return True


SAVED_RECORDS = {
    "chat": ("saved_chats", "messages", True),
    "system_prompt": ("saved_system_prompts", "content", False),
}


def list_saved(record_type):
    """List saved chat or system-prompt names in display order."""
    if not CHAT_STORE.path().exists():
        return []
    table, _value_column, _uses_json = SAVED_RECORDS[record_type]
    rows = CHAT_STORE.fetch(
        f"SELECT name FROM {table} ORDER BY name COLLATE NOCASE"
    )
    return [row[0] for row in rows]


def save_saved(record_type, name, value):
    """Create or replace one named chat or system prompt."""
    table, value_column, uses_json = SAVED_RECORDS[record_type]
    payload = json.dumps(value, ensure_ascii=False) if uses_json else value
    CHAT_STORE.execute(
        f"""
        INSERT INTO {table} (name, {value_column})
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET
            {value_column} = excluded.{value_column},
            updated_at = CURRENT_TIMESTAMP
        """,
        (name, payload),
    )


def get_saved(record_type, name):
    """Return one saved chat or system prompt, or ``None`` when absent."""
    if not CHAT_STORE.path().exists():
        return None
    table, value_column, uses_json = SAVED_RECORDS[record_type]
    row = CHAT_STORE.fetch(
        f"SELECT {value_column} FROM {table} WHERE name = ?",
        (name,),
        one=True,
    )
    if not row:
        return None
    if not uses_json:
        return row[0]
    try:
        return json.loads(row[0])
    except (ValueError, TypeError):
        return None


def delete_saved(record_type, name):
    """Delete one named chat or system prompt and report whether it existed."""
    if not CHAT_STORE.path().exists():
        return False
    table, _value_column, _uses_json = SAVED_RECORDS[record_type]
    rowcount, _lastrowid = CHAT_STORE.execute(
        f"DELETE FROM {table} WHERE name = ?",
        (name,),
    )
    return rowcount > 0


list_saved_chats = partial(list_saved, "chat")
save_saved_chat = partial(save_saved, "chat")
get_saved_chat = partial(get_saved, "chat")
delete_saved_chat = partial(delete_saved, "chat")
list_saved_system_prompts = partial(list_saved, "system_prompt")
save_saved_system_prompt = partial(save_saved, "system_prompt")
get_saved_system_prompt = partial(get_saved, "system_prompt")
delete_saved_system_prompt = partial(delete_saved, "system_prompt")


def load_saved_chat(name):
    messages = get_saved_chat(name)
    if messages is None:
        return False
    with CHAT_STORE.transaction() as connection:
        connection.execute("DELETE FROM chat_messages")
        for m in messages:
            preview_images = m.get("preview_images", [])
            if isinstance(preview_images, str):
                preview_images = _parse_list(preview_images, csv_fallback=True)
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
                    _stored_list(preview_images),
                    1 if m.get("has_audio") else 0,
                    _stored_list(m.get("preview_media", [])),
                ),
            )
    return True
