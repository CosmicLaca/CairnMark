(() => {
    "use strict";

    const api = window.CairnmarkApi;
    const templatesEl = document.getElementById("prompt-templates");
    let templates = { system: "", user: "" };
    try {
        templates = JSON.parse(templatesEl?.textContent || "{}");
    } catch (error) {
        templates = { system: "", user: "" };
    }

    const createButton = document.querySelector("[data-create-benchmark]");
    const categorySelect = document.querySelector("[data-category-select]");
    const modelSelect = document.querySelector("#model");
    const newCategoryInput = document.querySelector("#new-category");
    const systemPromptTextarea = document.querySelector("[data-system-prompt]");
    const userPromptTextarea = document.querySelector("[data-request-response-details]");
    const statusEl = document.getElementById("create-benchmark-status");
    let activeGenerationController = null;
    let topicLoadSequence = 0;

    const getSelectedDifficulty = () => {
        const checked = document.querySelector('input[name="difficulty"]:checked');
        return checked ? checked.value : "Normal";
    };

    const getFilledTopics = () => {
        const rows = document.querySelectorAll("[data-topic-row]");
        const topics = [];
        rows.forEach((row) => {
            const nameInput = row.querySelector("[data-topic-name]");
            const pairsInput = row.querySelector("[data-topic-pairs]");
            const name = nameInput?.value?.trim() || "";
            const pairsRaw = pairsInput?.value?.trim() || "";
            if (name) {
                topics.push({ name, pairs: pairsRaw });
            }
        });
        return topics;
    };

    const validate = () => {
        const errors = [];

        let categoryName = categorySelect?.value || "";
        if (categoryName === "__new__") {
            if (!newCategoryInput?.value?.trim()) {
                errors.push("Category is required.");
            }
        } else if (!categoryName || categoryName === "") {
            errors.push("Category is required.");
        }

        if (!modelSelect || !modelSelect.value) {
            errors.push("Model is required.");
        }

        const topics = getFilledTopics();
        if (topics.length === 0) {
            errors.push("At least one main topic is required.");
        }

        topics.forEach((topic) => {
            if (topic.pairs !== "") {
                const value = Number(topic.pairs);
                if (!Number.isInteger(value) || value < 1 || value > 100) {
                    errors.push(
                        `Request-response pairs for "${topic.name}" must be between 1 and 100.`
                    );
                }
            }
        });

        return { valid: errors.length === 0, errors, topics };
    };

    const resolveCategoryName = () => {
        const value = categorySelect?.value || "";
        if (value === "__new__") {
            return newCategoryInput?.value?.trim() || "";
        }
        return value;
    };

    const loadSavedTopics = async () => {
        const sequence = ++topicLoadSequence;
        const category = categorySelect?.value || "";
        if (!category || category === "__new__") {
            window.CairnmarkBenchmarkTopics?.reset();
            return;
        }
        try {
            const payload = await api.request(
                `/create_benchmark/topics?category=${encodeURIComponent(category)}`
            );
            if (
                sequence === topicLoadSequence
                && categorySelect?.value === category
            ) {
                if (payload?.saved) {
                    window.CairnmarkBenchmarkTopics?.replace(payload.topics);
                } else {
                    window.CairnmarkBenchmarkTopics?.reset();
                }
            }
        } catch (_error) {
            if (
                sequence === topicLoadSequence
                && categorySelect?.value === category
            ) {
                window.CairnmarkBenchmarkTopics?.reset();
            }
        }
    };

    const buildUserTopics = (topics) => {
        return topics
            .map((topic) => {
                const pairs = topic.pairs === "" ? 5 : Number(topic.pairs);
                return `- \`${topic.name}\`, create ${pairs} request-response pairs for this topic`;
            })
            .join("\n");
    };

    const setStatus = (message, isError, isRunning) => {
        if (!statusEl) return;
        statusEl.hidden = false;
        statusEl.classList.toggle("is-running", !!isRunning);
        statusEl.classList.toggle("is-error", !!isError);
        statusEl.classList.add("save-confirmation");
        statusEl.classList.remove("form-errors");
        // Render message with an optional spinner while running.
        statusEl.textContent = "";
        if (isRunning) {
            const spinner = document.createElement("span");
            spinner.className = "status-spinner";
            spinner.setAttribute("aria-hidden", "true");
            statusEl.appendChild(spinner);
        } else {
            const icon = document.createElement("span");
            icon.className = isError
                ? "status-icon status-icon--error"
                : "status-icon";
            icon.setAttribute("aria-hidden", "true");
            icon.textContent = isError ? "!" : "✓";
            statusEl.appendChild(icon);
        }
        const text = document.createElement("span");
        text.className = "status-text";
        text.textContent = message;
        statusEl.appendChild(text);
        if (isRunning && activeGenerationController) {
            const abortButton = document.createElement("button");
            abortButton.className = "status-abort-button";
            abortButton.type = "button";
            abortButton.textContent = "Abort";
            abortButton.addEventListener("click", () => {
                abortButton.disabled = true;
                abortButton.textContent = "Aborting...";
                activeGenerationController?.abort();
            }, { once: true });
            statusEl.appendChild(abortButton);
        }
    };

    const abortableDelay = (milliseconds, signal) => new Promise((resolve, reject) => {
        const timeout = window.setTimeout(resolve, milliseconds);
        signal.addEventListener("abort", () => {
            window.clearTimeout(timeout);
            reject(new DOMException("Generation aborted.", "AbortError"));
        }, { once: true });
    });

    const hideStatus = () => {
        if (!statusEl) return;
        statusEl.hidden = true;
        statusEl.textContent = "";
    };

    const disablePromptInputs = (disabled) => {
        if (systemPromptTextarea) systemPromptTextarea.disabled = disabled;
        if (userPromptTextarea) userPromptTextarea.disabled = disabled;
    };

    const resetPromptInputs = () => {
        if (systemPromptTextarea) systemPromptTextarea.value = "";
        if (userPromptTextarea) userPromptTextarea.value = "";
        disablePromptInputs(false);
    };

    const handleCreate = async () => {
        if (modelSelect?.value) {
            try {
                await api.json("/create_benchmark/model_selection", {
                    method: "POST",
                    body: { model: modelSelect.value },
                });
            } catch (error) {
                window.alert(`Model selection could not be saved: ${error}`);
            }
        }

        const { valid, errors, topics } = validate();
        if (!valid) {
            window.alert(errors.join("\n"));
            return;
        }

        const categoryName = resolveCategoryName();
        const difficulty = getSelectedDifficulty();
        const userTopics = buildUserTopics(topics);

        if (systemPromptTextarea) {
            systemPromptTextarea.value = templates.system || "";
        }
        if (userPromptTextarea) {
            let userPrompt = templates.user || "";
            userPrompt = userPrompt.replace(/\{\{category\}\}/g, categoryName);
            userPrompt = userPrompt.replace(/\{\{difficulty_level\}\}/g, difficulty);
            userPrompt = userPrompt.replace(/\{\{user_topics\}\}/g, userTopics);
            userPromptTextarea.value = userPrompt;
        }

        // Disable the multiline inputs so they stay readable but not editable.
        disablePromptInputs(true);
        if (createButton) createButton.disabled = true;
        const generationController = new AbortController();
        activeGenerationController = generationController;

        // The server streams the model output and reports the topic and the
        // number of finished pairs it has actually parsed so far.
        const progressMessage = (state) => {
            const pairs = Number.isFinite(state.pairs) ? state.pairs : 0;
            const expected = Number.isFinite(state.expected) ? state.expected : null;
            const count = expected === null ? `${pairs}` : `${pairs} / ${expected}`;
            return `Model is running, please wait... ${state.topic} ${count}`;
        };

        try {
            setStatus("Validating configuration...", false, true);

            // Small delay so the user sees the state transition.
            await abortableDelay(150, generationController.signal);

            setStatus("Checking model server status...", false, true);
            await abortableDelay(150, generationController.signal);

            setStatus(
                `Model is running, please wait... Preparing the ${categoryName} benchmark`,
                false,
                true
            );

            const events = api.eventStream("/create_benchmark/generate?stream=1", {
                method: "POST",
                signal: generationController.signal,
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    category: categorySelect?.value || "",
                    new_category: newCategoryInput?.value?.trim() || "",
                    difficulty: difficulty,
                    model: modelSelect?.value || "",
                    system_prompt: systemPromptTextarea?.value || "",
                    user_prompt: userPromptTextarea?.value || "",
                    user_prompt_template: templates.user || "",
                    topics: topics,
                    ...(window.CairnmarkBenchmarkSetup?.requestValues?.() || {}),
                }),
            });
            let result = null;
            let failure = "";

            for await (const message of events) {
                if (message.type === "progress") {
                    setStatus(progressMessage(message), false, true);
                } else if (message.type === "retry") {
                    const attempt = message.attempt || 1;
                    const maximum = message.max_attempts || 3;
                    const pair = message.pair || 1;
                    const expected = message.expected || "?";
                    const detail = message.error || "Invalid model response.";
                    const action = attempt < maximum ? " Retrying..." : " Aborting...";
                    setStatus(
                        `${detail} ${message.topic} pair ${pair} / ${expected}, failed attempt ${attempt} / ${maximum}.${action}`,
                        true,
                        attempt < maximum
                    );
                } else if (message.type === "result") {
                    result = message;
                } else if (message.type === "error") {
                    failure = message.error || "Request failed";
                }
            }

            if (failure) throw new Error(failure);
            if (!result) throw new Error("The model did not return a benchmark.");

            const filename = result.filename || "";
            const characters = result.characters || 0;
            setStatus(
                `Benchmark JSON is ready: ${filename} (${characters.toLocaleString()} characters generated)${result.log_filename ? `; log: ${result.log_filename}` : ""}`,
                false,
                false
            );

            // Reset generated prompt text while preserving the current topics.
            resetPromptInputs();
        } catch (error) {
            if (generationController.signal.aborted || error?.name === "AbortError") {
                setStatus("Generation aborted.", true, false);
                disablePromptInputs(false);
                return;
            }
            const message = error && error.message
                ? error.message
                : `Request failed: ${error}`;
            setStatus(message, true, false);
            window.alert(message);
            disablePromptInputs(false);
        } finally {
            if (activeGenerationController === generationController) {
                activeGenerationController = null;
            }
            if (createButton) createButton.disabled = false;
        }
    };

    if (createButton) {
        createButton.addEventListener("click", handleCreate);
    }
    categorySelect?.addEventListener("change", loadSavedTopics);
    loadSavedTopics();
})();
