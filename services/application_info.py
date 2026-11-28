"""Load the application metadata declared in ``info.xml``."""

import xml.etree.ElementTree as element_tree
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApplicationMetadata:
    """Validated values declared in ``info.xml``."""

    name: str
    author: str
    repository: str
    last_update_date: str
    major: int
    minor: int
    patch: int
    release: str


class ApplicationInfoService:
    """Read the tracked metadata used by the shared workspace header."""

    def load(self, info_path):
        """Return display metadata directly from ``info.xml``."""
        info_path = Path(info_path)
        metadata = self._read_metadata(info_path)
        return {
            "name": metadata.name,
            "author": metadata.author,
            "repository": metadata.repository,
            "release": metadata.release,
            "last_update_date": metadata.last_update_date,
            "major": metadata.major,
            "minor": metadata.minor,
            "patch": metadata.patch,
            "version": f"{metadata.major}.{metadata.minor}.{metadata.patch}",
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
            patch=patch,
            release=required_text("release"),
        )


APPLICATION_INFO = ApplicationInfoService()


def initialize_application_info(app):
    """Initialize and cache metadata for shared template rendering."""
    with app.app_context():
        app.extensions["application_info"] = APPLICATION_INFO.load(
            app.config["APPLICATION_INFO_PATH"]
        )
