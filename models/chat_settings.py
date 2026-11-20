"""SQLite persistence for chat form, switches, and attachment defaults."""

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


def _add_column_if_missing(connection, table, column, definition):
    """Add one legacy column without hiding migration failures."""
    columns = {
        row[1] for row in connection.execute(f"PRAGMA table_info({table})")
    }
    if columns and column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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

    _add_column_if_missing(connection, "mineru_settings", "api_key", "TEXT")
    _add_column_if_missing(
        connection,
        "mineru_settings",
        "timeout",
        "INTEGER NOT NULL DEFAULT 3",
    )
    _add_column_if_missing(
        connection,
        "chat_attachment_settings",
        "video_fps",
        "REAL NOT NULL DEFAULT 2",
    )
    _add_column_if_missing(
        connection,
        "chat_attachment_settings",
        "send_all_previous",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        connection,
        "chat_attachment_settings",
        "stream_responses",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        connection,
        "chat_compact_settings",
        "threshold",
        "INTEGER NOT NULL DEFAULT 75",
    )
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
    migrate=_migrate_chat_settings,
)

_UNSET = object()
_SWITCH_TABLES = {
    "randomize_seed": "chat_seed_settings",
    "send_all_previous": "chat_history_settings",
    "auto_compact": "chat_compact_settings",
}


