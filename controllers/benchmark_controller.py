"""Controller and view context for benchmark file organization."""

import json
import time
from pathlib import Path

from flask import (
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from models.benchmark_metadata import BENCHMARK_METADATA
from models.run_benchmark_settings import RUN_BENCHMARK_SETTINGS
from services.benchmark_categories import (
    UNCATEGORIZED,
    category_names,
    create_category,
    normalize_new_category,
)
from services.benchmark_documents import (
    DIFFICULTY_LEVELS,
    BenchmarkRepository,
    build_benchmark_log,
    group_benchmarks,
    has_model_answers,
    read_prompt_template,
)
from services.chat_requests import ChatRequestWorkflow
from services.model_providers import (
    ModelProviderService,
    ProviderOfflineError,
    ProviderValidationError,
)


MAX_NOTES_LENGTH = 2000
MAX_GENERATION_PROMPT_LENGTH = 10000
MAX_MODEL_NAME_LENGTH = 200


class BenchmarkController:
    """Organize benchmark files and render their saved metadata."""

    def __init__(
        self,
        service=None,
        repository=None,
        metadata_repository=None,
        settings_repository=None,
    ):
        self.service = service or ModelProviderService()
        self.repository = repository or BenchmarkRepository()
        self.metadata = metadata_repository or BENCHMARK_METADATA
        self.settings = settings_repository or RUN_BENCHMARK_SETTINGS

    def list_files(self):
        """Return prompt JSON filenames in stable display order."""
        try:
            return self.repository.list_files()
        except OSError:
            current_app.logger.exception(
                "Could not read benchmark prompts from %s",
                self.repository.directory,
            )
            return []

    def _catalog_context(self, filenames, prompt_filename):
        """Build the shared selector context for run and evaluation pages."""
        metadata = self.metadata.for_files(filenames)
        return {
            "benchmark_files": filenames,
            "benchmark_groups": group_benchmarks(filenames, metadata),
            "active_models": self.service.active_models(),
            "run_system_prompt": read_prompt_template(prompt_filename),
        }

    def selection_context(self):
        """Build categorized benchmark data for the selection page."""
        benchmark_files = self.list_files()
        context = self._catalog_context(
            benchmark_files,
            "run_benchmark-SYSTEM.md",
        )
        context["run_benchmark_settings"] = self.settings.get()
        return context

    @staticmethod
    def _validate_generation_parameters(parameters):
        """Validate the run page's allowlisted sampling parameters."""
        ranges = {
            "temperature": (0, 2),
            "top_p": (0, 1),
            "top_k": (0, 200),
            "min_p": (0, 1),
            "seed": (-1, 4294967295),
        }
        cleaned = {}
        for name, (minimum, maximum) in ranges.items():
            value = parameters.get(name)
            if value in (None, ""):
                cleaned[name] = None
                continue
            converter = int if name in {"top_k", "seed"} else float
            try:
                value = converter(value)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"{name.replace('_', ' ').title()} must be a valid number."
                ) from error
            if value < minimum or value > maximum:
                raise ValueError(
                    f"{name.replace('_', ' ').title()} must be between "
                    f"{minimum} and {maximum}."
                )
            cleaned[name] = value
        return cleaned

    def save_generation_settings(self):
        """Persist settings used only while running benchmark JSON files."""
        data = request.get_json(silent=True) or {}
        try:
            saved = {
                **self._validate_generation_parameters(data),
                "randomize_seed": bool(data.get("randomize_seed", False)),
                "create_log": bool(data.get("create_log", False)),
            }
            saved = self.settings.save(saved)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify(saved)

    def _has_model_answers(self, filename):
        """Return True when a benchmark file contains runnable model answers."""
        try:
            content = self.repository.load(filename)
        except (OSError, json.JSONDecodeError):
            current_app.logger.warning(
                "Skipping unreadable benchmark %s during evaluation scan",
                filename,
            )
            return False
        return has_model_answers(content)

    def evaluate_context(self):
        """Build selection data only for benchmark files that have model answers."""
        benchmark_files = [
            filename
            for filename in self.list_files()
            if self._has_model_answers(filename)
        ]
        return self._catalog_context(
            benchmark_files,
            "evaluate_benchmark-SYSTEM.md",
        )

    def load_content(self, filename):
        """Load one validated JSON document from the prompt directory."""
        if not self.repository.contains(filename):
            abort(404)
        try:
            return self.repository.load(filename)
        except FileNotFoundError:
            abort(404)
        except (OSError, json.JSONDecodeError):
            current_app.logger.exception(
                "Could not load benchmark JSON %s", filename
            )
            abort(500)

    def select(self, filename, page):
        """Display and update organization metadata for a benchmark file."""
        if not self.repository.contains(filename):
            abort(404)

        metadata = self.metadata.metadata(filename) or {
            "category": UNCATEGORIZED,
            "difficulty": "Normal",
            "notes": "",
            "generation_prompt": "",
            "model_name": "",
        }
        categories = category_names()
        errors = []

        if request.method == "POST":
            category_choice = request.form.get("category", UNCATEGORIZED)
            category = category_choice
            if category_choice == "__new__":
                category, error = normalize_new_category(
                    request.form.get("new_category", ""),
                    categories,
                )
                if error:
                    errors.append(error)
            elif category not in {UNCATEGORIZED, *categories}:
                errors.append("Select an available category.")

            difficulty = request.form.get("difficulty", "Normal")
            if difficulty not in DIFFICULTY_LEVELS:
                errors.append("Select a valid difficulty level.")

            notes = request.form.get("notes", "").strip()
            if len(notes) > MAX_NOTES_LENGTH:
                errors.append("Notes must be 2,000 characters or fewer.")

            generation_prompt = request.form.get(
                "generation_prompt", ""
            ).strip()
            if len(generation_prompt) > MAX_GENERATION_PROMPT_LENGTH:
                errors.append(
                    "Generation prompt must be 10,000 characters or fewer."
                )

            model_name = request.form.get("model_name", "").strip()
            if len(model_name) > MAX_MODEL_NAME_LENGTH:
                errors.append("Model name must be 200 characters or fewer.")

            metadata = {
                "category": (
                    "__new__" if category_choice == "__new__" and errors else category
                ),
                "difficulty": difficulty,
                "notes": notes,
                "generation_prompt": generation_prompt,
                "model_name": model_name,
            }
            if not errors:
                self.metadata.metadata(
                    filename,
                    {
                        "category": category,
                        "difficulty": difficulty,
                        "notes": notes,
                        "generation_prompt": generation_prompt,
                        "model_name": model_name,
                    },
                )
                return redirect(
                    url_for(
                        "run_benchmark_select",
                        filename=filename,
                        saved="1",
                    )
                )

        return render_template(
            "benchmark_selected.html",
            page=page,
            filename=filename,
            metadata=metadata,
            categories=categories,
            difficulty_levels=DIFFICULTY_LEVELS,
            errors=errors,
            saved=request.args.get("saved") == "1",
        )

    def process_one(self, filename):
        """Process a single request against the selected model."""
        if not self.repository.contains(filename):
            abort(404)
        data = request.get_json(silent=True) or {}
        model_spec = (data.get("model") or "").strip()
        system_prompt = data.get("system_prompt") or ""
        subcategory = data.get("subcategory") or ""
        request_text = data.get("request") or ""

        try:
            parameters = self._validate_generation_parameters(data)
            extra_parameters = ChatRequestWorkflow.model_parameters(
                data.get("model_params")
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        if not model_spec or "::" not in model_spec:
            return jsonify({"error": "Model is required."}), 400

        try:
            provider, model = self.service.resolve_online_model(model_spec)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderOfflineError as error:
            return jsonify({"error": str(error)}), 503

        prompt = system_prompt.replace("{{subcategory}}", subcategory)

        started = time.monotonic()
        try:
            content = self.service.benchmark_run_completion(
                provider,
                model,
                prompt,
                request_text,
                **parameters,
                extra_parameters=extra_parameters,
            )
        except Exception as error:  # noqa: BLE001
            current_app.logger.exception(
                "Benchmark request failed for provider=%s model=%s",
                provider,
                model,
            )
            return jsonify({"error": str(error)}), 502
        elapsed = int(round(time.monotonic() - started))

        return jsonify(
            {
                "response": content,
                "time": elapsed,
            }
        )

    def save_result(self, filename):
        """Overwrite a benchmark file and its metadata with processed results."""
        if not self.repository.contains(filename):
            abort(404)
        data = request.get_json(silent=True) or {}
        content = data.get("content")
        if not isinstance(content, (dict, list)):
            return jsonify({"error": "Invalid content."}), 400

        try:
            self.repository.save(filename, content)
        except OSError:
            current_app.logger.exception("Could not save benchmark %s", filename)
            return jsonify({"error": "Could not save benchmark results."}), 500

        category = data.get("category", "Uncategorized")
        difficulty = data.get("difficulty", "Normal")
        if difficulty not in DIFFICULTY_LEVELS:
            difficulty = "Normal"
        generation_prompt = data.get("generation_prompt", "")
        system_prompt = data.get("system_prompt", "")
        model_name = data.get("model_name", "")
        create_log = bool(data.get("create_log", False))

        create_category(category)

        if create_log:
            log_text = build_benchmark_log(
                filename, content, system_prompt
            )
            log_filename = Path(filename).stem + ".md"
            try:
                self.repository.save_log(log_filename, log_text)
            except OSError:
                current_app.logger.exception(
                    "Could not save benchmark log for %s", filename
                )
                return jsonify({"error": "Could not save benchmark log."}), 500

        self.metadata.metadata(
            filename,
            {
                "category": category,
                "difficulty": difficulty,
                "notes": "",
                "generation_prompt": generation_prompt,
                "model_name": model_name,
            },
        )

        return jsonify(
            {
                "message": "Benchmark saved.",
                "filename": filename,
                "log_created": create_log,
            }
        )

    def update_response(self, filename):
        """Update a single response value in a benchmark JSON file."""
        if not self.repository.contains(filename):
            abort(404)
        data = request.get_json(silent=True) or {}
        try:
            topic_index = int(data.get("topic_index"))
            request_index = int(data.get("request_index"))
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid indices."}), 400
        new_response = data.get("response")
        if not isinstance(new_response, str):
            return jsonify({"error": "Response must be text."}), 400

        try:
            self.repository.update_response(
                filename,
                topic_index,
                request_index,
                new_response,
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except OSError:
            current_app.logger.exception("Could not update benchmark %s", filename)
            return jsonify({"error": "Could not update the response."}), 500
        return jsonify({"message": "Response updated.", "filename": filename})

    def content(self, filename):
        """Return one benchmark document for the selection-page preview."""
        return jsonify({"filename": filename, "content": self.load_content(filename)})


benchmark_controller = BenchmarkController()
