"""SQLite repository for messages, saved chats, and saved prompts."""

import json
from datetime import datetime, timedelta, timezone
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
    model_context_window INTEGER NOT NULL DEFAULT 0,
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

SQL_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
MESSAGE_COLUMNS = (
    "role",
    "content",
    "model_name",
    "provider",
    "response_time",
    "input_tokens",
    "output_tokens",
    "model_context_window",
    "system_prompt",
    "saved_system_prompt_name",
    "request_body",
    "preview_images",
    "has_audio",
    "preview_media",
    "compacted",
    "is_error",
    "used_tools",
    "webpage_previews",
    "webpage_preview_checked",
    "generated_documents",
    "created_at",
)
MESSAGE_DEFAULTS = {
    "role": "user",
    "content": "",
    "model_name": "",
    "provider": "",
    "response_time": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "model_context_window": 0,
    "system_prompt": "",
    "saved_system_prompt_name": "",
    "request_body": "",
    "preview_images": [],
    "has_audio": False,
    "preview_media": [],
    "compacted": False,
    "is_error": False,
    "used_tools": [],
    "webpage_previews": [],
    "webpage_preview_checked": False,
    "generated_documents": [],
}
LATER_MESSAGE_COLUMNS = {
    "model_name": "TEXT NOT NULL DEFAULT ''",
    "provider": "TEXT NOT NULL DEFAULT ''",
    "response_time": "REAL NOT NULL DEFAULT 0",
    "input_tokens": "INTEGER NOT NULL DEFAULT 0",
    "output_tokens": "INTEGER NOT NULL DEFAULT 0",
    "model_context_window": "INTEGER NOT NULL DEFAULT 0",
    "system_prompt": "TEXT NOT NULL DEFAULT ''",
    "saved_system_prompt_name": "TEXT NOT NULL DEFAULT ''",
    "request_body": "TEXT NOT NULL DEFAULT ''",
    "preview_images": "TEXT NOT NULL DEFAULT ''",
    "has_audio": "INTEGER NOT NULL DEFAULT 0",
    "preview_media": "TEXT NOT NULL DEFAULT ''",
    "compacted": "INTEGER NOT NULL DEFAULT 0",
    "is_error": "INTEGER NOT NULL DEFAULT 0",
    "used_tools": "TEXT NOT NULL DEFAULT ''",
    "webpage_previews": "TEXT NOT NULL DEFAULT ''",
    "webpage_preview_checked": "INTEGER NOT NULL DEFAULT 0",
    "generated_documents": "TEXT NOT NULL DEFAULT ''",
}
SAVED_RECORDS = {
    "chat": ("saved_chats", "messages", True),
    "system_prompt": ("saved_system_prompts", "content", False),
}
_UNSET = object()


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


def _sql_timestamp(value=None):
    """Return a UTC timestamp in SQLite's standard text representation."""
    moment = value or datetime.now(timezone.utc)
    return moment.strftime(SQL_TIMESTAMP_FORMAT)


def _timestamp_saved_messages(messages):
    """Add ordered timestamps only where legacy saved messages lack them."""
    normalized = []
    changed = False
    fallback = datetime.now(timezone.utc).replace(microsecond=0)
    previous = None
    for index, message in enumerate(messages):
        item = dict(message)
        created_at = str(item.get("created_at") or "").strip()
        if created_at:
            try:
                previous = datetime.strptime(created_at, SQL_TIMESTAMP_FORMAT)
            except ValueError:
                previous = None
        else:
            moment = (
                previous + timedelta(seconds=1)
                if previous
                else fallback + timedelta(seconds=index)
            )
            item["created_at"] = _sql_timestamp(moment)
            previous = moment
            changed = True
        normalized.append(item)
    return normalized, changed


CHAT_STORE = SQLiteStore(
    "CHAT_DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "chathistory.db",
    schema=CHAT_SCHEMA,
    columns={"chat_messages": LATER_MESSAGE_COLUMNS},
)


