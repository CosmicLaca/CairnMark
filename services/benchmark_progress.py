"""Read streamed benchmark JSON and report the topic being generated."""

import json


def _normalize_topic_name(name):
    """Return a comparison key for matching generated and requested topics."""
    return " ".join(str(name or "").split()).casefold()


def _pair_target(raw):
    """Return the requested pair count, defaulting the same way the form does."""
    if raw is None or str(raw).strip() == "":
        return 5
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= 100 else None


class _Frame:
    """Track one open JSON container and the role it plays in the document."""

    __slots__ = ("kind", "role", "consumed")

    def __init__(self, kind, role):
        self.kind = kind
        self.role = role
        self.consumed = False


class BenchmarkStreamParser:
    """Track topic and pair progress in a streamed benchmark JSON document.

    The model writes one JSON document, so the only honest progress signal is
    the document itself. This parser consumes text as it arrives and reports
    which topic key and how many completed ``benchmarks`` items were seen.
    """

    def __init__(self, topics=None):
        expected = {}
        for topic in topics or ():
            if not isinstance(topic, dict):
                continue
            name = _normalize_topic_name(topic.get("name"))
            if name:
                expected[name] = _pair_target(topic.get("pairs"))
        self._expected = expected
        self._stack = []
        self._started = False
        self._complete = False
        self._in_string = False
        self._escaped = False
        self._string_chars = []
        self._closed_string = None
        self._last_key = None
        self._topic = ""
        self._pairs = 0
        self._topics_done = 0

    def feed(self, text):
        """Consume streamed text and return the current progress state."""
        for char in text or "":
            self._consume(char)
        return self.state()

    def state(self):
        """Return the parsed topic progress, or ``None`` before the first topic."""
        if not self._topic:
            return None
        return {
            "topic": self._topic,
            "pairs": self._pairs,
            "expected": self._expected.get(_normalize_topic_name(self._topic)),
            "topics_done": self._topics_done,
        }

    def _start_topic(self, name):
        self._topic = name.strip()
        self._pairs = 0

    def _record_key(self, key):
        self._last_key = key
        if not self._stack:
            return
        frame = self._stack[-1]
        if frame.kind != "object" or frame.role not in ("wrapper", "root"):
            return
        # A wrapper object holds exactly one topic key; a top-level object
        # holds one topic key per generated topic.
        if frame.role == "wrapper":
            if frame.consumed:
                return
            frame.consumed = True
        self._start_topic(key)

    def _push(self, bracket):
        kind = "object" if bracket == "{" else "array"
        parent = self._stack[-1] if self._stack else None
        if parent is None:
            role = "root"
        elif kind == "object":
            if parent.role == "pairs":
                role = "item"
            elif parent.role == "root" and parent.kind == "array":
                role = "wrapper"
            elif parent.role in ("root", "wrapper"):
                role = "topic"
            else:
                role = None
        elif parent.role == "topic" and self._last_key == "benchmarks":
            role = "pairs"
        elif parent.role in ("root", "wrapper"):
            # The model mapped a topic directly to an array of pairs.
            role = "pairs"
        else:
            role = None
        self._last_key = None
        self._stack.append(_Frame(kind, role))

    def _pop(self):
        if not self._stack:
            self._complete = True
            return
        frame = self._stack.pop()
        if frame.role == "item":
            self._pairs += 1
        elif frame.role == "topic":
            self._topics_done += 1
        if not self._stack:
            self._complete = True

    def _consume(self, char):
        if self._complete:
            return
        if self._in_string:
            if self._escaped:
                self._string_chars.append("\\")
                self._string_chars.append(char)
                self._escaped = False
            elif char == "\\":
                self._escaped = True
            elif char == '"':
                self._in_string = False
                self._closed_string = self._decode_string(self._string_chars)
                self._string_chars = []
            else:
                self._string_chars.append(char)
            return
        if self._closed_string is not None:
            if char.isspace():
                return
            if char == ":":
                self._record_key(self._closed_string)
                self._closed_string = None
                return
            self._closed_string = None
        if char == '"':
            self._in_string = True
            self._escaped = False
            self._string_chars = []
            return
        if not self._started:
            if char in "[{":
                self._started = True
                self._push(char)
            return
        if char in "[{":
            self._push(char)
        elif char in "]}":
            self._pop()

    @staticmethod
    def _decode_string(chars):
        raw = "".join(chars)
        try:
            return json.loads(f'"{raw}"')
        except (json.JSONDecodeError, ValueError):
            return raw
