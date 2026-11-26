#!/usr/bin/env python3
"""Cairnmark Flask application factory."""

import argparse
import logging
import os
import socket
from pathlib import Path

from flask import Flask

from config import CONFIGS
from models import init_storage
from routes import init_routes
from services.application_info import initialize_application_info


def port_is_in_use(host, port):
    """Return whether another local process is already accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def parse_arguments(argv=None):
    """Parse command-line options for the local server."""
    parser = argparse.ArgumentParser(
        description="Run the Cairnmark server on localhost."
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode and show unfinished pages in the sidebar.",
    )
    return parser.parse_args(argv)


def create_app(config_name=None, config_overrides=None):
    """Create and configure a Cairnmark application instance."""
    environment = config_name or os.environ.get("CAIRNMARK_ENV", "development")
    try:
        config_class = CONFIGS[environment]
    except KeyError as error:
        valid_names = ", ".join(sorted(CONFIGS))
        raise ValueError(
            f"Unknown Cairnmark environment {environment!r}. Use: {valid_names}."
        ) from error

    app = Flask(__name__)
    app.config.from_object(config_class)
    if config_overrides:
        app.config.from_mapping(config_overrides)
        if (
            "CHAT_DATABASE_PATH" in config_overrides
            and "MEDIA_DATABASE_PATH" not in config_overrides
        ):
            chat_path = Path(app.config["CHAT_DATABASE_PATH"])
            app.config["MEDIA_DATABASE_PATH"] = str(
                chat_path.with_name("media.db")
            )
        if (
            "CHAT_DATABASE_PATH" in config_overrides
            and "DOCUMENT_PREVIEW_DIRECTORY" not in config_overrides
        ):
            chat_path = Path(app.config["CHAT_DATABASE_PATH"])
            app.config["DOCUMENT_PREVIEW_DIRECTORY"] = str(
                chat_path.with_name("document-previews")
            )
    app.logger.setLevel(getattr(logging, app.config["LOG_LEVEL"], logging.INFO))
    init_storage(app)
    initialize_application_info(app)
    init_routes(app)

    return app


if __name__ == "__main__":
    arguments = parse_arguments()
    server_host = "127.0.0.1"
    server_port = int(os.environ.get("PORT", 5000))
    if port_is_in_use(server_host, server_port):
        raise SystemExit(
            f"Cairnmark did not start: http://{server_host}:{server_port} "
            "is already in use. Stop the existing server or choose another PORT."
        )

    create_app(config_overrides={"DEV_MODE": arguments.dev}).run(
        host=server_host,
        port=server_port,
        use_reloader=False,
    )