class ChatRepository:
    """Persist the active conversation and reusable named chat records."""

    def __init__(self, store=CHAT_STORE):
        self.store = store

    def messages(self, values=_UNSET):
        """Read the active conversation, or atomically replace it."""
        if values is not _UNSET:
            normalized, _timestamps_added = _timestamp_saved_messages(values)
            with self.store.transaction() as connection:
                self._replace(connection, normalized)
            return normalized
        if not self.store.path().exists():
            return []
        rows = self.store.fetch(
            "SELECT id, " + ", ".join(MESSAGE_COLUMNS)
            + " FROM chat_messages ORDER BY id"
        )
        messages = []
        for row in rows:
            message = dict(zip(("id", *MESSAGE_COLUMNS), row))
            message["preview_images"] = _parse_list(
                message["preview_images"],
                csv_fallback=True,
            )
            message["preview_media"] = _parse_list(message["preview_media"])
            message["used_tools"] = [
                item.strip()
                for item in _parse_list(message["used_tools"])
                if isinstance(item, str) and item.strip()
            ]
            message["webpage_previews"] = _parse_list(
                message["webpage_previews"]
            )
            message["generated_documents"] = _parse_list(
                message["generated_documents"]
            )
            message["has_audio"] = bool(message["has_audio"])
            message["compacted"] = bool(message["compacted"])
            message["is_error"] = bool(message["is_error"])
            message["webpage_preview_checked"] = bool(
                message["webpage_preview_checked"]
            )
            for field, default in MESSAGE_DEFAULTS.items():
                if message[field] is None:
                    message[field] = default
            messages.append(message)
        return messages

    def add(self, role, content, **metadata):
        """Append one message and return its database identifier."""
        message = {**MESSAGE_DEFAULTS, **metadata, "role": role, "content": content}
        message["created_at"] = (
            str(message.get("created_at") or "").strip() or _sql_timestamp()
        )
        _rowcount, lastrowid = self.store.execute(
            f"INSERT INTO chat_messages ({', '.join(MESSAGE_COLUMNS)}) "
            f"VALUES ({', '.join('?' for _column in MESSAGE_COLUMNS)})",
            self._stored_values(message),
        )
        return lastrowid

    def delete_last(self):
        """Remove the most recent message only when it is an unanswered request."""
        if not self.store.path().exists():
            return False
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT id, role FROM chat_messages ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row or row[1] != "user":
                return False
            connection.execute("DELETE FROM chat_messages WHERE id = ?", (row[0],))
        return True

    def update_webpage_previews(self, message_id, previews):
        """Attach captured webpage metadata to one assistant message."""
        rowcount, _lastrowid = self.store.execute(
            """
            UPDATE chat_messages
            SET webpage_previews = ?, webpage_preview_checked = 1
            WHERE id = ? AND role = 'assistant'
            """,
            (_stored_list(previews), message_id),
        )
        return rowcount > 0

    def saved(self, operation, record_type, name=None, value=None):
        """List, read, write, or delete a named chat or system prompt."""
        table, value_column, uses_json = SAVED_RECORDS[record_type]
        if operation == "list":
            if not self.store.path().exists():
                return []
            rows = self.store.fetch(
                f"SELECT name FROM {table} ORDER BY name COLLATE NOCASE"
            )
            return [row[0] for row in rows]
        if operation == "save":
            payload = json.dumps(value, ensure_ascii=False) if uses_json else value
            self.store.execute(
                f"""
                INSERT INTO {table} (name, {value_column}) VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    {value_column} = excluded.{value_column},
                    updated_at = CURRENT_TIMESTAMP
                """,
                (name, payload),
            )
            return value
        if not self.store.path().exists():
            return False if operation == "delete" else None
        if operation == "delete":
            rowcount, _lastrowid = self.store.execute(
                f"DELETE FROM {table} WHERE name = ?",
                (name,),
            )
            return rowcount > 0
        row = self.store.fetch(
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

    def load(self, name):
        """Load a saved chat and upgrade any missing message timestamps."""
        messages = self.saved("get", "chat", name)
        if messages is None:
            return False
        messages, timestamps_added = _timestamp_saved_messages(messages)
        with self.store.transaction() as connection:
            if timestamps_added:
                connection.execute(
                    "UPDATE saved_chats SET messages = ? WHERE name = ?",
                    (json.dumps(messages, ensure_ascii=False), name),
                )
            self._replace(connection, messages)
        return True

    @staticmethod
    def _stored_values(message):
        values = {**MESSAGE_DEFAULTS, **message}
        values["preview_images"] = _stored_list(values["preview_images"])
        values["preview_media"] = _stored_list(values["preview_media"])
        values["used_tools"] = _stored_list(values["used_tools"])
        values["webpage_previews"] = _stored_list(values["webpage_previews"])
        values["generated_documents"] = _stored_list(
            values["generated_documents"]
        )
        values["has_audio"] = int(bool(values["has_audio"]))
        values["compacted"] = int(bool(values["compacted"]))
        values["is_error"] = int(bool(values["is_error"]))
        values["webpage_preview_checked"] = int(
            bool(values["webpage_preview_checked"])
        )
        return tuple(values.get(column) for column in MESSAGE_COLUMNS)

    def _replace(self, connection, messages):
        connection.execute("DELETE FROM chat_messages")
        statement = (
            f"INSERT INTO chat_messages ({', '.join(MESSAGE_COLUMNS)}) "
            f"VALUES ({', '.join('?' for _column in MESSAGE_COLUMNS)})"
        )
        connection.executemany(
            statement,
            (self._stored_values(message) for message in messages),
        )


CHAT_HISTORY = ChatRepository()

# Stable aliases keep existing integrations working while application code can
# depend on the repository object directly.
list_chat_messages = CHAT_HISTORY.messages
replace_chat_messages = CHAT_HISTORY.messages
clear_chat_messages = partial(CHAT_HISTORY.messages, [])
add_chat_message = CHAT_HISTORY.add
delete_last_chat_message = CHAT_HISTORY.delete_last
list_saved = partial(CHAT_HISTORY.saved, "list")
save_saved = partial(CHAT_HISTORY.saved, "save")
get_saved = partial(CHAT_HISTORY.saved, "get")
delete_saved = partial(CHAT_HISTORY.saved, "delete")
load_saved_chat = CHAT_HISTORY.load
list_saved_chats = partial(CHAT_HISTORY.saved, "list", "chat")
save_saved_chat = partial(CHAT_HISTORY.saved, "save", "chat")
get_saved_chat = partial(CHAT_HISTORY.saved, "get", "chat")
delete_saved_chat = partial(CHAT_HISTORY.saved, "delete", "chat")
list_saved_system_prompts = partial(
    CHAT_HISTORY.saved,
    "list",
    "system_prompt",
)
save_saved_system_prompt = partial(
    CHAT_HISTORY.saved,
    "save",
    "system_prompt",
)
get_saved_system_prompt = partial(
    CHAT_HISTORY.saved,
    "get",
    "system_prompt",
)
delete_saved_system_prompt = partial(
    CHAT_HISTORY.saved,
    "delete",
    "system_prompt",
)
