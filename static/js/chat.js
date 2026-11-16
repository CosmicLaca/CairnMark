(() => {
    "use strict";

    const api = window.CairnmarkApi;
    const historyEl = document.querySelector("[data-chat-history]");
    const emptyStateEl = document.querySelector("[data-chat-empty]");
    const inputEl = document.querySelector("[data-chat-input]");
    const sendBtn = document.querySelector("[data-chat-send]");
    const modelSelect = document.querySelector("[data-chat-model]");
    const systemPromptEl = document.querySelector("[data-chat-system-prompt]");
    const tempEl = document.querySelector("[data-chat-temperature]");
    const topPEl = document.querySelector("[data-chat-top-p]");
    const topKEl = document.querySelector("[data-chat-top-k]");
    const seedEl = document.querySelector("[data-chat-seed]");
    const historyLimitEl = document.querySelector("[data-chat-history-limit]");
    const saveBtn = document.querySelector("[data-chat-save-settings]");
    const clearBtn = document.querySelector("[data-chat-clear]");
    const savedSelect = document.querySelector("[data-chat-saved]");
    const deleteBtn = document.querySelector("[data-chat-delete]");
    const saveOpenBtn = document.querySelector("[data-chat-save-open]");
    const saveModal = document.querySelector("[data-save-chat-modal]");
    const saveNameInput = document.querySelector("[data-save-chat-name]");
    const saveConfirmBtn = document.querySelector("[data-save-chat-confirm]");
    const saveCloseBtns = document.querySelectorAll("[data-save-chat-close]");
    const savedSpSelect = document.querySelector("[data-chat-saved-sp]");
    const deleteSpBtn = document.querySelector("[data-chat-delete-sp]");
    const promptModal = document.querySelector("[data-prompt-modal]");
    const promptText = document.querySelector("[data-prompt-text]");
    const promptCloseBtns = document.querySelectorAll("[data-prompt-close]");
    const requestBodyModal = document.querySelector("[data-request-body-modal]");
    const requestBodyText = document.querySelector("[data-request-body-text]");
    const requestBodyCloseBtns = document.querySelectorAll("[data-request-body-close]");
    const saveSpOpenBtn = document.querySelector("[data-chat-save-sp-open]");
    const saveSpModal = document.querySelector("[data-save-sp-modal]");
    const saveSpNameInput = document.querySelector("[data-save-sp-name]");
    const saveSpConfirmBtn = document.querySelector("[data-save-sp-confirm]");
    const saveSpCloseBtns = document.querySelectorAll("[data-save-sp-close]");
    const moreParamsBtn = document.querySelector("[data-chat-more-params]");
    const moreParamsModal = document.querySelector("[data-more-params-modal]");
    const moreParamsTitle = document.querySelector("[data-more-params-title]");
    const moreParamsCloseBtns = document.querySelectorAll("[data-more-params-close]");
    const moreParamsSaveBtn = document.querySelector("[data-more-params-save]");
    const moreParamsLoading = document.querySelector("[data-more-params-loading]");
    const moreParamsContent = document.querySelector("[data-more-params-content]");
    const moreParamsDisabledSign = document.querySelector("[data-more-params-disabled]");
    const moreParamsStateSign = document.querySelector("[data-more-params-state]");
    const moreParamsDeleteBtn = document.querySelector("[data-more-params-delete]");
    const mediaUploadsEl = document.querySelector("[data-chat-media-uploads]");
    let moreParamsModelKey = "";
    const renderMarkdown = window.CairnmarkMarkdown.render;

    // Toggle state per message
    const rawSource = new WeakMap();

    const syncEmptyState = () => {
        if (!historyEl || !emptyStateEl) return;
        const hasMessages = Boolean(historyEl.querySelector(".chat-message"));
        if (hasMessages) {
            emptyStateEl.remove();
            return;
        }
        if (!emptyStateEl.isConnected) {
            historyEl.prepend(emptyStateEl);
        }
        emptyStateEl.hidden = false;
    };

    const appendMessage = (role, content, meta) => {
        if (!historyEl) return;
        const div = document.createElement("div");
        div.className = `chat-message chat-message--${role}`;
        const roleSpan = document.createElement("span");
        roleSpan.className = "chat-role";
        if (role === "assistant" && meta && meta.provider) {
            let label = `assistant::${meta.provider}::${meta.model}`;
            if (meta.saved_system_prompt_name) {
                label += `::${meta.saved_system_prompt_name}`;
            }
            roleSpan.textContent = label;
        } else {
            roleSpan.textContent = role;
        }
        div.appendChild(roleSpan);
        if (role === "assistant" && meta) {
            const metaRow = document.createElement("span");
            metaRow.className = "chat-meta-row";
            const time = (meta.time != null) ? meta.time : 0;
            const inTok = (meta.input_tokens != null) ? meta.input_tokens : 0;
            const outTok = (meta.output_tokens != null) ? meta.output_tokens : 0;
            if (meta.time != null || meta.input_tokens || meta.output_tokens) {
                const metaSpan = document.createElement("span");
                metaSpan.className = "chat-meta";
                metaSpan.textContent = `${time} sec, ${inTok}/${outTok}`;
                metaRow.appendChild(metaSpan);
            }
            if (meta.saved_system_prompt_name) {
                const nameSpan = document.createElement("span");
                nameSpan.className = "chat-saved-prompt-name";
                nameSpan.textContent = meta.saved_system_prompt_name;
                metaRow.appendChild(nameSpan);
            }
            const promptIcon = document.createElement("span");
            promptIcon.className = "chat-prompt-icon";
            promptIcon.setAttribute("data-system-prompt", meta.system_prompt || "");
            promptIcon.title = "Show system prompt";
            const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("viewBox", "0 0 16 16");
            svg.setAttribute("width", "14");
            svg.setAttribute("height", "14");
            svg.setAttribute("aria-hidden", "true");
            svg.setAttribute("focusable", "false");
            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            path.setAttribute("fill", "currentColor");
            path.setAttribute("d", "M3 2h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zm1 2v8h8V4H4zm1 1h6v1H5V5zm0 2h6v1H5V7zm0 2h4v1H5V9z");
            svg.appendChild(path);
            promptIcon.appendChild(svg);
            metaRow.appendChild(promptIcon);
            if (meta.request_body) {
                const bodyIcon = document.createElement("span");
                bodyIcon.className = "chat-prompt-icon";
                bodyIcon.setAttribute("data-action", "request-body");
                bodyIcon.setAttribute("data-request-body", JSON.stringify(meta.request_body));
                bodyIcon.title = "Show API request body";
                const bodySvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                bodySvg.setAttribute("viewBox", "0 0 16 16");
                bodySvg.setAttribute("width", "14");
                bodySvg.setAttribute("height", "14");
                bodySvg.setAttribute("aria-hidden", "true");
                bodySvg.setAttribute("focusable", "false");
                const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                circle.setAttribute("cx", "8");
                circle.setAttribute("cy", "8");
                circle.setAttribute("r", "5.5");
                circle.setAttribute("fill", "none");
                circle.setAttribute("stroke", "currentColor");
                circle.setAttribute("stroke-width", "1.5");
                const bodyPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
                bodyPath.setAttribute("fill", "currentColor");
                bodyPath.setAttribute("d", "M6 9l3 3 3-3");
                bodySvg.appendChild(circle);
                bodySvg.appendChild(bodyPath);
                bodyIcon.appendChild(bodySvg);
                metaRow.appendChild(bodyIcon);
            }
            div.appendChild(metaRow);
        }

        const contentDiv = document.createElement("div");
        contentDiv.className =
            role === "assistant" ? "chat-content markdown-content" : "chat-content";
        if (role === "assistant") {
            rawSource.set(contentDiv, content);
            if (meta && meta.response_html) {
                contentDiv.innerHTML = meta.response_html;
            } else {
                contentDiv.innerHTML = renderMarkdown(content);
            }
            div.appendChild(contentDiv);
            // actions row
            const actions = document.createElement("div");
            actions.className = "chat-message-actions";
            // toggle button
            const toggleBtn = document.createElement("button");
            toggleBtn.type = "button";
            toggleBtn.className = "chat-view-toggle";
            toggleBtn.textContent = "Raw";
            let showingRaw = false;
            toggleBtn.addEventListener("click", () => {
                showingRaw = !showingRaw;
                if (showingRaw) {
                    contentDiv.textContent = rawSource.get(contentDiv);
                    toggleBtn.textContent = "Rendered";
                } else {
                    contentDiv.innerHTML = renderMarkdown(rawSource.get(contentDiv));
                    toggleBtn.textContent = "Raw";
                }
            });
            actions.appendChild(toggleBtn);
            // copy button
            const copyBtn = document.createElement("button");
            copyBtn.type = "button";
            copyBtn.className = "chat-copy-button";
            copyBtn.textContent = "Copy";
            copyBtn.addEventListener("click", async () => {
                try {
                    await navigator.clipboard.writeText(content);
                    copyBtn.textContent = "Copied";
                    setTimeout(() => { copyBtn.textContent = "Copy"; }, 1500);
                } catch (error) {
                    copyBtn.textContent = "Failed";
                    setTimeout(() => { copyBtn.textContent = "Copy"; }, 1500);
                }
            });
            actions.appendChild(copyBtn);
            div.appendChild(actions);
        } else {
            contentDiv.textContent = content;
            div.appendChild(contentDiv);
        }

        historyEl.appendChild(div);
        syncEmptyState();
        historyEl.scrollTop = historyEl.scrollHeight;
        return div;
    };

    const renderHistory = (messages) => {
        if (!historyEl) return;
        historyEl.replaceChildren(emptyStateEl);
        (messages || []).forEach((m) => {
            appendMessage(m.role, m.content, {
                provider: m.provider,
                model: m.model_name,
                time: m.response_time,
                input_tokens: m.input_tokens,
                output_tokens: m.output_tokens,
                saved_system_prompt_name: m.saved_system_prompt_name,
                system_prompt: m.system_prompt,
            });
        });
        syncEmptyState();
    };

    const showLoading = (onAbort) => {
        if (!historyEl) return null;
        const div = document.createElement("div");
        div.className = "chat-message chat-message--assistant is-loading";
        const roleSpan = document.createElement("span");
        roleSpan.className = "chat-role";
        roleSpan.textContent = "assistant";
        const spinner = document.createElement("span");
        spinner.className = "chat-spinner";
        spinner.setAttribute("aria-hidden", "true");
        const text = document.createElement("span");
        text.className = "chat-loading-text";
        text.textContent = "thinking…";
        const tokenCount = document.createElement("span");
        tokenCount.className = "chat-loading-tokens";
        tokenCount.setAttribute("data-chat-output-tokens", "");
        tokenCount.textContent = "0 chars";
        const abortBtn = document.createElement("button");
        abortBtn.type = "button";
        abortBtn.className = "chat-abort-button";
        abortBtn.setAttribute("data-chat-abort", "");
        abortBtn.textContent = "Abort";
        if (typeof onAbort === "function") {
            abortBtn.addEventListener("click", onAbort);
        }
        div.append(roleSpan, spinner, text, tokenCount, abortBtn);
        historyEl.appendChild(div);
        historyEl.scrollTop = historyEl.scrollHeight;
        return { element: div, tokenCount, abortBtn };
    };

    const optionalNumber = (element, converter) => {
        const raw = String(element?.value ?? "").trim();
        if (!raw) return null;
        const value = converter(raw);
        return Number.isFinite(value) ? value : null;
    };

    // Only these fields belong to the saved chat setup; modal overrides are
    // session-only and must never be persisted by Save setup.
    const setupSettings = () => ({
        model: modelSelect?.value || "",
        system_prompt: systemPromptEl?.value || "",
        temperature: optionalNumber(tempEl, Number.parseFloat),
        top_p: optionalNumber(topPEl, Number.parseFloat),
        top_k: optionalNumber(topKEl, Number.parseInt),
        seed: optionalNumber(seedEl, Number.parseInt),
        history_limit: optionalNumber(historyLimitEl, Number.parseInt),
    });

    const gatherSettings = () => ({
        ...setupSettings(),
        saved_system_prompt_name: savedSpSelect?.value || "",
    });

    const handleSend = async () => {
        const message = inputEl?.value?.trim() || "";
        if (!message) return;
        const settings = gatherSettings();
        if (!settings.model) {
            window.alert("Model is required.");
            return;
        }
        const userMessageEl = appendMessage("user", message);
        if (inputEl) inputEl.value = "";
        if (sendBtn) sendBtn.disabled = true;

        const requestBody = { message, ...settings };
        const modelParams = collectMoreParams();
        if (Object.keys(modelParams).length > 0) {
            requestBody.model_params = modelParams;
        }

        const controller = new AbortController();
        let aborted = false;
        const loadingEl = showLoading(() => {
            aborted = true;
            controller.abort();
        });

        try {
            const response = await fetch("/chat/send?stream=1", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "text/event-stream",
                },
                body: JSON.stringify(requestBody),
                signal: controller.signal,
            });
            if (!response.ok) {
                let payload = {};
                try {
                    payload = await response.json();
                } catch (error) {
                    payload = {};
                }
                throw new Error(payload.error || `HTTP ${response.status}`);
            }
            if (!response.body) {
                throw new Error("Streaming is not supported by this browser.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let accumulated = "";
            let finalPayload = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const events = buffer.split("\n\n");
                buffer = events.pop() || "";
                for (const event of events) {
                    const lines = event.split("\n");
                    for (const line of lines) {
                        if (!line.startsWith("data:")) continue;
                        const raw = line.slice(5).trim();
                        if (!raw) continue;
                        let data;
                        try {
                            data = JSON.parse(raw);
                        } catch (error) {
                            continue;
                        }
                        if (data.type === "chunk") {
                            accumulated += data.text || "";
                            if (loadingEl && loadingEl.tokenCount) {
                                loadingEl.tokenCount.textContent = `${accumulated.length} chars`;
                            }
                        } else if (data.type === "done") {
                            if (loadingEl && loadingEl.tokenCount) {
                                loadingEl.tokenCount.textContent = `${accumulated.length} chars`;
                            }
                        } else if (data.type === "result") {
                            finalPayload = data;
                        } else if (data.type === "error") {
                            throw new Error(data.error || "Request failed");
                        }
                    }
                }
            }

            if (aborted) {
                if (userMessageEl) userMessageEl.remove();
                if (loadingEl && loadingEl.element) loadingEl.element.remove();
                syncEmptyState();
                try {
                    await api.request("/chat/abort", { method: "POST" });
                } catch (error) {
                    // Ignore abort persistence failures.
                }
                return;
            }
            if (loadingEl && loadingEl.element) loadingEl.element.remove();
            if (finalPayload) {
                appendMessage("assistant", finalPayload.response || "", {
                    provider: finalPayload.provider,
                    model: finalPayload.model,
                    time: finalPayload.time,
                    input_tokens: finalPayload.input_tokens,
                    output_tokens: finalPayload.output_tokens,
                    saved_system_prompt_name: finalPayload.saved_system_prompt_name,
                    system_prompt: finalPayload.system_prompt,
                    response_html: finalPayload.response_html,
                    request_body: finalPayload.request_body,
                });
            } else if (accumulated) {
                appendMessage("assistant", accumulated, {});
            }
        } catch (error) {
            if (loadingEl && loadingEl.element) loadingEl.element.remove();
            if (aborted || (error && error.name === "AbortError")) {
                if (userMessageEl) userMessageEl.remove();
                if (loadingEl && loadingEl.element) loadingEl.element.remove();
                syncEmptyState();
                try {
                    await api.request("/chat/abort", { method: "POST" });
                } catch (error) {
                    // Ignore abort persistence failures.
                }
                return;
            }
            window.alert(`Request failed: ${error}`);
        } finally {
            if (sendBtn) sendBtn.disabled = false;
        }
    };

    const handleSave = async () => {
        const settings = setupSettings();
        if (saveBtn) saveBtn.disabled = true;
        try {
            await api.json("/chat/save_settings", {
                method: "POST",
                body: settings,
            });
            window.alert("Settings saved.");
        } catch (error) {
            window.alert(`Save failed: ${error}`);
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    };

    const handleClear = async () => {
        try {
            await api.request("/chat/clear", { method: "POST" });
            if (historyEl) {
                historyEl.replaceChildren(emptyStateEl);
                syncEmptyState();
            }
        } catch (error) {
            window.alert(`Clear failed: ${error}`);
        }
    };

    const openSaveModal = () => {
        if (saveModal) {
            saveModal.hidden = false;
            if (saveNameInput) {
                saveNameInput.value = "";
                saveNameInput.focus();
            }
        }
    };

    const closeSaveModal = () => {
        if (saveModal) saveModal.hidden = true;
    };

    const handleSaveChat = async () => {
        const name = saveNameInput?.value?.trim() || "";
        if (!name) {
            window.alert("Chat name is required.");
            return;
        }
        try {
            await api.json("/chat/save_chat", {
                method: "POST",
                body: { name },
            });
            await refreshSavedChats(name);
            closeSaveModal();
        } catch (error) {
            window.alert(`Save chat failed: ${error}`);
        }
    };

    const refreshSavedChats = async (selectName) => {
        if (!savedSelect) return;
        try {
            const payload = await api.request("/chat/saved");
            const names = payload.names || [];
            savedSelect.replaceChildren();
            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "— select a saved chat —";
            savedSelect.appendChild(placeholder);
            names.forEach((n) => {
                const opt = document.createElement("option");
                opt.value = n;
                opt.textContent = n;
                if (selectName && n === selectName) opt.selected = true;
                savedSelect.appendChild(opt);
            });
        } catch (error) {
            console.error("Failed to load saved chats:", error);
        }
    };

    const handleLoadChat = async () => {
        const name = savedSelect?.value || "";
        if (!name) return;
        try {
            const payload = await api.json("/chat/load_chat", {
                method: "POST",
                body: { name },
            });
            renderHistory(payload.messages || []);
        } catch (error) {
            window.alert(`Load chat failed: ${error}`);
        }
    };

    const handleDeleteChat = async () => {
        const name = savedSelect?.value || "";
        if (!name) {
            window.alert("Select a saved chat to delete.");
            return;
        }
        if (!window.confirm(`Delete saved chat "${name}"?`)) return;
        try {
            await api.json("/chat/delete_chat", {
                method: "POST",
                body: { name },
            });
            await refreshSavedChats("");
            if (historyEl) {
                historyEl.replaceChildren(emptyStateEl);
                syncEmptyState();
            }
        } catch (error) {
            window.alert(`Delete chat failed: ${error}`);
        }
    };

    const refreshSavedSystemPrompts = async (selectName) => {
        if (!savedSpSelect) return;
        try {
            const payload = await api.request("/chat/saved_system_prompts");
            const names = payload.names || [];
            savedSpSelect.replaceChildren();
            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "— select —";
            savedSpSelect.appendChild(placeholder);
            names.forEach((n) => {
                const opt = document.createElement("option");
                opt.value = n;
                opt.textContent = n;
                if (selectName && n === selectName) opt.selected = true;
                savedSpSelect.appendChild(opt);
            });
        } catch (error) {
            console.error("Failed to load saved system prompts:", error);
        }
    };

    const handleLoadSystemPrompt = async () => {
        const name = savedSpSelect?.value || "";
        if (!name) return;
        try {
            const payload = await api.json("/chat/load_system_prompt", {
                method: "POST",
                body: { name },
            });
            if (systemPromptEl) systemPromptEl.value = payload.content || "";
        } catch (error) {
            window.alert(`Load failed: ${error}`);
        }
    };

    const handleDeleteSystemPrompt = async () => {
        const name = savedSpSelect?.value || "";
        if (!name) {
            window.alert("Select a saved system prompt to delete.");
            return;
        }
        if (!window.confirm(`Delete saved system prompt "${name}"?`)) return;
        try {
            await api.json("/chat/delete_system_prompt", {
                method: "POST",
                body: { name },
            });
            await refreshSavedSystemPrompts("");
        } catch (error) {
            window.alert(`Delete failed: ${error}`);
        }
    };

    const openPromptModal = (text) => {
        if (promptModal) {
            promptModal.hidden = false;
            if (promptText) {
                promptText.innerHTML = renderMarkdown(text || "");
            }
        }
    };
    const closePromptModal = () => {
        if (promptModal) promptModal.hidden = true;
    };

    const openRequestBodyModal = (body) => {
        if (requestBodyModal) {
            requestBodyModal.hidden = false;
            if (requestBodyText) {
                requestBodyText.innerHTML = renderMarkdown("```json\n" + JSON.stringify(body, null, 2) + "\n```");
            }
        }
    };
    const closeRequestBodyModal = () => {
        if (requestBodyModal) requestBodyModal.hidden = true;
    };

    const openSaveSpModal = () => {
        if (saveSpModal) {
            saveSpModal.hidden = false;
            if (saveSpNameInput) {
                saveSpNameInput.value = "";
                saveSpNameInput.focus();
            }
        }
    };

    const closeSaveSpModal = () => {
        if (saveSpModal) saveSpModal.hidden = true;
    };

    const labelForParam = (key) => {
        return String(key)
            .replace(/_/g, " ")
            .replace(/^./, (c) => c.toUpperCase());
    };

    const isFilteredParam = (key, value) => {
        const name = String(key).toLowerCase();
        if (name === "samplers") return true;
        if (name === "temperature" || name === "top_p" || name === "top_k" || name === "seed") return true;
        if (value === null || value === undefined) return true;
        if (typeof value === "string" && value.toLowerCase() === "none") return true;
        return false;
    };

    const createParamInput = (key, value) => {
        const wrapper = document.createElement("div");
        wrapper.className = "field-group more-params-field";

        const label = document.createElement("label");
        label.textContent = labelForParam(key);
        label.setAttribute("for", `more-param-${key}`);
        wrapper.appendChild(label);

        let input;
        if (typeof value === "boolean") {
            const switchWrap = document.createElement("label");
            switchWrap.className = "more-params-switch";
            input = document.createElement("input");
            input.type = "checkbox";
            input.checked = value;
            input.className = "more-params-switch-input";
            const knob = document.createElement("span");
            knob.className = "more-params-switch-knob";
            switchWrap.appendChild(input);
            switchWrap.appendChild(knob);
            wrapper.appendChild(switchWrap);
            input.id = `more-param-${key}`;
            input.name = key;
            input.setAttribute("data-more-param", key);
            return wrapper;
        } else if (typeof value === "number") {
            input = document.createElement("input");
            input.type = "number";
            input.step = Number.isInteger(value) ? "1" : "0.01";
            input.value = value;
        } else if (Array.isArray(value)) {
            input = document.createElement("input");
            input.type = "text";
            input.value = JSON.stringify(value);
        } else {
            input = document.createElement("input");
            input.type = "text";
            input.value = value == null ? "" : String(value);
        }
        input.id = `more-param-${key}`;
        input.name = key;
        input.setAttribute("data-more-param", key);
        wrapper.appendChild(input);
        return wrapper;
    };

    const setMoreParamsLoading = (active) => {
        if (!moreParamsLoading) return;
        moreParamsLoading.hidden = !active;
        moreParamsLoading.style.display = active ? "flex" : "none";
    };

    const setMoreParamsDeleteVisible = (visible) => {
        if (moreParamsDeleteBtn) moreParamsDeleteBtn.hidden = !visible;
    };

    const showMoreParamsNote = (message) => {
        if (!moreParamsContent) return;
        const note = document.createElement("p");
        note.className = "field-hint";
        note.textContent = message;
        moreParamsContent.appendChild(note);
    };

    const renderMoreParams = (params) => {
        if (!moreParamsContent) return;
        const grid = document.createElement("div");
        grid.className = "more-params-grid";
        const keys = Object.keys(params).filter((key) => !isFilteredParam(key, params[key]));
        if (keys.length === 0) {
            showMoreParamsNote("No parameters returned by the provider.");
            updateMoreParamsSign();
            return;
        }
        keys.forEach((key) => {
            grid.appendChild(createParamInput(key, params[key]));
        });
        moreParamsContent.appendChild(grid);
        updateMoreParamsSign();
    };

    // Read the applied modal inputs; Cancel removes them so nothing is sent.
    const collectMoreParams = () => {
        const params = {};
        if (!moreParamsContent) return params;
        moreParamsContent.querySelectorAll("[data-more-param]").forEach((input) => {
            const key = input.getAttribute("data-more-param");
            if (!key) return;
            if (input.type === "checkbox") {
                params[key] = input.checked;
                return;
            }
            const raw = String(input.value ?? "").trim();
            if (!raw) return;
            if (input.type === "number") {
                const value = Number(raw);
                if (Number.isFinite(value)) params[key] = value;
                return;
            }
            if (raw.startsWith("[") || raw.startsWith("{")) {
                try {
                    params[key] = JSON.parse(raw);
                    return;
                } catch (error) {
                    // Fall through and send the text unchanged.
                }
            }
            params[key] = raw;
        });
        return params;
    };

    // Mirror the modal state on the button: SET when inputs exist and will be
    // sent with the next request, UNSET when the modal is empty and any
    // parameters are ignored. Hidden while the button is disabled.
    const updateMoreParamsSign = () => {
        if (!moreParamsStateSign) return;
        if (!moreParamsBtn || moreParamsBtn.disabled) {
            moreParamsStateSign.hidden = true;
            return;
        }
        const active = Object.keys(collectMoreParams()).length > 0;
        moreParamsStateSign.textContent = active ? "SET" : "UNSET";
        moreParamsStateSign.classList.toggle("more-params-state-sign--set", active);
        moreParamsStateSign.classList.toggle("more-params-state-sign--unset", !active);
        moreParamsStateSign.hidden = false;
    };

    const loadMoreParams = async (provider, model) => {
        if (moreParamsContent) moreParamsContent.replaceChildren();
        setMoreParamsDeleteVisible(false);
        setMoreParamsLoading(true);
        try {
            const payload = await api.request(
                `/setup_models/model_params?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`
            );
            setMoreParamsLoading(false);
            renderMoreParams((payload && payload.params) || {});
            setMoreParamsDeleteVisible(payload && payload.source === "database");
            moreParamsModelKey = `${provider}::${model}`;
        } catch (error) {
            setMoreParamsLoading(false);
            showMoreParamsNote(`Failed to load parameters: ${error}`);
            updateMoreParamsSign();
        }
    };

    // Media upload icons shown under the message input, driven by the saved
    // modalities for the selected local model. Icons only: no click handling yet.
    // The document icon is always available (document processing is assumed to
    // be supported by every model), so it is rendered first in every state.
    const DOCUMENT_UPLOAD_ICON = { glyph: "📄", label: "Upload document" };
    const MEDIA_UPLOAD_ICONS = [
        { key: "vision", glyph: "📷", label: "Upload image" },
        { key: "video", glyph: "🎥", label: "Upload video" },
        { key: "audio", glyph: "🎤", label: "Upload audio" },
    ];

    const createMediaUploadButton = (item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "chat-media-icon";
        button.title = item.label;
        button.setAttribute("aria-label", item.label);
        button.disabled = true;
        const glyph = document.createElement("span");
        glyph.className = "chat-media-glyph";
        glyph.setAttribute("aria-hidden", "true");
        glyph.textContent = item.glyph;
        const tooltip = document.createElement("span");
        tooltip.className = "chat-media-tooltip";
        tooltip.setAttribute("role", "tooltip");
        tooltip.textContent = item.label;
        button.append(glyph, tooltip);
        return button;
    };

    const renderMediaUploads = (modalities) => {
        if (!mediaUploadsEl) return;
        mediaUploadsEl.replaceChildren();
        // Document upload is always shown, regardless of model modalities.
        mediaUploadsEl.appendChild(createMediaUploadButton(DOCUMENT_UPLOAD_ICON));
        const active = MEDIA_UPLOAD_ICONS.filter(
            (item) => modalities && modalities[item.key] === true
        );
        active.forEach((item) => {
            mediaUploadsEl.appendChild(createMediaUploadButton(item));
        });
        mediaUploadsEl.hidden = false;
    };

    let mediaUploadsSeq = 0;

    const refreshMediaUploads = async (provider, model) => {
        const requestSeq = ++mediaUploadsSeq;
        // Clear icons first: without saved modalities the default is false.
        renderMediaUploads(null);
        const isLocal = provider === "llama.cpp" || provider === "vllm";
        if (!isLocal || !model) {
            return;
        }
        try {
            const payload = await api.request(
                `/setup_models/model_params?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`
            );
            if (requestSeq !== mediaUploadsSeq) return;
            renderMediaUploads(payload && payload.modalities);
        } catch (error) {
            if (requestSeq !== mediaUploadsSeq) return;
            renderMediaUploads(null);
        }
    };

    const openMoreParamsModal = async () => {
        if (!moreParamsModal) return;
        const selectedOption = modelSelect && modelSelect.selectedOptions && modelSelect.selectedOptions[0];
        const modelName = (selectedOption && (selectedOption.textContent || "").trim()) || (modelSelect && modelSelect.value) || "";
        if (moreParamsTitle) {
            moreParamsTitle.textContent = modelName
                ? `Additional model parameters for ${modelName}`
                : "Additional model parameters";
        }

        const modelValue = modelSelect?.value || "";
        const parts = modelValue.split("::");
        const provider = (parts[0] || "").trim();
        const model = parts.slice(1).join("::").trim() || modelName;

        const isLocal = provider === "llama.cpp" || provider === "vllm";
        if (!isLocal) {
            moreParamsModal.hidden = false;
            resetMoreParamsModal();
            showMoreParamsNote("Additional parameters are only available for local providers (llama.cpp, vLLM).");
            return;
        }

        // Keep the saved inputs untouched when the same model's modal is reopened.
        if (moreParamsModelKey === modelValue && moreParamsContent && moreParamsContent.children.length > 0) {
            setMoreParamsLoading(false);
            moreParamsModal.hidden = false;
            return;
        }

        moreParamsModal.hidden = false;
        resetMoreParamsModal();

        // Yield to the browser so the loading spinner paints before fetching.
        setMoreParamsLoading(true);
        await new Promise((resolve) => setTimeout(resolve, 0));
        await loadMoreParams(provider, model);
    };

    const closeMoreParamsModal = () => {
        if (moreParamsModal) moreParamsModal.hidden = true;
    };

    const resetMoreParamsModal = () => {
        if (moreParamsContent) moreParamsContent.replaceChildren();
        setMoreParamsLoading(false);
        setMoreParamsDeleteVisible(false);
        moreParamsModelKey = "";
        updateMoreParamsSign();
    };

    const handleDeleteMoreParams = async () => {
        const modelValue = modelSelect?.value || "";
        const parts = modelValue.split("::");
        const provider = (parts[0] || "").trim();
        const model = parts.slice(1).join("::").trim();
        if (!provider || !model) return;

        if (moreParamsDeleteBtn) moreParamsDeleteBtn.disabled = true;
        try {
            await api.json("/setup_models/model_params/delete", {
                method: "POST",
                body: { provider, model },
            });
        } catch (error) {
            window.alert(`Delete failed: ${error}`);
            if (moreParamsDeleteBtn) moreParamsDeleteBtn.disabled = false;
            return;
        }
        // Re-read from the provider; the fresh defaults are cached again.
        await loadMoreParams(provider, model);
        if (moreParamsDeleteBtn) moreParamsDeleteBtn.disabled = false;
    };

    const handleSaveSystemPrompt = async () => {
        const name = saveSpNameInput?.value?.trim() || "";
        if (!name) {
            window.alert("Name is required.");
            return;
        }
        const content = systemPromptEl?.value || "";
        try {
            await api.json("/chat/save_system_prompt", {
                method: "POST",
                body: { name, content },
            });
            await refreshSavedSystemPrompts(name);
            closeSaveSpModal();
        } catch (error) {
            window.alert(`Save failed: ${error}`);
        }
    };

    // Render server-side assistant messages as markdown.
    if (historyEl) {
        historyEl.querySelectorAll(".chat-message--assistant .chat-content").forEach((el) => {
            const raw = el.dataset.raw || el.textContent;
            rawSource.set(el, raw);
            const parent = el.parentElement;
            if (parent && !parent.querySelector(".chat-message-actions")) {
                const actions = document.createElement("div");
                actions.className = "chat-message-actions";
                const toggleBtn = document.createElement("button");
                toggleBtn.type = "button";
                toggleBtn.className = "chat-view-toggle";
                toggleBtn.textContent = "Raw";
                let showingRaw = false;
                toggleBtn.addEventListener("click", () => {
                    showingRaw = !showingRaw;
                    if (showingRaw) {
                        el.textContent = rawSource.get(el);
                        toggleBtn.textContent = "Rendered";
                    } else {
                        el.innerHTML = renderMarkdown(rawSource.get(el));
                        toggleBtn.textContent = "Raw";
                    }
                });
                actions.appendChild(toggleBtn);
                const copyBtn = document.createElement("button");
                copyBtn.type = "button";
                copyBtn.className = "chat-copy-button";
                copyBtn.textContent = "Copy";
                copyBtn.addEventListener("click", async () => {
                    try {
                        await navigator.clipboard.writeText(raw);
                        copyBtn.textContent = "Copied";
                        setTimeout(() => { copyBtn.textContent = "Copy"; }, 1500);
                    } catch (error) {
                        copyBtn.textContent = "Failed";
                        setTimeout(() => { copyBtn.textContent = "Copy"; }, 1500);
                    }
                });
                actions.appendChild(copyBtn);
                parent.appendChild(actions);
            }
        });
    }

    sendBtn?.addEventListener("click", handleSend);
    saveBtn?.addEventListener("click", handleSave);
    clearBtn?.addEventListener("click", handleClear);
    saveOpenBtn?.addEventListener("click", openSaveModal);
    saveConfirmBtn?.addEventListener("click", handleSaveChat);
    saveCloseBtns.forEach((b) => b.addEventListener("click", closeSaveModal));
    savedSelect?.addEventListener("change", handleLoadChat);
    deleteBtn?.addEventListener("click", handleDeleteChat);
    savedSpSelect?.addEventListener("change", handleLoadSystemPrompt);
    deleteSpBtn?.addEventListener("click", handleDeleteSystemPrompt);
    saveSpOpenBtn?.addEventListener("click", openSaveSpModal);
    saveSpConfirmBtn?.addEventListener("click", handleSaveSystemPrompt);
    saveSpCloseBtns.forEach((b) => b.addEventListener("click", closeSaveSpModal));
    const updateMoreParamsButtonState = async () => {
        resetMoreParamsModal();

        const modelValue = modelSelect?.value || "";
        const parts = modelValue.split("::");
        const provider = (parts[0] || "").trim();
        const model = parts.slice(1).join("::").trim();

        refreshMediaUploads(provider, model);

        const isLocal = provider === "llama.cpp" || provider === "vllm";
        if (!isLocal || !model) {
            if (moreParamsBtn) moreParamsBtn.disabled = true;
            if (moreParamsDisabledSign) moreParamsDisabledSign.hidden = false;
            updateMoreParamsSign();
            return;
        }
        if (moreParamsBtn) moreParamsBtn.disabled = true;
        if (moreParamsDisabledSign) moreParamsDisabledSign.hidden = false;
        updateMoreParamsSign();
        try {
            const response = await fetch(
                `/setup_models/props_available?provider=${encodeURIComponent(provider)}`
            );
            const payload = await response.json().catch(() => ({}));
            const accessible = response.ok && payload.available === true;
            if (moreParamsBtn) moreParamsBtn.disabled = !accessible;
            if (moreParamsDisabledSign) moreParamsDisabledSign.hidden = accessible;
            updateMoreParamsSign();
        } catch (error) {
            if (moreParamsBtn) moreParamsBtn.disabled = true;
            if (moreParamsDisabledSign) moreParamsDisabledSign.hidden = false;
            updateMoreParamsSign();
        }
    };

    moreParamsBtn?.addEventListener("click", openMoreParamsModal);
    moreParamsDeleteBtn?.addEventListener("click", handleDeleteMoreParams);
    moreParamsCloseBtns.forEach((b) => b.addEventListener("click", () => {
        resetMoreParamsModal();
        closeMoreParamsModal();
    }));
    moreParamsSaveBtn?.addEventListener("click", closeMoreParamsModal);
    moreParamsModal?.addEventListener("click", (event) => {
        if (event.target === moreParamsModal) {
            resetMoreParamsModal();
            closeMoreParamsModal();
        }
    });
    modelSelect?.addEventListener("change", updateMoreParamsButtonState);
    saveSpNameInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            handleSaveSystemPrompt();
        }
    });

    inputEl?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            handleSend();
        }
    });

    // Reset saved system prompt dropdown when the textarea is manually edited.
    systemPromptEl?.addEventListener("input", () => {
        if (savedSpSelect && savedSpSelect.value !== "") {
            savedSpSelect.value = "";
        }
    });

    // Open prompt/request-body modals on icon click (delegated).
    historyEl?.addEventListener("click", (event) => {
        const icon = event.target.closest(".chat-prompt-icon");
        if (!icon) return;
        if (icon.getAttribute("data-action") === "request-body") {
            const raw = icon.getAttribute("data-request-body") || "";
            let body = {};
            try {
                body = raw ? JSON.parse(raw) : {};
            } catch (error) {
                body = { raw: raw };
            }
            openRequestBodyModal(body);
            return;
        }
        openPromptModal(icon.getAttribute("data-system-prompt") || "");
    });
    promptCloseBtns.forEach((b) => b.addEventListener("click", closePromptModal));
    promptModal?.addEventListener("click", (event) => {
        if (event.target === promptModal) closePromptModal();
    });
    requestBodyCloseBtns.forEach((b) => b.addEventListener("click", closeRequestBodyModal));
    requestBodyModal?.addEventListener("click", (event) => {
        if (event.target === requestBodyModal) closeRequestBodyModal();
    });

    const savedModel = modelSelect?.dataset?.savedModel?.trim();
    if (savedModel && modelSelect) {
        const option = [...modelSelect.options].find((o) => o.value.trim() === savedModel);
        if (option) {
            modelSelect.value = savedModel;
        }
    }

    // Keep the always-available document icon visible from first paint.
    renderMediaUploads(null);
    setTimeout(updateMoreParamsButtonState, 2000);

    if (historyEl) {
        historyEl.scrollTop = historyEl.scrollHeight;
    }
})();
