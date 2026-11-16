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

from models.benchmark_metadata import (
    get_benchmark_metadata,
    get_metadata_for_files,
    save_benchmark_metadata,
)
from services.benchmark_categories import (
    UNCATEGORIZED,
    category_names,
    create_category,
    normalize_new_category,
)
from services.model_providers import (
    ModelProviderService,
    ProviderOfflineError,
    ProviderValidationError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PROMPTS_PATH = PROJECT_ROOT / "Benchmark-prompts"
LOGS_PATH = BENCHMARK_PROMPTS_PATH / "logs"
SYSTEM_PROMPTS_PATH = PROJECT_ROOT / "System-prompts"
DIFFICULTY_LEVELS = ("Easy", "Normal", "Hard")
MAX_NOTES_LENGTH = 2000
MAX_GENERATION_PROMPT_LENGTH = 10000
MAX_MODEL_NAME_LENGTH = 200
# Each topic section stores its request-response pairs under this key.
BENCHMARK_ITEMS_KEY = "benchmarks"


class BenchmarkController:
    """Organize benchmark files and render their saved metadata."""

    def __init__(self, service=None):
        self.service = service or ModelProviderService()

    @staticmethod
    def list_files():
        """Return prompt JSON filenames in stable display order."""
        try:
            return sorted(
                (
                    path.name
                    for path in BENCHMARK_PROMPTS_PATH.iterdir()
                    if path.is_file() and path.suffix.lower() == ".json"
                ),
                key=str.casefold,
            )
        except OSError:
            current_app.logger.exception(
                "Could not read benchmark prompts from %s",
                BENCHMARK_PROMPTS_PATH,
            )
            return []

    def selection_context(self):
        """Build categorized benchmark data for the selection page."""
        benchmark_files = self.list_files()
        metadata = get_metadata_for_files(benchmark_files)
        grouped_files = {}
        for filename in benchmark_files:
            file_metadata = metadata.get(filename)
            category = (
                file_metadata.get("category", UNCATEGORIZED)
                if file_metadata
                else UNCATEGORIZED
            )
            grouped_files.setdefault(category, []).append(
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

        category_names = sorted(
            grouped_files,
            key=lambda name: (name == UNCATEGORIZED, name.casefold()),
        )
        benchmark_groups = []
        for name in category_names:
            category_files = grouped_files[name]
            available_difficulties = {
                file_data["difficulty"] for file_data in category_files
            }
            benchmark_groups.append(
                {
                    "name": name,
                    "files": category_files,
                    "difficulties": [
                        level
                        for level in DIFFICULTY_LEVELS
                        if level in available_difficulties
                    ],
                }
            )
        system_prompt_template = ""
        try:
            system_prompt_template = (
                SYSTEM_PROMPTS_PATH / "run_benchmark-SYSTEM.md"
            ).read_text(encoding="utf-8")
        except OSError:
            pass

        return {
            "benchmark_files": benchmark_files,
            "benchmark_groups": benchmark_groups,
            "active_models": self.service.active_models(),
            "run_system_prompt": system_prompt_template,
        }

    @staticmethod
    def _has_model_answers(filename):
        """Return True when a benchmark file contains runnable model answers."""
        try:
            content = benchmark_controller.load_content(filename)
        except Exception:  # noqa: BLE001
            return False
        if not isinstance(content, list):
            return False
        for section in content:
            if not isinstance(section, dict):
                continue
            for section_content in section.values():
                items = (
                    section_content.get(BENCHMARK_ITEMS_KEY, [])
                    if isinstance(section_content, dict)
                    else []
                )
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    answers = item.get("answers")
                    if not isinstance(answers, list):
                        continue
                    for answer in answers:
                        if (
                            isinstance(answer, dict)
                            and answer.get("model_answer")
                            and answer.get("model_name")
                        ):
                            return True
        return False

    def evaluate_context(self):
        """Build selection data only for benchmark files that have model answers."""
        benchmark_files = [
            filename
            for filename in self.list_files()
            if self._has_model_answers(filename)
        ]
        metadata = get_metadata_for_files(benchmark_files)
        grouped_files = {}
        for filename in benchmark_files:
            file_metadata = metadata.get(filename)
            category = (
                file_metadata.get("category", UNCATEGORIZED)
                if file_metadata
                else UNCATEGORIZED
            )
            grouped_files.setdefault(category, []).append(
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

        category_names = sorted(
            grouped_files,
            key=lambda name: (name == UNCATEGORIZED, name.casefold()),
        )
        benchmark_groups = []
        for name in category_names:
            category_files = grouped_files[name]
            available_difficulties = {
                file_data["difficulty"] for file_data in category_files
            }
            benchmark_groups.append(
                {
                    "name": name,
                    "files": category_files,
                    "difficulties": [
                        level
                        for level in DIFFICULTY_LEVELS
                        if level in available_difficulties
                    ],
                }
            )

        system_prompt_template = ""
        try:
            system_prompt_template = (
                SYSTEM_PROMPTS_PATH / "evaluate_benchmark-SYSTEM.md"
            ).read_text(encoding="utf-8")
        except OSError:
            pass

        return {
            "benchmark_files": benchmark_files,
            "benchmark_groups": benchmark_groups,
            "active_models": self.service.active_models(),
            "run_system_prompt": system_prompt_template,
        }

    def load_content(self, filename):
        """Load one validated JSON document from the prompt directory."""
        if filename not in self.list_files():
            abort(404)
        benchmark_path = BENCHMARK_PROMPTS_PATH / filename
        try:
            with benchmark_path.open(encoding="utf-8") as benchmark_file:
                return json.load(benchmark_file)
        except (OSError, json.JSONDecodeError):
            current_app.logger.exception(
                "Could not load benchmark JSON from %s", benchmark_path
            )
            abort(500)

    def select(self, filename, page):
        """Display and update organization metadata for a benchmark file."""
        if filename not in self.list_files():
            abort(404)

        metadata = get_benchmark_metadata(filename) or {
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
                save_benchmark_metadata(
                    filename,
                    category,
                    difficulty,
                    notes,
                    generation_prompt,
                    model_name,
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
        if filename not in self.list_files():
            abort(404)
        data = request.get_json(silent=True) or {}
        model_spec = (data.get("model") or "").strip()
        system_prompt = data.get("system_prompt") or ""
        subcategory = data.get("subcategory") or ""
        request_text = data.get("request") or ""

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
            content = self.service.chat_completion(
                provider, model, prompt, request_text
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
        if filename not in self.list_files():
            abort(404)
        data = request.get_json(silent=True) or {}
        content = data.get("content")
        if not isinstance(content, (dict, list)):
            return jsonify({"error": "Invalid content."}), 400

        benchmark_path = BENCHMARK_PROMPTS_PATH / filename
        benchmark_path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8"
        )

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
            log_text = self._build_log_markdown(
                filename, content, system_prompt
            )
            LOGS_PATH.mkdir(parents=True, exist_ok=True)
            log_filename = Path(filename).stem + ".md"
            (LOGS_PATH / log_filename).write_text(log_text, encoding="utf-8")

        save_benchmark_metadata(
            filename=filename,
            category=category,
            difficulty=difficulty,
            notes="",
            generation_prompt=generation_prompt,
            model_name=model_name,
        )

        return jsonify(
            {
                "message": "Benchmark saved.",
                "filename": filename,
                "log_created": create_log,
            }
        )

    @staticmethod
    def _build_log_markdown(filename, content, system_prompt=""):
        """Build a readable markdown log from a processed benchmark."""
        lines = [f"# Benchmark Log: {filename}", ""]
        if not isinstance(content, list):
            return "\n".join(lines)
        for section in content:
            if not isinstance(section, dict):
                continue
            for subcategory, section_content in section.items():
                lines.append(f"## {subcategory}")
                lines.append("")
                items = (
                    section_content.get(BENCHMARK_ITEMS_KEY, [])
                    if isinstance(section_content, dict)
                    else []
                )
                for index, item in enumerate(items, start=1):
                    if not isinstance(item, dict):
                        continue
                    lines.append(f"### Request {index}")
                    lines.append("")
                    lines.append(item.get("request", ""))
                    lines.append("")
                    processed_prompt = (system_prompt or "").replace(
                        "{{subcategory}}", subcategory
                    )
                    lines.append("**System prompt:**")
                    lines.append("")
                    lines.append(processed_prompt)
                    lines.append("")
                    answers = item.get("answers") or []
                    if answers:
                        for answer in answers:
                            if not isinstance(answer, dict):
                                continue
                            lines.append(
                                f"**Model:** {answer.get('model_name', '')}"
                            )
                            lines.append("")
                            lines.append(
                                f"**Model response:** {answer.get('model_answer', '')}"
                            )
                            lines.append("")
                            response_time = answer.get(
                                "response_time", answer.get("reponse_time", "")
                            )
                            lines.append(f"**Response time:** {response_time}s")
                            lines.append("")
                    else:
                        lines.append("_No model response recorded._")
                        lines.append("")
                    lines.append("---")
                    lines.append("")
        return "\n".join(lines)

    def update_response(self, filename):
        """Update a single response value in a benchmark JSON file."""
        if filename not in self.list_files():
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

        content = self.load_content(filename)
        if not isinstance(content, list):
            return jsonify({"error": "Unsupported benchmark structure."}), 400
        if topic_index < 0 or topic_index >= len(content):
            return jsonify({"error": "Topic index out of range."}), 400
        section = content[topic_index]
        if not isinstance(section, dict) or not section:
            return jsonify({"error": "Invalid topic section."}), 400
        topic_name = next(iter(section))
        section_content = section[topic_name]
        items = (
            section_content.get(BENCHMARK_ITEMS_KEY, [])
            if isinstance(section_content, dict)
            else []
        )
        if request_index < 0 or request_index >= len(items):
            return jsonify({"error": "Request index out of range."}), 400
        if not isinstance(items[request_index], dict):
            return jsonify({"error": "Invalid request entry."}), 400

        items[request_index]["response"] = new_response

        benchmark_path = BENCHMARK_PROMPTS_PATH / filename
        benchmark_path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return jsonify({"message": "Response updated.", "filename": filename})

    def content(self, filename):
        """Return one benchmark document for the selection-page preview."""
        return jsonify({"filename": filename, "content": self.load_content(filename)})


benchmark_controller = BenchmarkController()
