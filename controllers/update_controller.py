"""HTTP responses for application update state and startup."""

from flask import current_app, jsonify

from services.application_updates import (
    APPLICATION_UPDATES,
    ApplicationUpdateError,
)


class UpdateController:
    """Translate update service results into local JSON responses."""

    def __init__(self, service=APPLICATION_UPDATES):
        self.service = service

    def status(self):
        """Return cached state without triggering another remote check."""
        return jsonify(self.service.cached_status())

    def start(self):
        """Launch the detached fast-forward updater."""
        try:
            status = self.service.start_update(
                dev_mode=current_app.config.get("DEV_MODE", False)
            )
        except ApplicationUpdateError as error:
            return jsonify({"error": str(error)}), 409
        return jsonify({"message": "Update started.", **status}), 202


update_controller = UpdateController()
