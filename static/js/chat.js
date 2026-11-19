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
const minPEl = document.querySelector("[data-chat-min-p]");
    const seedEl = document.querySelector("[data-chat-seed]");
    const seedSwitch = document.querySelector("[data-chat-seed-switch]");
    const historyLimitEl = document.querySelector("[data-chat-history-limit]");
const historySwitch = document.querySelector("[data-chat-history-switch], [data-chat-send-all], [data-chat-all-previous], [data-chat-history-all], [data-history-switch]");
const tokenUsageEl = document.querySelector("[data-chat-token-usage]");
const contextBarEl = document.querySelector("[data-chat-context-bar]");
const contextBarFillEl = document.querySelector("[data-chat-context-bar-fill]");
let sessionCtxMode = null;
let sessionCtxModeFetched = false;
let currentNctx = null;
const chatMessageTokens = Array.isArray(window.CairnmarkChatMessageTokens)
    ? window.CairnmarkChatMessageTokens.slice()
    : [];
    const saveBtn = document.querySelector("[data-chat-save-settings]");
    const clearBtn = document.querySelector("[data-chat-clear]");
const compactBtn = document.querySelector("[data-chat-compact]");
    const savedSelect = document.querySelector("[data-chat-saved]");
    const replaceBtn = document.querySelector("[data-chat-replace]");
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
    const moreParamsSaveModelBtn = document.querySelector("[data-more-params-save-model]");
    const mineruModal = document.querySelector("[data-mineru-settings-modal]");
    const mineruEndpointInput = document.querySelector("[data-mineru-endpoint]");
    const mineruApiKeyInput = document.querySelector("[data-mineru-api-key]");
    const mineruSaveBtn = document.querySelector("[data-mineru-settings-save]");
    const mineruCloseBtns = document.querySelectorAll("[data-mineru-settings-close]");
    const mediaUploadsEl = document.querySelector("[data-chat-media-uploads]");
    const attachmentsEl = document.querySelector("[data-chat-attachments]");
    const audioAttachmentsEl = document.querySelector("[data-chat-audio-attachments]");
    const saveOriginalSwitch = document.querySelector("[data-chat-save-original]");
    const attachAudioSwitch = document.querySelector("[data-chat-attach-audio]");
    const fpsControl = document.querySelector("[data-chat-video-fps-control]");
    const fpsSlider = document.querySelector("[data-chat-video-fps]");
    const fpsValue = document.querySelector("[data-chat-video-fps-value]");
    const modelNctxEl = document.querySelector("[data-chat-model-nctx]");
    const attachmentSettings = window.CairnmarkChatAttachmentSettings || {};
    const videoFpsValues = [0.1, 0.25, 0.5, 1, 2, 4, 8, 16];
    const savedVideoFpsIndex = videoFpsValues.indexOf(Number(attachmentSettings.video_fps));
    if (fpsSlider && savedVideoFpsIndex >= 0) {
        fpsSlider.value = String(savedVideoFpsIndex);
    }
    const attachmentPreferences = new window.CairnmarkChatAttachmentPreferences({
        api,
        initial: attachmentSettings,
        controls: {
            save_original_media: saveOriginalSwitch,
            attach_audio: attachAudioSwitch,
        },
        onError: (error) => {
            window.alert(`Attachment preference could not be saved: ${error}`);
        },
    });
    let moreParamsModelKey = "";
    let mineruConfigured = Boolean(window.CairnmarkMineruSettings && window.CairnmarkMineruSettings.configured);
    let mineruEndpoint = (window.CairnmarkMineruSettings && window.CairnmarkMineruSettings.endpoint) || "http://127.0.0.1:8100";
    let mineruApiKey = (window.CairnmarkMineruSettings && window.CairnmarkMineruSettings.api_key) || "";
    let pendingDocumentPicker = false;
    const pendingAttachments = [];
    const renderMarkdown = window.CairnmarkMarkdown.render;
    const chatMedia = window.CairnmarkChatMedia;

    // Toggle state per message
    const rawSource = new WeakMap();

    // Floating hover preview keeps the embedded thumbnail size unchanged.
    let hoverPreviewEl = null;
    let hoverPreviewImg = null;
    let lastHoverPoint = null;

    const ensureHoverPreview = () => {
        if (hoverPreviewEl) return hoverPreviewEl;
        hoverPreviewEl = document.createElement("div");
        hoverPreviewEl.className = "chat-hover-preview";
        hoverPreviewEl.hidden = true;
        hoverPreviewImg = document.createElement("img");
        hoverPreviewImg.alt = "Expanded attachment preview";
        hoverPreviewImg.addEventListener("load", () => {
            if (lastHoverPoint && !hoverPreviewEl.hidden) {
                positionHoverPreview(lastHoverPoint);
            }
        });
        hoverPreviewEl.appendChild(hoverPreviewImg);
        document.body.appendChild(hoverPreviewEl);
        return hoverPreviewEl;
    };

    const positionHoverPreview = (event) => {
        if (!hoverPreviewEl || hoverPreviewEl.hidden) return;
        lastHoverPoint = { clientX: event.clientX, clientY: event.clientY };
        const pad = 12;
        const offset = 16;
        const natural = hoverPreviewImg.naturalWidth && hoverPreviewImg.naturalHeight
            ? hoverPreviewImg.naturalWidth / hoverPreviewImg.naturalHeight
            : null;
        const cardWidth = natural
            ? Math.min(300 * natural + 12, window.innerWidth - pad * 2)
            : hoverPreviewEl.offsetWidth;
        const cardHeight = natural
            ? Math.min(300, window.innerHeight - pad * 2) + 12
            : hoverPreviewEl.offsetHeight;
        let x = event.clientX + offset;
        let y = event.clientY + offset;
        if (x + cardWidth > window.innerWidth - pad) {
            x = Math.max(pad, event.clientX - cardWidth - offset);
        }
        if (y + cardHeight > window.innerHeight - pad) {
            y = Math.max(pad, window.innerHeight - cardHeight - pad);
        }
        hoverPreviewEl.style.left = `${x}px`;
        hoverPreviewEl.style.top = `${y}px`;
    };

    const showHoverPreview = (src, event) => {
        const el = ensureHoverPreview();
        if (hoverPreviewImg.getAttribute("src") !== src) {
            hoverPreviewImg.setAttribute("src", src);
        }
        el.hidden = false;
        positionHoverPreview(event);
    };

    const hideHoverPreview = () => {
        if (hoverPreviewEl) hoverPreviewEl.hidden = true;
        lastHoverPoint = null;
    };

    // Capture phase catches scrolling inside the chat history container too.
    window.addEventListener("scroll", hideHoverPreview, true);

    // Server-rendered preview thumbnails (initial page load) do not get the
    // per-element hover listeners attached by appendMessage, so delegate.
    // Wire up any server-rendered audio players.
    document.querySelectorAll(".chat-audio-player").forEach((item) => {
        chatMedia.wire(item, "audio");
    });

    // Wire up any server-rendered video players.
    document.querySelectorAll(".chat-video-player").forEach((item) => {
        chatMedia.wire(item, "video");
    });

    // Auto-rewind native video players on end.
    document.querySelectorAll("video.chat-user-media-player").forEach((video) => {
        video.addEventListener("ended", () => { video.currentTime = 0; });
    });

    if (historyEl) {
        historyEl.addEventListener("mouseover", (event) => {
            const img = event.target && event.target.closest
                ? event.target.closest(".chat-user-preview")
                : null;
            if (img && img.tagName === "IMG") {
                showHoverPreview(img.src, event);
            }
        });
        historyEl.addEventListener("mousemove", (event) => {
            const img = event.target && event.target.closest
                ? event.target.closest(".chat-user-preview")
                : null;
            if (img && img.tagName === "IMG") {
                positionHoverPreview(event);
            }
        });
        historyEl.addEventListener("mouseout", (event) => {
            const img = event.target && event.target.closest
                ? event.target.closest(".chat-user-preview")
                : null;
            if (img && img.tagName === "IMG") {
                const related = event.relatedTarget && event.relatedTarget.closest
                    ? event.relatedTarget.closest(".chat-user-preview")
                    : null;
                if (!related) {
                    hideHoverPreview();
                }
            }
        });
    }

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

    const attachAssistantActions = (contentEl, raw) => {
        rawSource.set(contentEl, raw);
        contentEl.innerHTML = renderMarkdown(raw);
        const message = contentEl.parentElement;
        if (!message || message.querySelector(".chat-message-actions")) return;

        const actions = document.createElement("div");
        actions.className = "chat-message-actions";
        const toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "chat-view-toggle";
        toggleBtn.textContent = "Raw";
        toggleBtn.addEventListener("click", () => {
            const showingRaw = toggleBtn.textContent === "Rendered";
            if (showingRaw) {
                contentEl.innerHTML = renderMarkdown(rawSource.get(contentEl));
                toggleBtn.textContent = "Raw";
            } else {
                contentEl.textContent = rawSource.get(contentEl);
                toggleBtn.textContent = "Rendered";
            }
        });

        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "chat-copy-button";
        copyBtn.textContent = "Copy";
        copyBtn.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(rawSource.get(contentEl));
                copyBtn.textContent = "Copied";
            } catch (error) {
                copyBtn.textContent = "Failed";
            }
            setTimeout(() => { copyBtn.textContent = "Copy"; }, 1500);
        });
        actions.append(toggleBtn, copyBtn);
        message.appendChild(actions);
    };

    const appendMessage = (role, content, meta) => {
        if (!historyEl) return;
        const div = document.createElement("div");
        div.className = `chat-message chat-message--${role}`;
        if (meta && meta.compacted) {
            div.classList.add("chat-message--compacted");
        }
        const roleSpan = document.createElement("span");
        roleSpan.className = "chat-role";
        if (meta && meta.compacted) {
            roleSpan.textContent = "compacted summary";
        } else if (role === "assistant" && meta && meta.provider) {
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
                // Ensure the request_body is stored as a string in the attribute
                bodyIcon.setAttribute("data-request-body", typeof meta.request_body === "string" ? meta.request_body : JSON.stringify(meta.request_body));
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
            div.appendChild(contentDiv);
            attachAssistantActions(contentDiv, content);
        } else {
            const previewImages =
                meta && Array.isArray(meta.preview_images)
                    ? meta.preview_images
                    : [];
            const showAudioIcon = Boolean(meta && meta.has_audio);
        if (showAudioIcon) {
            div.classList.add("chat-message--has-audio");
        }
            const previewMedia = (meta && Array.isArray(meta.preview_media)) ? meta.preview_media : [];
            // Audio player (composer style) placed below the role label.
            const audioMedia = previewMedia.filter((m) => m && m.type === "audio");
            audioMedia.forEach((item) => {
                const src = item.url || (item.filename ? `/chat/preview/${encodeURIComponent(item.filename)}` : null);
                if (!src) return;
                const displayName = item.original_name || item.filename || "";
                const player = chatMedia.createAudio(src, displayName);
                div.appendChild(player);
            });
            const videoMedia = previewMedia.filter((m) => m && m.type === "video");
            const documentMedia = previewMedia.filter((m) => m && m.type === "document");
            const hasPreviews = previewImages.length > 0 || videoMedia.length > 0 || documentMedia.length > 0;
            if (hasPreviews) {
                const body = document.createElement("div");
                body.className = "chat-user-body";
                const previews = document.createElement("div");
                previews.className = "chat-user-previews";
                previewImages.forEach((src) => {
                    const img = document.createElement("img");
                    img.className = "chat-user-preview";
                    img.alt = "Attached image preview";
                    img.src = String(src).startsWith("data:")
                        ? src
                        : `/chat/preview/${encodeURIComponent(src)}`;
                    img.addEventListener("error", () => {
                        hideHoverPreview();
                        const broken = document.createElement("span");
                        broken.className = "chat-user-preview--broken";
                        broken.textContent = "🔗";
                        broken.title = "Preview image missing";
                        img.replaceWith(broken);
                    });
                    previews.appendChild(img);
                });
                videoMedia.forEach((item) => {
                    const src = item.url || (item.filename ? `/chat/preview/${encodeURIComponent(item.filename)}` : null);
                    if (!src) return;
                    const wrap = document.createElement("div");
                    wrap.className = "chat-video-player chat-video-player--compact chat-video-player--thumb";
                    const video = document.createElement("video");
                    video.className = "chat-user-media-player";
                    video.src = src;
                    video.preload = "metadata";
                    video.addEventListener("ended", () => { video.currentTime = 0; });
                    wrap.appendChild(video);
                    const controls = document.createElement("div");
                    controls.className = "chat-video-controls";
                    const toggleBtn = document.createElement("button");
                    toggleBtn.type = "button";
                    toggleBtn.className = "chat-video-toggle";
                    toggleBtn.textContent = "▶";
                    toggleBtn.title = "Play";
                    controls.appendChild(toggleBtn);
                    const backBtn = document.createElement("button");
                    backBtn.type = "button";
                    backBtn.className = "chat-video-back";
                    backBtn.textContent = "⏪";
                    backBtn.title = "Rewind to beginning";
                    controls.appendChild(backBtn);
                    wrap.appendChild(controls);
                    chatMedia.wire(wrap, "video");
                    previews.appendChild(wrap);
                });
                documentMedia.forEach((item) => {
                    const name = item.original_name || item.filename || "Document";
                    const icon = document.createElement("span");
                    icon.className = "chat-document-icon";
                    icon.textContent = documentIconFor(name);
                    icon.title = name;
                    previews.appendChild(icon);
                });
                body.appendChild(previews);
                contentDiv.textContent = content;
                body.appendChild(contentDiv);
                if (showAudioIcon) {
                    const mic = document.createElement("span");
                    mic.className = "chat-user-audio-icon";
                    mic.textContent = "🎤";
                    mic.title = "Audio attachment";
                    div.appendChild(mic);
                }
                div.appendChild(body);
            } else {
                contentDiv.textContent = content;
                div.appendChild(contentDiv);
                if (showAudioIcon) {
                    const mic = document.createElement("span");
                    mic.className = "chat-user-audio-icon";
                    mic.textContent = "🎤";
                    mic.title = "Audio attachment";
                    div.appendChild(mic);
                }
            }
        }

        historyEl.appendChild(div);
        syncEmptyState();
        historyEl.scrollTop = historyEl.scrollHeight;
        return div;
    };

    const renderHistory = (messages) => {
        if (!historyEl) return;
        hideHoverPreview();
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
                preview_images: m.preview_images || [],
                has_audio: Boolean(m.has_audio),
                preview_media: m.preview_media || [],
                request_body: m.request_body,
                compacted: Boolean(m.compacted),
            });
        });
        syncEmptyState();
    };

    const showLoading = (onAbort, meta = {}) => {
        if (!historyEl) return null;
        const div = document.createElement("div");
        div.className = "chat-message chat-message--assistant is-loading";
        if (meta.compacted) {
            div.classList.add("chat-message--compacted");
        }
        const roleSpan = document.createElement("span");
        roleSpan.className = "chat-role";
        roleSpan.textContent = meta.compacted ? "compacted summary" : "assistant";
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
        return { element: div, tokenCount, loadingText: text, abortBtn };
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
        min_p: optionalNumber(minPEl, Number.parseFloat),
        seed: optionalNumber(seedEl, Number.parseInt),
        history_limit: optionalNumber(historyLimitEl, Number.parseInt),
    });

    const gatherSettings = () => ({
        ...setupSettings(),
        saved_system_prompt_name: savedSpSelect?.value || "",
    });

    const selectedVideoFps = () => {
        const index = Number(fpsSlider?.value);
        return videoFpsValues[index] != null ? videoFpsValues[index] : 2;
    };

    const handleSend = async () => {
        const message = inputEl?.value?.trim() || "";
        if (!message) return;
        if (seedSwitch && seedSwitch.getAttribute("aria-checked") === "true" && seedEl) {
            const randomSeed = Math.floor(Math.random() * 4294967296);
            seedEl.value = String(randomSeed);
        }
        const settings = gatherSettings();
        if (!settings.model) {
            window.alert("Model is required.");
            return;
        }
        const saveOriginalMedia = attachmentPreferences.get("save_original_media");
        const userPreviewImages = pendingAttachments
            .filter((attachment) => attachment.previewUrl && (
                attachment.type === "image"
                || (attachment.type === "video" && !saveOriginalMedia)
            ))
            .map((attachment) => attachment.previewUrl);
        const hasAudioAttachment = pendingAttachments.some(
            (attachment) => attachment.type === "audio"
        );
        const immediateMedia = saveOriginalMedia
            ? pendingAttachments
                .filter((attachment) => attachment.type === "video" || attachment.type === "audio")
                .map((attachment) => ({
                    type: attachment.type,
                    url: attachment.type === "video" ? attachment.videoUrl : attachment.audioUrl,
                    original_name: attachment.name,
                }))
            : [];
        const documentPreviewMedia = pendingAttachments
            .filter((attachment) => attachment.type === "document")
            .map((attachment) => ({
                type: "document",
                original_name: attachment.documentPayload
                    ? attachment.documentPayload.filename
                    : attachment.name,
                filename: "",
            }));
        chatMessageTokens.push({ input_tokens: 0, output_tokens: 0, compacted: false });
        const userMessageEl = appendMessage("user", message, {
            preview_images: userPreviewImages,
            has_audio: hasAudioAttachment && !saveOriginalMedia,
            save_original_media: saveOriginalMedia,
            preview_media: immediateMedia.concat(documentPreviewMedia),
        });
        if (inputEl) inputEl.value = "";
        if (sendBtn) sendBtn.disabled = true;

        const controller = new AbortController();
        let aborted = false;
        const loadingEl = showLoading(() => {
            aborted = true;
            controller.abort();
        });

        const binaryDocuments = pendingAttachments.filter(
            (attachment) => attachment.type === "document" && !attachment.documentPayload
        );
        if (binaryDocuments.length > 0) {
            if (loadingEl && loadingEl.loadingText) {
                loadingEl.loadingText.textContent = "Document processing…";
            }
            for (const attachment of binaryDocuments) {
                try {
                    const payload = await api.json("/chat/process_document", {
                        method: "POST",
                        body: {
                            filename: attachment.name,
                            mime_type: attachment.mime,
                            data: attachment.data,
                        },
                    });
                    const ext = String(attachment.name || "").split(".").pop().toLowerCase();
                    attachment.documentPayload = {
                        filename: attachment.name,
                        mime_type: attachment.mime,
                        extension: ext,
                        size: attachment.size || 0,
                        content: payload.content,
                    };
                    // Update the already-rendered document icon? Not needed.
                } catch (error) {
                    if (loadingEl && loadingEl.element) loadingEl.element.remove();
                    window.alert(`Document processing failed: ${error}`);
                    if (sendBtn) sendBtn.disabled = false;
                    return;
                }
            }
        }
        if (loadingEl && loadingEl.loadingText) {
            loadingEl.loadingText.textContent = "thinking…";
        }

        const requestBody = {
            message,
            ...settings,
            video_fps: selectedVideoFps(),
        };

        const binaryAttachments = pendingAttachments.filter(
            (attachment) => attachment.type !== "document"
        );
        if (binaryAttachments.length > 0) {
            requestBody.attachments = binaryAttachments.map((attachment) => ({
                type: attachment.type,
                data: attachment.data,
                mime_type: attachment.mime,
                preview_data: attachment.previewData || undefined,
                attach_audio: attachment.type === "video" ? attachmentPreferences.get("attach_audio") : undefined,
                original_name: attachment.name,
            }));
            requestBody.save_original_media = saveOriginalMedia;
        }

        const documents = pendingAttachments
            .filter((attachment) => attachment.type === "document" && attachment.documentPayload)
            .map((attachment, index) => ({
                id: `doc_${String(index + 1).padStart(3, "0")}`,
                filename: attachment.documentPayload.filename,
                mime_type: attachment.documentPayload.mime_type,
                extension: attachment.documentPayload.extension,
                size: attachment.documentPayload.size,
                content: attachment.documentPayload.content,
            }));
        if (documents.length > 0) {
            requestBody.documents = documents;
        }

        const modelParams = collectMoreParams();
        if (Object.keys(modelParams).length > 0) {
            requestBody.model_params = modelParams;
        }

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
                        if (data.type === "status") {
                            if (loadingEl && loadingEl.loadingText) {
                                loadingEl.loadingText.textContent = data.text || "thinking…";
                            }
                        } else if (data.type === "chunk") {
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
                chatMessageTokens.push({
                    input_tokens: finalPayload.input_tokens || 0,
                    output_tokens: finalPayload.output_tokens || 0,
                    compacted: false,
                });
                updateTokenUsage();
                appendMessage("assistant", finalPayload.response || "", {
                    provider: finalPayload.provider,
                    model: finalPayload.model,
                    time: finalPayload.time,
                    input_tokens: finalPayload.input_tokens,
                    output_tokens: finalPayload.output_tokens,
                    saved_system_prompt_name: finalPayload.saved_system_prompt_name,
                    system_prompt: finalPayload.system_prompt,
                    request_body: finalPayload.request_body,
                });
            } else if (accumulated) {
                appendMessage("assistant", accumulated, {});
            }
            pendingAttachments.forEach((attachment) => {
                if (attachment.audioUrl) {
                    try { URL.revokeObjectURL(attachment.audioUrl); } catch (error) {}
                }
                if (attachment.videoUrl) {
                    try { URL.revokeObjectURL(attachment.videoUrl); } catch (error) {}
                }
            });
            pendingAttachments.length = 0;
            renderAttachments();
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
            updateTokenUsage();
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
            if (savedSelect) savedSelect.value = "";
            chatMessageTokens.length = 0;
            updateTokenUsage();
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
            const messages = payload.messages || [];
            renderHistory(messages);
            chatMessageTokens.length = 0;
            messages.forEach((message) => {
                chatMessageTokens.push({
                    input_tokens: message.input_tokens || 0,
                    output_tokens: message.output_tokens || 0,
                    compacted: Boolean(message.compacted),
                });
            });
            updateTokenUsage();
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

    const handleReplaceChat = async () => {
        const name = savedSelect?.value || "";
        if (!name) {
            window.alert("Select a saved chat to replace.");
            return;
        }
        if (replaceBtn) replaceBtn.disabled = true;
        try {
            await api.json("/chat/replace_chat", {
                method: "POST",
                body: { name },
            });
            await refreshSavedChats(name);
        } catch (error) {
            window.alert(`Replace chat failed: ${error}`);
        } finally {
            if (replaceBtn) replaceBtn.disabled = false;
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
                if (body && typeof body === 'object' && !Array.isArray(body) && (body.video_request || body.audio_request)) {
                    let html = '';
                    if (body.video_request) {
                        html += `### Video request\n\n\`\`\`json\n${JSON.stringify(body.video_request, null, 2)}\n\`\`\`\n\n`;
                    }
                    if (body.audio_request) {
                        html += `### Audio request\n\n\`\`\`json\n${JSON.stringify(body.audio_request, null, 2)}\n\`\`\`\n`;
                    }
                    requestBodyText.innerHTML = renderMarkdown(html);
                } else {
                    requestBodyText.innerHTML = renderMarkdown("```json\n" + JSON.stringify(body, null, 2) + "\n```");
                }
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
        if (name === "temperature" || name === "top_p" || name === "top_k" || name === "seed" || name === "min_p") return true;
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
    };

    const setMoreParamsDeleteVisible = (visible) => {
        if (moreParamsDeleteBtn) moreParamsDeleteBtn.hidden = !visible;
        if (moreParamsSaveModelBtn) moreParamsSaveModelBtn.hidden = !visible;
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
        if (provider === "llama.cpp") {
            try {
                const modePayload = await api.request(
                    `/setup_models/ctx_mode?provider=${encodeURIComponent(provider)}`
                );
                const mode = modePayload && modePayload.ctx_mode;
                if (mode) {
                    const label = moreParamsLoading
                        ? moreParamsLoading.querySelector("span:not(.chat-spinner)")
                        : null;
                    if (label) {
                        label.textContent = `Getting ctx for ${mode} mode…`;
                    }
                }
            } catch (error) {
                // Keep the default loading label.
            }
        }
        try {
            const payload = await api.request(
                `/setup_models/model_params?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`
            );
            setMoreParamsLoading(false);
            renderMoreParams((payload && payload.params) || {});
            setMoreParamsDeleteVisible(true);
            moreParamsModelKey = `${provider}::${model}`;
        } catch (error) {
            setMoreParamsLoading(false);
            setMoreParamsDeleteVisible(false);
            showMoreParamsNote(`Failed to load parameters: ${error}`);
            updateMoreParamsSign();
        }
    };

    // Media upload icons shown under the message input, driven by the saved
    // modalities for the selected local model. Icons only: no click handling yet.
    // The document icon is always available (document processing is assumed to
    // be supported by every model), so it is rendered first in every state.
    const DOCUMENT_UPLOAD_ICON = {
        key: "document",
        glyph: "📄",
        label: "Upload document",
        accept: ".txt,.md,.doc,.rtf,.docx",
        attachmentType: "document",
    };
    const MEDIA_UPLOAD_ICONS = [
        { key: "vision", glyph: "📷", label: "Upload image", accept: "image/*", attachmentType: "image" },
        { key: "video", glyph: "🎥", label: "Upload video", accept: ".mp4,video/mp4", attachmentType: "video" },
        { key: "audio", glyph: "🎤", label: "Upload audio", accept: ".mp3,.wav,audio/mpeg,audio/wav", attachmentType: "audio" },
    ];

    const createMediaUploadButton = (item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "chat-media-icon";
        button.title = item.label;
        button.setAttribute("aria-label", item.label);
        button.disabled = false;
        const glyph = document.createElement("span");
        glyph.className = "chat-media-glyph";
        glyph.setAttribute("aria-hidden", "true");
        glyph.textContent = item.glyph;
        const tooltip = document.createElement("span");
        tooltip.className = "chat-media-tooltip";
        tooltip.setAttribute("role", "tooltip");
        tooltip.textContent = item.label;
        button.append(glyph, tooltip);
        button.addEventListener("click", () => {
            if (item.key === "document" && !mineruConfigured) {
                pendingDocumentPicker = true;
                openMineruSettings();
                return;
            }
            openFilePicker(item);
        });
        if (item.key === "document") {
            button.addEventListener("contextmenu", (event) => {
                event.preventDefault();
                openMineruSettings();
            });
        }
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

    const ensureCtxMode = async (provider) => {
        if (provider !== "llama.cpp") return null;
        if (sessionCtxModeFetched) return sessionCtxMode;
        sessionCtxModeFetched = true;
        try {
            const payload = await api.request(
                `/setup_models/ctx_mode?provider=${encodeURIComponent(provider)}`
            );
            sessionCtxMode = (payload && payload.ctx_mode) || null;
        } catch (error) {
            sessionCtxMode = null;
        }
        return sessionCtxMode;
    };

    const refreshMediaUploads = async (provider, model) => {
        const requestSeq = ++mediaUploadsSeq;
        // Clear icons first: without saved modalities the default is false.
        renderMediaUploads(null);
        if (modelNctxEl) {
            modelNctxEl.textContent = "";
        }
        const isLocal = provider === "llama.cpp" || provider === "vllm";
        if (!isLocal || !model) {
            return;
        }
        try {
            if (provider === "llama.cpp") {
                if (tokenUsageEl) {
                    tokenUsageEl.classList.remove(
                        "chat-token-usage--ok",
                        "chat-token-usage--warn",
                        "chat-token-usage--over"
                    );
                    tokenUsageEl.classList.add("chat-token-usage--loading");
                    tokenUsageEl.innerHTML =
                        '<span class="chat-spinner" aria-hidden="true"></span> getting context data...';
                }
                if (contextBarFillEl) {
                    contextBarFillEl.style.width = "100%";
                    contextBarFillEl.classList.remove(
                        "chat-context-bar-fill--ok",
                        "chat-context-bar-fill--warn",
                        "chat-context-bar-fill--over"
                    );
                    contextBarFillEl.classList.add("chat-context-bar-fill--loading");
                }
            }
            const mode = provider === "llama.cpp" ? await ensureCtxMode(provider) : null;
            const payload = await api.request(
                `/setup_models/model_params?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`
            );
            if (requestSeq !== mediaUploadsSeq) return;
            renderMediaUploads(payload && payload.modalities);
            const resolvedMode = (payload && payload.ctx_mode) || mode;
            if (payload && payload.n_ctx != null) {
                currentNctx = payload.n_ctx;
            }
            if (modelNctxEl) {
                if (payload && payload.n_ctx != null && resolvedMode) {
                    modelNctxEl.textContent = `| N ctx: ${payload.n_ctx} | ${resolvedMode}`;
                } else if (resolvedMode) {
                    modelNctxEl.textContent = `| ${resolvedMode}`;
                } else {
                    modelNctxEl.textContent = "";
                }
            }
            updateTokenUsage();
        } catch (error) {
            if (requestSeq !== mediaUploadsSeq) return;
            renderMediaUploads(null);
            if (modelNctxEl) {
                modelNctxEl.textContent = "";
            }
            updateTokenUsage();
        }
    };

    const documentIconFor = (name) => {
        const lower = String(name || "").toLowerCase();
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg") || lower.endsWith(".png")) return "📷";
        if (lower.endsWith(".pdf")) return "📕";
        if (lower.endsWith(".doc") || lower.endsWith(".docx")) return "📘";
        if (lower.endsWith(".ppt") || lower.endsWith(".pptx")) return "📙";
        if (lower.endsWith(".xls") || lower.endsWith(".xlsx")) return "📗";
        if (lower.endsWith(".json")) return "📋";
        if (lower.endsWith(".csv") || lower.endsWith(".tsv")) return "📊";
        if (lower.endsWith(".html") || lower.endsWith(".mhtml") || lower.endsWith(".htm")) return "🌐";
        if (lower.endsWith(".md")) return "📝";
        if (lower.endsWith(".txt")) return "📄";
        return "📄";
    };

    const mimeForName = (name, fallback) => {
        const lower = String(name || "").toLowerCase();
        if (lower.endsWith(".txt")) return "text/plain";
        if (lower.endsWith(".md")) return "text/markdown";
        if (lower.endsWith(".doc")) return "application/msword";
        if (lower.endsWith(".rtf")) return "application/rtf";
        if (lower.endsWith(".docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        if (lower.endsWith(".mp4")) return "video/mp4";
        if (lower.endsWith(".mp3")) return "audio/mpeg";
        if (lower.endsWith(".wav")) return "audio/wav";
        return fallback || "application/octet-stream";
    };

    const readFileAsDataURL = (file) => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("File read failed"));
        reader.readAsDataURL(file);
    });

    const readFileAsText = (file) => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("File read failed"));
        reader.readAsText(file);
    });

    const processImageFile = (file) => new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => {
            try {
                const maxPixels = 1.2 * 1000 * 1000;
                const pixels = img.width * img.height;
                let width = img.width;
                let height = img.height;
                if (pixels > maxPixels) {
                    const scale = Math.sqrt(maxPixels / pixels);
                    width = Math.max(1, Math.round(img.width * scale));
                    height = Math.max(1, Math.round(img.height * scale));
                }
                if (width === img.width && height === img.height) {
                    readFileAsDataURL(file).then((dataUrl) => {
                        const parts = dataUrl.split(",");
                        resolve({ data: parts[1] || "", mime: file.type || mimeForName(file.name, "image/png") });
                    }).catch(reject);
                    return;
                }
                const canvas = document.createElement("canvas");
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0, width, height);
                const mime = "image/jpeg";
                const dataUrl = canvas.toDataURL(mime, 0.9);
                resolve({ data: dataUrl.split(",")[1] || "", mime });
            } catch (error) {
                reject(error);
            } finally {
                URL.revokeObjectURL(url);
            }
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("Image load failed"));
        };
        img.src = url;
    });

    const processVideoFile = (file) => new Promise((resolve) => {
        const url = URL.createObjectURL(file);
        const video = document.createElement("video");
        video.preload = "metadata";
        video.muted = true;
        video.playsInline = true;
        const cleanup = () => URL.revokeObjectURL(url);
        video.onloadedmetadata = () => {
            const middle = (video.duration && Number.isFinite(video.duration))
                ? video.duration / 2
                : 0;
            const onSeeked = () => {
                try {
                    const canvas = document.createElement("canvas");
                    const width = video.videoWidth || 320;
                    const height = video.videoHeight || 180;
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext("2d");
                    ctx.drawImage(video, 0, 0, width, height);
                    resolve(canvas.toDataURL("image/jpeg", 0.7));
                } catch (error) {
                    resolve(null);
                } finally {
                    cleanup();
                }
            };
            video.onseeked = onSeeked;
            try {
                video.currentTime = middle;
            } catch (error) {
                onSeeked();
            }
        };
        video.onerror = () => {
            cleanup();
            resolve(null);
        };
        video.src = url;
    });

    const processSelectedFile = async (file, attachmentType) => {
        if (!file) return null;
        if (attachmentType === "document") {
            const ext = String(file.name || "").split(".").pop().toLowerCase();
            const textExtensions = new Set([
                "txt", "md", "json", "csv", "tsv", "html", "htm", "xml", "rtf",
            ]);
            const isText = textExtensions.has(ext)
                || String(file.type || "").startsWith("text/")
                || file.type === "application/json";

            const compatibleExtensions = new Set([
                "pdf", "jpg", "jpeg", "png", "doc", "docx", "ppt", "pptx",
                "xls", "xlsx", "rtf", "odt", "ods", "odp", "epub", "html",
                "htm", "mhtml", "ofd", "csv", "tsv",
            ]);
            if (!isText && !compatibleExtensions.has(ext)) {
                window.alert("This file type is not supported.");
                return null;
            }

            if (isText) {
                const content = await readFileAsText(file);
                const mime = file.type || mimeForName(file.name, "text/plain");
                return {
                    type: "document",
                    name: file.name,
                    mime,
                    data: null,
                    size: file.size,
                    previewUrl: null,
                    audioUrl: null,
                    videoUrl: null,
                    previewData: null,
                    needsMineru: false,
                    documentPayload: {
                        filename: file.name,
                        mime_type: mime,
                        extension: ext,
                        size: file.size,
                        content,
                    },
                };
            }

            // Binary document compatible with MinerU.
            const dataUrl = await readFileAsDataURL(file);
            const parts = dataUrl.split(",");
            const mime = file.type || mimeForName(file.name);
            return {
                type: "document",
                name: file.name,
                mime,
                data: parts[1] || "",
                size: file.size,
                previewUrl: null,
                audioUrl: null,
                videoUrl: null,
                previewData: null,
                needsMineru: true,
                documentPayload: null,
            };
        }
        if (attachmentType === "image") {
            const processed = await processImageFile(file);
            return {
                type: "image",
                name: file.name,
                mime: processed.mime,
                data: processed.data,
                previewUrl: processed.mime.startsWith("image/")
                    ? `data:${processed.mime};base64,${processed.data}`
                    : null,
                audioUrl: null,
                videoUrl: null,
                previewData: null,
            };
        }
        if (attachmentType === "video") {
            const dataUrl = await readFileAsDataURL(file);
            const parts = dataUrl.split(",");
            const mime = file.type || mimeForName(file.name);
            const previewDataUrl = await processVideoFile(file);
            const previewBase64 = previewDataUrl
                ? previewDataUrl.split(",")[1] || null
                : null;
            return {
                type: "video",
                name: file.name,
                mime,
                data: parts[1] || "",
                previewUrl: previewDataUrl,
                audioUrl: null,
                videoUrl: URL.createObjectURL(file),
                previewData: previewBase64,
            };
        }
        if (attachmentType === "audio") {
            const dataUrl = await readFileAsDataURL(file);
            const parts = dataUrl.split(",");
            const mime = file.type || mimeForName(file.name);
            return {
                type: "audio",
                name: file.name,
                mime,
                data: parts[1] || "",
                previewUrl: null,
                audioUrl: URL.createObjectURL(file),
                videoUrl: null,
                previewData: null,
            };
        }
        const dataUrl = await readFileAsDataURL(file);
        const parts = dataUrl.split(",");
        const mime = file.type || mimeForName(file.name);
        return {
            type: attachmentType,
            name: file.name,
            mime,
            data: parts[1] || "",
            size: file.size,
            previewUrl: null,
            audioUrl: null,
            videoUrl: null,
            previewData: null,
        };
    };

    const renderAttachments = () => {
        if (attachmentsEl) attachmentsEl.replaceChildren();
        if (audioAttachmentsEl) audioAttachmentsEl.replaceChildren();
        const hasOriginalMedia = pendingAttachments.some(
            (attachment) => attachment.type === "video" || attachment.type === "audio"
        );
        const hasVideo = pendingAttachments.some(
            (attachment) => attachment.type === "video"
        );
        if (saveOriginalSwitch) {
            saveOriginalSwitch.hidden = !hasOriginalMedia;
        }
        if (attachAudioSwitch) {
            attachAudioSwitch.hidden = !hasVideo;
        }
        if (fpsControl) {
            fpsControl.hidden = !hasVideo;
        }
        if (pendingAttachments.length === 0) {
            if (attachmentsEl) attachmentsEl.hidden = true;
            if (audioAttachmentsEl) audioAttachmentsEl.hidden = true;
            return;
        }

        pendingAttachments.forEach((attachment, index) => {
            const removeAttachment = () => {
                if (attachment.audioUrl) {
                    try { URL.revokeObjectURL(attachment.audioUrl); } catch (error) {}
                }
                if (attachment.videoUrl) {
                    try { URL.revokeObjectURL(attachment.videoUrl); } catch (error) {}
                }
                pendingAttachments.splice(index, 1);
                renderAttachments();
            };

            if (attachment.type === "document") {
                const item = document.createElement("div");
                item.className = "chat-attachment";
                item.setAttribute("data-chat-attachment", attachment.type);

                const icon = document.createElement("span");
                icon.className = "chat-attachment-document-icon";
                icon.textContent = documentIconFor(attachment.name);
                item.appendChild(icon);

                const name = document.createElement("span");
                name.className = "chat-attachment-name";
                name.textContent = attachment.name;
                name.title = attachment.name;
                item.appendChild(name);

                if (attachment.needsMineru) {
                    const badge = document.createElement("span");
                    badge.className = "chat-attachment-mineru-badge";
                    badge.textContent = "MinerU";
                    item.appendChild(badge);
                }

                const removeBtn = document.createElement("button");
                removeBtn.type = "button";
                removeBtn.className = "chat-attachment-remove";
                removeBtn.textContent = "×";
                removeBtn.title = "Remove attachment";
                removeBtn.addEventListener("click", removeAttachment);
                item.appendChild(removeBtn);
                attachmentsEl.appendChild(item);
                return;
            } else if (attachment.type === "audio") {
                if (!audioAttachmentsEl) return;
                const item = chatMedia.createAudio(
                    attachment.audioUrl,
                    attachment.name,
                    false
                );
                item.setAttribute("data-chat-attachment", "audio");

                const removeBtn = document.createElement("button");
                removeBtn.type = "button";
                removeBtn.className = "chat-attachment-remove";
                removeBtn.textContent = "×";
                removeBtn.title = "Remove attachment";
                removeBtn.addEventListener("click", removeAttachment);
                item.appendChild(removeBtn);

                audioAttachmentsEl.appendChild(item);
                return;
            }

            if (!attachmentsEl) return;
            const item = document.createElement("div");
            item.className = "chat-attachment";
            item.setAttribute("data-chat-attachment", attachment.type);
            if (attachment.type === "image" && attachment.previewUrl) {
                const img = document.createElement("img");
                img.className = "chat-attachment-preview";
                img.src = attachment.previewUrl;
                img.alt = attachment.name;
                item.appendChild(img);
            } else if (attachment.type === "video" && attachment.videoUrl) {
                item.className = "chat-attachment chat-attachment--video";
                const videoWrap = document.createElement("div");
                videoWrap.className = "chat-video-wrap";
                const video = document.createElement("video");
                video.className = "chat-attachment-video";
                video.src = attachment.videoUrl;
                video.height = 130;
                video.controls = false;
                video.preload = "metadata";
                videoWrap.appendChild(video);

                const controls = document.createElement("div");
                controls.className = "chat-video-controls";
                const toggleBtn = document.createElement("button");
                toggleBtn.type = "button";
                toggleBtn.className = "chat-video-toggle";
                toggleBtn.textContent = "▶";
                toggleBtn.title = "Play";
                controls.appendChild(toggleBtn);
                const backBtn = document.createElement("button");
                backBtn.type = "button";
                backBtn.className = "chat-video-back";
                backBtn.textContent = "⏪";
                backBtn.title = "Rewind to beginning";
                controls.appendChild(backBtn);
                videoWrap.appendChild(controls);
                chatMedia.wire(videoWrap, "video");
                item.appendChild(videoWrap);
            } else {
                const name = document.createElement("span");
                name.className = "chat-attachment-name";
                name.textContent = attachment.name;
                name.title = attachment.name;
                item.appendChild(name);
            }
            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "chat-attachment-remove";
            removeBtn.textContent = "×";
            removeBtn.title = "Remove attachment";
            removeBtn.addEventListener("click", removeAttachment);
            item.appendChild(removeBtn);
            attachmentsEl.appendChild(item);
        });

        if (attachmentsEl) {
            attachmentsEl.hidden = attachmentsEl.children.length === 0;
        }
        if (audioAttachmentsEl) {
            audioAttachmentsEl.hidden = audioAttachmentsEl.children.length === 0;
        }
    };

    const openFilePicker = async (icon) => {
        const input = document.createElement("input");
        input.type = "file";
        let accept = icon.accept;
        let checkingEl = null;
        if (icon.attachmentType === "document") {
            checkingEl = document.createElement("div");
            checkingEl.className = "chat-checking-attachment";
            checkingEl.innerHTML = '<span class="chat-spinner" aria-hidden="true"></span><span>Checking attachment…</span>';
            const container = mediaUploadsEl || document.querySelector(".chat-media-row");
            if (container) {
                container.appendChild(checkingEl);
                container.hidden = false;
            }
            try {
                const payload = await api.request("/chat/mineru_available");
                accept = payload && payload.available
                    ? ".pdf,.jpg,.jpeg,.png,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.rtf,.odt,.ods,.odp,.epub,.html,.mhtml,.ofd,.csv,.tsv,.txt,.md,.json"
                    : ".txt,.md,.json";
            } catch (error) {
                accept = ".txt,.md,.json";
            } finally {
                if (checkingEl && checkingEl.parentNode) {
                    checkingEl.parentNode.removeChild(checkingEl);
                }
                if (attachmentsEl && attachmentsEl.children.length === 0) {
                    attachmentsEl.hidden = true;
                }
            }
        }
        input.accept = accept;
        input.className = "chat-file-input";
        document.body.appendChild(input);
        input.addEventListener("change", async () => {
            const file = input.files && input.files[0];
            try {
                if (file) {
                    const attachment = await processSelectedFile(file, icon.attachmentType);
                    if (attachment) {
                        pendingAttachments.push(attachment);
                        renderAttachments();
                    }
                }
            } catch (error) {
                window.alert(`File could not be attached: ${error}`);
            } finally {
                input.remove();
            }
        });
        input.click();
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

    const handleSaveMoreParamsModel = async () => {
        const modelValue = modelSelect?.value || "";
        const parts = modelValue.split("::");
        const provider = (parts[0] || "").trim();
        const model = parts.slice(1).join("::").trim();
        if (!provider || !model) return;

        const params = collectMoreParams();
        if (moreParamsSaveModelBtn) moreParamsSaveModelBtn.disabled = true;
        try {
            await api.json("/setup_models/model_params/save", {
                method: "POST",
                body: { provider, model, params },
            });
            window.alert("Model parameters saved.");
        } catch (error) {
            window.alert(`Save failed: ${error}`);
        } finally {
            if (moreParamsSaveModelBtn) moreParamsSaveModelBtn.disabled = false;
        }
    };

    const openMineruSettings = () => {
        if (mineruModal) {
            mineruModal.hidden = false;
            if (mineruEndpointInput) mineruEndpointInput.value = mineruEndpoint;
            if (mineruApiKeyInput) mineruApiKeyInput.value = mineruApiKey;
        }
    };
    const closeMineruSettings = () => {
        if (mineruModal) mineruModal.hidden = true;
    };
    const saveMineruSettings = async () => {
        const endpoint = mineruEndpointInput?.value?.trim() || "";
        const api_key = mineruApiKeyInput?.value?.trim() || "";
        if (!endpoint) {
            window.alert("MinerU endpoint is required.");
            return;
        }
        if (mineruSaveBtn) mineruSaveBtn.disabled = true;
        try {
            const payload = await api.json("/chat/save_mineru_settings", {
                method: "POST",
                body: { endpoint, api_key },
            });
            mineruEndpoint = payload.endpoint || endpoint;
            mineruApiKey = payload.api_key || api_key;
            mineruConfigured = true;
            window.CairnmarkMineruSettings = {
                endpoint: mineruEndpoint,
                api_key: mineruApiKey,
                configured: true,
            };
            closeMineruSettings();
            if (pendingDocumentPicker) {
                pendingDocumentPicker = false;
                openFilePicker(DOCUMENT_UPLOAD_ICON);
            }
        } catch (error) {
            window.alert(`Save failed: ${error}`);
        } finally {
            if (mineruSaveBtn) mineruSaveBtn.disabled = false;
        }
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
            attachAssistantActions(el, el.dataset.raw || el.textContent);
        });
    }

    const updateFpsValue = () => {
        if (!fpsSlider || !fpsValue) return;
        const index = Number(fpsSlider.value) || 0;
        const value = videoFpsValues[index] != null ? videoFpsValues[index] : videoFpsValues[0];
        fpsValue.textContent = String(value);
        fpsSlider.title = `Set FPS: ${value}`;
    };
    fpsSlider?.addEventListener("input", updateFpsValue);
    updateFpsValue();

    seedSwitch?.addEventListener("click", () => {
        if (!seedSwitch) return;
        const next = seedSwitch.getAttribute("aria-checked") !== "true";
        seedSwitch.setAttribute("aria-checked", next ? "true" : "false");
        if (api) {
            api.json("/chat/save_attachment_settings", {
                method: "POST",
                body: { randomize_seed: next },
            }).catch((error) => {
                console.error("Failed to save seed switch:", error);
            });
        }
    });

    const syncHistoryInputState = () => {
        if (!historyLimitEl) return;
        const allPrevious = Boolean(
            historySwitch && historySwitch.getAttribute("aria-checked") === "true"
        );
        historyLimitEl.disabled = allPrevious;
    };

    const usageHistory = () => {
        let lastCompacted = -1;
        chatMessageTokens.forEach((item, index) => {
            if (item && item.compacted) lastCompacted = index;
        });
        if (lastCompacted >= 0) {
            return chatMessageTokens.slice(lastCompacted);
        }
        return chatMessageTokens.slice();
    };

    const selectedUsageMessages = () => {
        const allPrevious = Boolean(
            historySwitch && historySwitch.getAttribute("aria-checked") === "true"
        );
        const rawLimit = historyLimitEl ? String(historyLimitEl.value || "").trim() : "";
        const limit = rawLimit ? parseInt(rawLimit, 10) : NaN;
        const history = usageHistory();
        if (allPrevious || !Number.isFinite(limit) || limit < 0) {
            return history.slice();
        }
        if (history.length === 0) return [];
        const currentTurn = history.slice(-1);
        const previous = history.slice(0, -1);
        if (limit <= 0) {
            return [];
        }
        const keptPrevious = limit * 2;
        let start = Math.max(0, previous.length - keptPrevious);
        const selectedPrevious = previous.slice(start);
        return selectedPrevious.concat(currentTurn);
    };

    const updateCompactButtonVisibility = () => {
        if (!compactBtn) return;
        const hasMessages = chatMessageTokens.length > 0;
        const hasMultipleMessages = chatMessageTokens.length > 1;
        const lastIsCompacted = Boolean(
            chatMessageTokens.length &&
                chatMessageTokens[chatMessageTokens.length - 1].compacted
        );
        const switchOn = Boolean(
            historySwitch && historySwitch.getAttribute("aria-checked") === "true"
        );
        const rawLimit = historyLimitEl ? String(historyLimitEl.value || "").trim() : "";
        const limit = rawLimit ? parseInt(rawLimit, 10) : 0;
        const hasHistoryToSend = switchOn || (Number.isFinite(limit) && limit > 0);
        let notFull = false;
        let overLimit = false;
        if (currentNctx) {
            const messages = selectedUsageMessages();
            const used = messages.reduce(
                (total, item) =>
                    total + (Number(item && item.input_tokens) || 0) +
                    (Number(item && item.output_tokens) || 0),
                0
            );
            notFull = used / currentNctx < 1;
            overLimit = used / currentNctx > 1;
        }
        const canCompact = hasMessages && hasHistoryToSend && !overLimit && !lastIsCompacted && (hasMultipleMessages || notFull);
        compactBtn.hidden = !canCompact;
        compactBtn.disabled = !canCompact;
    };

    const updateTokenUsage = () => {
        if (!tokenUsageEl) return;
        const messages = selectedUsageMessages();
        const used = messages.reduce(
            (total, item) =>
                total + (Number(item && item.input_tokens) || 0) +
                (Number(item && item.output_tokens) || 0),
            0
        );
        if (currentNctx) {
            const percent = Math.round((used / currentNctx) * 100);
            tokenUsageEl.textContent = `${used} / ${currentNctx} (${percent}%)`;
            tokenUsageEl.classList.remove(
                "chat-token-usage--ok",
                "chat-token-usage--warn",
                "chat-token-usage--over",
                "chat-token-usage--loading"
            );
            if (contextBarFillEl) {
                contextBarFillEl.classList.remove(
                    "chat-context-bar-fill--ok",
                    "chat-context-bar-fill--warn",
                    "chat-context-bar-fill--over",
                    "chat-context-bar-fill--loading"
                );
            }
            let overLimit = false;
            if (percent <= 75) {
                tokenUsageEl.classList.add("chat-token-usage--ok");
                if (contextBarFillEl) contextBarFillEl.classList.add("chat-context-bar-fill--ok");
            } else if (percent <= 95) {
                tokenUsageEl.classList.add("chat-token-usage--warn");
                if (contextBarFillEl) contextBarFillEl.classList.add("chat-context-bar-fill--warn");
            } else {
                tokenUsageEl.classList.add("chat-token-usage--over");
                if (contextBarFillEl) contextBarFillEl.classList.add("chat-context-bar-fill--over");
                overLimit = true;
            }
            if (contextBarFillEl) {
                contextBarFillEl.style.width = `${Math.min(100, Math.max(0, percent))}%`;
            }
            if (sendBtn) {
                sendBtn.disabled = overLimit;
                sendBtn.title = overLimit
                    ? "The context window not enough to send new message"
                    : "";
            }
        } else {
            tokenUsageEl.textContent = "getting context data...";
            tokenUsageEl.classList.remove(
                "chat-token-usage--ok",
                "chat-token-usage--warn",
                "chat-token-usage--over",
                "chat-token-usage--loading"
            );
            if (contextBarFillEl) {
                contextBarFillEl.style.width = "100%";
                contextBarFillEl.classList.remove(
                    "chat-context-bar-fill--warn",
                    "chat-context-bar-fill--over",
                    "chat-context-bar-fill--loading"
                );
                contextBarFillEl.classList.add("chat-context-bar-fill--ok");
            }
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.title = "";
            }
        }
        updateCompactButtonVisibility();
    };

    if (historySwitch) {
        const savedHistoryState =
            (window.CairnmarkChatAttachmentSettings &&
                window.CairnmarkChatAttachmentSettings.send_all_previous) ||
            (window.CairnmarkHistorySettings &&
                window.CairnmarkHistorySettings.send_all_previous);
        if (savedHistoryState) {
            historySwitch.setAttribute("aria-checked", "true");
        } else {
            historySwitch.setAttribute(
                "aria-checked",
                historySwitch.getAttribute("aria-checked") || "false"
            );
        }
        syncHistoryInputState();
        updateTokenUsage();
    }

    historyLimitEl?.addEventListener("input", updateTokenUsage);

    historySwitch?.addEventListener("click", () => {
        if (!historySwitch) return;
        const next = historySwitch.getAttribute("aria-checked") !== "true";
        historySwitch.setAttribute("aria-checked", next ? "true" : "false");
        syncHistoryInputState();
        updateTokenUsage();
        if (api) {
            api.json("/chat/save_attachment_settings", {
                method: "POST",
                body: { send_all_previous: next },
            }).catch((error) => {
                console.error("Failed to save history switch:", error);
            });
        }
    });
    updateTokenUsage();
    const handleCompact = async () => {
        if (!compactBtn) return;
        const message = inputEl ? "" : "";
        const model = modelSelect?.value || "";
        if (!model) {
            window.alert("Model is required.");
            return;
        }
        compactBtn.disabled = true;
        if (sendBtn) sendBtn.disabled = true;

        const controller = new AbortController();
        let aborted = false;
        const loadingEl = showLoading(() => {
            aborted = true;
            controller.abort();
        }, { compacted: true });

        const requestBody = {
            model,
            history_limit: optionalNumber(historyLimitEl, Number.parseInt),
            send_all_previous: Boolean(
                historySwitch && historySwitch.getAttribute("aria-checked") === "true"
            ),
        };

        try {
            const response = await fetch("/chat/compact?stream=1", {
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
                try { payload = await response.json(); } catch (error) {}
                throw new Error(payload.error || `HTTP ${response.status}`);
            }
            if (!response.body) throw new Error("Streaming is not supported by this browser.");

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
                        try { data = JSON.parse(raw); } catch (error) { continue; }
                        if (data.type === "status") {
                            if (loadingEl && loadingEl.loadingText) loadingEl.loadingText.textContent = data.text || "thinking…";
                        } else if (data.type === "chunk") {
                            accumulated += data.text || "";
                            if (loadingEl && loadingEl.tokenCount) loadingEl.tokenCount.textContent = `${accumulated.length} chars`;
                        } else if (data.type === "done") {
                            if (loadingEl && loadingEl.tokenCount) loadingEl.tokenCount.textContent = `${accumulated.length} chars`;
                        } else if (data.type === "result") {
                            finalPayload = data;
                        } else if (data.type === "error") {
                            throw new Error(data.error || "Request failed");
                        }
                    }
                }
            }

            if (aborted) {
                if (loadingEl && loadingEl.element) loadingEl.element.remove();
                syncEmptyState();
                try { await api.request("/chat/abort", { method: "POST" }); } catch (error) {}
                return;
            }
            if (loadingEl && loadingEl.element) loadingEl.element.remove();
            if (finalPayload) {
                chatMessageTokens.push({
                    input_tokens: finalPayload.input_tokens || 0,
                    output_tokens: finalPayload.output_tokens || 0,
                    compacted: true,
                });
                appendMessage("assistant", finalPayload.response || "", {
                    provider: finalPayload.provider,
                    model: finalPayload.model,
                    time: finalPayload.time,
                    input_tokens: finalPayload.input_tokens,
                    output_tokens: finalPayload.output_tokens,
                    system_prompt: finalPayload.system_prompt,
                    request_body: finalPayload.request_body,
                    compacted: true,
                });
                updateTokenUsage();
            } else if (accumulated) {
                appendMessage("assistant", accumulated, { compacted: true });
            }
        } catch (error) {
            if (loadingEl && loadingEl.element) loadingEl.element.remove();
            if (aborted || (error && error.name === "AbortError")) {
                if (loadingEl && loadingEl.element) loadingEl.element.remove();
                syncEmptyState();
                try { await api.request("/chat/abort", { method: "POST" }); } catch (error2) {}
                return;
            }
            window.alert(`Compact failed: ${error}`);
        } finally {
            if (compactBtn) compactBtn.disabled = false;
            updateTokenUsage();
        }
    };

    compactBtn?.addEventListener("click", handleCompact);
    updateTokenUsage();
    sendBtn?.addEventListener("click", handleSend);
    saveBtn?.addEventListener("click", handleSave);
    clearBtn?.addEventListener("click", handleClear);
    saveOpenBtn?.addEventListener("click", openSaveModal);
    saveConfirmBtn?.addEventListener("click", handleSaveChat);
    saveCloseBtns.forEach((b) => b.addEventListener("click", closeSaveModal));
    savedSelect?.addEventListener("change", handleLoadChat);
    replaceBtn?.addEventListener("click", handleReplaceChat);
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
    moreParamsSaveModelBtn?.addEventListener("click", handleSaveMoreParamsModel);
    mineruCloseBtns.forEach((btn) => btn.addEventListener("click", closeMineruSettings));
    mineruSaveBtn?.addEventListener("click", saveMineruSettings);
    mineruModal?.addEventListener("click", (event) => {
        if (event.target === mineruModal) closeMineruSettings();
    });
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

    const clearSavedSystemPrompt = () => {
        if (savedSpSelect && savedSpSelect.value !== "") {
            savedSpSelect.value = "";
            savedSpSelect.dispatchEvent(new Event("change", { bubbles: true }));
        }
    };

    // A manual edit is no longer associated with the loaded saved prompt.
    systemPromptEl?.addEventListener("input", clearSavedSystemPrompt);
    systemPromptEl?.addEventListener("change", clearSavedSystemPrompt);

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
            modelSelect.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    // Keep the always-available document icon visible from first paint.
    renderMediaUploads(null);
    setTimeout(updateMoreParamsButtonState, 2000);

    if (historyEl) {
        historyEl.scrollTop = historyEl.scrollHeight;
    }
})();