class ChatSettingsRepository:
    """Read and update the singleton chat configuration records."""

    def __init__(self, store=SETTINGS_STORE):
        self.store = store

    def form(self):
        """Return the saved chat form values or first-run defaults."""
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

    def save_form(self, settings):
        """Persist only fields supported by the chat setup form."""
        writable_columns = ("model_name", "system_prompt", *CHAT_PARAMETER_DEFAULTS)
        values = [settings.get("model_name", ""), settings.get("system_prompt", "")]
        for key, converter in CHAT_PARAMETER_CONVERTERS.items():
            value = settings.get(key, CHAT_PARAMETER_DEFAULTS[key])
            if isinstance(value, str):
                value = value.strip() or None
            values.append(None if value is None else converter(value))
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
            values,
        )

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

    def compact(self, updates=None):
        """Read or partially update automatic compaction settings."""
        defaults = {
            "auto_compact": False,
            "threshold": DEFAULT_AUTO_COMPACT_THRESHOLD,
        }
        row = None
        if self.store.path().exists():
            row = self.store.fetch(
                "SELECT auto_compact, threshold "
                "FROM chat_compact_settings WHERE id = 1",
                one=True,
            )
        current = defaults if not row else {
            "auto_compact": bool(row[0]),
            "threshold": self._auto_compact_threshold(row[1]),
        }
        if updates is None:
            return current

        values = {**current, **updates}
        threshold = self._auto_compact_threshold(values.get("threshold"))
        self.store.execute(
            """
            INSERT INTO chat_compact_settings (id, auto_compact, threshold)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                auto_compact = excluded.auto_compact,
                threshold = excluded.threshold,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(bool(values["auto_compact"])), threshold),
        )
        return {
            "auto_compact": bool(values["auto_compact"]),
            "threshold": threshold,
        }

    def attachments(self, updates=None):
        """Read or partially update attachment preferences."""
        defaults = {
            "save_original_media": False,
            "attach_audio": False,
            "video_fps": DEFAULT_VIDEO_FPS,
            "randomize_seed": self.switch("randomize_seed"),
            "send_all_previous": self.switch("send_all_previous"),
            "stream_responses": False,
        }
        row = None
        if self.store.path().exists():
            row = self.store.fetch(
                "SELECT save_original_media, attach_audio, video_fps, "
                "send_all_previous, stream_responses "
                "FROM chat_attachment_settings WHERE id = 1",
                one=True,
            )
        current = defaults if not row else {
            "save_original_media": bool(row[0]),
            "attach_audio": bool(row[1]),
            "video_fps": self._video_fps(row[2]),
            "randomize_seed": defaults["randomize_seed"],
            "send_all_previous": defaults["send_all_previous"],
            "stream_responses": bool(row[4]),
        }
        if updates is None:
            return current

        values = {**current, **updates}
        for name in ("randomize_seed", "send_all_previous"):
            if name in updates:
                values[name] = self.switch(name, updates[name])
        values["video_fps"] = self._video_fps(values["video_fps"])
        self.store.execute(
            """
            INSERT INTO chat_attachment_settings
                (id, save_original_media, attach_audio, video_fps,
                 send_all_previous, stream_responses)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                save_original_media = excluded.save_original_media,
                attach_audio = excluded.attach_audio,
                video_fps = excluded.video_fps,
                send_all_previous = excluded.send_all_previous,
                stream_responses = excluded.stream_responses,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(bool(values["save_original_media"])),
                int(bool(values["attach_audio"])),
                values["video_fps"],
                int(bool(values["send_all_previous"])),
                int(bool(values["stream_responses"])),
            ),
        )
        return {
            "save_original_media": bool(values["save_original_media"]),
            "attach_audio": bool(values["attach_audio"]),
            "video_fps": values["video_fps"],
            "randomize_seed": bool(values["randomize_seed"]),
            "send_all_previous": bool(values["send_all_previous"]),
            "stream_responses": bool(values["stream_responses"]),
        }

    def mineru(self, updates=None):
        """Read or update the saved MinerU API endpoint."""
        defaults = {
            "endpoint": "http://127.0.0.1:8100",
            "api_key": "",
            "timeout": DEFAULT_MINERU_TIMEOUT,
            "configured": False,
        }
        if updates is None:
            if not self.store.path().exists():
                return defaults
            row = self.store.fetch(
                "SELECT endpoint, api_key, timeout FROM mineru_settings WHERE id = 1",
                one=True,
            )
            if not row:
                return defaults
            return {
                "endpoint": str(row[0] or defaults["endpoint"]).strip()
                or defaults["endpoint"],
                "api_key": str(row[1] or "").strip(),
                "timeout": self._mineru_timeout(row[2]),
                "configured": True,
            }

        values = {**defaults, **updates}
        endpoint = str(values.get("endpoint") or "").strip().rstrip("/")
        endpoint = endpoint or defaults["endpoint"]
        api_key = str(values.get("api_key") or "").strip()
        timeout = self._mineru_timeout(values.get("timeout"))
        self.store.execute(
            """
            INSERT INTO mineru_settings (id, endpoint, api_key, timeout)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                endpoint = excluded.endpoint,
                api_key = excluded.api_key,
                timeout = excluded.timeout,
                updated_at = CURRENT_TIMESTAMP
            """,
            (endpoint, api_key or None, timeout),
        )
        return {
            "endpoint": endpoint,
            "api_key": api_key,
            "timeout": timeout,
            "configured": True,
        }

    @staticmethod
    def _mineru_timeout(value):
        """Return a valid saved reachability timeout or the default."""
        if isinstance(value, bool):
            return DEFAULT_MINERU_TIMEOUT
        try:
            timeout = int(value)
        except (TypeError, ValueError):
            return DEFAULT_MINERU_TIMEOUT
        if MINERU_TIMEOUT_MIN <= timeout <= MINERU_TIMEOUT_MAX:
            return timeout
        return DEFAULT_MINERU_TIMEOUT

    @staticmethod
    def _auto_compact_threshold(value):
        """Return a valid compaction percentage or the default."""
        if isinstance(value, bool):
            return DEFAULT_AUTO_COMPACT_THRESHOLD
        try:
            threshold = int(value)
        except (TypeError, ValueError):
            return DEFAULT_AUTO_COMPACT_THRESHOLD
        if AUTO_COMPACT_THRESHOLD_MIN <= threshold <= AUTO_COMPACT_THRESHOLD_MAX:
            return threshold
        return DEFAULT_AUTO_COMPACT_THRESHOLD

    @staticmethod
    def _video_fps(value):
        """Return a supported FPS value, falling back for corrupt saved data."""
        try:
            fps = float(value)
        except (TypeError, ValueError):
            return DEFAULT_VIDEO_FPS
        return fps if fps in VIDEO_FPS_VALUES else DEFAULT_VIDEO_FPS


CHAT_SETTINGS = ChatSettingsRepository()
