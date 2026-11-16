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
        if (isError) {
            statusEl.classList.remove("save-confirmation");
            statusEl.classList.add("form-errors");
        } else {
            statusEl.classList.remove("form-errors");
            statusEl.classList.add("save-confirmation");
        }
        // Render message with an optional spinner while running.
        statusEl.textContent = "";
        if (isRunning) {
            const spinner = document.createElement("span");
            spinner.className = "status-spinner";
            spinner.setAttribute("aria-hidden", "true");
            statusEl.appendChild(spinner);
        } else if (!isError) {
            const icon = document.createElement("span");
            icon.className = "status-icon";
            icon.setAttribute("aria-hidden", "true");
            icon.textContent = "✓";
            statusEl.appendChild(icon);
        }
        const text = document.createElement("span");
        text.className = "status-text";
        text.textContent = message;
        statusEl.appendChild(text);
    };

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

        setStatus("Validating configuration...", false, true);

        // Small delay so the user sees the state transition.
        await new Promise((resolve) => setTimeout(resolve, 150));

        setStatus("Checking model server status...", false, true);
        await new Promise((resolve) => setTimeout(resolve, 150));

        // The server streams the model output and reports the topic and the
        // number of finished pairs it has actually parsed so far.
        const progressMessage = (state) => {
            const pairs = Number.isFinite(state.pairs) ? state.pairs : 0;
            const expected = Number.isFinite(state.expected) ? state.expected : null;
            const count = expected === null ? `${pairs}` : `${pairs} / ${expected}`;
            return `Model is running, please wait... ${state.topic} ${count}`;
        };

        setStatus(
            `Model is running, please wait... Preparing the ${categoryName} benchmark`,
            false,
            true
        );

        try {
            const response = await fetch("/create_benchmark/generate?stream=1", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "text/event-stream",
                },
                body: JSON.stringify({
                    category: categorySelect?.value || "",
                    new_category: newCategoryInput?.value?.trim() || "",
                    difficulty: difficulty,
                    model: modelSelect?.value || "",
                    system_prompt: systemPromptTextarea?.value || "",
                    user_prompt: userPromptTextarea?.value || "",
                    topics: topics,
                }),
            });
            if (!response.ok) {
                const payload = await response.json().catch(() => ({}));
                throw new api.ApiError(
                    payload.error || `HTTP ${response.status}`,
                    response.status,
                    payload
                );
            }
            if (!response.body) {
                throw new Error("Streaming is not supported by this browser.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let result = null;
            let failure = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const events = buffer.split("\n\n");
                buffer = events.pop() || "";
                for (const event of events) {
                    for (const line of event.split("\n")) {
                        if (!line.startsWith("data:")) continue;
                        const raw = line.slice(5).trim();
                        if (!raw) continue;
                        let message;
                        try {
                            message = JSON.parse(raw);
                        } catch (error) {
                            continue;
                        }
                        if (message.type === "progress") {
                            setStatus(progressMessage(message), false, true);
                        } else if (message.type === "result") {
                            result = message;
                        } else if (message.type === "error") {
                            failure = message.error || "Request failed";
                        }
                    }
                }
            }

            if (failure) throw new Error(failure);
            if (!result) throw new Error("The model did not return a benchmark.");

            const filename = result.filename || "";
            const characters = result.characters || 0;
            setStatus(
                `Benchmark JSON is ready: ${filename} (${characters.toLocaleString()} characters generated)`,
                false,
                false
            );

            // Reset all inputs to their default empty state.
            resetPromptInputs();
            if (typeof window.resetBenchmarkTopics === "function") {
                window.resetBenchmarkTopics();
            }
            if (createButton) createButton.disabled = false;
        } catch (error) {
            const message = error && error.message
                ? error.message
                : `Request failed: ${error}`;
            setStatus(message, true, false);
            window.alert(message);
            disablePromptInputs(false);
            if (createButton) createButton.disabled = false;
        }
    };

    if (createButton) {
        createButton.addEventListener("click", handleCreate);
    }
})();
