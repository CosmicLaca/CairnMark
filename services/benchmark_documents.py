"""Benchmark JSON storage and structure helpers.

Controllers own HTTP behavior; this module owns filesystem persistence and the
reusable rules for walking and grouping benchmark documents.
"""

import json
import os
import tempfile
from pathlib import Path

from flask import current_app

from services.benchmark_categories import UNCATEGORIZED


BENCHMARK_ITEMS_KEY = "benchmarks"
DIFFICULTY_LEVELS = ("Easy", "Normal", "Hard")


class BenchmarkRepository:
    """Read and atomically update benchmark documents in the configured folder."""

    def __init__(self, directory=None):
        self._directory = Path(directory) if directory else None

    @property
    def directory(self):
        """Return the explicit or application-configured benchmark directory."""
        if self._directory is not None:
            return self._directory
        return Path(current_app.config["BENCHMARK_DIRECTORY"])

    @property
    def logs_directory(self):
        """Return the log directory stored beside benchmark documents."""
        return self.directory / "logs"

    def list_files(self):
        """Return JSON filenames in stable, case-insensitive display order."""
        if not self.directory.is_dir():
            return []
        return sorted(
            (
                path.name
                for path in self.directory.iterdir()
                if path.is_file() and path.suffix.lower() == ".json"
            ),
            key=str.casefold,
        )

    def contains(self, filename):
        """Return whether *filename* names a listed benchmark document."""
        return filename in self.list_files()

    def load(self, filename):
        """Load one JSON document after validating its filename."""
        if not self.contains(filename):
            raise FileNotFoundError(filename)
        with (self.directory / filename).open(encoding="utf-8") as document:
            return json.load(document)

    def save(self, filename, content):
        """Atomically replace one existing benchmark JSON document."""
        if not self.contains(filename):
            raise FileNotFoundError(filename)
        self._atomic_write(
            self.directory / filename,
            json.dumps(content, indent=2, ensure_ascii=False),
        )

    def update_response(self, filename, topic_index, request_index, response):
        """Validate and atomically update one expected response value."""
        content = self.load(filename)
        if not isinstance(content, list):
            raise ValueError("Unsupported benchmark structure.")
        if topic_index < 0 or topic_index >= len(content):
            raise ValueError("Topic index out of range.")
        section = content[topic_index]
        if not isinstance(section, dict) or not section:
            raise ValueError("Invalid topic section.")
        section_content = section[next(iter(section))]
        items = (
            section_content.get(BENCHMARK_ITEMS_KEY, [])
            if isinstance(section_content, dict)
            else []
        )
        if request_index < 0 or request_index >= len(items):
            raise ValueError("Request index out of range.")
        if not isinstance(items[request_index], dict):
            raise ValueError("Invalid request entry.")
        items[request_index]["response"] = response
        self.save(filename, content)

    def create(self, filename, content):
        """Atomically create a new benchmark JSON document."""
        self.directory.mkdir(parents=True, exist_ok=True)
        self._atomic_write(
            self.directory / filename,
            json.dumps(content, indent=2, ensure_ascii=False),
        )

    def save_log(self, filename, content):
        """Atomically write a Markdown log for a benchmark filename."""
        self.logs_directory.mkdir(parents=True, exist_ok=True)
        self._atomic_write(self.logs_directory / filename, content)

    def unique_filename(self, stem, suffix=".json"):
        """Return a filename that does not exist in the benchmark directory."""
        candidate = f"{stem}{suffix}"
        counter = 1
        while (self.directory / candidate).exists():
            candidate = f"{stem}-{counter}{suffix}"
            counter += 1
        return candidate

    @staticmethod
    def _atomic_write(target, content):
        """Write UTF-8 text beside *target*, then replace it in one operation."""
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, target)
        except Exception:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)
            raise


def iter_benchmark_items(content):
    """Yield ``(topic, item)`` pairs from a supported benchmark document."""
    if not isinstance(content, list):
        return
    for section in content:
        if not isinstance(section, dict):
            continue
        for topic, section_content in section.items():
            items = (
                section_content.get(BENCHMARK_ITEMS_KEY, [])
                if isinstance(section_content, dict)
                else []
            )
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    yield topic, item


def read_prompt_template(filename):
    """Read one configured prompt template, returning empty text on failure."""
    path = Path(current_app.config["SYSTEM_PROMPT_DIRECTORY"]) / filename
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        current_app.logger.warning("Could not read system prompt %s", path)
        return ""


def build_benchmark_log(filename, content, system_prompt=""):
    """Build a readable Markdown run log from a benchmark document."""
    lines = [f"# Benchmark Log: {filename}", ""]
    if not isinstance(content, list):
        return "\n".join(lines)
    for section in content:
        if not isinstance(section, dict):
            continue
        for subcategory, section_content in section.items():
            lines.extend((f"## {subcategory}", ""))
            items = (
                section_content.get(BENCHMARK_ITEMS_KEY, [])
                if isinstance(section_content, dict)
                else []
            )
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                lines.extend(
                    (f"### Request {index}", "", item.get("request", ""), "")
                )
                lines.extend(
                    (
                        "**System prompt:**",
                        "",
                        (system_prompt or "").replace(
                            "{{subcategory}}", subcategory
                        ),
                        "",
                    )
                )
                answers = item.get("answers") or []
                if answers:
                    for answer in answers:
                        if not isinstance(answer, dict):
                            continue
                        response_time = answer.get(
                            "response_time", answer.get("reponse_time", "")
                        )
                        lines.extend(
                            (
                                f"**Model:** {answer.get('model_name', '')}",
                                "",
                                "**Model response:** "
                                f"{answer.get('model_answer', '')}",
                                "",
                                f"**Response time:** {response_time}s",
                                "",
                            )
                        )
                else:
                    lines.extend(("_No model response recorded._", ""))
                lines.extend(("---", ""))
    return "\n".join(lines)


def has_model_answers(content):
    """Return whether a document contains at least one usable model answer."""
    for _topic, item in iter_benchmark_items(content):
        answers = item.get("answers")
        if not isinstance(answers, list):
            continue
        if any(
            isinstance(answer, dict)
            and answer.get("model_answer")
            and answer.get("model_name")
            for answer in answers
        ):
            return True
    return False


def group_benchmarks(filenames, metadata):
    """Build the category and difficulty groups consumed by page templates."""
    grouped = {}
    for filename in filenames:
        file_metadata = metadata.get(filename)
        category = (
            file_metadata.get("category", UNCATEGORIZED)
            if file_metadata
            else UNCATEGORIZED
        )
        grouped.setdefault(category, []).append(
            {
                "name": filename,
                "metadata": file_metadata,
                "difficulty": (
                    file_metadata.get("difficulty", "Normal")
                    if file_metadata
                    else "Normal"
                ),
            }
        )

    groups = []
    for name in sorted(
        grouped,
        key=lambda category: (
            category == UNCATEGORIZED,
            category.casefold(),
        ),
    ):
        files = grouped[name]
        available = {file_data["difficulty"] for file_data in files}
        groups.append(
            {
                "name": name,
                "files": files,
                "difficulties": [
                    level for level in DIFFICULTY_LEVELS if level in available
                ],
            }
        )
    return groups
