"""SQLite persistence for chat form, switches, and attachment defaults."""

from functools import partialmethod

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
DEFAULT_MINERU_TIMEOUT = 3
MINERU_TIMEOUT_MIN = 1
MINERU_TIMEOUT_MAX = 30
DEFAULT_AUTO_COMPACT_THRESHOLD = 75
AUTO_COMPACT_THRESHOLD_MIN = 5
AUTO_COMPACT_THRESHOLD_MAX = 100
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
    stream_responses INTEGER NOT NULL DEFAULT 0,
    cache_prompt INTEGER NOT NULL DEFAULT 1,
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
    threshold INTEGER NOT NULL DEFAULT 75,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mineru_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    endpoint TEXT NOT NULL DEFAULT 'http://127.0.0.1:8100',
    api_key TEXT,
    timeout INTEGER NOT NULL DEFAULT 3,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _migrate_chat_settings(connection):
    """Keep older singleton setting tables compatible with the current schema."""
    existing = {
        row[1]: row for row in connection.execute("PRAGMA table_info(chat_settings)")
    }
    parameter_columns = tuple(CHAT_PARAMETER_DEFAULTS)
    extra_columns = {
        column for column in existing if column not in CHAT_SETTINGS_COLUMNS
    }
    needs_rebuild = existing and (
        any(column not in existing for column in CHAT_SETTINGS_COLUMNS)
        or any(
            existing.get(column, (None, None, None, 0))[3]
            for column in parameter_columns
        )
        or bool(extra_columns)
    )
    if needs_rebuild:
        select_columns = ", ".join(
            column if column in existing else CHAT_SETTINGS_DEFAULT_SQL[column]
            for column in CHAT_SETTINGS_COLUMNS
        )
        connection.execute("DROP TABLE IF EXISTS chat_settings_new")
        connection.execute(
            f"CREATE TABLE chat_settings_new ({CHAT_SETTINGS_COLUMNS_SQL})"
        )
        connection.execute(
            f"INSERT INTO chat_settings_new ({', '.join(CHAT_SETTINGS_COLUMNS)}) "
            f"SELECT {select_columns} FROM chat_settings"
        )
        connection.execute("DROP TABLE chat_settings")
        connection.execute("ALTER TABLE chat_settings_new RENAME TO chat_settings")

    # Preserve the pre-history-table value when upgrading an older database.
    connection.execute(
        """
        INSERT INTO chat_history_settings (id, send_all_previous)
        SELECT 1, send_all_previous
        FROM chat_attachment_settings
        WHERE id = 1
          AND NOT EXISTS (SELECT 1 FROM chat_history_settings WHERE id = 1)
        """
    )


SETTINGS_STORE = SQLiteStore(
    "DATABASE_PATH",
    default_path=PROJECT_ROOT / "instance" / "cairnmark.db",
    schema=SETTINGS_SCHEMA,
    columns={
        "mineru_settings": {
            "api_key": "TEXT",
            "timeout": "INTEGER NOT NULL DEFAULT 3",
        },
        "chat_attachment_settings": {
            "video_fps": "REAL NOT NULL DEFAULT 2",
            "send_all_previous": "INTEGER NOT NULL DEFAULT 0",
            "stream_responses": "INTEGER NOT NULL DEFAULT 0",
            "cache_prompt": "INTEGER NOT NULL DEFAULT 1",
        },
        "chat_compact_settings": {
            "threshold": "INTEGER NOT NULL DEFAULT 75",
        },
    },
    migrate=_migrate_chat_settings,
)

_UNSET = object()
_SWITCH_TABLES = {
    "randomize_seed": "chat_seed_settings",
    "send_all_previous": "chat_history_settings",
    "auto_compact": "chat_compact_settings",
}
_SETTING_GROUPS = {
    "attachments": {
        "table": "chat_attachment_settings",
        "columns": (
            "save_original_media",
            "attach_audio",
            "video_fps",
            "send_all_previous",
            "stream_responses",
            "cache_prompt",
        ),
        "defaults": {
            "save_original_media": False,
            "attach_audio": False,
            "video_fps": DEFAULT_VIDEO_FPS,
            "send_all_previous": False,
            "stream_responses": False,
            "cache_prompt": True,
            "randomize_seed": False,
        },
        "booleans": {
            "save_original_media",
            "attach_audio",
            "send_all_previous",
            "stream_responses",
            "cache_prompt",
            "randomize_seed",
        },
        "choices": {"video_fps": VIDEO_FPS_VALUES},
        "switches": ("randomize_seed", "send_all_previous"),
    },
    "compact": {
        "table": "chat_compact_settings",
        "columns": ("auto_compact", "threshold"),
        "defaults": {
            "auto_compact": False,
            "threshold": DEFAULT_AUTO_COMPACT_THRESHOLD,
        },
        "booleans": {"auto_compact"},
        "ranges": {
            "threshold": (
                AUTO_COMPACT_THRESHOLD_MIN,
                AUTO_COMPACT_THRESHOLD_MAX,
            ),
        },
    },
    "mineru": {
        "table": "mineru_settings",
        "columns": ("endpoint", "api_key", "timeout"),
        "defaults": {
            "endpoint": "http://127.0.0.1:8100",
            "api_key": "",
            "timeout": DEFAULT_MINERU_TIMEOUT,
        },
        "text": {"endpoint", "api_key"},
        "ranges": {
            "timeout": (MINERU_TIMEOUT_MIN, MINERU_TIMEOUT_MAX),
        },
        "reports_configured": True,
    },
}


