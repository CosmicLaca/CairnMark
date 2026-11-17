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
