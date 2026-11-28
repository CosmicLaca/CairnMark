"""Application configuration for Cairnmark."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


class Config:
    """Settings shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DATABASE_PATH = PROJECT_ROOT / "instance" / "cairnmark.db"
    CHAT_DATABASE_PATH = PROJECT_ROOT / "instance" / "chathistory.db"
    MEDIA_DATABASE_PATH = PROJECT_ROOT / "instance" / "media.db"
    PARAMETER_DATABASE_PATH = PROJECT_ROOT / "instance" / "parameters.db"
    TOOLS_DATABASE_PATH = PROJECT_ROOT / "instance" / "tools.db"
    BENCHMARK_DIRECTORY = PROJECT_ROOT / "Benchmark-prompts"
    SYSTEM_PROMPT_DIRECTORY = PROJECT_ROOT / "System-prompts"
    CHAT_EXPORT_DIRECTORY = PROJECT_ROOT / "Exported-chat"
    GENERATED_DOCUMENT_DIRECTORY = PROJECT_ROOT / "Generated-documents"
    DOCUMENT_PREVIEW_DIRECTORY = PROJECT_ROOT / "instance" / "document-previews"
    MANUAL_DIRECTORY = PROJECT_ROOT / "manual"
    MCP_CONFIG_PATH = PROJECT_ROOT / "services" / "mcp.json"
    APPLICATION_INFO_PATH = PROJECT_ROOT / "info.xml"
    OPENCODE_CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
    LOG_LEVEL = os.environ.get("CAIRNMARK_LOG_LEVEL", "INFO").upper()
    # Enabled by the --dev launcher flag; public launches hide unfinished pages.
    DEV_MODE = False
    UPDATE_CHECK_ENABLED = True


class DevelopmentConfig(Config):
    """Local development settings."""

    DEBUG = True


class ProductionConfig(Config):
    """Production settings."""

    DEBUG = False


class TestingConfig(Config):
    """Automated-test settings."""

    TESTING = True
    UPDATE_CHECK_ENABLED = False


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