class ChatSettingsRepository:
    """Read and update the singleton chat configuration records."""

    def __init__(self, store=SETTINGS_STORE):
        self.store = store

    def form(self, values=_UNSET):
        """Read the saved chat form, or replace it when values are supplied."""
        if values is not _UNSET:
            writable_columns = (
                "model_name",
                "system_prompt",
                *CHAT_PARAMETER_DEFAULTS,
            )
            saved = [values.get("model_name", ""), values.get("system_prompt", "")]
            for key, converter in CHAT_PARAMETER_CONVERTERS.items():
                value = values.get(key, CHAT_PARAMETER_DEFAULTS[key])
                if isinstance(value, str):
                    value = value.strip() or None
                saved.append(None if value is None else converter(value))
            assignments = ",\n                ".join(
                f"{column} = excluded.{column}" for column in writable_columns
            )
            self.store.execute(
                f"""
                INSERT INTO chat_settings (id, {', '.join(writable_columns)})
                VALUES (1, {', '.join('?' for _column in writable_columns)})
                ON CONFLICT(id) DO UPDATE SET
                    {assignments},
                    updated_at = CURRENT_TIMESTAMP
                """,
                saved,
            )
            return values

        defaults = {"model_name": "", "system_prompt": "", **CHAT_PARAMETER_DEFAULTS}
        if not self.store.path().exists():
            return defaults
        parameter_columns = tuple(CHAT_PARAMETER_DEFAULTS)
        row = self.store.fetch(
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
        if result["min_p"] is None:
            result["min_p"] = CHAT_PARAMETER_DEFAULTS["min_p"]
        return result

    def switch(self, name, value=_UNSET):
        """Read or update a named boolean chat switch."""
        try:
            table = _SWITCH_TABLES[name]
        except KeyError as error:
            raise KeyError(f"Unsupported chat switch: {name}") from error
        if value is _UNSET:
            if not self.store.path().exists():
                return False
            row = self.store.fetch(
                f"SELECT {name} FROM {table} WHERE id = 1",
                one=True,
            )
            return bool(row[0]) if row else False
        saved = bool(value)
        self.store.execute(
            f"""
            INSERT INTO {table} (id, {name}) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET
                {name} = excluded.{name},
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(saved),),
        )
        return saved

    def group(self, name, updates=_UNSET):
        """Read or partially update a declared singleton settings group."""
        try:
            spec = _SETTING_GROUPS[name]
        except KeyError as error:
            raise KeyError(f"Unsupported chat settings group: {name}") from error

        columns = spec["columns"]
        row = None
        if self.store.path().exists():
            row = self.store.fetch(
                f"SELECT {', '.join(columns)} FROM {spec['table']} WHERE id = 1",
                one=True,
            )
        values = dict(spec["defaults"])
        if row:
            values.update(zip(columns, row))
        for switch in spec.get("switches", ()):
            values[switch] = self.switch(switch)
        if updates is not _UNSET:
            values.update(updates)
            for switch in spec.get("switches", ()):
                if switch in updates:
                    values[switch] = self.switch(switch, updates[switch])

        values = self._normalize_group(spec, values, configured=bool(row))
        if updates is _UNSET:
            return values

        assignments = ",\n                ".join(
            f"{column} = excluded.{column}" for column in columns
        )
        saved = [
            int(values[column])
            if column in spec.get("booleans", ())
            else values[column] or None
            if name == "mineru" and column == "api_key"
            else values[column]
            for column in columns
        ]
        self.store.execute(
            f"""
            INSERT INTO {spec['table']} (id, {', '.join(columns)})
            VALUES (1, {', '.join('?' for _column in columns)})
            ON CONFLICT(id) DO UPDATE SET
                {assignments},
                updated_at = CURRENT_TIMESTAMP
            """,
            saved,
        )
        if spec.get("reports_configured"):
            values["configured"] = True
        return values

    @staticmethod
    def _normalize_group(spec, values, *, configured):
        """Normalize corrupt or partially supplied values from one group."""
        normalized = dict(values)
        defaults = spec["defaults"]
        for field in spec.get("booleans", ()):
            normalized[field] = bool(normalized.get(field))
        for field, choices in spec.get("choices", {}).items():
            try:
                value = float(normalized.get(field))
            except (TypeError, ValueError):
                value = defaults[field]
            normalized[field] = value if value in choices else defaults[field]
        for field, (minimum, maximum) in spec.get("ranges", {}).items():
            value = normalized.get(field)
            try:
                value = int(value) if not isinstance(value, bool) else None
            except (TypeError, ValueError):
                value = None
            normalized[field] = (
                value if value is not None and minimum <= value <= maximum
                else defaults[field]
            )
        for field in spec.get("text", ()):
            normalized[field] = str(normalized.get(field) or "").strip()
        if "endpoint" in normalized:
            normalized["endpoint"] = (
                normalized["endpoint"].rstrip("/") or defaults["endpoint"]
            )
        if spec.get("reports_configured"):
            normalized["configured"] = configured
        return normalized

    # Keep the former focused repository API without maintaining duplicate
    # implementations. New code can use ``form`` and ``group`` directly.
    save_form = form
    attachments = partialmethod(group, "attachments")
    compact = partialmethod(group, "compact")
    mineru = partialmethod(group, "mineru")


CHAT_SETTINGS = ChatSettingsRepository()
