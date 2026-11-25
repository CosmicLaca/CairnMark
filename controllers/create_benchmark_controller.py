"""Page context and category creation for the benchmark creator."""

import json
import re
import secrets
from datetime import datetime

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

from models.benchmark_metadata import BENCHMARK_METADATA
from models.create_benchmark_settings import (
    CREATE_BENCHMARK_SETTINGS,
    CREATE_BENCHMARK_TOPICS,
)
from services.benchmark_categories import (
    UNCATEGORIZED,
    category_names,
    create_category,
    normalize_new_category,
)
from services.benchmark_documents import (
    DIFFICULTY_LEVELS,
    BenchmarkRepository,
    read_prompt_template,
)
from services.chat_requests import ChatRequestWorkflow
from services.model_providers import (
    ModelProviderService,
    ProviderOfflineError,
    ProviderValidationError,
)


PAIR_GENERATION_ATTEMPTS = 3
BENCHMARK_PAIR_FIELDS = (
    "request",
    "response",
    "answer_type",
    "accepted_answers",
    "numeric_tolerance",
    "key_points",
)


class BenchmarkGenerationError(Exception):
    """Raised when a model cannot deliver a benchmark JSON document."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


class CreateBenchmarkController:
    """Provide model choices and category creation for the creator."""

    def __init__(
        self,
        service=None,
        repository=None,
        metadata_repository=None,
        settings_repository=None,
        topics_repository=None,
    ):
        self.service = service or ModelProviderService()
        self.repository = repository or BenchmarkRepository()
        self.metadata = metadata_repository or BENCHMARK_METADATA
        self.settings = settings_repository or CREATE_BENCHMARK_SETTINGS
        self.topics = topics_repository or CREATE_BENCHMARK_TOPICS

    def context(self):
        """Return selector options and the current category selection."""
        categories = category_names()
        selected_category = request.args.get("category", UNCATEGORIZED)
        if selected_category not in {UNCATEGORIZED, *categories}:
            selected_category = UNCATEGORIZED

        created_category = request.args.get("created")
        if created_category not in categories:
            created_category = None

        active_models = self.service.active_models()
        saved_model = self.service.model_selector_model(
            "create_benchmark",
            active_models,
        )

        return {
            "active_models": active_models,
            "saved_model": saved_model,
            "benchmark_settings": self.settings.get(),
            "categories": categories,
            "selected_category": selected_category,
            "created_category": created_category,
            "difficulty_levels": DIFFICULTY_LEVELS,
            "system_prompt_template": read_prompt_template(
                "create_benchmark-SYSTEM.md"
            ),
            "user_prompt_template": read_prompt_template(
                "create_benchmark-USER.md"
            ),
            "new_category": "",
            "errors": [],
        }

    def save_model_selection(self):
        """Persist the benchmark creator's optional active-model selection."""
        data = request.get_json(silent=True) or {}
        try:
            model = self.service.save_model_selector_model(
                "create_benchmark",
                data.get("model"),
            )
        except ProviderValidationError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"model": model})

    def save_settings(self):
        """Persist settings used only by benchmark JSON creation."""
        data = request.get_json(silent=True) or {}
        try:
            saved = {
                **self._validate_parameters(data),
                "create_log": bool(data.get("create_log", False)),
            }
            saved = self.settings.save(saved)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"settings": saved})

    def saved_topics(self):
        """Return the latest topic rows saved for one category."""
        category = (request.args.get("category") or "").strip()
        if not category:
            return jsonify({"error": "Category is required."}), 400
        if category.casefold() == UNCATEGORIZED.casefold():
            return jsonify({"saved": False, "topics": []})
        topics = self.topics.get(category)
        return jsonify({"saved": topics is not None, "topics": topics or []})

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

    @staticmethod
    def _validate_parameters(parameters):
        """Validate the creator's allowlisted sampling parameters."""
        ranges = {
            "temperature": (0, 2),
            "top_p": (0, 1),
            "top_k": (0, 200),
            "min_p": (0, 1),
        }
        cleaned = {}
        for name, (minimum, maximum) in ranges.items():
            value = parameters.get(name)
            if value in (None, ""):
                cleaned[name] = None
                continue
            converter = int if name == "top_k" else float
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

    @staticmethod
    def _render_pair_prompt(
        template,
        category,
        difficulty,
        topic,
    ):
        """Render the user prompt for one model-generated benchmark pair."""
        return (
            template.replace("{{category}}", category)
            .replace("{{difficulty_level}}", difficulty)
            .replace("{{user_topics}}", topic)
        )

    @staticmethod
    def _pair_target(topic):
        """Return the validated pair count, including the form default."""
        raw = topic.get("pairs")
        return 5 if raw is None or str(raw).strip() == "" else int(raw)

    @staticmethod
    def _is_benchmark_pair(value):
        """Return whether model output has the required pair-object shape."""
        return (
            isinstance(value, dict)
            and set(value) == set(BENCHMARK_PAIR_FIELDS)
        )

    @staticmethod
    def _pair_shape_error(value):
        """Describe the model's structural mistake for the retry prompt."""
        if value is None:
            return "The response was not valid JSON."
        if isinstance(value, list):
            return "The response was a JSON array instead of one JSON object."
        if not isinstance(value, dict):
            return "The response was not a JSON object."

        required = set(BENCHMARK_PAIR_FIELDS)
        actual = set(value)
        details = []
        missing = sorted(required - actual)
        extra = sorted(actual - required)
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        if extra:
            details.append(f"extra keys: {', '.join(extra)}")
        return "The JSON object had " + "; ".join(details) + "."

    @staticmethod
    def _repair_pair_prompt(base_prompt, attempt, failure):
        """Add a compact structural correction after an invalid response."""
        schema = (
            '{"request":"...","response":"...","answer_type":"exact",'
            '"accepted_answers":[],"numeric_tolerance":null,'
            '"key_points":[]}'
        )
        return (
            f"{base_prompt}\n\nFORMAT CORRECTION (attempt {attempt}/"
            f"{PAIR_GENERATION_ATTEMPTS}): {failure} Discard the previous "
            "output. Return one object only, with exactly these keys and no "
            f"wrapper: {schema}"
        )

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
        user_prompt_template = data.get("user_prompt_template") or user_prompt

        try:
            parameters = self._validate_parameters(data)
            extra_parameters = ChatRequestWorkflow.model_parameters(
                data.get("model_params")
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        create_log = bool(data.get("create_log", False))

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

        if category.casefold() != UNCATEGORIZED.casefold():
            self.topics.save(category, filled_topics)

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
            "user_prompt_template": user_prompt_template,
            "topics": filled_topics,
            "parameters": parameters,
            "extra_parameters": extra_parameters,
            "create_log": create_log,
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
        user_prompt_template,
        topics,
        parameters,
        extra_parameters,
        create_log,
    ):
        """Generate individual pairs and assemble the final benchmark JSON."""
        document = []
        creation_log = {}
        character_count = 0
        topics_done = 0

        for topic in topics:
            topic_name = topic["name"].strip()
            expected = self._pair_target(topic)
            benchmarks = []
            generations = []

            for pair_number in range(1, expected + 1):
                pair_prompt = self._render_pair_prompt(
                    user_prompt_template,
                    category,
                    difficulty,
                    topic_name,
                )
                parsed = None
                attempt_prompt = pair_prompt
                for attempt in range(1, PAIR_GENERATION_ATTEMPTS + 1):
                    content = ""
                    activity_characters = 0
                    round_parameters = dict(parameters)
                    round_parameters["seed"] = secrets.randbelow(4294967296)
                    try:
                        for event in self.service.benchmark_generation_stream(
                            provider,
                            model,
                            system_prompt,
                            attempt_prompt,
                            **round_parameters,
                            extra_parameters=extra_parameters,
                        ):
                            if event.get("type") == "chunk":
                                text = event.get("text") or ""
                                if not text:
                                    continue
                                first_chunk = not content
                                content += text
                                activity_characters += len(text)
                                if first_chunk or activity_characters >= 128:
                                    activity_characters = 0
                                    yield {"type": "activity"}
                    except Exception as error:  # noqa: BLE001 - provider boundary
                        current_app.logger.exception(
                            "Benchmark generation failed for provider=%s model=%s",
                            provider,
                            model,
                        )
                        raise BenchmarkGenerationError(str(error)) from error

                    character_count += len(content)
                    parsed = self._extract_json(content)
                    if self._is_benchmark_pair(parsed):
                        break

                    failure = self._pair_shape_error(parsed)
                    yield {
                        "type": "retry",
                        "topic": topic_name,
                        "pair": pair_number,
                        "expected": expected,
                        "attempt": attempt,
                        "max_attempts": PAIR_GENERATION_ATTEMPTS,
                        "error": failure,
                    }
                    if attempt == PAIR_GENERATION_ATTEMPTS:
                        raise BenchmarkGenerationError(
                            f"{failure} Aborted after "
                            f"{PAIR_GENERATION_ATTEMPTS} failed attempts for "
                            f"'{topic_name}' pair {pair_number} of {expected}."
                        )
                    attempt_prompt = self._repair_pair_prompt(
                        pair_prompt,
                        attempt + 1,
                        failure,
                    )

                benchmarks.append(parsed)

                if create_log:
                    request_body = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": attempt_prompt},
                        ],
                        **{
                            name: value
                            for name, value in round_parameters.items()
                            if value is not None
                        },
                        **self.service.local_extra_parameters(
                            provider, extra_parameters
                        ),
                    }
                    generations.append(
                        {
                            "request_body": request_body,
                            "raw_response": parsed,
                        }
                    )

                yield {
                    "type": "progress",
                    "topic": topic_name,
                    "pairs": pair_number,
                    "expected": expected,
                    "topics_done": topics_done,
                }

            document.append({topic_name: {"benchmarks": benchmarks}})
            if create_log:
                creation_log[topic_name] = {"generations": generations}
            topics_done += 1

        # The model uses INSERT OR IGNORE and returns the canonical spelling.
        create_category(category)

        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        safe_category = self._sanitize_filename_part(category)
        filename = self.repository.unique_filename(
            f"Benchamrk-prompts-{timestamp}-{safe_category}-{difficulty}"
        )
        try:
            self.repository.create(filename, document)
        except OSError as error:
            current_app.logger.exception("Could not save generated benchmark")
            raise BenchmarkGenerationError(
                "The benchmark was generated but could not be saved."
            ) from error

        self.metadata.metadata(
            filename,
            {
                "category": category,
                "difficulty": difficulty,
                "notes": "",
                "generation_prompt": user_prompt,
                "model_name": model_spec,
            },
        )

        log_filename = None
        if create_log:
            log_filename = f"{filename.rsplit('.', 1)[0]}-creation.json"
            try:
                self.repository.save_json_log(
                    log_filename,
                    creation_log,
                )
            except OSError as error:
                current_app.logger.exception(
                    "Could not save benchmark creation log"
                )
                raise BenchmarkGenerationError(
                    "The benchmark was saved but its creation log could not be saved."
                ) from error

        yield {
            "type": "result",
            "message": "Benchmark JSON is ready.",
            "filename": filename,
            "characters": character_count,
            "log_filename": log_filename,
        }


create_benchmark_controller = CreateBenchmarkController()
