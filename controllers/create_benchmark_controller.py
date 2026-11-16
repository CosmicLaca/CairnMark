"""Page context and category creation for the benchmark creator."""

import json
import re
from datetime import datetime
from pathlib import Path

from flask import (
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)

from models.benchmark_metadata import save_benchmark_metadata
from services.benchmark_categories import (
    UNCATEGORIZED,
    category_names,
    create_category,
    normalize_new_category,
)
from services.benchmark_documents import DIFFICULTY_LEVELS, BenchmarkRepository
from services.benchmark_progress import BenchmarkStreamParser
from services.model_providers import (
    ModelProviderService,
    ProviderOfflineError,
    ProviderValidationError,
)


class BenchmarkGenerationError(Exception):
    """Raised when a model cannot deliver a benchmark JSON document."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


class CreateBenchmarkController:
    """Provide model choices and category creation for the creator."""

    def __init__(self, service=None, repository=None):
        self.service = service or ModelProviderService()
        self.repository = repository or BenchmarkRepository()

    @staticmethod
    def _prompt_template(filename):
        """Read one configured prompt template and log missing files."""
        path = Path(current_app.config["SYSTEM_PROMPT_DIRECTORY"]) / filename
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            current_app.logger.warning("Could not read system prompt %s", path)
            return ""

    def context(self):
        """Return selector options and the current category selection."""
        categories = category_names()
        selected_category = request.args.get("category", UNCATEGORIZED)
        if selected_category not in {UNCATEGORIZED, *categories}:
            selected_category = UNCATEGORIZED

        created_category = request.args.get("created")
        if created_category not in categories:
            created_category = None

        return {
            "active_models": self.service.active_models(),
            "categories": categories,
            "selected_category": selected_category,
            "created_category": created_category,
            "difficulty_levels": DIFFICULTY_LEVELS,
            "system_prompt_template": self._prompt_template(
                "create_benchmark-SYSTEM.md"
            ),
            "user_prompt_template": self._prompt_template(
                "create_benchmark-USER.md"
            ),
            "new_category": "",
            "errors": [],
        }

    def save_category(self, page):
        """Create a category from the creator form and return to the page."""
        categories = category_names()
        choice = request.form.get("category", UNCATEGORIZED)
        new_category = request.form.get("new_category", "")

        if choice == "__new__":
            category, error = normalize_new_category(new_category, categories)
            if not error and category.casefold() == UNCATEGORIZED.casefold():
                error = "Choose a different name for the new category."
            if not error:
                category = create_category(category)
                return redirect(
                    url_for(
                        "create_benchmark",
                        category=category,
                        created=category,
                    )
                )
            context = self.context()
            context.update(
                {
                    "page": page,
                    "errors": [error],
                    "selected_category": "__new__",
                    "new_category": new_category,
                }
            )
            return render_template("create_benchmark.html", **context)

        if choice not in {UNCATEGORIZED, *categories}:
            context = self.context()
            context.update(
                {
                    "page": page,
                    "errors": ["Select an available category."],
                }
            )
            return render_template("create_benchmark.html", **context)

        return redirect(url_for("create_benchmark", category=choice))

    @staticmethod
    def _extract_json(text):
        """Return the first JSON value found in a model response."""
        if not text:
            return None
        text = text.strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except (json.JSONDecodeError, ValueError):
                pass
        for index, char in enumerate(text):
            if char in "[{":
                try:
                    value, _end = json.JSONDecoder().raw_decode(text[index:])
                    return value
                except (json.JSONDecodeError, ValueError):
                    continue
        return None

    @staticmethod
    def _sanitize_filename_part(value):
        """Make a string safe for use in a filename."""
        value = (value or "").strip()
        value = value.replace("/", "_").replace("\\\\", "_")
        value = re.sub(r"[^\w\-. ]+", "", value)
        value = re.sub(r"\s+", "_", value)
        return value or "benchmark"

    def generate(self):
        """Generate a benchmark JSON via the selected model."""
        data = request.get_json(silent=True) or {}

        category = (data.get("category") or "").strip()
        new_category = (data.get("new_category") or "").strip()
        if category == "__new__":
            category = new_category

        difficulty = (data.get("difficulty") or "").strip()
        model_spec = (data.get("model") or "").strip()
        system_prompt = data.get("system_prompt") or ""
        user_prompt = data.get("user_prompt") or ""

        topics = data.get("topics") or []
        filled_topics = [
            topic for topic in topics
            if isinstance(topic, dict) and (topic.get("name") or "").strip()
        ]

        errors = []
        if not category:
            errors.append("Category is required.")
        if difficulty not in {"Easy", "Normal", "Hard"}:
            errors.append("Difficulty is required.")
        if not model_spec or "::" not in model_spec:
            errors.append("Model is required.")
        if not filled_topics:
            errors.append("At least one main topic is required.")
        for topic in filled_topics:
            topic_name = topic["name"]
            pairs = (topic.get("pairs") or "").strip()
            if pairs:
                try:
                    value = int(pairs)
                except ValueError:
                    errors.append(
                        f"Request-response pairs for '{topic_name}' must be a number."
                    )
                    continue
                if value < 1 or value > 100:
                    errors.append(
                        f"Request-response pairs for '{topic_name}' must be "
                        "between 1 and 100."
                    )

        if errors:
            return jsonify({"error": errors[0]}), 400

        try:
            provider, model = self.service.resolve_online_model(model_spec)
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderOfflineError as error:
            return jsonify({"error": str(error)}), 503

        generation = {
            "category": category,
            "difficulty": difficulty,
            "model_spec": model_spec,
            "provider": provider,
            "model": model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "topics": filled_topics,
        }

        stream_requested = (
            request.args.get("stream") == "1"
            or "text/event-stream" in (request.accept_mimetypes or "")
        )

        if not stream_requested:
            result = None
            try:
                for event in self._generation_events(**generation):
                    if event.get("type") == "result":
                        result = event
            except BenchmarkGenerationError as error:
                return jsonify({"error": str(error)}), error.status
            if result is None:
                return jsonify({"error": "The model did not return valid JSON."}), 502
            payload = dict(result)
            payload.pop("type", None)
            return jsonify(payload)

        def generate_stream():
            try:
                for event in self._generation_events(**generation):
                    yield f"data: {json.dumps(event)}\n\n"
            except BenchmarkGenerationError as error:
                payload = {"type": "error", "error": str(error)}
                yield f"data: {json.dumps(payload)}\n\n"

        return Response(
            stream_with_context(generate_stream()),
            mimetype="text/event-stream",
        )

    def _generation_events(
        self,
        category,
        difficulty,
        model_spec,
        provider,
        model,
        system_prompt,
        user_prompt,
        topics,
    ):
        """Yield topic progress while the model writes, then the saved result."""
        parser = BenchmarkStreamParser(topics)
        content = ""
        last_progress = None
        try:
            for event in self.service.chat_completion_stream(
                provider, model, system_prompt, user_prompt
            ):
                if event.get("type") != "chunk":
                    continue
                text = event.get("text") or ""
                if not text:
                    continue
                content += text
                state = parser.feed(text)
                if not state:
                    continue
                progress = (state["topic"], state["pairs"])
                if progress == last_progress:
                    continue
                last_progress = progress
                yield {"type": "progress", **state}
        except Exception as error:  # noqa: BLE001 - surface provider errors
            current_app.logger.exception(
                "Benchmark generation failed for provider=%s model=%s",
                provider,
                model,
            )
            raise BenchmarkGenerationError(str(error)) from error

        parsed = self._extract_json(content)
        if parsed is None:
            raise BenchmarkGenerationError("The model did not return valid JSON.")

        # The model uses INSERT OR IGNORE and returns the canonical spelling.
        create_category(category)

        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        safe_category = self._sanitize_filename_part(category)
        filename = self.repository.unique_filename(
            f"Benchamrk-prompts-{timestamp}-{safe_category}-{difficulty}"
        )
        try:
            self.repository.create(filename, parsed)
        except OSError as error:
            current_app.logger.exception("Could not save generated benchmark")
            raise BenchmarkGenerationError(
                "The benchmark was generated but could not be saved."
            ) from error

        save_benchmark_metadata(
            filename=filename,
            category=category,
            difficulty=difficulty,
            notes="",
            generation_prompt=user_prompt,
            model_name=model_spec,
        )

        yield {
            "type": "result",
            "message": "Benchmark JSON is ready.",
            "filename": filename,
            "characters": len(content),
        }


create_benchmark_controller = CreateBenchmarkController()
