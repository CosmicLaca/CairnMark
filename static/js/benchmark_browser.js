(() => {
    "use strict";

    const api = window.CairnmarkApi;
    // Each topic section stores its request-response pairs under this key.
    const BENCHMARK_ITEMS_KEY = "benchmarks";
    const tabs = [...document.querySelectorAll("[data-category-trigger]")];
    const panels = [...document.querySelectorAll("[data-category-panel]")];
    const fileCount = document.querySelector("[data-visible-file-count]");
    const viewButtons = [...document.querySelectorAll("[data-view-benchmark]")];
    const createButtons = [...document.querySelectorAll("[data-create-benchmark]")];
    const evaluateButtons = [...document.querySelectorAll("[data-evaluate-benchmark]")];
    const preview = document.querySelector("[data-benchmark-preview]");
    const previewFilename = preview?.querySelector("[data-preview-filename]");
    const previewBody = preview?.querySelector("[data-preview-body]");
    const closePreviewButton = preview?.querySelector("[data-close-preview]");
    const createSetup = document.querySelector("[data-create-benchmark-setup]");
    const createSetupFilename = createSetup?.querySelector("[data-create-benchmark-filename]");
    const createSetupBody = createSetup?.querySelector("[data-create-benchmark-body]");
    const closeCreateSetupButton = createSetup?.querySelector("[data-close-create-benchmark-setup]");
    const evaluateSetup = document.querySelector("[data-evaluate-benchmark-setup]");
    const evaluateSetupFilename = evaluateSetup?.querySelector("[data-evaluate-benchmark-filename]");
    const evaluateSetupBody = evaluateSetup?.querySelector("[data-evaluate-benchmark-body]");
    const closeEvaluateSetupButton = evaluateSetup?.querySelector("[data-close-evaluate-benchmark-setup]");
    const evaluateRunButton = document.querySelector("[data-evaluate-benchmark-run]");
    const systemPromptTextarea = document.querySelector("[data-system-prompt]");
    const systemPromptTemplate = systemPromptTextarea ? systemPromptTextarea.value : "";
    let systemPromptLast = systemPromptTemplate;
    const runButton = document.querySelector("[data-run-benchmark]");
    const runStatus = document.getElementById("run-benchmark-status");

    if (!tabs.length || !panels.length || !fileCount) {
        return;
    }

    let activeViewButton = null;
    let activeCreateButton = null;
    let activeEvaluateButton = null;
    let activeRequest = null;
    let currentPreviewFilename = null;

    const createElement = (tagName, className, text) => {
        const element = document.createElement(tagName);
        if (className) {
            element.className = className;
        }
        if (text !== undefined) {
            element.textContent = text;
        }
        return element;
    };

    const printableValue = (value) =>
        typeof value === "string" ? value : JSON.stringify(value, null, 2);

    const benchmarkSections = (content) => {
        // Only the new structure is supported: an array of objects, each
        // with a single topic key mapping to { benchmarks: [...] }.
        if (!Array.isArray(content)) {
            return [];
        }
        return content.flatMap((section) =>
            section && typeof section === "object"
                ? Object.entries(section)
                : []
        );
    };

    const closePreview = (restoreFocus = false) => {
        activeRequest?.abort();
        activeRequest = null;
        if (activeViewButton) {
            activeViewButton.classList.remove("is-active");
            activeViewButton.setAttribute("aria-expanded", "false");
            if (restoreFocus) {
                activeViewButton.focus();
            }
        }
        activeViewButton = null;
        if (preview) {
            preview.hidden = true;
        }
        previewBody?.replaceChildren();
    };

    const closeCreateSetup = (restoreFocus = false) => {
        if (activeCreateButton) {
            activeCreateButton.classList.remove("is-active");
            activeCreateButton.setAttribute("aria-expanded", "false");
            if (restoreFocus) {
                activeCreateButton.focus();
            }
        }
        activeCreateButton = null;
        if (createSetup) {
            createSetup.hidden = true;
        }
    };

    const closeEvaluateSetup = (restoreFocus = false) => {
        if (activeEvaluateButton) {
            activeEvaluateButton.classList.remove("is-active");
            activeEvaluateButton.setAttribute("aria-expanded", "false");
            if (restoreFocus) {
                activeEvaluateButton.focus();
            }
        }
        activeEvaluateButton = null;
        if (evaluateSetup) {
            evaluateSetup.hidden = true;
        }
    };

    const applyDifficultyFilter = (panel, selectedButton) => {
        const filter = selectedButton.dataset.difficultyFilter;
        const filterButtons = [
            ...panel.querySelectorAll("[data-difficulty-filter]"),
        ];
        const files = [...panel.querySelectorAll("[data-benchmark-file]")];

        filterButtons.forEach((button) => {
            const active = button === selectedButton;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
        });

        let visibleCount = 0;
        files.forEach((file) => {
            const visible =
                filter === "All" || file.dataset.difficulty === filter;
            file.hidden = !visible;
            visibleCount += Number(visible);
        });

        const totalCount = files.length;
        const summary = panel.querySelector("[data-category-file-summary]");
        summary.textContent =
            filter === "All"
                ? `${totalCount} ${totalCount === 1 ? "file" : "files"}`
                : `${visibleCount} of ${totalCount} files`;
        fileCount.textContent = `${visibleCount} ${
            visibleCount === 1 ? "file" : "files"
        } ready`;

        if (activeViewButton) {
            closePreview();
        }
        if (activeCreateButton) {
            closeCreateSetup();
        }
        if (activeEvaluateButton) {
            closeEvaluateSetup();
        }
    };

    const startEditResponse = (
        responseBlock,
        responseTextEl,
        editButton,
        filename,
        topicIndex,
        requestIndex,
        currentValue
    ) => {
        // Avoid duplicate editors.
        if (responseBlock.querySelector(".response-editor")) return;

        responseTextEl.hidden = true;
        editButton.hidden = true;

        const editor = createElement("div", "response-editor");
        const textarea = document.createElement("textarea");
        textarea.className = "response-editor-input";
        textarea.value = currentValue ?? "";
        const actions = createElement("div", "response-editor-actions");
        const saveBtn = createElement("button", "response-editor-save", "Save");
        saveBtn.type = "button";
        const cancelBtn = createElement("button", "response-editor-cancel", "Cancel");
        cancelBtn.type = "button";

        saveBtn.addEventListener("click", async () => {
            const newValue = textarea.value;
            saveBtn.disabled = true;
            try {
                await api.json(
                    `/run_benchmark/${encodeURIComponent(filename)}/update_response`,
                    {
                        method: "POST",
                        body: {
                            topic_index: topicIndex,
                            request_index: requestIndex,
                            response: newValue,
                        },
                    }
                );
                responseTextEl.textContent = printableValue(newValue);
                exitEdit();
            } catch (error) {
                window.alert(`Save failed: ${error.message || error}`);
            } finally {
                saveBtn.disabled = false;
            }
        });

        const exitEdit = () => {
            editor.remove();
            responseTextEl.hidden = false;
            editButton.hidden = false;
        };
        cancelBtn.addEventListener("click", exitEdit);

        actions.append(saveBtn, cancelBtn);
        editor.append(textarea, actions);
        responseBlock.append(editor);
        textarea.focus();
    };

    const renderBenchmark = (content) => {
        const sections = benchmarkSections(content);
        const fragment = document.createDocumentFragment();

        if (!sections.length) {
            fragment.append(
                createElement(
                    "p",
                    "preview-message",
                    "This JSON file has no supported benchmark sections."
                )
            );
            previewBody.replaceChildren(fragment);
            return;
        }

        sections.forEach(([sectionName, sectionContent], sectionIndex) => {
            const items = Array.isArray(sectionContent?.[BENCHMARK_ITEMS_KEY])
                ? sectionContent[BENCHMARK_ITEMS_KEY]
                : [];
            const entries = items.map((item, index) => [
                String(index + 1),
                item && typeof item === "object" ? item : {},
            ]);
            const details = createElement("details", "benchmark-accordion");
            details.open = sectionIndex === 0;

            const summary = createElement("summary");
            summary.append(
                createElement(
                    "span",
                    "accordion-index",
                    String(sectionIndex + 1).padStart(2, "0")
                ),
                createElement("strong", "accordion-title", sectionName),
                createElement(
                    "small",
                    "accordion-count",
                    `${entries.length} ${entries.length === 1 ? "prompt" : "prompts"}`
                ),
                createElement("span", "accordion-toggle", "+")
            );
            details.append(summary);

            const promptList = createElement("ol", "prompt-pair-list");
            entries.forEach(([entryKey, entry], entryIndex) => {
                const item = createElement("li", "prompt-pair");
                item.append(
                    createElement("span", "prompt-number", entryKey)
                );

                const requestBlock = createElement("div", "prompt-request");
                requestBlock.append(
                    createElement("span", "prompt-label", "Request"),
                    createElement(
                        "p",
                        null,
                        printableValue(entry?.request ?? "Request not provided")
                    )
                );

                const responseBlock = createElement("div", "prompt-response");
                const responseLabel = createElement("span", "prompt-label", "Response");
                const responseText = createElement(
                    "p",
                    null,
                    printableValue(entry?.response ?? "Response not provided")
                );
                const hasAnswers =
                    Array.isArray(entry?.answers) &&
                    entry.answers.some(
                        (answer) =>
                            answer &&
                            typeof answer === "object" &&
                            (answer.model_answer || answer.model_name)
                    );

                const editButton = createElement(
                    "button",
                    "response-edit-button" + (hasAnswers ? " is-locked" : ""),
                    "✎"
                );
                editButton.type = "button";
                if (hasAnswers) {
                    editButton.disabled = true;
                    editButton.title =
                        "Response cannot be edited because the request already has model answers.";
                } else {
                    editButton.title = "Edit response";
                    editButton.addEventListener("click", () => {
                        startEditResponse(
                            responseBlock,
                            responseText,
                            editButton,
                            currentPreviewFilename,
                            sectionIndex,
                            entryIndex,
                            entry?.response ?? ""
                        );
                    });
                }
                responseBlock.append(responseLabel, responseText, editButton);

                item.append(requestBlock, responseBlock);
                promptList.append(item);
            });
            details.append(promptList);
            fragment.append(details);
        });

        previewBody.replaceChildren(fragment);
    };

    const showPreview = async (button) => {
        activeRequest?.abort();
        if (activeCreateButton) {
            closeCreateSetup();
        }
        if (activeEvaluateButton) {
            closeEvaluateSetup();
        }
        viewButtons.forEach((viewButton) => {
            const active = viewButton === button;
            viewButton.classList.toggle("is-active", active);
            viewButton.setAttribute("aria-expanded", String(active));
        });
        activeViewButton = button;
        const requestController = new AbortController();
        activeRequest = requestController;
        preview.hidden = false;
        previewFilename.textContent = button.dataset.filename;
        currentPreviewFilename = button.dataset.filename;
        previewBody.replaceChildren(
            createElement("p", "preview-message is-loading", "Reading local JSON…")
        );
        preview.scrollIntoView({ behavior: "smooth", block: "start" });

        try {
            const payload = await api.request(button.dataset.contentUrl, {
                headers: { Accept: "application/json" },
                signal: requestController.signal,
            });
            renderBenchmark(payload.content);
        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }
            previewBody.replaceChildren(
                createElement(
                    "p",
                    "preview-message is-error",
                    "The benchmark JSON could not be displayed."
                )
            );
        } finally {
            if (activeRequest === requestController) {
                activeRequest = null;
            }
        }
    };

    const showCreateSetup = (button) => {
        // Close any other open panel first.
        if (activeViewButton) {
            closePreview();
        }
        if (activeEvaluateButton) {
            closeEvaluateSetup();
        }
        if (activeCreateButton && activeCreateButton !== button) {
            closeCreateSetup();
        }

        createButtons.forEach((createButton) => {
            const active = createButton === button;
            createButton.classList.toggle("is-active", active);
            createButton.setAttribute("aria-expanded", String(active));
        });
        activeCreateButton = button;
        if (createSetup) {
            createSetup.hidden = false;
        }
        if (createSetupFilename) {
            createSetupFilename.textContent = button.dataset.filename || "Benchmark setup";
        }
        if (systemPromptTextarea) {
            const current = systemPromptTextarea.value;
            const canReplace =
                current === systemPromptTemplate || current === systemPromptLast;
            if (canReplace) {
                const category = button.dataset.category || "";
                const difficulty = button.dataset.difficulty || "";
                let value = systemPromptTemplate;
                value = value.replace(/\{\{category\}\}/g, category);
                value = value.replace(/\{\{difficulty_level\}\}/g, difficulty);
                systemPromptTextarea.value = value;
                systemPromptLast = value;
            }
        }
        createSetup?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const showEvaluateSetup = (button) => {
        if (activeViewButton) {
            closePreview();
        }
        if (activeCreateButton) {
            closeCreateSetup();
        }
        if (activeEvaluateButton && activeEvaluateButton !== button) {
            closeEvaluateSetup();
        }

        evaluateButtons.forEach((evaluateButton) => {
            const active = evaluateButton === button;
            evaluateButton.classList.toggle("is-active", active);
            evaluateButton.setAttribute("aria-expanded", String(active));
        });
        activeEvaluateButton = button;
        if (evaluateSetup) {
            evaluateSetup.hidden = false;
        }
        if (evaluateSetupFilename) {
            evaluateSetupFilename.textContent = button.dataset.filename || "Benchmark setup";
        }
        if (systemPromptTextarea) {
            const current = systemPromptTextarea.value;
            const canReplace =
                current === systemPromptTemplate || current === systemPromptLast;
            if (canReplace) {
                const category = button.dataset.category || "";
                const difficulty = button.dataset.difficulty || "";
                let value = systemPromptTemplate;
                value = value.replace(/\{\{category\}\}/g, category);
                value = value.replace(/\{\{difficulty_level\}\}/g, difficulty);
                systemPromptTextarea.value = value;
                systemPromptLast = value;
            }
        }
        evaluateSetup?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const setRunStatus = (message, isError, isRunning) => {
        if (!runStatus) return;
        runStatus.hidden = false;
        runStatus.classList.toggle("is-running", !!isRunning);
        if (isError) {
            runStatus.classList.remove("save-confirmation");
            runStatus.classList.add("form-errors");
        } else {
            runStatus.classList.remove("form-errors");
            runStatus.classList.add("save-confirmation");
        }
        runStatus.textContent = "";
        if (isRunning) {
            const spinner = document.createElement("span");
            spinner.className = "status-spinner";
            spinner.setAttribute("aria-hidden", "true");
            runStatus.appendChild(spinner);
        } else {
            const icon = document.createElement("span");
            icon.className = "status-icon";
            icon.setAttribute("aria-hidden", "true");
            icon.textContent = isError ? "!" : "✓";
            runStatus.appendChild(icon);
        }
        const text = document.createElement("span");
        text.className = "status-text";
        text.textContent = message;
        runStatus.appendChild(text);
    };

    const runBenchmark = async () => {
        const filename = activeCreateButton?.dataset?.filename;
        if (!filename) {
            window.alert("Select a benchmark file first.");
            return;
        }
        const modelSelect = document.querySelector("#create-benchmark-model");
        const model = modelSelect?.value || "";
        if (!model) {
            window.alert("Model is required.");
            return;
        }
        const systemPrompt = systemPromptTextarea?.value || "";
        const generationSettings =
            window.CairnmarkRunBenchmarkSetup?.requestValues?.() || {};

        if (runButton) runButton.disabled = true;
        setRunStatus("Loading benchmark JSON…", false, true);

        let payload;
        try {
            payload = await api.request(
                `/run_benchmark/${encodeURIComponent(filename)}/content`,
                { headers: { Accept: "application/json" } }
            );
        } catch (error) {
            setRunStatus(`Failed to load benchmark: ${error}`, true, false);
            if (runButton) runButton.disabled = false;
            return;
        }

        const content = payload.content;
        if (!Array.isArray(content)) {
            setRunStatus("Unsupported benchmark JSON structure.", true, false);
            if (runButton) runButton.disabled = false;
            return;
        }

        // Count total request-response pairs.
        let total = 0;
        content.forEach((section) => {
            if (section && typeof section === "object") {
                Object.values(section).forEach((value) => {
                    if (value && Array.isArray(value[BENCHMARK_ITEMS_KEY])) {
                        total += value[BENCHMARK_ITEMS_KEY].length;
                    }
                });
            }
        });

        let processed = 0;
        try {
            for (const section of content) {
                if (!section || typeof section !== "object") continue;
                for (const [subcategory, sectionContent] of Object.entries(section)) {
                    const items = Array.isArray(sectionContent?.[BENCHMARK_ITEMS_KEY])
                        ? sectionContent[BENCHMARK_ITEMS_KEY]
                        : [];
                    for (const item of items) {
                        processed += 1;
                        setRunStatus(
                            `${subcategory}: ${processed}/${total}`,
                            false,
                            true
                        );
                        const result = await api.json(
                            `/run_benchmark/${encodeURIComponent(filename)}/process_one`,
                            {
                                method: "POST",
                                body: {
                                    model,
                                    system_prompt: systemPrompt,
                                    subcategory,
                                    request: item.request,
                                    ...generationSettings,
                                },
                            }
                        );
                        if (!Array.isArray(item.answers)) {
                            item.answers = [];
                        }
                        item.answers.push({
                            model_name: model,
                            model_answer: result.response,
                            response_time: result.time,
                        });
                    }
                }
            }
        } catch (error) {
            setRunStatus(`Run failed: ${error}`, true, false);
            if (runButton) runButton.disabled = false;
            return;
        }

        // Save result.
        setRunStatus("Saving benchmark JSON…", false, true);
        try {
            const createLog = Boolean(generationSettings.create_log);
            const saveResult = await api.json(
                `/run_benchmark/${encodeURIComponent(filename)}/save_result`,
                {
                    method: "POST",
                    body: {
                        content,
                        category: activeCreateButton?.dataset?.category || "Uncategorized",
                        difficulty: activeCreateButton?.dataset?.difficulty || "Normal",
                        generation_prompt: systemPrompt,
                        system_prompt: systemPrompt,
                        model_name: model,
                        create_log: createLog,
                    },
                }
            );
            const logNote = saveResult.log_created ? " (log saved)" : "";
            setRunStatus(
                `Benchmark run complete: ${saveResult.filename || filename}${logNote}`,
                false,
                false
            );
        } catch (error) {
            setRunStatus(`Save failed: ${error}`, true, false);
        } finally {
            if (runButton) runButton.disabled = false;
        }
    };

    const activateTab = (selectedTab, moveFocus = false) => {
        if (activeViewButton) {
            closePreview();
        }
        if (activeCreateButton) {
            closeCreateSetup();
        }
        if (activeEvaluateButton) {
            closeEvaluateSetup();
        }
        tabs.forEach((tab) => {
            const active = tab === selectedTab;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", String(active));
            tab.tabIndex = active ? 0 : -1;
            if (active && moveFocus) {
                tab.focus();
            }
        });

        panels.forEach((panel) => {
            panel.hidden = panel.id !== selectedTab.dataset.categoryTrigger;
        });

        const activePanel = panels.find(
            (panel) => panel.id === selectedTab.dataset.categoryTrigger
        );
        const allDifficulties = activePanel.querySelector(
            '[data-difficulty-filter="All"]'
        );
        applyDifficultyFilter(activePanel, allDifficulties);
    };

    tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => activateTab(tab));
        tab.addEventListener("keydown", (event) => {
            let nextIndex;
            if (event.key === "ArrowRight") {
                nextIndex = (index + 1) % tabs.length;
            } else if (event.key === "ArrowLeft") {
                nextIndex = (index - 1 + tabs.length) % tabs.length;
            } else if (event.key === "Home") {
                nextIndex = 0;
            } else if (event.key === "End") {
                nextIndex = tabs.length - 1;
            } else {
                return;
            }
            activateTab(tabs[nextIndex], true);
            event.preventDefault();
        });
    });

    viewButtons.forEach((button) => {
        button.addEventListener("click", () => showPreview(button));
    });
    createButtons.forEach((button) => {
        button.addEventListener("click", () => showCreateSetup(button));
    });
    evaluateButtons.forEach((button) => {
        button.addEventListener("click", () => showEvaluateSetup(button));
    });
    closeCreateSetupButton?.addEventListener("click", () => closeCreateSetup(true));
    closeEvaluateSetupButton?.addEventListener("click", () => closeEvaluateSetup(true));
    runButton?.addEventListener("click", () => runBenchmark());
    panels.forEach((panel) => {
        panel.querySelectorAll("[data-difficulty-filter]").forEach((button) => {
            button.addEventListener("click", () =>
                applyDifficultyFilter(panel, button)
            );
        });
    });
    closePreviewButton?.addEventListener("click", () => closePreview(true));

    activateTab(tabs[0]);
})();
