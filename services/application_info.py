"""Load application metadata and advance its commit-based patch version."""

import os
import subprocess
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from models.application_info import APPLICATION_INFO_STORAGE


@dataclass(frozen=True)
class ApplicationMetadata:
    """Validated values declared in ``info.xml``."""

    name: str
    author: str
    repository: str
    last_update_date: str
    major: int
    minor: int
    initial_patch: int
    release: str


class ApplicationInfoService:
    """Combine tracked release metadata with local version state."""

    def __init__(self, storage=APPLICATION_INFO_STORAGE):
        self.storage = storage

    def synchronize(self, info_path, *, git_enabled=True):
        """Read metadata and synchronize its live version with Git."""
        info_path = Path(info_path)
        metadata = self._read_metadata(info_path)
        stored = self.storage.status()
        current_commit = ""
        commit_increment = 0
        if git_enabled:
            current_commit = self._git(info_path.parent, "rev-parse", "HEAD")
            previous_commit = stored["commit_hash"] if stored else ""
            if previous_commit and previous_commit != current_commit:
                count = self._git(
                    info_path.parent,
                    "rev-list",
                    "--count",
                    f"{previous_commit}..{current_commit}",
                )
                commit_increment = int(count) if count.isdigit() else 1

        version = self.storage.synchronize(
            major=metadata.major,
            minor=metadata.minor,
            initial_patch=metadata.initial_patch,
            commit_hash=current_commit,
            commit_increment=commit_increment,
            metadata_date=metadata.last_update_date,
            commit_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        return {
            "name": metadata.name,
            "author": metadata.author,
            "repository": metadata.repository,
            "release": metadata.release,
            **version,
            "version": (
                f"{version['major']}.{version['minor']}.{version['patch']}"
            ),
        }

    @staticmethod
    def _read_metadata(info_path):
        root = element_tree.parse(info_path).getroot()

        def required_text(path):
            value = root.findtext(path, default="").strip()
            if not value:
                raise ValueError(f"Missing application metadata: {path}")
            return value

        version = root.find("version")
        if version is None:
            raise ValueError("Missing application metadata: version")
        try:
            major = int(required_text("version/major"))
            minor = int(required_text("version/minor"))
            patch = int(required_text("version/patch"))
        except ValueError as error:
            raise ValueError("Application version values must be integers.") from error
        if min(major, minor, patch) < 0:
            raise ValueError("Application version values cannot be negative.")
        return ApplicationMetadata(
            name=required_text("name"),
            author=required_text("author"),
            repository=required_text("repository"),
            last_update_date=required_text("last-update"),
            major=major,
            minor=minor,
            initial_patch=patch,
            release=required_text("release"),
        )

    @staticmethod
    def _git(project_root, *arguments):
        options = {
            "cwd": project_root,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": 10,
            "check": False,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        completed = subprocess.run(["git", *arguments], **options)
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()


APPLICATION_INFO = ApplicationInfoService()


def initialize_application_info(app):
    """Initialize and cache metadata for shared template rendering."""
    with app.app_context():
        app.extensions["application_info"] = APPLICATION_INFO.synchronize(
            app.config["APPLICATION_INFO_PATH"],
            git_enabled=app.config.get("APPLICATION_VERSION_GIT_ENABLED", True),
        )
