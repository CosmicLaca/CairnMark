"""HTTP controller for model-provider setup and state management."""

import sqlite3

from flask import current_app, jsonify, request

from services.model_providers import (
    CATALOG_ERRORS,
    ModelProviderService,
    ProviderCatalogError,
    ProviderConflictError,
    ProviderValidationError,
)
from services.provider_setup import custom_provider_modal, provider_setup_cards


PROVIDER_OPERATION_ERRORS = CATALOG_ERRORS + (sqlite3.Error,)


class ProviderController:
    """Translate provider HTTP requests into service operations."""

    def __init__(self, service=None):
        self.service = service or ModelProviderService()

    def setup_context(self):
        """Build provider summaries used by the setup page."""
        return {
            "providers": provider_setup_cards(self.service),
            "custom_provider": custom_provider_modal(),
            "selected_provider": self.service.setup_selection(),
        }

    def save_selection(self):
        """Persist the provider filter used by the setup workspace."""
        data = request.get_json(silent=True) or {}
        provider = str(data.get("provider", "")).strip()
        if not provider or len(provider) > 100:
            return jsonify({"error": "A valid provider is required"}), 400
        try:
            selected = self.service.save_setup_selection(provider)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"provider": selected})

    def fetch_models(self):
        """Read a live catalog without changing saved configuration."""
        data = request.get_json(silent=True) or request.args
        provider = str(data.get("provider", "")).strip()
        try:
            models = self.service.fetch_models(provider, data)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderCatalogError as error:
            current_app.logger.warning(
                "Provider catalog request failed for %s: %s",
                provider or "provider",
                error,
            )
            return jsonify({"error": str(error)}), 502
        except CATALOG_ERRORS:
            current_app.logger.exception(
                "Could not read models from %s", provider or "provider"
            )
            return jsonify({"error": "Could not read models from the provider"}), 502
        return jsonify({"data": models})

    def save_configuration(self):
        """Validate and save a provider-specific model configuration."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No data provided"}), 400
        provider = str(data.get("provider", "")).strip()
        try:
            result = self.service.save_configuration(provider, data)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderCatalogError as error:
            current_app.logger.warning(
                "Provider verification failed for %s: %s",
                provider or "provider",
                error,
            )
            return jsonify({"error": str(error)}), 502
        except PROVIDER_OPERATION_ERRORS:
            current_app.logger.exception(
                "Could not save configuration for %s", provider or "provider"
            )
            return jsonify({"error": "Could not verify and save the provider"}), 502
        return jsonify(result)

    def load_configuration(self):
        """Return saved models only for the requested provider name."""
        provider = request.args.get("provider", "").strip()
        if not provider or len(provider) > 100:
            return jsonify({"error": "A valid provider is required"}), 400
        try:
            return jsonify(self.service.load_configuration(provider))
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except sqlite3.Error:
            current_app.logger.exception(
                "Could not load configuration for %s", provider
            )
            return jsonify({"error": "Could not load model configuration"}), 500

    def props_available(self):
        """Quickly report whether a local provider exposes the props endpoint."""
        provider = request.args.get("provider", "").strip()
        if not provider or len(provider) > 100:
            return jsonify({"error": "A valid provider is required"}), 400
        try:
            available = self.service.check_props_available(provider)
            return jsonify({"available": available})
        except Exception:  # noqa: BLE001
            current_app.logger.exception(
                "Could not check props availability for %s", provider
            )
            return jsonify({"available": False})

    def ctx_mode(self):
        """Report the llama.cpp router-mode context setting mode."""
        provider = request.args.get("provider", "").strip()
        if not provider or len(provider) > 100:
            return jsonify({"error": "A valid provider is required"}), 400
        try:
            mode = self.service.detect_ctx_mode(provider)
            return jsonify({"ctx_mode": mode})
        except Exception:  # noqa: BLE001
            current_app.logger.exception(
                "Could not detect ctx mode for %s", provider
            )
            return jsonify({"ctx_mode": None})

    def model_params(self):
        """Return default generation parameters for a local provider model."""
        provider = request.args.get("provider", "").strip()
        model = request.args.get("model", "").strip()
        if not provider or not model or len(provider) > 100 or len(model) > 300:
            return jsonify({"error": "A valid provider and model are required"}), 400
        try:
            return jsonify(self.service.fetch_model_params(provider, model))
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderCatalogError as error:
            current_app.logger.warning(
                "Could not read model parameters for %s/%s: %s",
                provider,
                model,
                error,
            )
            return jsonify({"error": str(error)}), 502
        except sqlite3.Error:
            current_app.logger.exception(
                "Could not read or save model parameters for %s/%s", provider, model
            )
            return jsonify({"error": "Could not load saved model parameters"}), 500
        except CATALOG_ERRORS:
            current_app.logger.exception(
                "Could not read model parameters for %s/%s", provider, model
            )
            return jsonify({"error": "Could not read model parameters"}), 502

    def model_params_status(self):
        """Return database-only parameter state for a local model."""
        provider = request.args.get("provider", "").strip()
        model = request.args.get("model", "").strip()
        if not provider or not model or len(provider) > 100 or len(model) > 300:
            return jsonify({"error": "A valid provider and model are required"}), 400
        try:
            return jsonify(self.service.model_params_status(provider, model))
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except sqlite3.Error:
            current_app.logger.exception(
                "Could not read saved parameter state for %s/%s", provider, model
            )
            return jsonify({"error": "Could not read saved model parameters"}), 500

    def delete_model_params(self):
        """Delete cached generation parameters for a local provider model."""
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        provider = str(data.get("provider", "")).strip()
        model = str(data.get("model", "")).strip()
        if not provider or not model or len(provider) > 100 or len(model) > 300:
            return jsonify({"error": "A valid provider and model are required"}), 400
        try:
            deleted = self.service.delete_model_params(provider, model)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except sqlite3.Error:
            current_app.logger.exception(
                "Could not delete model parameters for %s/%s", provider, model
            )
            return jsonify({"error": "Could not delete saved model parameters"}), 500
        return jsonify({"deleted": deleted})

    def save_model_params(self):
        """Persist custom default parameters for a local provider model."""
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        provider = str(data.get("provider", "")).strip()
        model = str(data.get("model", "")).strip()
        if not provider or not model or len(provider) > 100 or len(model) > 300:
            return jsonify({"error": "A valid provider and model are required"}), 400

        params = None
        for key in ("params", "model_params", "parameters", "values"):
            if key in data and isinstance(data[key], dict):
                params = data[key]
                break
        if params is None:
            params = {
                key: value
                for key, value in data.items()
                if key not in {"provider", "model"}
            }
        try:
            saved = self.service.save_model_params(provider, model, params)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except sqlite3.Error:
            current_app.logger.exception(
                "Could not save model parameters for %s/%s", provider, model
            )
            return jsonify({"error": "Could not save model parameters"}), 500
        except CATALOG_ERRORS:
            current_app.logger.exception(
                "Could not save model parameters for %s/%s", provider, model
            )
            return jsonify({"error": "Could not save model parameters"}), 502
        return jsonify({"saved": True, "params": saved.get("params", params)})

    def status(self):
        """Return live health and persisted state for one provider."""
        provider = request.args.get("provider", "").strip()
        try:
            return jsonify(self.service.status(provider))
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400

    def update_state(self):
        """Enable or disable a configured and reachable provider."""
        data = request.get_json(silent=True) or {}
        provider = str(data.get("provider", "")).strip()
        enabled = data.get("enabled")
        if not provider or not isinstance(enabled, bool):
            return jsonify({"error": "Valid provider state is required"}), 400
        try:
            return jsonify(self.service.update_state(provider, enabled))
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderConflictError as error:
            return jsonify({"error": str(error)}), 409


provider_controller = ProviderController()
