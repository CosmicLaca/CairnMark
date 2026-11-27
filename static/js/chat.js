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
    const historySwitch = document.querySelector("[data-chat-history-switch]");
    const tokenUsageEl = document.querySelector("[data-chat-token-usage]");
    const contextBarFillEl = document.querySelector("[data-chat-context-bar-fill]");
    let sessionCtxMode = null;
    let contextStatus = "idle";
    let compactRequestActive = false;
    const chatContext = new window.CairnmarkChatContextState(
        window.CairnmarkChatMessageTokens
    );
    const saveBtn = document.querySelector("[data-chat-save-settings]");
    const clearBtn = document.querySelector("[data-chat-clear]");
    const compactBtn = document.querySelector("[data-chat-compact]");
    const compactSwitch = document.querySelector("[data-chat-compact-switch]");
    const compactTooltip = document.querySelector("[data-chat-compact-tooltip]");
    const compactSettingsModal = document.querySelector("[data-auto-compact-settings-modal]");
    const compactThresholdInput = document.querySelector("[data-auto-compact-threshold]");
    const compactSettingsSaveBtn = document.querySelector("[data-auto-compact-settings-save]");
    const compactSettingsCloseBtns = document.querySelectorAll("[data-auto-compact-settings-close]");
    const importBtn = document.querySelector("[data-chat-import]");
    const exportBtn = document.querySelector("[data-chat-export]");
    const savedSelect = document.querySelector("[data-chat-saved]");
    const replaceBtn = document.querySelector("[data-chat-replace]");
    const deleteBtn = document.querySelector("[data-chat-delete]");
    const chatFileAccordion = document.querySelector("[data-chat-file-accordion]");
    const chatFileList = document.querySelector("[data-chat-file-list]");
    const chatFileCount = document.querySelector("[data-chat-file-count]");
    const saveOpenBtn = document.querySelector("[data-chat-save-open]");
    const saveModal = document.querySelector("[data-save-chat-modal]");
    const saveNameInput = document.querySelector("[data-save-chat-name]");
    const saveConfirmBtn = document.querySelector("[data-save-chat-confirm]");
    const saveCloseBtns = document.querySelectorAll("[data-save-chat-close]");
    const reverseImageModal = document.querySelector("[data-reverse-image-modal]");
    const reverseImagePreview = document.querySelector("[data-reverse-image-preview]");
    const reverseImageDescription = document.querySelector(
        "[data-reverse-image-description]"
    );
    const reverseImageHint = document.querySelector("[data-reverse-image-hint]");
    const reverseImageServiceBtns = document.querySelectorAll(
        "[data-reverse-image-service]"
    );
    const reverseImageCloseBtns = document.querySelectorAll(
        "[data-reverse-image-close]"
    );
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
    const moreParamsCacheState = document.querySelector("[data-more-params-cache-state]");
    const moreParamsCacheTooltip = document.querySelector("[data-more-params-cache-tooltip]");
    const mineruModal = document.querySelector("[data-mineru-settings-modal]");
    const mineruEndpointInput = document.querySelector("[data-mineru-endpoint]");
    const mineruApiKeyInput = document.querySelector("[data-mineru-api-key]");
    const mineruTimeoutInput = document.querySelector("[data-mineru-timeout]");
    const mineruSaveBtn = document.querySelector("[data-mineru-settings-save]");
    const mineruCloseBtns = document.querySelectorAll("[data-mineru-settings-close]");
    const mediaUploadsEl = document.querySelector("[data-chat-media-uploads]");
    const toolCapabilityEl = document.querySelector("[data-chat-tool-capability]");
    const toolCapabilityTooltip = document.querySelector("[data-chat-tool-tooltip]");
    const toolCapabilityControl = document.querySelector(
        "[data-chat-tool-capability-control]"
    );
    const toolScopeToggle = document.querySelector("[data-chat-tool-scope-toggle]");
    const toolScopeAccordion = document.querySelector(
        "[data-chat-tool-scope-accordion]"
    );
    const toolSubserviceDropdown = document.querySelector(
        "[data-chat-tool-subservice-dropdown]"
    );
    const toolGlobalSettingsModal = document.querySelector(
        "[data-tool-global-settings-modal]"
    );
    const toolGlobalSwitch = document.querySelector("[data-tool-global-switch]");
    const toolAutomaticScopeSwitch = document.querySelector(
        "[data-tool-automatic-scope-switch]"
    );
    const toolMaxRoundsInput = document.querySelector("[data-tool-max-rounds]");
    const toolMaxTotalCallsInput = document.querySelector(
        "[data-tool-max-total-calls]"
    );
    const toolMaxFailuresInput = document.querySelector(
        "[data-tool-max-failures]"
    );
    const toolMaxResultCharsInput = document.querySelector(
        "[data-tool-max-result-chars]"
    );
    const toolUsePolicySelect = document.querySelector("[data-tool-use-policy]");
    const toolGuidanceSwitch = document.querySelector(
        "[data-tool-guidance-switch]"
    );
    const toolGuidanceTemplate = document.querySelector(
        "[data-tool-guidance-template]"
    );
    const toolWebpagePreviewSwitch = document.querySelector(
        "[data-tool-webpage-preview-switch]"
    );
    const toolWebpagePreviewTimeoutInput = document.querySelector(
        "[data-tool-webpage-preview-timeout]"
    );
    const toolGlobalSaveBtn = document.querySelector(
        "[data-tool-global-settings-save]"
    );
    const toolGlobalCloseBtns = document.querySelectorAll(
        "[data-tool-global-settings-close]"
    );
    const mcpSettingsModal = document.querySelector("[data-mcp-settings-modal]");
    const mcpServiceList = document.querySelector("[data-mcp-service-list]");
    const mcpSettingsSaveBtn = document.querySelector("[data-mcp-settings-save]");
    const mcpToolsRefreshBtn = document.querySelector("[data-mcp-tools-refresh]");
    const mcpStatusCheckBtn = document.querySelector("[data-mcp-status-check]");
    const mcpSettingsCloseBtns = document.querySelectorAll("[data-mcp-settings-close]");
    const attachmentsEl = document.querySelector("[data-chat-attachments]");
    const audioAttachmentsEl = document.querySelector("[data-chat-audio-attachments]");
    const saveOriginalSwitch = document.querySelector("[data-chat-save-original]");
    const attachAudioSwitch = document.querySelector("[data-chat-attach-audio]");
    const streamResponsesSwitch = document.querySelector("[data-chat-stream-responses]");
    const fpsControl = document.querySelector("[data-chat-video-fps-control]");
    const fpsSlider = document.querySelector("[data-chat-video-fps]");
    const fpsValue = document.querySelector("[data-chat-video-fps-value]");
    const modelNctxEl = document.querySelector("[data-chat-model-nctx]");
    const attachmentSettings = window.CairnmarkChatAttachmentSettings || {};
    if (streamResponsesSwitch && typeof attachmentSettings.stream_responses === "boolean") {
        streamResponsesSwitch.setAttribute(
            "aria-checked",
            attachmentSettings.stream_responses ? "true" : "false"
        );
    }
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
    let mineruTimeout = Number(window.CairnmarkMineruSettings?.timeout) || 3;
    let autoCompactThreshold = Number(
        window.CairnmarkChatCompactSettings?.threshold
    ) || 75;
    let reverseImageSource = "";
    let reverseImageIsExternal = false;
    const chatLocalFiles = new Map();
    let chatFileImageHover = null;

    const categoryForFilename = (filename) => {
        const name = String(filename || "");
        if (/\.(?:avif|bmp|gif|jpe?g|png|svg|tiff?|webp)$/i.test(name)) {
            return "image";
        }
        if (/\.(?:aac|flac|m4a|mp3|ogg|opus|wav)$/i.test(name)) {
            return "audio";
        }
        if (/\.(?:avi|m4v|mkv|mov|mp4|webm)$/i.test(name)) {
            return "video";
        }
        return "document";
    };

    const localFileKey = (item) => (
        `${String(item?.kind || "preview")}::${String(item?.filename || "")}`
    );

    const localFileHref = (item) => {
        if (item.kind === "external") return item.filename;
        const encoded = String(item.filename || "")
            .split("/")
            .map(encodeURIComponent)
            .join("/");
        if (item.kind === "generated") {
            return `/chat/generated_document/${encoded}`;
        }
        return `/chat/preview/${encoded}?download=1`;
    };

    const localFilePreviewHref = (item) => {
        const encoded = String(item.filename || "")
            .split("/")
            .map(encodeURIComponent)
            .join("/");
        if (item.kind === "generated") {
            return `/chat/generated_document/${encoded}?preview=1`;
        }
        return `/chat/preview/${encoded}`;
    };

    const hideChatFileImageHover = () => {
        if (chatFileImageHover) chatFileImageHover.hidden = true;
    };

    let generatedDocumentHover = null;
    let generatedDocumentHoverTimer = null;
    const generatedDocumentPreviewRequests = new Map();
    const generatedDocumentPreviewPattern = /\.(?:csv|docx|json|md|odt|pdf|txt)$/i;

    const generatedDocumentPreviewUrl = (name) => {
        const encoded = String(name || "")
            .split("/")
            .map(encodeURIComponent)
            .join("/");
        return `/chat/generated_document_preview/${encoded}`;
    };

    const ensureGeneratedDocumentHover = () => {
        if (generatedDocumentHover) return generatedDocumentHover;
        const preview = document.createElement("div");
        preview.className = "chat-generated-document-hover";
        preview.hidden = true;
        const status = document.createElement("span");
        status.className = "chat-generated-document-hover-status";
        status.textContent = "Preparing preview…";
        const frame = document.createElement("iframe");
        frame.className = "chat-generated-document-hover-frame";
        frame.title = "Document preview";
        frame.hidden = true;
        preview.append(status, frame);
        preview.addEventListener("mouseenter", () => {
            if (generatedDocumentHoverTimer !== null) {
                window.clearTimeout(generatedDocumentHoverTimer);
                generatedDocumentHoverTimer = null;
            }
        });
        preview.addEventListener("mouseleave", () => {
            generatedDocumentHoverTimer = window.setTimeout(() => {
                preview.hidden = true;
            }, 180);
        });
        document.body.appendChild(preview);
        generatedDocumentHover = preview;
        return preview;
    };

    const positionGeneratedDocumentHover = (preview, anchor) => {
        const anchorRect = anchor.getBoundingClientRect();
        const previewRect = preview.getBoundingClientRect();
        const margin = 12;
        const gap = 8;
        let left = anchorRect.right + gap;
        if (left + previewRect.width > window.innerWidth - margin) {
            left = anchorRect.left - previewRect.width - gap;
        }
        left = Math.max(
            margin,
            Math.min(left, window.innerWidth - previewRect.width - margin)
        );
        const top = Math.max(
            margin,
            Math.min(anchorRect.top, window.innerHeight - previewRect.height - margin)
        );
        preview.style.left = `${Math.round(left)}px`;
        preview.style.top = `${Math.round(top)}px`;
    };

    const showGeneratedDocumentHover = async (link, name) => {
        if (!generatedDocumentPreviewPattern.test(name)) return;
        if (generatedDocumentHoverTimer !== null) {
            window.clearTimeout(generatedDocumentHoverTimer);
            generatedDocumentHoverTimer = null;
        }
        const preview = ensureGeneratedDocumentHover();
        const status = preview.querySelector(".chat-generated-document-hover-status");
        const frame = preview.querySelector(".chat-generated-document-hover-frame");
        const previewUrl = generatedDocumentPreviewUrl(name);
        preview.dataset.previewUrl = previewUrl;
        status.textContent = "Preparing preview…";
        status.hidden = false;
        frame.hidden = true;
        preview.hidden = false;
        window.requestAnimationFrame(() => positionGeneratedDocumentHover(preview, link));

        let request = generatedDocumentPreviewRequests.get(previewUrl);
        if (!request) {
            request = fetch(previewUrl, { method: "HEAD", cache: "no-store" })
                .then((response) => {
                    const contentType = response.headers.get("Content-Type") || "";
                    const supportedType = contentType.includes("application/pdf")
                        || contentType.includes("text/html");
                    if (!response.ok || !supportedType) {
                        throw new Error("Document preview is unavailable.");
                    }
                    return true;
                })
                .catch((error) => {
                    generatedDocumentPreviewRequests.delete(previewUrl);
                    throw error;
                });
            generatedDocumentPreviewRequests.set(previewUrl, request);
        }
        try {
            await request;
        } catch (error) {
            if (preview.dataset.previewUrl === previewUrl) preview.hidden = true;
            return;
        }
        if (preview.hidden || preview.dataset.previewUrl !== previewUrl) return;
        if (frame.src !== new URL(previewUrl, window.location.href).href) {
            frame.src = previewUrl;
        }
        status.hidden = true;
        frame.hidden = false;
        window.requestAnimationFrame(() => positionGeneratedDocumentHover(preview, link));
    };

    const hideGeneratedDocumentHover = (immediate = false) => {
        if (!generatedDocumentHover) return;
        if (generatedDocumentHoverTimer !== null) {
            window.clearTimeout(generatedDocumentHoverTimer);
        }
        if (immediate) {
            generatedDocumentHover.hidden = true;
            generatedDocumentHoverTimer = null;
            return;
        }
        generatedDocumentHoverTimer = window.setTimeout(() => {
            generatedDocumentHover.hidden = true;
        }, 180);
    };

    const bindGeneratedDocumentPreview = (link, name) => {
        if (!link || link.dataset.documentPreviewBound === "true") return;
        link.dataset.documentPreviewBound = "true";
        if (!generatedDocumentPreviewPattern.test(name)) return;
        link.addEventListener("mouseenter", () => {
            void showGeneratedDocumentHover(link, name);
        });
        link.addEventListener("mouseleave", () => hideGeneratedDocumentHover());
        link.addEventListener("focus", () => {
            void showGeneratedDocumentHover(link, name);
        });
        link.addEventListener("blur", () => hideGeneratedDocumentHover());
    };

    const showChatFileImageHover = (item, anchor) => {
        if (!chatFileImageHover) {
            chatFileImageHover = document.createElement("div");
            chatFileImageHover.className = "chat-file-image-hover";
            const image = document.createElement("img");
            image.alt = "Attachment preview";
            chatFileImageHover.appendChild(image);
            document.body.appendChild(chatFileImageHover);
        }
        const image = chatFileImageHover.querySelector("img");
        image.src = localFilePreviewHref(item);
        chatFileImageHover.hidden = false;
        const position = () => {
            const anchorRect = anchor.getBoundingClientRect();
            const previewRect = chatFileImageHover.getBoundingClientRect();
            const margin = 12;
            const fitsRight = anchorRect.right + margin + previewRect.width
                <= window.innerWidth;
            const left = fitsRight
                ? anchorRect.right + margin
                : Math.max(margin, anchorRect.left - previewRect.width - margin);
            const top = Math.max(
                margin,
                Math.min(anchorRect.top, window.innerHeight - previewRect.height - margin)
            );
            chatFileImageHover.style.left = `${Math.round(left)}px`;
            chatFileImageHover.style.top = `${Math.round(top)}px`;
        };
        image.onload = position;
        window.requestAnimationFrame(position);
    };

    const appendChatFileSection = (label, items) => {
        if (items.length === 0) return;
        const heading = document.createElement("div");
        heading.className = "chat-file-section-heading";
        heading.textContent = label;
        chatFileList.appendChild(heading);
        items.forEach((item) => {
            const row = document.createElement(item.exists ? "a" : "div");
            row.className = "chat-file-item";
            if (item.category === "image") {
                row.classList.add("chat-file-item--image");
            }
            if (item.exists) {
                row.href = localFileHref(item);
                if (item.kind === "external") {
                    row.target = "_blank";
                    row.rel = "noopener noreferrer";
                } else {
                    row.download = item.name
                        || String(item.filename).split("/").pop();
                }
                if (item.kind === "generated" && item.category === "document") {
                    row.dataset.generatedDocumentName = item.filename;
                    bindGeneratedDocumentPreview(row, item.filename);
                }
            } else {
                row.classList.add("chat-file-item--missing");
            }
            const name = document.createElement("span");
            name.className = "chat-file-name";
            name.textContent = item.name || item.filename;
            const status = document.createElement("span");
            if (item.exists) {
                status.className = "chat-file-download";
                status.setAttribute("aria-hidden", "true");
                status.textContent = item.kind === "external" ? "↗" : "⇩";
            } else {
                status.className = "chat-file-missing";
                status.textContent = "Missing";
            }
            row.append(name, status);
            if (item.exists && item.category === "image") {
                row.addEventListener("mouseenter", () => {
                    showChatFileImageHover(item, row);
                });
                row.addEventListener("mouseleave", hideChatFileImageHover);
                row.addEventListener("focus", () => {
                    showChatFileImageHover(item, row);
                });
                row.addEventListener("blur", hideChatFileImageHover);
            }
            chatFileList.appendChild(row);
        });
    };

    const renderChatLocalFiles = () => {
        if (!chatFileAccordion || !chatFileList || !chatFileCount) return;
        hideChatFileImageHover();
        hideGeneratedDocumentHover(true);
        chatFileList.replaceChildren();
        const files = [...chatLocalFiles.values()];
        appendChatFileSection(
            "Images",
            files.filter((item) => item.category === "image")
        );
        appendChatFileSection(
            "Audios",
            files.filter((item) => item.category === "audio")
        );
        appendChatFileSection(
            "Videos",
            files.filter((item) => item.category === "video")
        );
        appendChatFileSection(
            "Documents",
            files.filter((item) => item.category === "document")
        );
        appendChatFileSection(
            "External links",
            files.filter((item) => item.category === "external")
        );
        chatFileCount.textContent = String(chatLocalFiles.size);
        chatFileAccordion.hidden = chatLocalFiles.size === 0;
        if (chatLocalFiles.size === 0) chatFileAccordion.open = false;
    };

    const addChatLocalFiles = (items, render = true) => {
        (Array.isArray(items) ? items : []).forEach((item) => {
            const filename = String(item?.filename || "").trim();
            const kind = ["generated", "external"].includes(item?.kind)
                ? item.kind
                : "preview";
            if (!filename) return;
            const suppliedCategory = String(item?.category || "");
            const category = [
                "image", "audio", "video", "document", "external",
            ].includes(
                suppliedCategory
            )
                ? suppliedCategory
                : categoryForFilename(item?.name || filename);
            const normalized = {
                kind,
                filename,
                name: String(item?.name || filename.split("/").pop()),
                exists: item?.exists !== false,
                category,
            };
            chatLocalFiles.set(localFileKey(normalized), normalized);
        });
        if (render) renderChatLocalFiles();
    };

    const replaceChatLocalFiles = (items) => {
        chatLocalFiles.clear();
        addChatLocalFiles(items, false);
        renderChatLocalFiles();
    };

    replaceChatLocalFiles(window.CairnmarkChatLocalAttachments || []);
    chatFileList?.addEventListener("scroll", hideChatFileImageHover);
    chatFileAccordion?.addEventListener("toggle", () => {
        if (!chatFileAccordion.open) hideChatFileImageHover();
    });
    const mcpConfigUrl = window.CairnmarkMcpConfigUrl || "/chat/mcp_configuration";
    const mcpImportUrl = window.CairnmarkMcpImportUrl
        || "/chat/mcp_configuration/import_opencode";
    const mcpServerSaveUrl = window.CairnmarkMcpServerSaveUrl
        || "/chat/mcp_configuration/server";
    const mcpSettingsUrl = window.CairnmarkMcpSettingsUrl || "/chat/mcp_settings";
    const mcpSettingsSaveUrl = window.CairnmarkMcpSettingsSaveUrl
        || "/chat/mcp_settings/save";
    const mcpGlobalStateUrl = window.CairnmarkMcpGlobalStateUrl
        || "/chat/mcp_global_state";
    const mcpToolsRefreshUrl = window.CairnmarkMcpToolsRefreshUrl
        || "/chat/mcp_tools/refresh";
    const mcpEndpointTestUrl = window.CairnmarkMcpEndpointTestUrl
        || "/chat/mcp_endpoint_test";
    const llamaManagedToolsUrl = window.CairnmarkLlamaManagedToolsUrl
        || "/chat/llama_managed_tools";
    const llamaManagedMcpStatusUrl = window.CairnmarkLlamaManagedMcpStatusUrl
        || "/chat/llama_managed_mcp_status";
    const toolSetupUrlTemplate = window.CairnmarkToolSetupUrlTemplate
        || "/static/tool-setup-__SERVICE__.json";
    const savedMcpStates = new Map();
    const savedMcpToolSettings = new Map();
    const savedMcpSecretFields = new Set();
    const savedCustomToolStates = new Map();
    const cachedCustomTools = new Map();
    const mcpSetupDefinitions = new Map();
    const savedLlamaToolStates = new Map();
    const savedLlamaServiceStates = new Map();
    const savedLlamaServiceSettings = new Map();
    const knownLlamaTools = new Map();
    const knownLlamaToolsStorageKey = "cairnmark:llama-managed-tools";
    try {
        const cachedTools = JSON.parse(
            window.localStorage.getItem(knownLlamaToolsStorageKey) || "[]"
        );
        if (Array.isArray(cachedTools)) {
            cachedTools.forEach((tool) => {
                const definition = tool?.definition?.function;
                const toolName = String(tool?.tool || definition?.name || "").trim();
                if (toolName) knownLlamaTools.set(toolName, tool);
            });
        }
    } catch (error) {
        // Discovery still works when browser storage is unavailable or invalid.
    }
    let mcpSettingsSequence = 0;
    let mcpDefaultTimeoutMs = 10000;
    let toolCapabilityBaseLabel = "";
    let globalToolsEnabled = null;
    let enabledMcpServiceNames = [];
    let enabledMcpSubservices = {};
    const mcpServiceAvailability = new Map();
    const managedMcpServiceNames = new Set();
    const toolSubserviceUiStates = new Map();
    let globalToolSettings = {
        max_rounds: 6,
        max_total_calls: 12,
        max_consecutive_failures: 2,
        max_result_chars: 20000,
        tool_policy: "automatic",
        automatic_tool_scope: false,
        guidance_enabled: true,
        guidance_template: "",
        capture_webpage_preview: true,
        webpage_preview_timeout: 2,
    };
    let globalToolSettingsLoaded = false;
    let pendingDocumentPicker = false;
    const pendingAttachments = [];
    const renderMarkdown = window.CairnmarkMarkdown.render;
    const chatMedia = window.CairnmarkChatMedia;
    const parameterHelpUrl = window.CairnmarkParameterHelpUrl || "/static/parameters.json";
    let parameterHelp = {};
    const mcpToolHelpUrl = window.CairnmarkMcpToolHelpUrl || "/static/mcp-tools.json";
    let mcpToolHelp = {};

    const applyParameterHelp = (root = document) => {
        root.querySelectorAll("[data-parameter-help-key]").forEach((button) => {
            const key = button.getAttribute("data-parameter-help-key");
            const help = parameterHelp[key];
            if (typeof help !== "string" || !help.trim()) return;
            const tooltip = button.querySelector(".chat-info-tooltip");
            if (tooltip) tooltip.textContent = help;
            const label = button.closest(".chat-parameter-label, .more-params-label")
                ?.querySelector("label")?.textContent?.trim() || labelForParam(key);
            button.setAttribute("aria-label", `${label} help: ${help}`);
        });
    };

    const loadParameterHelp = async () => {
        try {
            const response = await fetch(parameterHelpUrl, {
                cache: "no-store",
                headers: { Accept: "application/json" },
            });
            if (!response.ok) throw new Error("Parameter help could not be loaded.");
            const payload = await response.json();
            if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
                throw new Error("Parameter help is invalid.");
            }
            parameterHelp = Object.fromEntries(
                Object.entries(payload).filter(
                    ([key, value]) => key && typeof value === "string" && value.trim()
                )
            );
            applyParameterHelp();
        } catch (error) {
            // Keep server-rendered help and modal fallbacks when the local file is unavailable.
        }
        return parameterHelp;
    };

    const loadMcpToolHelp = async () => {
        try {
            const response = await fetch(mcpToolHelpUrl, {
                cache: "no-store",
                headers: { Accept: "application/json" },
            });
            if (!response.ok) throw new Error("MCP tool help could not be loaded.");
            const payload = await response.json();
            if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
                throw new Error("MCP tool help is invalid.");
            }
            mcpToolHelp = Object.fromEntries(
                Object.entries(payload).filter(
                    ([key, value]) => key && typeof value === "string" && value.trim()
                )
            );
        } catch (error) {
            mcpToolHelp = {};
        }
        return mcpToolHelp;
    };

    const createMcpName = (name, displayName = name) => {
        const wrapper = document.createElement("span");
        wrapper.className = "mcp-name-with-help";
        const label = document.createElement("strong");
        label.textContent = displayName;
        if (displayName !== name) wrapper.title = name;
        wrapper.appendChild(label);
        const help = mcpToolHelp[name];
        if (typeof help !== "string" || !help.trim()) return wrapper;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "mcp-name-info";
        button.setAttribute("aria-label", `${name} help: ${help}`);
        button.textContent = "i";
        const tooltip = document.createElement("span");
        tooltip.className = "mcp-name-info-tooltip";
        tooltip.setAttribute("role", "tooltip");
        tooltip.textContent = help;
        button.appendChild(tooltip);
        wrapper.appendChild(button);
        return wrapper;
    };

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
    document.addEventListener("cairnmark:navigation-before", () => {
        window.removeEventListener("scroll", hideHoverPreview, true);
    }, { once: true });

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
        historyEl.addEventListener("click", (event) => {
            const button = event.target.closest("[data-reverse-image-src]");
            if (!button || !reverseImageModal || !reverseImagePreview) return;
            reverseImageSource = button.dataset.reverseImageSrc || "";
            if (!reverseImageSource) return;
            try {
                const sourceUrl = new URL(reverseImageSource, window.location.href);
                reverseImageIsExternal = ["http:", "https:"].includes(sourceUrl.protocol)
                    && sourceUrl.origin !== window.location.origin;
            } catch (error) {
                reverseImageIsExternal = false;
            }
            if (reverseImageDescription) {
                reverseImageDescription.textContent = reverseImageIsExternal
                    ? "Choose a provider. CairnMark sends the public image URL directly to the selected reverse-image service."
                    : "Choose a provider. CairnMark opens the provider's official upload page in a new tab.";
            }
            if (reverseImageHint) {
                reverseImageHint.textContent = reverseImageIsExternal
                    ? "The selected provider receives the external image URL when its search page opens."
                    : "The image is not sent automatically. Uploading it on the opened page shares it with that third party.";
            }
            hideHoverPreview();
            reverseImagePreview.src = reverseImageSource;
            reverseImageModal.hidden = false;
        });
    }

    const closeReverseImageModal = () => {
        if (reverseImageModal) reverseImageModal.hidden = true;
        if (reverseImagePreview) reverseImagePreview.removeAttribute("src");
        reverseImageSource = "";
        reverseImageIsExternal = false;
    };

    const openReverseImageProvider = (button) => {
        const providerUrl = button.dataset.providerUrl || "";
        if (!reverseImageSource || !providerUrl) return;

        const providerUrlTemplate = button.dataset.providerUrlTemplate || "";
        const targetUrl = reverseImageIsExternal && providerUrlTemplate
            ? providerUrlTemplate.replace("{url}", encodeURIComponent(reverseImageSource))
            : providerUrl;

        const providerTab = window.open("about:blank", "_blank");
        if (!providerTab) {
            window.alert("The provider page was blocked. Allow pop-ups and try again.");
            return;
        }
        providerTab.opener = null;
        providerTab.location.replace(targetUrl);
        closeReverseImageModal();
    };

    const createUserImagePreview = (source) => {
        const frame = document.createElement("span");
        frame.className = "chat-user-preview-frame";
        const img = document.createElement("img");
        img.className = "chat-user-preview";
        img.alt = "Attached image preview";
        img.src = String(source).startsWith("data:")
            ? source
            : `/chat/preview/${encodeURIComponent(source)}`;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "chat-reverse-image-button";
        button.dataset.reverseImageSrc = img.src;
        button.title = "Reverse image search";
        button.setAttribute("aria-label", "Reverse image search");
        button.textContent = "⌕";
        img.addEventListener("error", () => {
            hideHoverPreview();
            frame.classList.add("is-broken");
            const broken = document.createElement("span");
            broken.className = "chat-user-preview--broken";
            broken.textContent = "🔗";
            broken.title = "Preview image missing";
            img.replaceWith(broken);
        });
        frame.append(img, button);
        return frame;
    };

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

    const externalImageDownloadUrl = "/chat/external_image_download";
    const externalImageInspectUrl = "/chat/external_image_inspect";
    const externalImageTimeoutMs = 1000;
    const externalImageInspections = new Map();

    const externalImageFilename = (url) => {
        try {
            const filename = decodeURIComponent(new URL(url).pathname.split("/").pop() || "");
            return filename.replace(/[^A-Za-z0-9._-]+/g, "_") || "external-image";
        } catch (error) {
            return "external-image";
        }
    };

    const downloadExternalImage = async (url, button, suggestedName = "") => {
        let parsedUrl = null;
        try {
            parsedUrl = new URL(url, window.location.origin);
        } catch (error) {
            parsedUrl = null;
        }
        const isLocalPreview = Boolean(
            parsedUrl
            && parsedUrl.origin === window.location.origin
            && parsedUrl.pathname.startsWith("/chat/preview/")
        );
        const endpoint = isLocalPreview
            ? `${parsedUrl.pathname}?download=1`
            : `${externalImageDownloadUrl}?url=${encodeURIComponent(url)}`;
        const filename = suggestedName || externalImageFilename(url);
        button.disabled = true;
        try {
            if (typeof window.showSaveFilePicker === "function") {
                const fileHandle = await window.showSaveFilePicker({
                    suggestedName: filename,
                });
                const response = await fetch(endpoint, { cache: "no-store" });
                if (!response.ok) {
                    const payload = await response.json().catch(() => ({}));
                    throw new Error(payload.error || "Image download failed.");
                }
                const writable = await fileHandle.createWritable();
                await writable.write(await response.blob());
                await writable.close();
                return;
            }
            const link = document.createElement("a");
            link.href = endpoint;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (error) {
            if (error?.name !== "AbortError") {
                window.alert(`Image download failed: ${error}`);
            }
        } finally {
            button.disabled = false;
        }
    };

    let externalImageHover = null;
    let externalImageHoverTimer = null;

    const ensureExternalImageHover = () => {
        if (externalImageHover) return externalImageHover;
        const overlay = document.createElement("div");
        overlay.className = "chat-image-hover-preview";
        overlay.hidden = true;
        overlay.innerHTML = `
            <a class="chat-image-hover-link" target="_blank" rel="noopener noreferrer">
                <img class="chat-image-hover-image" alt="Large external image preview">
            </a>
            <button class="chat-image-hover-download" type="button" title="Download image" aria-label="Download image">⇩</button>
        `;
        const cancelHide = () => {
            if (externalImageHoverTimer !== null) {
                window.clearTimeout(externalImageHoverTimer);
                externalImageHoverTimer = null;
            }
        };
        overlay.addEventListener("mouseenter", cancelHide);
        overlay.addEventListener("mouseleave", () => {
            externalImageHoverTimer = window.setTimeout(() => {
                overlay.hidden = true;
            }, 160);
        });
        overlay.querySelector(".chat-image-hover-download")
            .addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const button = event.currentTarget;
                downloadExternalImage(
                    overlay.dataset.imageUrl || "",
                    button,
                    overlay.dataset.imageFilename || ""
                );
            });
        document.body.appendChild(overlay);
        externalImageHover = overlay;
        return overlay;
    };

    const hideExternalImageHover = () => {
        if (!externalImageHover) return;
        if (externalImageHoverTimer !== null) {
            window.clearTimeout(externalImageHoverTimer);
        }
        externalImageHoverTimer = window.setTimeout(() => {
            externalImageHover.hidden = true;
        }, 160);
    };

    const positionExternalImageHover = (overlay, target) => {
        const targetRect = target.getBoundingClientRect();
        const overlayRect = overlay.getBoundingClientRect();
        const margin = 12;
        const gap = 8;
        let left = targetRect.right + gap;
        if (left + overlayRect.width > window.innerWidth - margin) {
            left = targetRect.left - overlayRect.width - gap;
        }
        left = Math.max(
            margin,
            Math.min(left, window.innerWidth - overlayRect.width - margin)
        );
        const top = Math.max(
            margin,
            Math.min(targetRect.top, window.innerHeight - overlayRect.height - margin)
        );
        overlay.style.left = `${Math.round(left)}px`;
        overlay.style.top = `${Math.round(top)}px`;
        overlay.style.visibility = "visible";
    };

    const showExternalImageHover = (preview, image, url) => {
        if (!preview.classList.contains("is-available") || !image.src) return;
        const overlay = ensureExternalImageHover();
        if (externalImageHoverTimer !== null) {
            window.clearTimeout(externalImageHoverTimer);
            externalImageHoverTimer = null;
        }
        const hoverImage = overlay.querySelector(".chat-image-hover-image");
        const hoverLink = overlay.querySelector(".chat-image-hover-link");
        overlay.dataset.imageUrl = url;
        overlay.dataset.imageFilename = preview.dataset.imageFilename || "";
        hoverLink.href = url;
        hoverImage.src = image.src;
        overlay.style.visibility = "hidden";
        overlay.hidden = false;
        window.requestAnimationFrame(() => positionExternalImageHover(overlay, image));
    };

    const hydrateAssistantImages = (root) => {
        root.querySelectorAll("[data-chat-image-preview]:not([data-image-bound])")
            .forEach((preview) => {
                preview.setAttribute("data-image-bound", "true");
                const url = preview.getAttribute("data-image-url") || "";
                const image = preview.querySelector(".chat-markdown-image");
                const download = preview.querySelector(".chat-markdown-image-download");
                const filename = preview.dataset.imageFilename || "";
                if (!url || !image || !download) return;

                let finished = false;
                let proxyStarted = false;
                const probe = new Image();
                const finish = (available, source = url) => {
                    if (finished) return;
                    window.clearTimeout(timeout);
                    if (!available) return;
                    finished = true;
                    image.src = source;
                    preview.classList.add("is-available");
                };
                const tryProxyPreview = () => {
                    if (finished || proxyStarted) return;
                    proxyStarted = true;
                    window.clearTimeout(timeout);
                    const proxyUrl = `${externalImageDownloadUrl}?preview=1&url=${
                        encodeURIComponent(url)
                    }`;
                    image.addEventListener("load", () => {
                        finish(
                            image.naturalWidth > 0 && image.naturalHeight > 0,
                            proxyUrl
                        );
                    }, { once: true });
                    image.src = proxyUrl;
                };
                const timeout = window.setTimeout(
                    tryProxyPreview,
                    externalImageTimeoutMs
                );
                probe.addEventListener(
                    "load",
                    () => finish(probe.naturalWidth > 0 && probe.naturalHeight > 0),
                    { once: true }
                );
                probe.addEventListener("error", tryProxyPreview, { once: true });
                image.addEventListener("error", () => {
                    image.removeAttribute("src");
                    preview.classList.remove("is-available");
                    hideExternalImageHover();
                });
                image.addEventListener("mouseenter", () => {
                    showExternalImageHover(preview, image, url);
                });
                image.addEventListener("mouseleave", hideExternalImageHover);
                image.closest("a")?.addEventListener("focus", () => {
                    showExternalImageHover(preview, image, url);
                });
                image.closest("a")?.addEventListener("blur", hideExternalImageHover);
                download.addEventListener("click", (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    downloadExternalImage(url, download, filename);
                });
                probe.src = url;
            });
    };

    const createExternalImagePreview = (url, filename) => {
        const preview = document.createElement("span");
        preview.className = "chat-markdown-image-preview";
        preview.dataset.chatImagePreview = "";
        preview.dataset.imageUrl = url;
        preview.dataset.imageFilename = filename || "";

        const fallback = document.createElement("a");
        fallback.className = "chat-markdown-image-fallback";
        fallback.href = url;
        fallback.target = "_blank";
        fallback.rel = "noopener noreferrer";
        fallback.textContent = url;

        const imageLink = document.createElement("a");
        imageLink.className = "chat-markdown-image-link";
        imageLink.href = url;
        imageLink.target = "_blank";
        imageLink.rel = "noopener noreferrer";
        const image = document.createElement("img");
        image.className = "chat-markdown-image";
        image.alt = "External image preview";
        imageLink.appendChild(image);

        const reverse = document.createElement("button");
        reverse.className = "chat-markdown-image-reverse";
        reverse.type = "button";
        reverse.dataset.reverseImageSrc = url;
        reverse.title = "Reverse image search";
        reverse.setAttribute("aria-label", "Reverse image search");
        reverse.textContent = "⌕";

        const download = document.createElement("button");
        download.className = "chat-markdown-image-download";
        download.type = "button";
        download.title = "Download image";
        download.setAttribute("aria-label", "Download image");
        download.textContent = "⇩";

        preview.append(fallback, imageLink, reverse, download);
        return preview;
    };

    const inspectExternalImage = (url) => {
        if (!externalImageInspections.has(url)) {
            const endpoint = `${externalImageInspectUrl}?url=${encodeURIComponent(url)}`;
            externalImageInspections.set(
                url,
                fetch(endpoint, { cache: "no-store" })
                    .then((response) => response.ok ? response.json() : null)
                    .catch(() => null)
            );
        }
        return externalImageInspections.get(url);
    };

    const hydrateOpaqueAssistantImages = (root) => {
        root.querySelectorAll(
            "[data-external-image-candidate]:not([data-image-inspected])"
        ).forEach((link) => {
            link.dataset.imageInspected = "true";
            const url = link.dataset.externalImageCandidate || "";
            if (!url) return;
            inspectExternalImage(url).then((result) => {
                if (!result?.is_image || !link.isConnected) return;
                link.replaceWith(createExternalImagePreview(url, result.filename));
                hydrateAssistantImages(root);
            });
        });
    };

    const hydrateAssistantAudio = (root) => {
        root.querySelectorAll("[data-chat-audio-preview]:not([data-audio-bound])")
            .forEach((preview) => {
                preview.setAttribute("data-audio-bound", "true");
                const url = preview.getAttribute("data-audio-url") || "";
                const mount = preview.querySelector("[data-chat-audio-player]");
                if (!url || !mount || !chatMedia?.createAudio) return;

                let label = "Audio stream";
                try {
                    label = new URL(url).hostname || label;
                } catch (error) {
                    // The Markdown renderer already validates the URL.
                }
                const player = chatMedia.createAudio(
                    url,
                    label,
                    true,
                    { preload: "none" }
                );
                player.classList.add("chat-audio-player--external");
                const audio = player.querySelector("audio");
                audio?.addEventListener("error", () => {
                    player.classList.add("is-unavailable");
                    const name = player.querySelector(".chat-attachment-name");
                    if (name) {
                        name.textContent = "Stream unavailable";
                        name.title = "Open the original stream URL instead";
                    }
                });
                mount.appendChild(player);
            });
    };

    let webpagePreviewHover = null;

    const ensureWebpagePreviewHover = () => {
        if (webpagePreviewHover) return webpagePreviewHover;
        const preview = document.createElement("div");
        preview.className = "chat-webpage-hover-preview";
        preview.hidden = true;
        const image = document.createElement("img");
        image.alt = "Webpage screenshot preview";
        preview.appendChild(image);
        document.body.appendChild(preview);
        webpagePreviewHover = preview;
        return preview;
    };

    const positionWebpagePreview = (preview, link) => {
        const linkRect = link.getBoundingClientRect();
        const previewRect = preview.getBoundingClientRect();
        const margin = 12;
        const gap = 8;
        let left = linkRect.right + gap;
        if (left + previewRect.width > window.innerWidth - margin) {
            left = linkRect.left - previewRect.width - gap;
        }
        left = Math.max(
            margin,
            Math.min(left, window.innerWidth - previewRect.width - margin)
        );
        const top = Math.max(
            margin,
            Math.min(linkRect.top, window.innerHeight - previewRect.height - margin)
        );
        preview.style.left = `${Math.round(left)}px`;
        preview.style.top = `${Math.round(top)}px`;
        preview.style.visibility = "visible";
    };

    const showWebpagePreview = (link, record) => {
        const preview = ensureWebpagePreviewHover();
        const image = preview.querySelector("img");
        image.src = `/chat/preview/${encodeURIComponent(record.filename)}`;
        preview.style.visibility = "hidden";
        preview.hidden = false;
        image.onload = () => positionWebpagePreview(preview, link);
        window.requestAnimationFrame(() => positionWebpagePreview(preview, link));
    };

    const hideWebpagePreview = () => {
        if (webpagePreviewHover) webpagePreviewHover.hidden = true;
    };

    const bindWebpagePreviews = (root, records) => {
        const byUrl = new Map(
            (records || [])
                .filter((record) => record?.url && record?.filename)
                .map((record) => [record.url, record])
        );
        root.querySelectorAll("[data-webpage-preview-url]").forEach((link) => {
            const record = byUrl.get(link.dataset.webpagePreviewUrl || "");
            if (!record || link.dataset.webpagePreviewBound === record.id) return;
            link.dataset.webpagePreviewBound = record.id;
            link.addEventListener("mouseenter", () => showWebpagePreview(link, record));
            link.addEventListener("mouseleave", hideWebpagePreview);
            link.addEventListener("focus", () => showWebpagePreview(link, record));
            link.addEventListener("blur", hideWebpagePreview);
        });
    };

    const hydrateWebpagePreviews = (root) => {
        const message = root.closest(".chat-message--assistant");
        if (!message) return;
        let records = [];
        try {
            records = JSON.parse(message.dataset.webpagePreviews || "[]");
        } catch (error) {
            records = [];
        }
        bindWebpagePreviews(root, records);
        if (message.dataset.captureWebpagePreviews !== "true") return;
        if (!globalToolSettingsLoaded) return;
        if (globalToolSettings.capture_webpage_preview !== true) return;

        const urls = [...new Set(
            [...root.querySelectorAll("[data-webpage-preview-url]")]
                .map((link) => link.dataset.webpagePreviewUrl)
                .filter(Boolean)
        )];
        const messageId = Number(message.dataset.messageId);
        message.dataset.captureWebpagePreviews = "pending";
        if (!messageId || urls.length === 0) return;
        api.json("/chat/webpage_previews", {
            method: "POST",
            body: { message_id: messageId, urls },
        }).then((payload) => {
            if (!message.isConnected) return;
            const captured = Array.isArray(payload?.previews) ? payload.previews : [];
            message.dataset.webpagePreviews = JSON.stringify(captured);
            message.dataset.captureWebpagePreviews = "done";
            bindWebpagePreviews(root, captured);
            replaceChatLocalFiles(payload.attachments || []);
        }).catch(() => {
            // Screenshot failures intentionally leave ordinary links unchanged.
            message.dataset.captureWebpagePreviews = "done";
        });
    };

    const boundedTableColumnShares = (widths, maxTextLengths) => {
        const columnCount = widths.length;
        if (columnCount < 2) return widths.map(() => 100);
        const normalMinimum = 50 / columnCount;
        const shortTextMinimum = 25 / columnCount;
        const maximum = 200 / columnCount;
        const minimums = widths.map((_width, index) => (
            Number(maxTextLengths[index]) <= 4
                ? shortTextMinimum
                : normalMinimum
        ));
        const weights = widths.map((width) => Math.max(width, 1));
        const totalWeight = weights.reduce((total, weight) => total + weight, 0);
        const proportional = weights.map((weight) => 100 * weight / totalWeight);
        const widestIndex = weights.reduce(
            (widest, weight, index) => weight > weights[widest] ? index : widest,
            0
        );
        const usesShortTextRange = proportional.some((share, index) => (
            minimums[index] === shortTextMinimum && share < normalMinimum
        ));
        if (usesShortTextRange) {
            const specialShares = proportional.map((share, index) => Math.min(
                maximum,
                Math.max(minimums[index], share)
            ));
            const remainingForWidest = 100 - specialShares.reduce(
                (total, share, index) => (
                    index === widestIndex ? total : total + share
                ),
                0
            );
            if (remainingForWidest >= minimums[widestIndex]) {
                specialShares[widestIndex] = remainingForWidest;
                return specialShares;
            }
        }
        const shares = weights.map((weight, index) => Math.min(
            maximum,
            Math.max(minimums[index], 100 * weight / totalWeight)
        ));
        let difference = 100 - shares.reduce((total, share) => total + share, 0);
        while (Math.abs(difference) > 0.0001) {
            const increasing = difference > 0;
            const eligible = shares.map((_share, index) => index).filter(
                (index) => increasing
                    ? shares[index] < maximum
                    : shares[index] > minimums[index]
            );
            if (!eligible.length) break;
            const eligibleWeight = eligible.reduce(
                (total, index) => total + weights[index],
                0
            );
            let applied = 0;
            eligible.forEach((index) => {
                const requested = Math.abs(difference) * (
                    weights[index] / eligibleWeight
                );
                const capacity = increasing
                    ? maximum - shares[index]
                    : shares[index] - minimums[index];
                const adjustment = Math.min(requested, capacity);
                shares[index] += increasing ? adjustment : -adjustment;
                applied += adjustment;
            });
            if (applied <= 0.0001) break;
            difference += increasing ? -applied : applied;
        }
        return shares;
    };

    const balanceAssistantTables = (root) => {
        root.querySelectorAll(
            ".markdown-table-wrap table:not([data-balanced-columns])"
        ).forEach((table) => {
            const cells = Array.from(table.rows[0]?.cells || []);
            if (cells.length < 2) return;
            const widths = cells.map((cell) => cell.getBoundingClientRect().width);
            if (!widths.every((width) => width > 0)) return;
            const maxTextLengths = cells.map((_cell, columnIndex) => Math.max(
                ...Array.from(table.rows).map((row) => (
                    row.cells[columnIndex]?.textContent || ""
                ).trim().length)
            ));
            const colgroup = document.createElement("colgroup");
            boundedTableColumnShares(widths, maxTextLengths).forEach((share) => {
                const column = document.createElement("col");
                column.style.width = `${share.toFixed(4)}%`;
                colgroup.appendChild(column);
            });
            table.prepend(colgroup);
            table.dataset.balancedColumns = "true";
            table.classList.add("markdown-table-balanced");
        });
    };

    const hydrateAssistantMedia = (root) => {
        balanceAssistantTables(root);
        hydrateAssistantImages(root);
        hydrateOpaqueAssistantImages(root);
        hydrateAssistantAudio(root);
        hydrateWebpagePreviews(root);
    };

    const attachAssistantActions = (contentEl, raw) => {
        rawSource.set(contentEl, raw);
        contentEl.innerHTML = renderMarkdown(raw);
        hydrateAssistantMedia(contentEl);
        const message = contentEl.parentElement;
        if (!message || message.querySelector(".chat-message-actions")) return;

        const separator = document.createElement("hr");
        separator.className = "chat-message-actions-separator";
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
                hydrateAssistantMedia(contentEl);
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
        message.append(separator, actions);
    };

    const sqlTimestamp = (value) => {
        const raw = String(value || "").trim();
        const stored = raw.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})/);
        if (stored) return `${stored[1]} ${stored[2]}`;
        return new Date().toISOString().slice(0, 19).replace("T", " ");
    };

    const appendMessageTimestamp = (message, value) => {
        const timestamp = sqlTimestamp(value);
        const time = document.createElement("time");
        time.className = "chat-message-timestamp";
        time.dateTime = `${timestamp.replace(" ", "T")}Z`;
        time.textContent = timestamp;
        message.appendChild(time);
    };

    const createUseModelButton = (provider, model) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "chat-use-model-button";
        button.setAttribute("data-chat-use-model", "");
        button.setAttribute("data-provider", provider);
        button.setAttribute("data-model", model);
        button.setAttribute("aria-label", `Use this model: ${model}`);
        const arrow = document.createElement("span");
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "↥";
        const tooltip = document.createElement("span");
        tooltip.className = "chat-use-model-tooltip";
        tooltip.setAttribute("role", "tooltip");
        tooltip.textContent = "Use this model";
        button.append(arrow, tooltip);
        return button;
    };

    const appendMessage = (role, content, meta) => {
        if (!historyEl) return;
        const div = document.createElement("div");
        div.className = `chat-message chat-message--${role}`;
        if (meta && meta.compacted) {
            div.classList.add("chat-message--compacted");
        }
        if (meta && meta.is_error) {
            div.classList.add("chat-message--error");
        }
        if (role === "assistant") {
            div.dataset.messageId = String(meta?.message_id || "");
            div.dataset.webpagePreviews = JSON.stringify(meta?.webpage_previews || []);
            div.dataset.captureWebpagePreviews = meta?.capture_webpage_previews
                ? "true"
                : "false";
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
        const header = document.createElement("div");
        header.className = "chat-message-header";
        const roleGroup = document.createElement("span");
        roleGroup.className = "chat-role-group";
        roleGroup.appendChild(roleSpan);
        if (role === "assistant" && meta && meta.provider && meta.model && !meta.compacted) {
            roleGroup.appendChild(createUseModelButton(meta.provider, meta.model));
        }
        header.appendChild(roleGroup);
        appendMessageTimestamp(header, meta && meta.created_at);
        div.appendChild(header);
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
            const usedTools = Array.isArray(meta.used_tools)
                ? [...new Set(meta.used_tools.map(String).filter(Boolean))]
                : [];
            if (usedTools.length > 0) {
                const toolIcon = document.createElement("span");
                toolIcon.className = "chat-used-tools-icon";
                toolIcon.setAttribute("aria-label", usedTools.join(", "));
                toolIcon.title = usedTools.join(", ");
                toolIcon.textContent = "🛠";
                metaRow.appendChild(toolIcon);
            }
            div.appendChild(metaRow);
        }

        const contentDiv = document.createElement("div");
        contentDiv.className =
            role === "assistant" ? "chat-content markdown-content" : "chat-content";
        if (role === "assistant") {
            div.appendChild(contentDiv);
            const generatedDocuments = Array.isArray(meta?.generated_documents)
                ? meta.generated_documents
                : [];
            if (generatedDocuments.length > 0) {
                const documents = document.createElement("div");
                documents.className = "chat-generated-documents";
                documents.setAttribute("aria-label", "Generated documents");
                generatedDocuments.forEach((item) => {
                    const name = String(item?.name || "").trim();
                    if (!name) return;
                    const link = document.createElement("a");
                    link.className = "chat-generated-document";
                    link.href = `/chat/generated_document/${name.split("/").map(encodeURIComponent).join("/")}`;
                    link.download = name.split("/").pop();
                    link.dataset.generatedDocumentName = name;
                    const label = document.createElement("span");
                    label.className = "chat-generated-document-name";
                    label.textContent = name;
                    const icon = document.createElement("span");
                    icon.className = "chat-generated-document-download";
                    icon.setAttribute("aria-hidden", "true");
                    icon.textContent = "⇩";
                    link.append(label, icon);
                    bindGeneratedDocumentPreview(link, name);
                    documents.appendChild(link);
                });
                if (documents.children.length > 0) div.appendChild(documents);
            }
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
                    previews.appendChild(createUserImagePreview(src));
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
        addChatLocalFiles(meta?.local_attachments || []);
        syncEmptyState();
        historyEl.scrollTop = historyEl.scrollHeight;
        return div;
    };

    const renderHistory = (messages) => {
        if (!historyEl) return;
        hideHoverPreview();
        replaceChatLocalFiles([]);
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
                used_tools: m.used_tools || [],
                generated_documents: m.generated_documents || [],
                message_id: m.id,
                webpage_previews: m.webpage_previews || [],
                capture_webpage_previews: !m.is_error
                    && !(m.webpage_previews || []).length
                    && !m.webpage_preview_checked,
                compacted: Boolean(m.compacted),
                is_error: Boolean(m.is_error),
                created_at: m.created_at,
            });
        });
        syncEmptyState();
    };

    const appendAssistantPayload = (payload) => {
        const generatedDocuments = Array.isArray(payload?.generated_documents)
            ? payload.generated_documents
            : [];
        if (!payload || (!payload.response && generatedDocuments.length === 0)) {
            return false;
        }
        chatContext.add({
            input_tokens: payload.input_tokens || 0,
            output_tokens: payload.output_tokens || 0,
            compacted: false,
        });
        updateTokenUsage();
        appendMessage("assistant", payload.response, {
            provider: payload.provider,
            model: payload.model,
            time: payload.time,
            input_tokens: payload.input_tokens,
            output_tokens: payload.output_tokens,
            saved_system_prompt_name: payload.saved_system_prompt_name,
            system_prompt: payload.system_prompt,
            request_body: payload.request_body,
            used_tools: payload.used_tools || [],
            generated_documents: generatedDocuments,
            local_attachments: payload.local_attachments || [],
            message_id: payload.message_id,
            webpage_previews: payload.webpage_previews || [],
            capture_webpage_previews: !payload.is_error && payload.type !== "error",
            is_error: Boolean(payload.is_error || payload.type === "error"),
            created_at: payload.created_at,
        });
        return true;
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
        const header = document.createElement("div");
        header.className = "chat-message-header";
        header.appendChild(roleSpan);
        appendMessageTimestamp(header, meta.created_at);
        div.appendChild(header);
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
        const streamContent = document.createElement("div");
        streamContent.className = "chat-content markdown-content chat-stream-content";
        streamContent.setAttribute("aria-live", "polite");
        streamContent.hidden = true;
        const abortBtn = document.createElement("button");
        abortBtn.type = "button";
        abortBtn.className = "chat-abort-button";
        abortBtn.setAttribute("data-chat-abort", "");
        abortBtn.textContent = "Abort";
        if (typeof onAbort === "function") {
            abortBtn.addEventListener("click", onAbort);
        }
        div.append(spinner, text, tokenCount);
        if (meta.streamContent) {
            div.appendChild(streamContent);
        }
        div.appendChild(abortBtn);
        historyEl.appendChild(div);
        historyEl.scrollTop = historyEl.scrollHeight;
        return {
            element: div,
            tokenCount,
            loadingText: text,
            spinner,
            streamContent: meta.streamContent ? streamContent : null,
            renderFrame: null,
            pendingMarkdown: "",
            abortBtn,
        };
    };

    const streamingMarkdown = (value) => {
        const markdown = String(value || "");
        const fences = markdown.match(/```/g) || [];
        return fences.length % 2 === 0 ? markdown : `${markdown}\n\`\`\``;
    };

    const renderStreamingBubble = (loading, markdown, { flush = false } = {}) => {
        if (!loading || !loading.streamContent) return;
        loading.pendingMarkdown = markdown;
        const render = () => {
            loading.renderFrame = null;
            loading.streamContent.innerHTML = renderMarkdown(
                streamingMarkdown(loading.pendingMarkdown)
            );
            if (flush) hydrateAssistantMedia(loading.streamContent);
            loading.streamContent.hidden = false;
            loading.element.classList.add("is-streaming");
            loading.spinner.hidden = true;
            loading.loadingText.hidden = true;
            loading.tokenCount.hidden = true;
            historyEl.scrollTop = historyEl.scrollHeight;
        };
        if (flush) {
            if (loading.renderFrame !== null) {
                window.cancelAnimationFrame(loading.renderFrame);
            }
            render();
        } else if (loading.renderFrame === null) {
            loading.renderFrame = window.requestAnimationFrame(render);
        }
    };

    const cancelStreamingBubble = (loading) => {
        if (loading && loading.renderFrame !== null) {
            window.cancelAnimationFrame(loading.renderFrame);
            loading.renderFrame = null;
        }
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

    const hasChatMessages = () => Boolean(historyEl?.querySelector(".chat-message"));

    const handleSend = async () => {
        const message = inputEl?.value?.trim() || "";
        if (!message) {
            window.alert("Enter request to the message input");
            inputEl?.focus();
            return;
        }
        if (seedSwitch && seedSwitch.getAttribute("aria-checked") === "true" && seedEl) {
            const randomSeed = Math.floor(Math.random() * 4294967296);
            seedEl.value = String(randomSeed);
        }
        const settings = gatherSettings();
        if (!settings.model) {
            window.alert("Model is required.");
            return;
        }
        if (globalToolsEnabled === null) {
            await loadToolGlobalState();
        }
        let toolsAllowed;
        if (
            globalToolsEnabled === true
            && enabledMcpServiceNames.length > 0
            && globalToolSettings.tool_policy === "ask"
        ) {
            toolsAllowed = window.confirm(
                "Allow the enabled tools for this response?"
            );
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
        chatContext.add({ input_tokens: 0, output_tokens: 0, compacted: false });
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
        const streamResponseContent = Boolean(
            streamResponsesSwitch
            && streamResponsesSwitch.getAttribute("aria-checked") === "true"
        );
        const loadingEl = showLoading(() => {
            aborted = true;
            controller.abort();
        }, { streamContent: streamResponseContent });

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
                        local_filename: payload.local_filename || "",
                        mime_type: attachment.mime,
                        extension: ext,
                        size: attachment.size || 0,
                        content: payload.content,
                    };
                    replaceChatLocalFiles(payload.attachments || []);
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
            stream_responses: Boolean(
                streamResponsesSwitch
                && streamResponsesSwitch.getAttribute("aria-checked") === "true"
            ),
            auto_compact: Boolean(
                compactSwitch && compactSwitch.getAttribute("aria-checked") === "true"
            ),
        };
        if (globalToolSettings.automatic_tool_scope === true) {
            requestBody.automatic_tool_scope_selection = (
                automaticToolScopeSelection()
            );
        }
        if (typeof toolsAllowed === "boolean") {
            requestBody.tools_allowed = toolsAllowed;
        }

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
                local_filename: attachment.documentPayload.local_filename || "",
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
                const requestError = new Error(
                    payload.error || `HTTP ${response.status}`
                );
                requestError.chatPayload = payload;
                throw requestError;
            }
            if (!response.body) {
                throw new Error("Streaming is not supported by this browser.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let accumulated = "";
            let finalPayload = null;
            let completedResponse = false;

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
                            if (streamResponseContent) {
                                renderStreamingBubble(loadingEl, accumulated);
                            } else if (loadingEl && loadingEl.tokenCount) {
                                loadingEl.tokenCount.textContent = `${accumulated.length} chars`;
                            }
                        } else if (data.type === "done") {
                            if (streamResponseContent) {
                                renderStreamingBubble(
                                    loadingEl,
                                    accumulated,
                                    { flush: true }
                                );
                            } else if (loadingEl && loadingEl.tokenCount) {
                                loadingEl.tokenCount.textContent = `${accumulated.length} chars`;
                            }
                        } else if (data.type === "result") {
                            finalPayload = data;
                        } else if (data.type === "error") {
                            const requestError = new Error(
                                data.error || "Request failed"
                            );
                            requestError.chatPayload = data;
                            throw requestError;
                        }
                    }
                }
            }

            if (aborted) {
                cancelStreamingBubble(loadingEl);
                chatContext.removeLast();
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
            cancelStreamingBubble(loadingEl);
            if (loadingEl && loadingEl.element) loadingEl.element.remove();
            if (finalPayload) {
                completedResponse = appendAssistantPayload(finalPayload);
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
            if (completedResponse && shouldAutoCompact()) {
                await handleCompact();
            }
        } catch (error) {
            cancelStreamingBubble(loadingEl);
            if (loadingEl && loadingEl.element) loadingEl.element.remove();
            if (aborted || (error && error.name === "AbortError")) {
                chatContext.removeLast();
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
            appendAssistantPayload(error && error.chatPayload);
            const errorMessage = error && error.message ? error.message : String(error);
            window.alert(`Request failed: ${errorMessage}`);
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
        if (!hasChatMessages()) {
            window.alert("No chat to clear...");
            return;
        }
        try {
            await api.request("/chat/clear", { method: "POST" });
            if (historyEl) {
                historyEl.replaceChildren(emptyStateEl);
                syncEmptyState();
            }
            if (savedSelect) savedSelect.value = "";
            replaceChatLocalFiles([]);
            chatContext.clear();
            updateTokenUsage();
        } catch (error) {
            window.alert(`Clear failed: ${error}`);
        }
    };

    const handleExportChat = async () => {
        const name = savedSelect?.value?.trim() || "";
        if (!name && !hasChatMessages()) {
            window.alert("No chat to export.");
            return;
        }
        if (exportBtn) exportBtn.disabled = true;
        try {
            const payload = await api.json("/chat/export", {
                method: "POST",
                body: { name },
            });
            window.alert(`Chat exported: ${payload.filename}`);
        } catch (error) {
            window.alert(`Export chat failed: ${error}`);
        } finally {
            if (exportBtn) exportBtn.disabled = false;
        }
    };

    const applyImportedHistory = (messages, attachments) => {
        renderHistory(messages);
        replaceChatLocalFiles(attachments || []);
        chatContext.replace((messages || []).map((message) => ({
            input_tokens: message.input_tokens || 0,
            output_tokens: message.output_tokens || 0,
            compacted: Boolean(message.compacted),
        })));
        if (savedSelect) savedSelect.value = "";
        updateTokenUsage();
    };

    const handleImportChat = () => {
        const picker = document.createElement("input");
        picker.type = "file";
        picker.accept = ".json,application/json";
        picker.addEventListener("change", async () => {
            const file = picker.files && picker.files[0];
            if (!file) return;
            if (importBtn) importBtn.disabled = true;
            try {
                let documentPayload;
                try {
                    documentPayload = JSON.parse(await file.text());
                } catch (error) {
                    throw new Error("Invalid JSON file.");
                }
                const payload = await api.json("/chat/import", {
                    method: "POST",
                    body: { document: documentPayload },
                });
                applyImportedHistory(
                    payload.messages || [],
                    payload.attachments || []
                );
            } catch (error) {
                window.alert(`Import chat failed: ${error}`);
            } finally {
                if (importBtn) importBtn.disabled = false;
            }
        }, { once: true });
        picker.click();
    };

    const openSaveModal = () => {
        if (!hasChatMessages()) {
            window.alert("No chat to be saved...");
            return;
        }
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
            replaceChatLocalFiles(payload.attachments || []);
            chatContext.replace(messages.map((message) => ({
                    input_tokens: message.input_tokens || 0,
                    output_tokens: message.output_tokens || 0,
                    compacted: Boolean(message.compacted),
                })));
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
            replaceChatLocalFiles([]);
            if (!hasChatMessages()) {
                chatContext.clear();
                updateTokenUsage();
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

    const appendRequestBodyInlineCode = (container, text) => {
        const pattern = /`([^`\r\n]+)`/g;
        let offset = 0;
        let match;
        while ((match = pattern.exec(text)) !== null) {
            container.appendChild(document.createTextNode(
                text.slice(offset, match.index)
            ));
            const code = document.createElement("code");
            code.className = "request-body-inline-code";
            code.textContent = match[1];
            container.appendChild(code);
            offset = pattern.lastIndex;
        }
        container.appendChild(document.createTextNode(text.slice(offset)));
    };

    const appendRequestBodyString = (container, value) => {
        const normalized = String(value).replace(/\r\n|\r/g, "\n");
        const pattern = /```([^`\r\n]*)\n([\s\S]*?)```/g;
        let offset = 0;
        let match;
        while ((match = pattern.exec(normalized)) !== null) {
            appendRequestBodyInlineCode(
                container,
                normalized.slice(offset, match.index)
            );
            const block = document.createElement("span");
            block.className = "request-body-code-block";
            const language = match[1].trim();
            if (language) {
                const label = document.createElement("span");
                label.className = "request-body-code-language";
                label.textContent = language;
                block.appendChild(label);
            }
            const code = document.createElement("code");
            code.textContent = match[2].replace(/\n$/, "");
            block.appendChild(code);
            container.appendChild(block);
            offset = pattern.lastIndex;
        }
        appendRequestBodyInlineCode(container, normalized.slice(offset));
    };

    const appendRequestBodyJsonValue = (container, value, depth = 0) => {
        const indent = (level) => "  ".repeat(level);
        if (typeof value === "string") {
            container.appendChild(document.createTextNode('"'));
            appendRequestBodyString(container, value);
            container.appendChild(document.createTextNode('"'));
            return;
        }
        if (Array.isArray(value)) {
            if (!value.length) {
                container.appendChild(document.createTextNode("[]"));
                return;
            }
            container.appendChild(document.createTextNode("[\n"));
            value.forEach((item, index) => {
                container.appendChild(document.createTextNode(indent(depth + 1)));
                appendRequestBodyJsonValue(container, item, depth + 1);
                container.appendChild(document.createTextNode(
                    `${index < value.length - 1 ? "," : ""}\n`
                ));
            });
            container.appendChild(document.createTextNode(`${indent(depth)}]`));
            return;
        }
        if (value && typeof value === "object") {
            const entries = Object.entries(value);
            if (!entries.length) {
                container.appendChild(document.createTextNode("{}"));
                return;
            }
            container.appendChild(document.createTextNode("{\n"));
            entries.forEach(([key, item], index) => {
                container.appendChild(document.createTextNode(
                    `${indent(depth + 1)}${JSON.stringify(key)}: `
                ));
                appendRequestBodyJsonValue(container, item, depth + 1);
                container.appendChild(document.createTextNode(
                    `${index < entries.length - 1 ? "," : ""}\n`
                ));
            });
            container.appendChild(document.createTextNode(`${indent(depth)}}`));
            return;
        }
        const serialized = JSON.stringify(value);
        container.appendChild(document.createTextNode(
            serialized === undefined ? String(value ?? "") : serialized
        ));
    };

    const appendRequestBodyJson = (container, value, title = "") => {
        const section = document.createElement("section");
        section.className = "request-body-json-section";
        if (title) {
            const heading = document.createElement("h3");
            heading.className = "request-body-json-title";
            heading.textContent = title;
            section.appendChild(heading);
        }
        const pre = document.createElement("pre");
        pre.className = "request-body-json-block";
        appendRequestBodyJsonValue(pre, value);
        section.appendChild(pre);
        container.appendChild(section);
    };

    const openRequestBodyModal = (body) => {
        if (requestBodyModal) {
            requestBodyModal.hidden = false;
            if (requestBodyText) {
                requestBodyText.replaceChildren();
                if (body && typeof body === 'object' && !Array.isArray(body) && (body.video_request || body.audio_request)) {
                    if (body.video_request) {
                        appendRequestBodyJson(
                            requestBodyText,
                            body.video_request,
                            "Video request"
                        );
                    }
                    if (body.audio_request) {
                        appendRequestBodyJson(
                            requestBodyText,
                            body.audio_request,
                            "Audio request"
                        );
                    }
                } else {
                    appendRequestBodyJson(requestBodyText, body);
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
        if (name === "samplers" || name === "stream") return true;
        if (name === "temperature" || name === "top_p" || name === "top_k" || name === "seed" || name === "min_p") return true;
        if (value === null || value === undefined) return true;
        if (typeof value === "string" && value.toLowerCase() === "none") return true;
        return false;
    };

    const createParameterInfo = (key, labelText) => {
        const help = parameterHelp[key] || "No description is available for this parameter.";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "chat-info more-params-info";
        button.setAttribute("data-parameter-help-key", key);
        button.setAttribute("aria-label", `${labelText} help: ${help}`);
        const badge = document.createElement("span");
        badge.setAttribute("aria-hidden", "true");
        badge.textContent = "i";
        const tooltip = document.createElement("span");
        tooltip.className = "chat-info-tooltip";
        tooltip.setAttribute("role", "tooltip");
        tooltip.textContent = help;
        button.append(badge, tooltip);
        return button;
    };

    const createParamInput = (key, value) => {
        const wrapper = document.createElement("div");
        wrapper.className = "field-group more-params-field";

        const labelText = labelForParam(key);
        const labelRow = document.createElement("div");
        labelRow.className = "more-params-label";
        const label = document.createElement("label");
        label.textContent = labelText;
        label.setAttribute("for", `more-param-${key}`);
        labelRow.append(label, createParameterInfo(key, labelText));
        wrapper.appendChild(labelRow);

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

    const updateParameterCacheState = (state, mode) => {
        if (!moreParamsCacheState || !moreParamsCacheTooltip) return;
        const colors = {
            missing_params: "red",
            missing_ctx: "orange",
            complete: "green",
        };
        const color = colors[state];
        moreParamsCacheState.classList.remove(
            "more-params-cache-state--red",
            "more-params-cache-state--orange",
            "more-params-cache-state--green"
        );
        if (!color) {
            moreParamsCacheState.hidden = true;
            moreParamsCacheState.removeAttribute("aria-label");
            return;
        }
        const tooltip = state === "missing_params"
            ? "No saved parameter and ctx data."
            : state === "missing_ctx"
                ? `n_ctx missing for: ${mode || "unknown"}`
                : "Parameters and n_ctx value exist.";
        moreParamsCacheState.classList.add(`more-params-cache-state--${color}`);
        moreParamsCacheTooltip.textContent = tooltip;
        moreParamsCacheState.setAttribute("aria-label", tooltip);
        moreParamsCacheState.hidden = false;
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
            setMoreParamsDeleteVisible(true);
            moreParamsModelKey = `${provider}::${model}`;
            await refreshSavedModelState(provider, model);
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

    const renderToolCapability = (capabilities) => {
        if (!toolCapabilityEl) return;
        if (toolCapabilityControl) toolCapabilityControl.hidden = true;
        toolCapabilityEl.hidden = true;
        toolCapabilityEl.classList.remove(
            "chat-tool-capability--full",
            "chat-tool-capability--partial",
            "chat-tool-capability--inactive"
        );
        toolCapabilityEl.removeAttribute("aria-label");
        toolCapabilityEl.removeAttribute("title");

        if (!capabilities || capabilities.supports_tool_calls !== true) return;
        let state;
        let label;
        if (capabilities.supports_tools === true) {
            state = "full";
            label = "Full tool support";
        } else if (capabilities.supports_tools === false) {
            state = "partial";
            label = "Partial tool support";
        } else {
            return;
        }

        toolCapabilityBaseLabel = label;
        toolCapabilityEl.classList.add(`chat-tool-capability--${state}`);
        updateToolCapabilityStatus();
        toolCapabilityEl.hidden = false;
        if (toolCapabilityControl) toolCapabilityControl.hidden = false;
    };

    const subserviceDisplayName = (serviceName, subserviceName) => {
        const providerFreeName = String(subserviceName).split("::").at(-1);
        const prefix = `${serviceName}_`;
        return providerFreeName.startsWith(prefix)
            ? providerFreeName.slice(prefix.length)
            : providerFreeName;
    };

    const enabledToolDisplayEntries = () => {
        const uniqueServices = new Map();
        enabledMcpServiceNames.forEach((serviceName) => {
            const parts = String(serviceName).split("::").filter(Boolean);
            const displayName = (parts.at(-1) || "").trim();
            const key = displayName.toLocaleLowerCase();
            if (!displayName) return;
            if (!uniqueServices.has(key)) {
                uniqueServices.set(key, {
                    displayName,
                    subservices: new Map(),
                    available: false,
                    managed: false,
                });
            }
            const entry = uniqueServices.get(key);
            const managed = managedMcpServiceNames.has(serviceName);
            entry.managed = entry.managed || managed;
            entry.available = entry.available || (
                managed || mcpServiceAvailability.get(serviceName) !== false
            );
            const subservices = Array.isArray(enabledMcpSubservices[serviceName])
                ? enabledMcpSubservices[serviceName]
                : [];
            subservices.forEach((subserviceName) => {
                const subservice = subserviceDisplayName(
                    displayName,
                    subserviceName
                ).trim();
                const subserviceKey = subservice.toLocaleLowerCase();
                if (subservice && !entry.subservices.has(subserviceKey)) {
                    entry.subservices.set(subserviceKey, subservice);
                }
            });
        });
        return [...uniqueServices.values()].map((entry) => ({
            displayName: entry.displayName,
            subservices: [...entry.subservices.values()],
            available: entry.available,
            managed: entry.managed,
        }));
    };

    const closeToolSubserviceDropdown = () => {
        if (!toolScopeAccordion || !toolSubserviceDropdown) return;
        toolScopeAccordion.querySelectorAll(".chat-tool-scope-name")
            .forEach((button) => button.setAttribute("aria-expanded", "false"));
        toolSubserviceDropdown.replaceChildren();
        toolSubserviceDropdown.hidden = true;
    };

    const subserviceUiStateKey = (serviceName, subserviceName) => (
        `${serviceName}\u0000${subserviceName}`.toLocaleLowerCase()
    );

    const subserviceIsEnabled = (serviceName, subserviceName) => (
        toolSubserviceUiStates.get(
            subserviceUiStateKey(serviceName, subserviceName)
        ) !== false
    );

    const updateMainServiceLed = (
        button,
        serviceName,
        subservices,
        available = true
    ) => {
        button.classList.toggle(
            "has-enabled-subservices",
            available
                && subservices.some((name) => subserviceIsEnabled(serviceName, name))
        );
    };

    const automaticToolScopeSelection = (includeOffline = true) => (
        enabledToolDisplayEntries().flatMap((entry) => (
            (entry.available || includeOffline ? entry.subservices : [])
                .filter((name) => subserviceIsEnabled(entry.displayName, name))
                .map((name) => ({
                    service: entry.displayName,
                    tool: name,
                }))
        ))
    );

    const updateToolCapabilityPresentation = () => {
        if (!toolCapabilityEl || !toolCapabilityBaseLabel) return;
        const hasEnabledServices = enabledMcpServiceNames.length > 0;
        const quickScopeHasTools = (
            globalToolSettings.automatic_tool_scope !== true
            || automaticToolScopeSelection(false).length > 0
        );
        let status;
        if (!hasEnabledServices || globalToolsEnabled === null) {
            status = "All tools disabled";
        } else if (globalToolsEnabled !== true || !quickScopeHasTools) {
            status = "Disabled";
        } else {
            status = enabledMcpServiceNames.join(", ");
        }
        const label = `${toolCapabilityBaseLabel} · ${status}`;
        toolCapabilityEl.classList.toggle(
            "chat-tool-capability--inactive",
            globalToolsEnabled !== true
                || !hasEnabledServices
                || !quickScopeHasTools
        );
        toolCapabilityEl.setAttribute("aria-label", label);
        if (toolCapabilityTooltip) toolCapabilityTooltip.textContent = label;
    };

    const toggleToolSubservices = (button, serviceName, subservices) => {
        if (!toolSubserviceDropdown) return;
        const opening = button.getAttribute("aria-expanded") !== "true";
        closeToolSubserviceDropdown();
        if (!opening || !subservices.length) return;
        const itemLedUpdates = [];
        let selectAllControl = null;
        const updateSelectAllControl = () => {
            if (!selectAllControl) return;
            const allEnabled = subservices.every((name) => (
                subserviceIsEnabled(serviceName, name)
            ));
            selectAllControl.setAttribute(
                "aria-checked",
                allEnabled ? "true" : "false"
            );
        };
        if (subservices.length > 4) {
            selectAllControl = document.createElement("button");
            selectAllControl.type = "button";
            selectAllControl.className = "chat-tool-subservice-select-all";
            selectAllControl.setAttribute("role", "switch");
            selectAllControl.setAttribute(
                "aria-label",
                "Select or deselect all sub-tools"
            );
            const selectAllLabel = document.createElement("span");
            selectAllLabel.textContent = "All sub-tools";
            const selectAllSwitch = document.createElement("span");
            selectAllSwitch.className = "chat-tool-subservice-select-all-switch";
            selectAllSwitch.setAttribute("aria-hidden", "true");
            selectAllControl.append(selectAllLabel, selectAllSwitch);
            selectAllControl.addEventListener("click", () => {
                const enableAll = (
                    selectAllControl.getAttribute("aria-checked") !== "true"
                );
                subservices.forEach((name) => {
                    toolSubserviceUiStates.set(
                        subserviceUiStateKey(serviceName, name),
                        enableAll
                    );
                });
                itemLedUpdates.forEach((updateLed) => updateLed());
                updateSelectAllControl();
                updateMainServiceLed(button, serviceName, subservices);
                updateToolCapabilityPresentation();
            });
            updateSelectAllControl();
            toolSubserviceDropdown.appendChild(selectAllControl);
        }
        subservices.forEach((name) => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "chat-tool-subservice-name";
            item.textContent = name;
            const updateLed = () => {
                const enabled = subserviceIsEnabled(serviceName, name);
                item.classList.toggle("is-enabled", enabled);
                item.setAttribute("aria-pressed", enabled ? "true" : "false");
            };
            itemLedUpdates.push(updateLed);
            updateLed();
            item.addEventListener("click", () => {
                toolSubserviceUiStates.set(
                    subserviceUiStateKey(serviceName, name),
                    !subserviceIsEnabled(serviceName, name)
                );
                updateLed();
                updateSelectAllControl();
                updateMainServiceLed(button, serviceName, subservices);
                updateToolCapabilityPresentation();
            });
            toolSubserviceDropdown.appendChild(item);
        });
        const controlRect = toolCapabilityControl.getBoundingClientRect();
        const buttonRect = button.getBoundingClientRect();
        toolSubserviceDropdown.style.setProperty(
            "--chat-tool-subservice-left",
            `${buttonRect.left - controlRect.left}px`
        );
        toolSubserviceDropdown.style.setProperty(
            "--chat-tool-subservice-top",
            `${buttonRect.bottom - controlRect.top}px`
        );
        button.setAttribute("aria-expanded", "true");
        toolSubserviceDropdown.hidden = false;
    };

    const setToolScopeExpanded = (expanded) => {
        if (!toolCapabilityControl || !toolScopeToggle || !toolScopeAccordion) {
            return;
        }
        const allowed = globalToolSettings.automatic_tool_scope === true;
        const nextExpanded = allowed && expanded;
        toolCapabilityControl.classList.toggle("is-expanded", nextExpanded);
        toolScopeToggle.setAttribute(
            "aria-expanded",
            nextExpanded ? "true" : "false"
        );
        toolScopeToggle.setAttribute(
            "aria-label",
            nextExpanded ? "Hide enabled tools" : "Show enabled tools"
        );
        toolScopeAccordion.setAttribute(
            "aria-hidden",
            nextExpanded ? "false" : "true"
        );
        if (!nextExpanded) closeToolSubserviceDropdown();
    };

    const updateToolScopeControl = () => {
        if (!toolScopeToggle || !toolScopeAccordion) return;
        const automaticScope = globalToolSettings.automatic_tool_scope === true;
        toolScopeToggle.hidden = !automaticScope;
        closeToolSubserviceDropdown();
        toolScopeAccordion.replaceChildren();
        enabledToolDisplayEntries().forEach((entry) => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "chat-tool-scope-name";
            item.textContent = entry.displayName;
            item.classList.toggle("is-offline", !entry.available);
            item.classList.toggle("is-managed", entry.managed);
            updateMainServiceLed(
                item,
                entry.displayName,
                entry.subservices,
                entry.available
            );
            item.setAttribute("aria-expanded", "false");
            item.disabled = !entry.available || entry.subservices.length === 0;
            if (!entry.available) {
                item.title = "Service endpoint is offline";
            } else if (entry.managed) {
                item.title = "Service starts automatically when needed";
            }
            item.addEventListener("click", () => {
                toggleToolSubservices(
                    item,
                    entry.displayName,
                    entry.subservices
                );
            });
            toolScopeAccordion.appendChild(item);
        });
        if (!automaticScope) setToolScopeExpanded(false);
    };

    const updateToolCapabilityStatus = () => {
        updateToolCapabilityPresentation();
        updateToolScopeControl();
    };

    const applyToolGlobalState = (payload) => {
        globalToolsEnabled = typeof payload?.enabled === "boolean"
            ? payload.enabled
            : null;
        enabledMcpServiceNames = Array.isArray(payload?.enabled_services)
            ? [...new Set(payload.enabled_services.map(String).filter(Boolean))]
            : [];
        enabledMcpSubservices = (
            payload?.enabled_subservices
            && typeof payload.enabled_subservices === "object"
            && !Array.isArray(payload.enabled_subservices)
        ) ? payload.enabled_subservices : {};
        mcpServiceAvailability.clear();
        const availability = (
            payload?.service_availability
            && typeof payload.service_availability === "object"
            && !Array.isArray(payload.service_availability)
        ) ? payload.service_availability : {};
        Object.entries(availability).forEach(([serviceName, online]) => {
            mcpServiceAvailability.set(serviceName, online === true);
        });
        managedMcpServiceNames.clear();
        const managedServices = Array.isArray(payload?.managed_services)
            ? payload.managed_services
            : [];
        managedServices.forEach((serviceName) => {
            managedMcpServiceNames.add(String(serviceName));
        });
        toolSubserviceUiStates.clear();
        if (Array.isArray(payload?.automatic_tool_scope_selection)) {
            const selected = new Set(
                payload.automatic_tool_scope_selection.map((item) => (
                    subserviceUiStateKey(item?.service || "", item?.tool || "")
                ))
            );
            enabledToolDisplayEntries().forEach((entry) => {
                entry.subservices.forEach((name) => {
                    const key = subserviceUiStateKey(entry.displayName, name);
                    toolSubserviceUiStates.set(key, selected.has(key));
                });
            });
        }
        const settings = payload?.settings && typeof payload.settings === "object"
            ? payload.settings
            : {};
        globalToolSettings = {...globalToolSettings, ...settings};
        globalToolSettingsLoaded = true;
        setMcpSwitch(toolGlobalSwitch, globalToolsEnabled === true);
        setMcpSwitch(
            toolAutomaticScopeSwitch,
            globalToolSettings.automatic_tool_scope === true
        );
        setMcpSwitch(toolGuidanceSwitch, globalToolSettings.guidance_enabled === true);
        setMcpSwitch(
            toolWebpagePreviewSwitch,
            globalToolSettings.capture_webpage_preview === true
        );
        if (toolMaxRoundsInput) {
            toolMaxRoundsInput.value = String(globalToolSettings.max_rounds);
        }
        if (toolMaxTotalCallsInput) {
            toolMaxTotalCallsInput.value = String(globalToolSettings.max_total_calls);
        }
        if (toolMaxFailuresInput) {
            toolMaxFailuresInput.value = String(
                globalToolSettings.max_consecutive_failures
            );
        }
        if (toolMaxResultCharsInput) {
            toolMaxResultCharsInput.value = String(
                globalToolSettings.max_result_chars
            );
        }
        if (toolUsePolicySelect) {
            toolUsePolicySelect.value = globalToolSettings.tool_policy;
        }
        if (toolGuidanceTemplate) {
            toolGuidanceTemplate.value = globalToolSettings.guidance_template;
        }
        if (toolWebpagePreviewTimeoutInput) {
            toolWebpagePreviewTimeoutInput.value = String(
                globalToolSettings.webpage_preview_timeout
            );
            toolWebpagePreviewTimeoutInput.disabled = (
                globalToolSettings.capture_webpage_preview !== true
            );
        }
        historyEl?.querySelectorAll(".chat-message--assistant .chat-content")
            .forEach(hydrateWebpagePreviews);
        updateToolCapabilityStatus();
        updateToolScopeControl();
    };

    const loadToolGlobalState = async () => {
        try {
            applyToolGlobalState(await api.request(mcpGlobalStateUrl));
        } catch (error) {
            applyToolGlobalState({enabled: null, enabled_services: []});
        }
    };

    const openToolGlobalSettings = async () => {
        if (!toolGlobalSettingsModal) return;
        await loadToolGlobalState();
        toolGlobalSettingsModal.hidden = false;
    };

    const closeToolGlobalSettings = () => {
        if (toolGlobalSettingsModal) toolGlobalSettingsModal.hidden = true;
    };

    const saveToolGlobalSettings = async () => {
        if (!toolGlobalSaveBtn || !toolGlobalSwitch) return;
        toolGlobalSaveBtn.disabled = true;
        try {
            const settings = {
                max_rounds: Number.parseInt(toolMaxRoundsInput?.value || "", 10),
                max_total_calls: Number.parseInt(
                    toolMaxTotalCallsInput?.value || "",
                    10
                ),
                max_consecutive_failures: Number.parseInt(
                    toolMaxFailuresInput?.value || "",
                    10
                ),
                max_result_chars: Number.parseInt(
                    toolMaxResultCharsInput?.value || "",
                    10
                ),
                tool_policy: toolUsePolicySelect?.value || "automatic",
                automatic_tool_scope: toolAutomaticScopeSwitch?.getAttribute(
                    "aria-checked"
                ) === "true",
                guidance_enabled: toolGuidanceSwitch?.getAttribute("aria-checked") === "true",
                guidance_template: toolGuidanceTemplate?.value || "",
                capture_webpage_preview: toolWebpagePreviewSwitch?.getAttribute(
                    "aria-checked"
                ) === "true",
                webpage_preview_timeout: Number.parseInt(
                    toolWebpagePreviewTimeoutInput?.value || "",
                    10
                ),
            };
            const payload = await api.json(mcpGlobalStateUrl, {
                method: "POST",
                body: {
                    enabled: toolGlobalSwitch.getAttribute("aria-checked") === "true",
                    settings,
                },
            });
            applyToolGlobalState(payload);
            closeToolGlobalSettings();
        } catch (error) {
            window.alert(`Tool status could not be saved: ${error}`);
        } finally {
            toolGlobalSaveBtn.disabled = false;
        }
    };

    const setMcpSwitch = (control, checked) => {
        control.setAttribute("aria-checked", checked ? "true" : "false");
    };

    const customMcpToolKey = (serviceName, toolName) => (
        `${serviceName}::${toolName}`
    );

    const hydrateMcpSettings = (payload) => {
        savedMcpStates.clear();
        savedMcpToolSettings.clear();
        savedMcpSecretFields.clear();
        savedCustomToolStates.clear();
        cachedCustomTools.clear();
        savedLlamaToolStates.clear();
        savedLlamaServiceStates.clear();
        savedLlamaServiceSettings.clear();
        const records = Array.isArray(payload && payload.records)
            ? payload.records
            : [];
        records.forEach((record) => {
            if (!record || typeof record !== "object") return;
            const settings = record.settings && typeof record.settings === "object"
                ? record.settings
                : {};
            const secretFields = Array.isArray(record.secret_fields_saved)
                ? record.secret_fields_saved
                : (record.password_saved === true ? ["password"] : []);
            secretFields.forEach((fieldName) => {
                savedMcpSecretFields.add(
                    `${record.source}::${record.service}::${fieldName}`
                );
            });
            if (record.source === "external") {
                savedMcpStates.set(record.service, record.enabled === true);
                savedMcpToolSettings.set(record.service, settings);
            } else if (record.source === "external_tool" && record.tool) {
                savedCustomToolStates.set(
                    customMcpToolKey(record.service, record.tool),
                    record.enabled === true
                );
            } else if (record.source === "llama_service") {
                savedLlamaServiceStates.set(record.service, record.enabled === true);
                savedLlamaServiceSettings.set(record.service, settings);
            } else if (record.source === "llama_tool" && record.tool) {
                savedLlamaToolStates.set(record.tool, record.enabled === true);
            }
        });
        const customTools = Array.isArray(payload && payload.custom_tools)
            ? payload.custom_tools
            : [];
        customTools.forEach((tool) => {
            if (!tool || typeof tool !== "object" || !tool.service || !tool.tool) return;
            if (!cachedCustomTools.has(tool.service)) {
                cachedCustomTools.set(tool.service, []);
            }
            cachedCustomTools.get(tool.service).push(tool);
        });
    };

    const createMcpProviderAccordion = (key, label) => {
        const section = document.createElement("section");
        section.className = "mcp-provider-group";
        section.setAttribute("data-mcp-provider-group", key);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "mcp-provider-group-toggle";
        button.setAttribute("aria-expanded", "false");
        const title = document.createElement("strong");
        title.textContent = label;
        const hint = document.createElement("span");
        hint.textContent = "Services and setup";
        const status = document.createElement("span");
        status.className = "mcp-provider-group-status";
        status.hidden = true;
        const marker = document.createElement("span");
        marker.className = "mcp-provider-group-marker";
        marker.setAttribute("aria-hidden", "true");
        marker.textContent = "▼";
        button.append(title, hint, status, marker);

        const content = document.createElement("div");
        content.className = "mcp-provider-group-content";
        content.hidden = true;
        button.addEventListener("click", () => {
            const opening = button.getAttribute("aria-expanded") !== "true";
            mcpServiceList.querySelectorAll("[data-mcp-provider-group]").forEach(
                (group) => {
                    const toggle = group.querySelector(".mcp-provider-group-toggle");
                    const body = group.querySelector(".mcp-provider-group-content");
                    toggle?.setAttribute("aria-expanded", "false");
                    if (body) body.hidden = true;
                }
            );
            button.setAttribute("aria-expanded", opening ? "true" : "false");
            content.hidden = !opening;
        });
        section.append(button, content);
        return {
            section,
            content,
            setStatus(value, tone = "") {
                const label = String(value || "").trim();
                status.textContent = label;
                status.hidden = !label;
                status.classList.toggle(
                    "mcp-provider-group-status--offline",
                    tone === "offline"
                );
            },
        };
    };

    const createCustomMcpToolRow = (serviceName, cachedTool) => {
        const toolName = String(cachedTool.tool || "").trim();
        const definition = cachedTool.definition && typeof cachedTool.definition === "object"
            ? cachedTool.definition
            : {};
        const row = document.createElement("div");
        row.className = "llama-managed-tool-row custom-mcp-tool-row";
        const identity = document.createElement("div");
        identity.className = "llama-managed-tool-identity";
        const name = document.createElement("strong");
        name.textContent = toolName;
        const description = document.createElement("span");
        description.textContent = definition.description || "No description available.";
        identity.append(name, description);

        const toolSwitch = document.createElement("button");
        toolSwitch.type = "button";
        toolSwitch.className = "chat-toggle-switch llama-managed-tool-switch";
        toolSwitch.setAttribute("data-custom-mcp-tool-switch", toolName);
        toolSwitch.setAttribute("data-custom-mcp-service", serviceName);
        toolSwitch.setAttribute("role", "switch");
        toolSwitch.setAttribute("aria-label", `Enable ${toolName}`);
        const stateKey = customMcpToolKey(serviceName, toolName);
        setMcpSwitch(toolSwitch, Boolean(savedCustomToolStates.get(stateKey)));
        const track = document.createElement("span");
        track.className = "chat-toggle-switch-track";
        track.setAttribute("aria-hidden", "true");
        const knob = document.createElement("span");
        knob.className = "chat-toggle-switch-knob";
        track.appendChild(knob);
        toolSwitch.appendChild(track);
        toolSwitch.addEventListener("click", () => {
            if (toolSwitch.disabled) return;
            const enabled = toolSwitch.getAttribute("aria-checked") !== "true";
            setMcpSwitch(toolSwitch, enabled);
            savedCustomToolStates.set(stateKey, enabled);
        });
        row.append(identity, toolSwitch);
        return row;
    };

    const applyCustomMcpServiceState = (row, online) => {
        const serviceSwitch = row.querySelector("[data-mcp-service-switch]");
        const serviceName = serviceSwitch?.getAttribute("data-mcp-service-switch");
        const serviceEnabled = Boolean(savedMcpStates.get(serviceName));
        const dependencyStartCommand = String(
            savedMcpToolSettings.get(serviceName)?.dependency_start_command || ""
        ).trim();
        row.setAttribute("data-mcp-service-online", online ? "true" : "false");
        if (serviceSwitch) {
            serviceSwitch.disabled = !online && !dependencyStartCommand;
            setMcpSwitch(serviceSwitch, serviceEnabled);
        }
        row.querySelectorAll("[data-custom-mcp-tool-switch]").forEach((toolSwitch) => {
            const toolName = toolSwitch.getAttribute("data-custom-mcp-tool-switch");
            toolSwitch.setAttribute(
                "data-custom-tool-available",
                online ? "true" : "false"
            );
            toolSwitch.disabled = !online || !serviceEnabled;
            setMcpSwitch(
                toolSwitch,
                Boolean(savedCustomToolStates.get(
                    customMcpToolKey(serviceName, toolName)
                ))
            );
        });
    };

    const createMcpServiceRow = (name, details) => {
        const serviceTools = cachedCustomTools.get(name) || [];
        const savedSettings = savedMcpToolSettings.get(name) || {};
        const settings = {
            command: details.command || "",
            args: Array.isArray(details.args) ? details.args : [],
            timeout_ms: details.timeout_ms,
            ...savedSettings,
        };
        const timeout = Number(settings.timeout_ms);
        settings.timeout_ms = Number.isInteger(timeout) && timeout > 0
            ? timeout
            : mcpDefaultTimeoutMs;
        savedMcpToolSettings.set(name, settings);
        const source = details && details.source;
        const row = document.createElement("div");
        row.className = "mcp-service-row mcp-service-row--checking";
        row.classList.add(
            source === "opencode"
                ? "mcp-service-row--opencode"
                : "mcp-service-row--custom"
        );
        row.setAttribute("data-mcp-service-row", name);

        const identity = document.createElement("div");
        identity.className = "mcp-service-identity";
        const marker = document.createElement("span");
        marker.className = "mcp-service-marker";
        marker.setAttribute("aria-hidden", "true");
        marker.textContent = "◆";
        const serviceName = createMcpName(name);
        const sourceBadge = document.createElement("span");
        sourceBadge.className = "mcp-source-badge mcp-source-badge--custom";
        sourceBadge.textContent = source === "opencode" ? "OpenCode" : "Custom";
        sourceBadge.title = source === "opencode"
            ? "Imported from OpenCode"
            : "Custom MCP service";
        const toolCount = document.createElement("span");
        toolCount.className = "mcp-service-tool-count";
        toolCount.textContent = `${serviceTools.length} ${
            serviceTools.length === 1 ? "tool" : "tools"
        }`;
        identity.append(marker, serviceName, sourceBadge, toolCount);

        const controls = document.createElement("div");
        controls.className = "mcp-service-controls";
        const statusLabel = document.createElement("span");
        statusLabel.className = "mcp-service-status";
        statusLabel.setAttribute("data-mcp-service-status", "");
        statusLabel.textContent = "Checking…";
        const switchWrap = document.createElement("span");
        switchWrap.className = "mcp-service-switch-wrap";
        const serviceSwitch = document.createElement("button");
        serviceSwitch.type = "button";
        serviceSwitch.className = "chat-toggle-switch mcp-service-switch";
        serviceSwitch.setAttribute("data-mcp-service-switch", name);
        serviceSwitch.setAttribute("role", "switch");
        serviceSwitch.setAttribute("aria-label", `Enable ${name}`);
        setMcpSwitch(serviceSwitch, false);
        serviceSwitch.disabled = true;
        const track = document.createElement("span");
        track.className = "chat-toggle-switch-track";
        track.setAttribute("aria-hidden", "true");
        const knob = document.createElement("span");
        knob.className = "chat-toggle-switch-knob";
        track.appendChild(knob);
        serviceSwitch.appendChild(track);
        serviceSwitch.addEventListener("click", () => {
            if (serviceSwitch.disabled) return;
            const enabled = serviceSwitch.getAttribute("aria-checked") !== "true";
            setMcpSwitch(serviceSwitch, enabled);
            savedMcpStates.set(name, enabled);
            applyCustomMcpServiceState(row, true);
        });
        const offlineTooltip = document.createElement("span");
        offlineTooltip.className = "mcp-service-offline-tooltip";
        offlineTooltip.setAttribute("role", "tooltip");
        offlineTooltip.textContent = "Server offline";
        offlineTooltip.hidden = true;
        switchWrap.append(serviceSwitch, offlineTooltip);

        const setupIcon = document.createElement("button");
        setupIcon.type = "button";
        setupIcon.className = "mcp-service-setup-icon";
        setupIcon.setAttribute("aria-label", `Set up ${name}`);
        setupIcon.setAttribute("aria-expanded", "false");
        setupIcon.textContent = "⚙";
        const spinner = document.createElement("span");
        spinner.className = "mcp-service-spinner";
        spinner.setAttribute("aria-label", `Checking ${name}`);
        spinner.setAttribute("role", "status");
        spinner.textContent = "↻";
        const toolList = document.createElement("div");
        toolList.className = "llama-managed-service-tools custom-mcp-service-tools";
        toolList.hidden = true;
        serviceTools.forEach((tool) => {
            toolList.appendChild(createCustomMcpToolRow(name, tool));
        });
        const expandButton = document.createElement("button");
        expandButton.type = "button";
        expandButton.className = "llama-managed-expand custom-mcp-expand";
        expandButton.setAttribute("aria-label", `Show tools for ${name}`);
        expandButton.setAttribute("aria-expanded", "false");
        expandButton.textContent = "▼";
        expandButton.disabled = serviceTools.length === 0;
        if (expandButton.disabled) {
            expandButton.title = "Refresh to discover tools";
        }
        expandButton.addEventListener("click", () => {
            toggleLlamaAccordion(expandButton, toolList);
        });
        controls.append(statusLabel, switchWrap, setupIcon, spinner, expandButton);
        row.append(identity, controls, toolList);
        setupIcon.addEventListener("click", () => {
            toggleMcpToolSetup(name, details, row, setupIcon);
        });
        return row;
    };

    const showSavedDisabledMcpService = (row) => {
        row.classList.remove(
            "mcp-service-row--checking",
            "mcp-service-row--offline",
            "mcp-service-row--online"
        );
        const status = row.querySelector("[data-mcp-service-status]");
        if (status) status.textContent = "Disabled";
        const spinner = row.querySelector(".mcp-service-spinner");
        if (spinner) spinner.hidden = true;
        const offlineTooltip = row.querySelector(
            ".mcp-service-offline-tooltip"
        );
        if (offlineTooltip) offlineTooltip.hidden = true;
        applyCustomMcpServiceState(row, true);
        row.setAttribute("data-mcp-service-online", "unchecked");
    };

    const testMcpSetupAccess = async (
        name,
        source,
        accessKey,
        button,
        result
    ) => {
        const accordion = button.closest(
            "[data-mcp-tool-setup], [data-llama-managed-defaults]"
        );
        if (!accordion || !accessKey) return;
        const initialSettings = source === "llama_service"
            ? (savedLlamaServiceSettings.get(name) || {})
            : (savedMcpToolSettings.get(name) || {});
        let settings;
        try {
            settings = readMcpAccordionSettings(accordion, initialSettings);
        } catch (error) {
            result.textContent = String(error.message || error);
            result.className = "mcp-endpoint-test-result mcp-endpoint-test-result--offline";
            return;
        }
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        result.textContent = "Testing…";
        result.className = "mcp-endpoint-test-result";
        try {
            const response = await api.json(mcpEndpointTestUrl, {
                method: "POST",
                body: {
                    source,
                    service: name,
                    access_key: accessKey,
                    settings,
                },
            });
            const online = Boolean(response && response.online);
            result.textContent = online ? "Online" : "Offline";
            result.className = `mcp-endpoint-test-result mcp-endpoint-test-result--${
                online ? "online" : "offline"
            }`;
            if (source === "llama_service") {
                const service = accordion.closest("[data-llama-managed-service]");
                const status = service?.querySelector(
                    "[data-llama-managed-service-status]"
                );
                if (status) status.textContent = online ? "Online" : "Offline";
                if (service) applyLlamaServiceOnlineState(service, online);
            }
        } catch (error) {
            result.textContent = "Test failed";
            result.className = "mcp-endpoint-test-result mcp-endpoint-test-result--offline";
        } finally {
            button.disabled = false;
            button.setAttribute("aria-busy", "false");
        }
    };

    const createMcpToolField = (
        name,
        key,
        definition,
        savedValues,
        source = "external"
    ) => {
        const field = document.createElement("div");
        field.className = "field-group mcp-tool-field";
        const inputId = `mcp-tool-${name}-${key}`;
        if (String(definition.type || "").toLowerCase() === "button") {
            field.classList.add("mcp-tool-field--button");
            const button = document.createElement("button");
            button.type = "button";
            button.className = "modal-cancel-button mcp-endpoint-test-button";
            button.textContent = definition.name || "Test access";
            button.setAttribute("data-mcp-endpoint-test", key);
            const result = document.createElement("span");
            result.className = "mcp-endpoint-test-result";
            result.setAttribute("role", "status");
            result.setAttribute("aria-live", "polite");
            button.addEventListener("click", () => {
                testMcpSetupAccess(
                    name,
                    source,
                    String(definition.access_key || ""),
                    button,
                    result
                );
            });
            field.append(button, result);
            return field;
        }
        const label = document.createElement("label");
        label.textContent = definition.name || key;
        const hasSavedValue = Object.prototype.hasOwnProperty.call(savedValues, key);
        const hasDefaultValue = Object.prototype.hasOwnProperty.call(definition, "default");
        const initialValue = hasSavedValue
            ? savedValues[key]
            : (hasDefaultValue ? definition.default : undefined);
        const fieldType = String(definition.type || "").toLowerCase();
        if (
            definition.type === "list"
            && definition.multiple === true
            && Array.isArray(definition.values)
        ) {
            field.classList.add("mcp-tool-field--multiple");
            label.id = `${inputId}-label`;
            const selectedValues = new Set(
                (Array.isArray(initialValue) ? initialValue : [initialValue])
                    .filter((value) => value !== undefined && value !== null && value !== "")
                    .map(String)
            );
            const options = document.createElement("div");
            options.id = inputId;
            options.className = "mcp-tool-multi-list";
            options.setAttribute("role", "group");
            options.setAttribute("aria-labelledby", label.id);
            options.setAttribute("data-mcp-multiple-setting", key);
            definition.values.forEach((value, index) => {
                const structured = value && typeof value === "object";
                const optionValue = String(
                    structured ? (value.value ?? "") : value
                );
                const optionLabel = String(
                    structured ? (value.label ?? value.value ?? "") : value
                );
                const option = document.createElement("label");
                option.className = "mcp-tool-multi-option";
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.value = optionValue;
                checkbox.id = `${inputId}-${index}`;
                checkbox.checked = selectedValues.has(optionValue);
                const text = document.createElement("span");
                text.textContent = optionLabel;
                option.append(checkbox, text);
                options.appendChild(option);
            });
            field.append(label, options);
            return field;
        }
        label.setAttribute("for", inputId);
        let input;
        if (fieldType === "list" && Array.isArray(definition.values)) {
            input = document.createElement("select");
            definition.values.forEach((value) => {
                const option = document.createElement("option");
                const structured = value && typeof value === "object";
                option.value = String(structured ? (value.value ?? "") : value);
                option.textContent = String(
                    structured ? (value.label ?? value.value ?? "") : value
                );
                input.appendChild(option);
            });
        } else {
            input = document.createElement("input");
            input.type = definition.type === "integer"
                ? "number"
                : (definition.type === "password" ? "password" : "text");
            if (fieldType === "boolean") input.type = "checkbox";
            if (fieldType === "integer") input.step = "1";
            if (fieldType === "boolean") {
                field.classList.add("mcp-tool-field--boolean");
                input.setAttribute("role", "switch");
                input.checked = initialValue === true
                    || String(initialValue).toLowerCase() === "true";
            }
        }
        input.id = inputId;
        input.setAttribute("data-mcp-tool-setting", key);
        if (
            fieldType !== "boolean"
            && initialValue !== undefined
            && initialValue !== null
        ) {
            input.value = String(initialValue);
        }
        if (
            definition.type === "password"
            && savedMcpSecretFields.has(`${source}::${name}::${key}`)
        ) input.placeholder = "Saved password";
        input.required = definition.required === true;
        if (input instanceof HTMLSelectElement) {
            const selectShell = document.createElement("div");
            selectShell.className = "select-shell mcp-tool-select-shell";
            selectShell.appendChild(input);
            field.append(label, selectShell);
        } else {
            field.append(label, input);
        }
        return field;
    };

    const createMcpConnectionField = (name, key, labelText, type, value) => {
        const field = document.createElement("div");
        field.className = `field-group mcp-connection-field mcp-connection-field--${key}`;
        const inputId = `mcp-connection-${name}-${key}`;
        const label = document.createElement("label");
        label.setAttribute("for", inputId);
        label.textContent = labelText;
        const input = document.createElement("input");
        input.id = inputId;
        input.type = type;
        input.setAttribute("data-mcp-connection-setting", key);
        if (type === "number") {
            input.min = "1";
            input.step = "1";
            if (key === "timeout_ms") {
                input.value = String(mcpDefaultTimeoutMs);
            }
        }
        if (value !== undefined && value !== null) input.value = String(value);
        field.append(label, input);
        return field;
    };

    const renderMcpToolSetup = (name, details, accordion, definitions) => {
        const savedValues = savedMcpToolSettings.get(name) || {};
        accordion.replaceChildren();
        const connectionHeading = document.createElement("div");
        connectionHeading.className = "mcp-tool-setup-heading";
        const connectionTitle = document.createElement("strong");
        connectionTitle.textContent = "Connection settings";
        const connectionHint = document.createElement("span");
        connectionHint.textContent = "Private server launch configuration";
        connectionHeading.append(connectionTitle, connectionHint);

        const connectionGrid = document.createElement("div");
        connectionGrid.className = "mcp-connection-grid";
        const savedCommand = savedValues.command !== undefined
            ? savedValues.command
            : details.command;
        const savedArgs = savedValues.args !== undefined
            ? savedValues.args
            : (Array.isArray(details.args) ? details.args : []);
        const savedTimeout = savedValues.timeout_ms !== undefined
            ? savedValues.timeout_ms
            : details.timeout_ms;
        connectionGrid.append(
            createMcpConnectionField(
                name,
                "command",
                "Command",
                "text",
                savedCommand
            ),
            createMcpConnectionField(
                name,
                "args",
                "Args (JSON array)",
                "text",
                JSON.stringify(Array.isArray(savedArgs) ? savedArgs : [])
            ),
            createMcpConnectionField(
                name,
                "timeout_ms",
                "Timeout (ms)",
                "number",
                savedTimeout
            )
        );

        const separator = document.createElement("div");
        separator.className = "mcp-tool-setup-separator";

        accordion.append(connectionHeading, connectionGrid);
        const setupEntries = Object.entries(definitions).filter(
            ([, definition]) => definition && typeof definition === "object"
        );
        if (!setupEntries.length) return;

        const heading = document.createElement("div");
        heading.className = "mcp-tool-setup-heading";
        const title = document.createElement("strong");
        title.textContent = `${name} setup`;
        const hint = document.createElement("span");
        hint.textContent = "Service-specific settings";
        heading.append(title, hint);

        const grid = document.createElement("div");
        grid.className = "mcp-tool-setup-grid";
        setupEntries.forEach(([key, definition]) => {
            if (!definition || typeof definition !== "object") return;
            grid.appendChild(createMcpToolField(
                name,
                key,
                definition,
                savedValues,
                "external"
            ));
        });

        accordion.append(separator, heading, grid);
    };

    const loadMcpSetupDefinitions = async (name) => {
        if (mcpSetupDefinitions.has(name)) {
            return mcpSetupDefinitions.get(name);
        }
        let definitions = {};
        let cacheDefinitions = false;
        try {
            const setupUrl = toolSetupUrlTemplate.replace(
                "__SERVICE__",
                encodeURIComponent(String(name).trim().toLowerCase())
            );
            const payload = await api.request(setupUrl);
            if (payload && typeof payload === "object" && !Array.isArray(payload)) {
                definitions = payload;
                cacheDefinitions = true;
            }
        } catch (error) {
            // Fall back to the universal default schema when no service-specific
            // settings file exists. Do not cache that fallback under the service
            // name, so a schema added later is discovered without a page reload.
            if (name !== "default") {
                definitions = await loadMcpSetupDefinitions("default");
            } else {
                // Most stdio MCP services do not require service-specific settings.
            }
        }
        if (cacheDefinitions) mcpSetupDefinitions.set(name, definitions);
        return definitions;
    };

    const toggleMcpToolSetup = async (name, details, row, setupButton) => {
        let accordion = row.querySelector("[data-mcp-tool-setup]");
        if (accordion) {
            const willOpen = accordion.hidden;
            accordion.hidden = !willOpen;
            setupButton.setAttribute("aria-expanded", willOpen ? "true" : "false");
            return;
        }

        accordion = document.createElement("div");
        accordion.className = "mcp-tool-setup";
        accordion.setAttribute("data-mcp-tool-setup", name);
        const loading = document.createElement("p");
        loading.className = "mcp-tool-setup-loading";
        loading.textContent = "Reading tool setup…";
        accordion.appendChild(loading);
        row.appendChild(accordion);
        setupButton.setAttribute("aria-expanded", "true");
        const definitions = await loadMcpSetupDefinitions(name);
        renderMcpToolSetup(name, details, accordion, definitions);
    };

    const closeMcpSettings = () => {
        mcpSettingsSequence += 1;
        if (mcpSettingsModal) mcpSettingsModal.hidden = true;
    };

    const setMcpSaveBusy = (busy) => {
        if (!mcpSettingsSaveBtn) return;
        const idleIcon = mcpSettingsSaveBtn.querySelector(".mcp-save-idle-icon");
        const spinner = mcpSettingsSaveBtn.querySelector(".mcp-save-spinner");
        const label = mcpSettingsSaveBtn.querySelector("[data-mcp-save-label]");
        if (idleIcon) idleIcon.hidden = busy;
        if (spinner) spinner.hidden = !busy;
        if (label) label.textContent = busy ? "Saving…" : "Save";
        mcpSettingsSaveBtn.classList.toggle("mcp-save-button--busy", busy);
        mcpSettingsSaveBtn.setAttribute("aria-busy", busy ? "true" : "false");
        if (busy) mcpSettingsSaveBtn.disabled = true;
    };

    const setMcpRefreshBusy = (busy) => {
        if (!mcpToolsRefreshBtn) return;
        const idleIcon = mcpToolsRefreshBtn.querySelector(".mcp-refresh-idle-icon");
        const spinner = mcpToolsRefreshBtn.querySelector(".mcp-refresh-spinner");
        const label = mcpToolsRefreshBtn.querySelector("[data-mcp-refresh-label]");
        if (idleIcon) idleIcon.hidden = busy;
        if (spinner) spinner.hidden = !busy;
        if (label) label.textContent = busy ? "Refreshing…" : "Refresh";
        mcpToolsRefreshBtn.setAttribute("aria-busy", busy ? "true" : "false");
        mcpToolsRefreshBtn.disabled = busy;
    };

    const setMcpStatusCheckBusy = (busy) => {
        if (!mcpStatusCheckBtn) return;
        const idleIcon = mcpStatusCheckBtn.querySelector(
            ".mcp-status-check-idle-icon"
        );
        const spinner = mcpStatusCheckBtn.querySelector(
            ".mcp-status-check-spinner"
        );
        const label = mcpStatusCheckBtn.querySelector(
            "[data-mcp-status-check-label]"
        );
        if (idleIcon) idleIcon.hidden = busy;
        if (spinner) spinner.hidden = !busy;
        if (label) label.textContent = busy ? "Checking…" : "Status check";
        mcpStatusCheckBtn.setAttribute("aria-busy", busy ? "true" : "false");
        mcpStatusCheckBtn.disabled = busy;
    };

    const checkMcpService = async (name, row, requestSequence) => {
        const serviceSwitch = row.querySelector("[data-mcp-service-switch]");
        const statusLabel = row.querySelector("[data-mcp-service-status]");
        const spinner = row.querySelector(".mcp-service-spinner");
        const offlineTooltip = row.querySelector(".mcp-service-offline-tooltip");
        try {
            const definitions = await loadMcpSetupDefinitions(name);
            const endpointDefinition = definitions.endpoint;
            const savedSettings = savedMcpToolSettings.get(name) || {};
            if (
                endpointDefinition
                && typeof endpointDefinition === "object"
                && savedSettings.endpoint === undefined
                && Object.prototype.hasOwnProperty.call(endpointDefinition, "default")
            ) {
                savedSettings.endpoint = endpointDefinition.default;
                savedMcpToolSettings.set(name, savedSettings);
            }
            const startDefinition = definitions.dependency_start_command;
            if (
                startDefinition
                && typeof startDefinition === "object"
                && savedSettings.dependency_start_command === undefined
                && Object.prototype.hasOwnProperty.call(startDefinition, "default")
            ) {
                savedSettings.dependency_start_command = startDefinition.default;
                savedMcpToolSettings.set(name, savedSettings);
            }
            const query = new URLSearchParams({name});
            if (savedSettings.endpoint) {
                query.set("endpoint", String(savedSettings.endpoint));
            }
            if (savedSettings.timeout_ms) {
                query.set("timeout_ms", String(savedSettings.timeout_ms));
            }
            const status = await api.request(
                `/chat/mcp_status?${query.toString()}`
            );
            if (requestSequence !== mcpSettingsSequence) return;
            const online = Boolean(status && status.online);
            row.classList.toggle("mcp-service-row--offline", !online);
            row.classList.toggle("mcp-service-row--online", online);
            if (statusLabel) statusLabel.textContent = online ? "Online" : "Offline";
            if (offlineTooltip) offlineTooltip.hidden = online;
            applyCustomMcpServiceState(row, online);
        } catch (error) {
            if (requestSequence !== mcpSettingsSequence) return;
            row.classList.add("mcp-service-row--offline");
            if (statusLabel) statusLabel.textContent = "Offline";
            if (offlineTooltip) offlineTooltip.hidden = false;
            applyCustomMcpServiceState(row, false);
        } finally {
            if (requestSequence === mcpSettingsSequence) {
                row.classList.remove("mcp-service-row--checking");
                if (spinner) spinner.hidden = true;
            }
        }
    };

    const createMcpEmptyField = (
        key,
        labelText,
        type = "text",
        required = false
    ) => {
        const field = document.createElement("div");
        field.className = `field-group mcp-empty-field mcp-empty-field--${key}`;
        const inputId = `mcp-empty-${key}`;
        const label = document.createElement("label");
        label.setAttribute("for", inputId);
        label.textContent = labelText;
        const input = document.createElement("input");
        input.id = inputId;
        input.type = type;
        input.required = required;
        input.setAttribute("data-mcp-custom-setting", key);
        if (key === "name") {
            input.pattern = "[A-Za-z0-9_.-]+";
            input.title = "Use letters, numbers, dots, underscores, or hyphens.";
        }
        if (type === "number") {
            input.min = "1";
            input.step = "1";
        }
        field.append(label, input);
        return field;
    };

    const llamaToolDefinition = (tool) => {
        const definition = tool && tool.definition;
        return definition && definition.function && typeof definition.function === "object"
            ? definition.function
            : {};
    };

    const llamaToolName = (tool) => {
        const definition = llamaToolDefinition(tool);
        return String((tool && tool.tool) || definition.name || "").trim();
    };

    const llamaToolDisplayName = (serviceName, toolName) => {
        const prefix = `${serviceName}_`;
        return toolName.startsWith(prefix) && toolName.length > prefix.length
            ? toolName.slice(prefix.length)
            : toolName;
    };

    const llamaToolServiceName = (tool) => {
        const definition = llamaToolDefinition(tool);
        const explicitName = [
            tool && tool.mcp_server,
            tool && tool.mcp_service,
            tool && tool.server,
            tool && tool.service,
            definition.mcp_server,
            definition.mcp_service,
        ].find((value) => typeof value === "string" && value.trim());
        if (explicitName) return explicitName.trim();
        const toolName = llamaToolName(tool);
        const separator = toolName.indexOf("_");
        return separator > 0 ? toolName.slice(0, separator) : toolName;
    };

    const llamaServiceSetupUrl = (serviceName) => toolSetupUrlTemplate.replace(
        "__SERVICE__",
        encodeURIComponent(serviceName)
    );

    const groupLlamaManagedTools = (entries) => {
        const groups = new Map();
        entries.forEach((entry) => {
            const serviceName = llamaToolServiceName(entry.tool);
            if (!groups.has(serviceName)) groups.set(serviceName, []);
            groups.get(serviceName).push(entry);
        });
        return groups;
    };

    const persistKnownLlamaTools = () => {
        try {
            window.localStorage.setItem(
                knownLlamaToolsStorageKey,
                JSON.stringify(Array.from(knownLlamaTools.values()))
            );
        } catch (error) {
            // The live list remains available for this page when storage is blocked.
        }
    };

    const toggleLlamaAccordion = (button, content) => {
        const willOpen = content.hidden;
        content.hidden = !willOpen;
        button.setAttribute("aria-expanded", willOpen ? "true" : "false");
    };

    const llamaServiceEndpoint = (serviceName, definitions) => {
        const saved = savedLlamaServiceSettings.get(serviceName) || {};
        const endpointDefinition = definitions && definitions.endpoint;
        return String(
            saved.endpoint
            || (endpointDefinition && endpointDefinition.default)
            || ""
        ).trim();
    };

    const mcpEndpointTestDefinition = (definitions) => {
        const testDefinition = definitions && definitions.test;
        if (
            !testDefinition
            || typeof testDefinition !== "object"
            || String(testDefinition.type || "").toLowerCase() !== "button"
        ) return null;
        const accessKey = String(testDefinition.access_key || "").trim();
        return accessKey && definitions[accessKey] ? testDefinition : null;
    };

    const checkLlamaManagedService = async (serviceName, definitions) => {
        const testDefinition = mcpEndpointTestDefinition(definitions);
        if (!testDefinition) return {online: true, status_code: null};
        const settings = {
            ...(savedLlamaServiceSettings.get(serviceName) || {}),
            [testDefinition.access_key]: llamaServiceEndpoint(
                serviceName,
                definitions
            ),
            timeout_ms: 3000,
        };
        return api.json(mcpEndpointTestUrl, {
            method: "POST",
            body: {
                source: "llama_service",
                service: serviceName,
                access_key: testDefinition.access_key,
                settings,
            },
        });
    };

    const applyLlamaServiceOnlineState = (service, online) => {
        service.classList.toggle("llama-managed-service--offline", !online);
        service.setAttribute("data-llama-service-online", online ? "true" : "false");
        const serviceSwitch = service.querySelector(
            "[data-llama-managed-service-switch]"
        );
        const serviceEnabled = Boolean(savedLlamaServiceStates.get(
            service.getAttribute("data-llama-managed-service")
        ));
        if (serviceSwitch) {
            serviceSwitch.disabled = !online;
            setMcpSwitch(serviceSwitch, online && serviceEnabled);
        }
        service.querySelectorAll("[data-llama-managed-tool-switch]").forEach(
            (toolSwitch) => {
                const row = toolSwitch.closest(".llama-managed-tool-row");
                const removed = row?.classList.contains(
                    "llama-managed-tool-row--removed"
                );
                const available = online && !removed;
                toolSwitch.setAttribute(
                    "data-llama-tool-available",
                    available ? "true" : "false"
                );
                toolSwitch.disabled = !available || !serviceEnabled;
                const toolName = toolSwitch.getAttribute(
                    "data-llama-managed-tool-switch"
                );
                setMcpSwitch(
                    toolSwitch,
                    available && Boolean(savedLlamaToolStates.get(toolName))
                );
            }
        );
    };

    const updateLlamaServiceAvailability = async (
        serviceName,
        service,
        definitions,
        providerOnline,
        servicePresent,
        providerName
    ) => {
        const status = service.querySelector("[data-llama-managed-service-status]");
        let online = false;
        if (!providerOnline) {
            status.textContent = `${providerName} offline`;
        } else if (!servicePresent) {
            status.textContent = "Service removed";
        } else {
            status.textContent = "Checking API…";
            try {
                const result = await checkLlamaManagedService(serviceName, definitions);
                online = Boolean(result && result.online);
                status.textContent = online ? "Online" : "Offline";
            } catch (error) {
                status.textContent = "Offline";
            }
        }
        applyLlamaServiceOnlineState(service, online);
        return online;
    };

    const renderLlamaServiceDefaults = (
        serviceName,
        accordion,
        definitions
    ) => {
        const supportedDefinitions = Object.entries(definitions || {}).filter(
            ([, fieldDefinition]) => fieldDefinition && typeof fieldDefinition === "object"
        );
        const savedValues = savedLlamaServiceSettings.get(serviceName) || {};
        accordion.replaceChildren();

        const heading = document.createElement("div");
        heading.className = "llama-managed-defaults-heading";
        const title = document.createElement("strong");
        title.textContent = `${serviceName} defaults`;
        const managedBadge = document.createElement("span");
        const providerName = accordion.closest("[data-mcp-provider]")
            ?.getAttribute("data-mcp-provider") || "provider";
        managedBadge.textContent = `Managed by ${providerName}`;
        heading.append(title, managedBadge);

        const hint = document.createElement("p");
        hint.className = "field-hint llama-managed-defaults-hint";
        hint.textContent = supportedDefinitions.length
            ? "Shared defaults are used only by tools that support each argument. Model-provided values take priority."
            : "No configurable defaults are defined for this MCP service.";

        const grid = document.createElement("div");
        grid.className = "mcp-tool-setup-grid llama-managed-defaults-grid";
        supportedDefinitions.forEach(([key, fieldDefinition]) => {
            grid.appendChild(createMcpToolField(
                serviceName,
                key,
                fieldDefinition,
                savedValues,
                "llama_service"
            ));
        });

        accordion.append(heading, hint, grid);
    };

    const toggleLlamaServiceDefaults = (
        serviceName,
        service,
        setupButton,
        definitions
    ) => {
        let accordion = service.querySelector("[data-llama-managed-defaults]");
        if (accordion) {
            toggleLlamaAccordion(setupButton, accordion);
            return;
        }
        accordion = document.createElement("div");
        accordion.className = "llama-managed-defaults";
        accordion.setAttribute("data-llama-managed-defaults", serviceName);
        const toolList = service.querySelector(".llama-managed-service-tools");
        service.insertBefore(accordion, toolList);
        setupButton.setAttribute("aria-expanded", "true");
        renderLlamaServiceDefaults(
            serviceName,
            accordion,
            definitions
        );
    };

    const createLlamaManagedToolRow = (serviceName, entry, providerOnline) => {
        const tool = entry.tool;
        const removed = Boolean(entry.removed);
        const toolName = llamaToolName(tool);
        const definition = llamaToolDefinition(tool);
        const row = document.createElement("div");
        row.className = "llama-managed-tool-row";
        row.classList.toggle("llama-managed-tool-row--removed", removed);

        const identity = document.createElement("div");
        identity.className = "llama-managed-tool-identity";
        const name = createMcpName(
            toolName,
            llamaToolDisplayName(serviceName, toolName)
        );
        const description = document.createElement("span");
        description.textContent = removed
            ? "This previously discovered tool is no longer available."
            : definition.description || "No description available.";
        identity.append(name, description);

        const toolSwitch = document.createElement("button");
        toolSwitch.type = "button";
        toolSwitch.className = "chat-toggle-switch llama-managed-tool-switch";
        toolSwitch.setAttribute("data-llama-managed-tool-switch", toolName);
        toolSwitch.setAttribute("role", "switch");
        toolSwitch.setAttribute("aria-label", `Enable ${toolName}`);
        toolSwitch.disabled = removed || !providerOnline;
        setMcpSwitch(
            toolSwitch,
            !toolSwitch.disabled && Boolean(savedLlamaToolStates.get(toolName))
        );
        const track = document.createElement("span");
        track.className = "chat-toggle-switch-track";
        track.setAttribute("aria-hidden", "true");
        const knob = document.createElement("span");
        knob.className = "chat-toggle-switch-knob";
        track.appendChild(knob);
        toolSwitch.appendChild(track);
        toolSwitch.addEventListener("click", () => {
            const enabled = toolSwitch.getAttribute("aria-checked") !== "true";
            setMcpSwitch(
                toolSwitch,
                enabled
            );
            savedLlamaToolStates.set(toolName, enabled);
        });
        row.append(identity, toolSwitch);
        return row;
    };

    const createLlamaManagedService = async (
        serviceName,
        entries,
        providerOnline,
        providerName,
        checkAvailability
    ) => {
        const servicePresent = entries.some((entry) => !entry.removed);
        const service = document.createElement("section");
        service.className = "llama-managed-service";
        service.setAttribute("data-llama-managed-service", serviceName);
        service.setAttribute("data-llama-provider-online", providerOnline ? "true" : "false");
        service.setAttribute("data-llama-service-present", servicePresent ? "true" : "false");
        service.setAttribute("data-mcp-provider", providerName);

        const header = document.createElement("div");
        header.className = "llama-managed-service-heading";
        const identity = document.createElement("div");
        const name = createMcpName(serviceName);
        const sourceBadge = document.createElement("span");
        sourceBadge.className = "mcp-source-badge mcp-source-badge--llama";
        sourceBadge.textContent = providerName;
        sourceBadge.title = `Tools supplied by the active ${providerName} provider`;
        const count = document.createElement("span");
        const activeCount = entries.filter((entry) => !entry.removed).length;
        const removedCount = entries.length - activeCount;
        count.textContent = `${activeCount} ${activeCount === 1 ? "tool" : "tools"}`;
        if (removedCount) count.textContent += ` · ${removedCount} removed`;
        identity.append(name, sourceBadge, count);

        const controls = document.createElement("div");
        controls.className = "llama-managed-service-controls";
        const status = document.createElement("span");
        status.className = "llama-managed-service-status";
        status.setAttribute("data-llama-managed-service-status", "");
        status.textContent = checkAvailability ? "Checking API…" : "Disabled";
        controls.appendChild(status);

        const serviceSwitch = document.createElement("button");
        serviceSwitch.type = "button";
        serviceSwitch.className = "chat-toggle-switch llama-managed-service-switch";
        serviceSwitch.setAttribute("data-llama-managed-service-switch", serviceName);
        serviceSwitch.setAttribute("role", "switch");
        serviceSwitch.setAttribute("aria-label", `Enable all ${serviceName} tools`);
        setMcpSwitch(
            serviceSwitch,
            Boolean(savedLlamaServiceStates.get(serviceName))
        );
        const serviceTrack = document.createElement("span");
        serviceTrack.className = "chat-toggle-switch-track";
        serviceTrack.setAttribute("aria-hidden", "true");
        const serviceKnob = document.createElement("span");
        serviceKnob.className = "chat-toggle-switch-knob";
        serviceTrack.appendChild(serviceKnob);
        serviceSwitch.appendChild(serviceTrack);
        serviceSwitch.addEventListener("click", () => {
            if (serviceSwitch.disabled) return;
            const enabled = serviceSwitch.getAttribute("aria-checked") !== "true";
            setMcpSwitch(serviceSwitch, enabled);
            savedLlamaServiceStates.set(serviceName, enabled);
            service.querySelectorAll("[data-llama-managed-tool-switch]").forEach(
                (toolSwitch) => {
                    const available = toolSwitch.getAttribute(
                        "data-llama-tool-available"
                    ) === "true";
                    toolSwitch.disabled = !available || !enabled;
                }
            );
        });
        controls.appendChild(serviceSwitch);

        let definitions = {};
        try {
            definitions = await api.request(llamaServiceSetupUrl(serviceName));
            const savedSettings = savedLlamaServiceSettings.get(serviceName) || {};
            Object.entries(definitions).forEach(([key, definition]) => {
                if (
                    definition
                    && typeof definition === "object"
                    && Object.prototype.hasOwnProperty.call(definition, "default")
                    && !Object.prototype.hasOwnProperty.call(savedSettings, key)
                ) {
                    savedSettings[key] = definition.default;
                }
            });
            savedLlamaServiceSettings.set(serviceName, savedSettings);
            const setupButton = document.createElement("button");
            setupButton.type = "button";
            setupButton.className = "mcp-service-setup-icon llama-managed-setup-icon";
            setupButton.setAttribute("aria-label", `Set shared defaults for ${serviceName}`);
            setupButton.setAttribute("aria-expanded", "false");
            setupButton.title = `Configure ${serviceName}`;
            setupButton.textContent = "⚙";
            setupButton.addEventListener("click", () => {
                toggleLlamaServiceDefaults(
                    serviceName,
                    service,
                    setupButton,
                    definitions
                );
            });
            controls.appendChild(setupButton);
        } catch (error) {
            // Service-specific configuration is optional.
        }

        const toolList = document.createElement("div");
        toolList.className = "llama-managed-service-tools";
        toolList.hidden = true;
        entries.forEach((entry) => {
            toolList.appendChild(createLlamaManagedToolRow(
                serviceName,
                entry,
                providerOnline
            ));
        });
        const expandButton = document.createElement("button");
        expandButton.type = "button";
        expandButton.className = "llama-managed-expand";
        expandButton.setAttribute("aria-label", `Show tools for ${serviceName}`);
        expandButton.setAttribute("aria-expanded", "false");
        expandButton.textContent = "▼";
        expandButton.addEventListener("click", () => {
            toggleLlamaAccordion(expandButton, toolList);
        });
        controls.appendChild(expandButton);
        header.append(identity, controls);
        service.append(header, toolList);
        if (checkAvailability) {
            await updateLlamaServiceAvailability(
                serviceName,
                service,
                definitions,
                providerOnline,
                servicePresent,
                providerName
            );
        } else {
            service.setAttribute("data-llama-service-online", "unchecked");
            serviceSwitch.disabled = !servicePresent;
            setMcpSwitch(serviceSwitch, false);
            service.querySelectorAll("[data-llama-managed-tool-switch]").forEach(
                (toolSwitch) => {
                    const removed = toolSwitch.closest(".llama-managed-tool-row")
                        ?.classList.contains("llama-managed-tool-row--removed");
                    toolSwitch.setAttribute(
                        "data-llama-tool-available",
                        removed ? "false" : "true"
                    );
                    toolSwitch.disabled = true;
                }
            );
        }
        return service;
    };

    const renderLlamaManagedTools = async (
        requestSequence,
        target,
        providerGroup
    ) => {
        const provider = "llama.cpp";

        const loading = document.createElement("p");
        loading.className = "mcp-settings-loading llama-managed-loading";
        loading.textContent = `Checking ${provider} managed services…`;
        target.appendChild(loading);

        try {
            const payload = await api.request(llamaManagedToolsUrl);
            if (requestSequence !== mcpSettingsSequence) return 0;
            const providerOnline = Boolean(payload && payload.online);
            const tools = Array.isArray(payload && payload.tools)
                ? payload.tools.filter(
                    (tool) => tool && tool.type === "mcp" && llamaToolName(tool)
                )
                : [];
            providerGroup?.setStatus(
                providerOnline && tools.length ? "" : "Offline",
                "offline"
            );
            const currentNames = new Set(tools.map(llamaToolName));
            tools.forEach((tool) => knownLlamaTools.set(llamaToolName(tool), tool));
            if (providerOnline) persistKnownLlamaTools();
            const entries = tools.map((tool) => ({tool, removed: false}));
            knownLlamaTools.forEach((tool, toolName) => {
                if (providerOnline && !currentNames.has(toolName)) {
                    entries.push({tool, removed: true});
                } else if (!providerOnline && !currentNames.has(toolName)) {
                    entries.push({tool, removed: false});
                }
            });
            const groups = groupLlamaManagedTools(entries);
            if (!groups.size) {
                const notice = document.createElement("div");
                notice.className = "llama-managed-status-row";
                const title = document.createElement("strong");
                title.textContent = `${provider} managed services`;
                const status = document.createElement("span");
                status.textContent = !payload.configured
                    ? "Not configured"
                    : providerOnline ? "No tools" : "Server offline";
                notice.append(title, status);
                loading.replaceWith(notice);
                return 0;
            }
            const services = await Promise.all(
                Array.from(groups, ([serviceName, serviceEntries]) => (
                    createLlamaManagedService(
                        serviceName,
                        serviceEntries,
                        providerOnline,
                        provider,
                        Boolean(savedLlamaServiceStates.get(serviceName))
                    )
                ))
            );
            if (requestSequence !== mcpSettingsSequence) return 0;
            loading.replaceWith(...services);
            return providerOnline ? tools.length : 0;
        } catch (error) {
            if (requestSequence !== mcpSettingsSequence) return 0;
            providerGroup?.setStatus("Offline", "offline");
            const notice = document.createElement("div");
            notice.className = "llama-managed-status-row";
            const title = document.createElement("strong");
            title.textContent = `${provider} managed services`;
            const status = document.createElement("span");
            status.textContent = "Check failed";
            notice.append(title, status);
            loading.replaceWith(notice);
            return 0;
        }
    };

    const renderMcpImportPanel = (config, requestSequence, target) => {
        if (!config || !config.opencode_import_available) return;
        const importPanel = document.createElement("section");
        importPanel.className = "mcp-import-panel";
        const importCopy = document.createElement("div");
        const importTitle = document.createElement("strong");
        importTitle.textContent = "OpenCode MCP settings found";
        const importHint = document.createElement("span");
        const names = Array.isArray(config.opencode_server_names)
            ? config.opencode_server_names.join(", ")
            : "";
        importHint.textContent = names
            ? `Available: ${names}`
            : "Import the available local MCP servers.";
        importCopy.append(importTitle, importHint);
        const importButton = document.createElement("button");
        importButton.type = "button";
        importButton.className = "modal-save-button mcp-import-button";
        importButton.textContent = "Import from OpenCode";
        importButton.addEventListener("click", async () => {
            importButton.disabled = true;
            try {
                await api.json(mcpImportUrl, {method: "POST"});
                if (requestSequence === mcpSettingsSequence) {
                    await openMcpSettings();
                }
            } catch (error) {
                importHint.textContent = String(error);
                importPanel.classList.add("mcp-import-panel--error");
                importButton.disabled = false;
            }
        });
        importPanel.append(importCopy, importButton);
        target.appendChild(importPanel);
    };

    const renderMcpCustomForm = (definitions, requestSequence, target) => {
        const form = document.createElement("section");
        form.className = "mcp-custom-server";
        const heading = document.createElement("div");
        heading.className = "mcp-custom-server-heading";
        const title = document.createElement("strong");
        title.textContent = "Add new custom MCP service";
        const hint = document.createElement("span");
        hint.textContent = "Saved privately to services/custom_mcp.json.";
        heading.append(title, hint);
        const grid = document.createElement("div");
        grid.className = "mcp-custom-server-grid";
        grid.append(
            createMcpEmptyField("name", "Name", "text", true),
            createMcpEmptyField("timeout_ms", "Timeout (ms)", "number"),
            createMcpEmptyField("command", "Command", "text", true),
            createMcpEmptyField("args", "Args (JSON array)", "text", true)
        );

        const setup = document.createElement("div");
        setup.className = "mcp-custom-tool-setup";
        setup.setAttribute("data-mcp-custom-tool-setup", "default");
        const setupHeading = document.createElement("div");
        setupHeading.className = "mcp-tool-setup-heading";
        const setupTitle = document.createElement("strong");
        setupTitle.textContent = "Default setup";
        const setupHint = document.createElement("span");
        setupHint.textContent = "Service-specific settings";
        setupHeading.append(setupTitle, setupHint);
        const setupGrid = document.createElement("div");
        setupGrid.className = "mcp-tool-setup-grid";
        setup.append(setupHeading, setupGrid);

        let setupRequestSequence = 0;
        const renderCustomSetup = (
            schemaName,
            displayName,
            setupDefinitions,
            savedValues = {}
        ) => {
            setup.setAttribute("data-mcp-custom-tool-setup", schemaName);
            setupTitle.textContent = schemaName === "default"
                ? "Default setup"
                : `${displayName} setup`;
            setupGrid.replaceChildren();
            Object.entries(setupDefinitions || {}).forEach(
                ([key, definition]) => {
                    if (!definition || typeof definition !== "object") return;
                    const field = createMcpToolField(
                        schemaName,
                        key,
                        definition,
                        savedValues,
                        "external"
                    );
                    const testButton = field.querySelector(
                        "[data-mcp-endpoint-test]"
                    );
                    if (testButton) {
                        testButton.disabled = true;
                        testButton.title = (
                            "Save the service before testing access."
                        );
                    }
                    setupGrid.appendChild(field);
                }
            );
        };
        renderCustomSetup("default", "default", definitions);

        const refreshCustomSetup = async () => {
            const nameInput = form.querySelector(
                '[data-mcp-custom-setting="name"]'
            );
            const displayName = nameInput?.value?.trim() || "";
            const schemaName = displayName.toLowerCase() || "default";
            if (
                setup.getAttribute("data-mcp-custom-tool-setup")
                === schemaName
            ) return;

            const savedValues = readMcpAccordionSettings(setup, {});
            const currentSequence = ++setupRequestSequence;
            setupHint.textContent = "Reading service-specific settings…";
            const setupDefinitions = await loadMcpSetupDefinitions(schemaName);
            if (currentSequence !== setupRequestSequence) return;
            const usesDefault = schemaName !== "default"
                && setupDefinitions === definitions;
            renderCustomSetup(
                schemaName,
                usesDefault ? "default" : displayName,
                setupDefinitions,
                savedValues
            );
            setupTitle.textContent = usesDefault
                ? "Default setup"
                : `${displayName} setup`;
            setupHint.textContent = "Service-specific settings";
        };
        form.refreshCustomSetup = refreshCustomSetup;
        grid.querySelector('[data-mcp-custom-setting="name"]')
            ?.addEventListener("change", () => {
                refreshCustomSetup().catch((error) => {
                    setupHint.textContent = `Could not read setup: ${error}`;
                });
            });

        const addButton = document.createElement("button");
        addButton.type = "button";
        addButton.className = "modal-save-button mcp-add-tool-button";
        addButton.textContent = "Add tool";
        addButton.addEventListener("click", async () => {
            addButton.disabled = true;
            addButton.textContent = "Checking…";
            try {
                await refreshCustomSetup();
                const saved = await saveFirstCustomMcpService(form, true);
                if (!saved) return;
                if (requestSequence !== mcpSettingsSequence) return;
                savedMcpStates.set(saved.name, false);
                savedMcpToolSettings.set(saved.name, saved.settings);
                const row = createMcpServiceRow(saved.name, saved.server);
                row.classList.remove(
                    "mcp-service-row--checking",
                    "mcp-service-row--offline"
                );
                row.classList.add("mcp-service-row--online");
                const status = row.querySelector("[data-mcp-service-status]");
                if (status) status.textContent = "Online";
                const spinner = row.querySelector(".mcp-service-spinner");
                if (spinner) spinner.hidden = true;
                const offlineTooltip = row.querySelector(
                    ".mcp-service-offline-tooltip"
                );
                if (offlineTooltip) offlineTooltip.hidden = true;
                applyCustomMcpServiceState(row, true);
                form.before(row);
                form.remove();
                renderMcpCustomForm(definitions, requestSequence, target);
            } catch (error) {
                window.alert(String(error));
            } finally {
                if (addButton.isConnected) {
                    addButton.disabled = false;
                    addButton.textContent = "Add tool";
                }
            }
        });
        form.append(heading, grid, setup, addButton);
        target.appendChild(form);
    };

    const openMcpSettings = async () => {
        if (!mcpSettingsModal || !mcpServiceList) return;
        const requestSequence = ++mcpSettingsSequence;
        mcpSettingsModal.hidden = false;
        mcpServiceList.replaceChildren();
        setMcpSaveBusy(false);
        setMcpRefreshBusy(false);
        setMcpStatusCheckBusy(false);
        if (mcpSettingsSaveBtn) mcpSettingsSaveBtn.disabled = true;
        if (mcpStatusCheckBtn) mcpStatusCheckBtn.disabled = true;
        const loading = document.createElement("p");
        loading.className = "mcp-settings-loading";
        loading.textContent = "Reading MCP services…";
        mcpServiceList.appendChild(loading);
        try {
            const [config, persistedSettings] = await Promise.all([
                api.request(mcpConfigUrl),
                api.request(mcpSettingsUrl),
                loadMcpToolHelp(),
            ]);
            if (requestSequence !== mcpSettingsSequence) return;
            const configuredTimeout = Number(config?.default_timeout_ms);
            mcpDefaultTimeoutMs = Number.isInteger(configuredTimeout)
                && configuredTimeout > 0
                ? configuredTimeout
                : 10000;
            hydrateMcpSettings(persistedSettings);
            const servers = config && config.mcpServers;
            const names = servers && typeof servers === "object"
                ? Object.keys(servers)
                : [];
            mcpServiceList.replaceChildren();
            const groups = {
                opencode: createMcpProviderAccordion("opencode", "OpenCode"),
                custom: createMcpProviderAccordion("custom", "Custom"),
                llama: createMcpProviderAccordion("llama", "llama.cpp"),
            };
            mcpServiceList.append(
                groups.opencode.section,
                groups.custom.section,
                groups.llama.section
            );
            const managedTools = renderLlamaManagedTools(
                requestSequence,
                groups.llama.content,
                groups.llama
            );
            renderMcpImportPanel(
                config || {},
                requestSequence,
                groups.opencode.content
            );
            const checks = names.map((name) => {
                const row = createMcpServiceRow(name, servers[name]);
                const target = servers[name]?.source === "opencode"
                    ? groups.opencode.content
                    : groups.custom.content;
                target.appendChild(row);
                if (!savedMcpStates.get(name)) {
                    showSavedDisabledMcpService(row);
                    return Promise.resolve();
                }
                return checkMcpService(name, row, requestSequence);
            });
            await Promise.all([...checks, managedTools]);
            const defaultSetupDefinitions = await loadMcpSetupDefinitions("default");
            if (requestSequence !== mcpSettingsSequence) return;
            renderMcpCustomForm(
                defaultSetupDefinitions,
                requestSequence,
                groups.custom.content
            );
            if (
                requestSequence === mcpSettingsSequence
                && mcpSettingsSaveBtn
            ) {
                mcpSettingsSaveBtn.disabled = false;
            }
            if (
                requestSequence === mcpSettingsSequence
                && mcpStatusCheckBtn
            ) {
                mcpStatusCheckBtn.disabled = false;
            }
        } catch (error) {
            if (requestSequence !== mcpSettingsSequence) return;
            loading.textContent = `Could not read MCP settings: ${error}`;
            mcpServiceList.replaceChildren(loading);
        }
    };

    const readMcpAccordionSettings = (accordion, initialSettings) => {
        const settings = {...initialSettings};
        accordion?.querySelectorAll("[data-mcp-multiple-setting]").forEach(
            (group) => {
                const key = group.getAttribute("data-mcp-multiple-setting");
                if (!key) return;
                settings[key] = Array.from(
                    group.querySelectorAll('input[type="checkbox"]:checked')
                ).map((input) => input.value);
            }
        );
        accordion?.querySelectorAll("[data-mcp-tool-setting]").forEach((input) => {
            const key = input.getAttribute("data-mcp-tool-setting");
            if (!key) return;
            settings[key] = input.type === "checkbox"
                ? input.checked
                : (input.type === "number" && input.value !== ""
                    ? Number.parseInt(input.value, 10)
                    : input.value);
        });
        accordion?.querySelectorAll("[data-mcp-connection-setting]").forEach((input) => {
            const key = input.getAttribute("data-mcp-connection-setting");
            if (!key) return;
            if (key === "args") {
                let args;
                try {
                    args = JSON.parse(input.value || "");
                } catch (error) {
                    args = null;
                }
                if (!Array.isArray(args) || args.some((value) => typeof value !== "string")) {
                    throw new Error("Args must be a JSON array of strings.");
                }
                settings.args = args;
            } else if (input.type === "number") {
                const value = input.value.trim();
                const parsed = value === "" ? null : Number(value);
                if (parsed !== null && (!Number.isInteger(parsed) || parsed < 1)) {
                    throw new Error("Timeout must be a positive integer.");
                }
                settings[key] = parsed;
            } else {
                settings[key] = input.value.trim();
            }
        });
        return settings;
    };

    const saveFirstCustomMcpService = async (
        customForm = null,
        requireEntry = false
    ) => {
        const form = customForm
            || mcpServiceList?.querySelector(".mcp-custom-server");
        if (!form) return;
        if (typeof form.refreshCustomSetup === "function") {
            await form.refreshCustomSetup();
        }
        if (requireEntry) {
            const invalidInput = Array.from(
                form.querySelectorAll("input, select")
            ).find((input) => !input.checkValidity());
            if (invalidInput) {
                invalidInput.reportValidity();
                return null;
            }
        }
        const value = (key) => form.querySelector(
            `[data-mcp-custom-setting="${key}"]`
        )?.value?.trim() || "";
        const fields = {
            name: value("name"),
            command: value("command"),
            args: value("args"),
            timeout: value("timeout_ms"),
        };
        if (!Object.values(fields).some(Boolean)) return;
        let args;
        try {
            args = JSON.parse(fields.args);
        } catch (error) {
            args = null;
        }
        if (!Array.isArray(args) || args.some((item) => typeof item !== "string")) {
            throw new Error("Args must be a JSON array of strings.");
        }
        const timeout = fields.timeout === "" ? null : Number(fields.timeout);
        if (timeout !== null && (!Number.isInteger(timeout) || timeout < 1)) {
            throw new Error("Timeout must be a positive integer.");
        }
        const settings = readMcpAccordionSettings(
            form.querySelector("[data-mcp-custom-tool-setup]"),
            {}
        );
        const response = await api.json(mcpServerSaveUrl, {
            method: "POST",
            body: {
                name: fields.name,
                command: fields.command,
                args,
                timeout_ms: timeout,
                settings,
            },
        });
        return {
            name: fields.name,
            server: response.server,
            availability: response.availability,
            settings,
        };
    };

    const collectMcpSettingsRecords = () => {
        const records = [];
        mcpServiceList?.querySelectorAll("[data-mcp-service-row]").forEach((row) => {
            const serviceSwitch = row.querySelector("[data-mcp-service-switch]");
            const name = serviceSwitch?.getAttribute("data-mcp-service-switch");
            if (!name) return;
            const settings = readMcpAccordionSettings(
                row.querySelector("[data-mcp-tool-setup]"),
                savedMcpToolSettings.get(name) || {}
            );
            savedMcpStates.set(name, serviceSwitch.getAttribute("aria-checked") === "true");
            savedMcpToolSettings.set(name, settings);
            records.push({
                source: "external",
                service: name,
                tool: "",
                enabled: savedMcpStates.get(name),
                settings,
            });
            row.querySelectorAll("[data-custom-mcp-tool-switch]").forEach(
                (toolSwitch) => {
                    if (
                        toolSwitch.getAttribute("data-custom-tool-available")
                        !== "true"
                    ) return;
                    const toolName = toolSwitch.getAttribute(
                        "data-custom-mcp-tool-switch"
                    );
                    if (!toolName) return;
                    const stateKey = customMcpToolKey(name, toolName);
                    const enabled = Boolean(savedCustomToolStates.get(stateKey));
                    savedCustomToolStates.set(stateKey, enabled);
                    records.push({
                        source: "external_tool",
                        service: name,
                        tool: toolName,
                        enabled,
                        settings: {},
                    });
                }
            );
        });

        mcpServiceList?.querySelectorAll("[data-llama-managed-service]").forEach(
            (service) => {
                const serviceName = service.getAttribute("data-llama-managed-service");
                const servicePresent = service.getAttribute("data-llama-service-present") === "true";
                if (
                    !serviceName
                    || !servicePresent
                ) return;
                const settings = readMcpAccordionSettings(
                    service.querySelector("[data-llama-managed-defaults]"),
                    savedLlamaServiceSettings.get(serviceName) || {}
                );
                savedLlamaServiceSettings.set(serviceName, settings);
                records.push({
                    source: "llama_service",
                    service: serviceName,
                    tool: "",
                    enabled: service.querySelector(
                        "[data-llama-managed-service-switch]"
                    )?.getAttribute("aria-checked") === "true",
                    settings,
                });
                service.querySelectorAll("[data-llama-managed-tool-switch]").forEach(
                    (toolSwitch) => {
                        if (
                            toolSwitch.getAttribute("data-llama-tool-available")
                            !== "true"
                        ) return;
                        const toolName = toolSwitch.getAttribute(
                            "data-llama-managed-tool-switch"
                        );
                        if (!toolName) return;
                        const enabled = Boolean(savedLlamaToolStates.get(toolName));
                        savedLlamaToolStates.set(toolName, enabled);
                        records.push({
                            source: "llama_tool",
                            service: serviceName,
                            tool: toolName,
                            enabled,
                            settings: {},
                        });
                    }
                );
            }
        );
        return records;
    };

    const saveMcpSettings = async () => {
        if (!mcpSettingsSaveBtn) return;
        setMcpSaveBusy(true);
        try {
            await saveFirstCustomMcpService();
            const records = collectMcpSettingsRecords();
            await api.json(mcpSettingsSaveUrl, {
                method: "POST",
                body: {records},
            });
            await loadToolGlobalState();
            closeMcpSettings();
        } catch (error) {
            window.alert(`MCP settings could not be saved: ${error}`);
            setMcpSaveBusy(false);
            mcpSettingsSaveBtn.disabled = false;
        }
    };

    const refreshMcpTools = async () => {
        if (!mcpToolsRefreshBtn) return;
        setMcpRefreshBusy(true);
        try {
            await api.json(mcpToolsRefreshUrl, {method: "POST"});
            await openMcpSettings();
        } catch (error) {
            window.alert(`MCP tools could not be refreshed: ${error}`);
            setMcpRefreshBusy(false);
        }
    };

    const syncMcpStatusCheckSettings = () => {
        mcpServiceList?.querySelectorAll("[data-mcp-service-row]").forEach((row) => {
            const name = row.getAttribute("data-mcp-service-row");
            if (!name) return;
            const settings = readMcpAccordionSettings(
                row.querySelector("[data-mcp-tool-setup]"),
                savedMcpToolSettings.get(name) || {}
            );
            savedMcpToolSettings.set(name, settings);
        });
        mcpServiceList?.querySelectorAll("[data-llama-managed-service]").forEach(
            (service) => {
                const name = service.getAttribute("data-llama-managed-service");
                if (!name) return;
                const settings = readMcpAccordionSettings(
                    service.querySelector("[data-llama-managed-defaults]"),
                    savedLlamaServiceSettings.get(name) || {}
                );
                savedLlamaServiceSettings.set(name, settings);
            }
        );
    };

    const checkAllMcpStatuses = async () => {
        if (!mcpStatusCheckBtn || !mcpServiceList) return;
        const requestSequence = ++mcpSettingsSequence;
        setMcpStatusCheckBusy(true);
        try {
            syncMcpStatusCheckSettings();
            const customChecks = Array.from(
                mcpServiceList.querySelectorAll("[data-mcp-service-row]")
            ).map((row) => {
                const name = row.getAttribute("data-mcp-service-row");
                if (!name) return Promise.resolve();
                row.classList.add("mcp-service-row--checking");
                row.querySelector(".mcp-service-spinner")?.removeAttribute("hidden");
                const status = row.querySelector("[data-mcp-service-status]");
                if (status) status.textContent = "Checking…";
                return checkMcpService(name, row, requestSequence);
            });
            const managedChecks = Array.from(
                mcpServiceList.querySelectorAll("[data-llama-managed-service]")
            ).map(async (service) => {
                const serviceName = service.getAttribute(
                    "data-llama-managed-service"
                );
                if (!serviceName) return;
                const definitions = await loadMcpSetupDefinitions(serviceName);
                await updateLlamaServiceAvailability(
                    serviceName,
                    service,
                    definitions,
                    service.getAttribute("data-llama-provider-online") === "true",
                    service.getAttribute("data-llama-service-present") === "true",
                    service.getAttribute("data-mcp-provider") || "provider"
                );
            });
            await Promise.all([...customChecks, ...managedChecks]);
        } catch (error) {
            window.alert(`MCP status check failed: ${error}`);
        } finally {
            if (requestSequence === mcpSettingsSequence) {
                setMcpStatusCheckBusy(false);
            }
        }
    };

    let mediaUploadsSeq = 0;

    const refreshSavedModelState = async (provider, model) => {
        const requestSeq = ++mediaUploadsSeq;
        renderMediaUploads(null);
        renderToolCapability(null);
        chatContext.setMaxTokens(null);
        sessionCtxMode = null;
        contextStatus = provider === "llama.cpp" ? "checking" : "unavailable";
        updateParameterCacheState(null);
        if (modelNctxEl) {
            modelNctxEl.textContent = "";
        }
        const isLocal = provider === "llama.cpp" || provider === "vllm";
        if (!model) {
            updateTokenUsage();
            return;
        }
        try {
            const payload = await api.request(
                `/setup_models/model_params/status?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`
            );
            if (requestSeq !== mediaUploadsSeq) return;
            renderMediaUploads(payload && payload.modalities);
            renderToolCapability(payload && payload.chat_template_caps);
            const resolvedMode = (payload && payload.ctx_mode) || null;
            chatContext.setMaxTokens(payload && payload.n_ctx);
            sessionCtxMode = resolvedMode;
            contextStatus = payload && payload.n_ctx != null ? "available" : "missing";
            if (provider === "llama.cpp") {
                updateParameterCacheState(payload && payload.state, resolvedMode);
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
            renderToolCapability(null);
            chatContext.setMaxTokens(null);
            contextStatus = "unavailable";
            updateParameterCacheState(provider === "llama.cpp" ? "missing_params" : null);
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
        void loadParameterHelp();
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
            await refreshSavedModelState(provider, model);
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
            if (mineruTimeoutInput) mineruTimeoutInput.value = String(mineruTimeout);
        }
    };
    const closeMineruSettings = () => {
        if (mineruModal) mineruModal.hidden = true;
    };
    const saveMineruSettings = async () => {
        const endpoint = mineruEndpointInput?.value?.trim() || "";
        const api_key = mineruApiKeyInput?.value?.trim() || "";
        const timeout = Number(mineruTimeoutInput?.value);
        if (!endpoint) {
            window.alert("MinerU endpoint is required.");
            return;
        }
        if (!Number.isInteger(timeout) || timeout < 1 || timeout > 30) {
            window.alert("MinerU timeout must be an integer from 1 to 30.");
            return;
        }
        if (mineruSaveBtn) mineruSaveBtn.disabled = true;
        try {
            const payload = await api.json("/chat/save_mineru_settings", {
                method: "POST",
                body: { endpoint, api_key, timeout },
            });
            mineruEndpoint = payload.endpoint || endpoint;
            mineruApiKey = payload.api_key || api_key;
            mineruTimeout = Number(payload.timeout) || timeout;
            mineruConfigured = true;
            window.CairnmarkMineruSettings = {
                endpoint: mineruEndpoint,
                api_key: mineruApiKey,
                timeout: mineruTimeout,
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

    const contextSelection = () => ({
        allPrevious: Boolean(
            historySwitch && historySwitch.getAttribute("aria-checked") === "true"
        ),
        historyLimit: historyLimitEl ? historyLimitEl.value : "",
    });

    const shouldAutoCompact = () => {
        const enabled = Boolean(
            compactSwitch && compactSwitch.getAttribute("aria-checked") === "true"
        );
        return chatContext.shouldAutoCompact(
            contextSelection(),
            enabled,
            compactRequestActive,
            autoCompactThreshold
        );
    };

    const updateAutoCompactTooltip = () => {
        const label = `Auto compact from ${autoCompactThreshold}%`;
        compactSwitch?.setAttribute("aria-label", label);
        compactSwitch?.setAttribute("title", label);
        if (compactTooltip) compactTooltip.textContent = label;
    };

    const openAutoCompactSettings = () => {
        if (!compactSettingsModal) return;
        if (compactThresholdInput) {
            compactThresholdInput.value = String(autoCompactThreshold);
        }
        compactSettingsModal.hidden = false;
        compactThresholdInput?.focus();
    };

    const closeAutoCompactSettings = () => {
        if (compactSettingsModal) compactSettingsModal.hidden = true;
    };

    const saveAutoCompactSettings = async () => {
        const threshold = Number(compactThresholdInput?.value);
        if (!Number.isInteger(threshold) || threshold < 5 || threshold > 100) {
            window.alert("Auto compact threshold must be an integer from 5 to 100.");
            return;
        }
        if (compactSettingsSaveBtn) compactSettingsSaveBtn.disabled = true;
        try {
            const payload = await api.json("/chat/save_compact_settings", {
                method: "POST",
                body: { threshold },
            });
            autoCompactThreshold = Number(payload.threshold) || threshold;
            window.CairnmarkChatCompactSettings = {
                ...(window.CairnmarkChatCompactSettings || {}),
                threshold: autoCompactThreshold,
            };
            updateAutoCompactTooltip();
            closeAutoCompactSettings();
        } catch (error) {
            window.alert(`Auto compact settings could not be saved: ${error}`);
        } finally {
            if (compactSettingsSaveBtn) compactSettingsSaveBtn.disabled = false;
        }
    };

    const updateCompactButtonVisibility = () => {
        if (!compactBtn) return;
        compactBtn.disabled = compactRequestActive
            || !chatContext.canCompact(contextSelection());
    };

    const updateTokenUsage = () => {
        if (!tokenUsageEl) return;
        const usage = chatContext.usage(contextSelection());
        if (usage.max) {
            const { used, max, percent } = usage;
            tokenUsageEl.textContent = `${used} / ${max} (${percent}%)`;
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
            if (contextStatus === "checking") {
                tokenUsageEl.textContent = "Checking saved n_ctx data…";
            } else if (contextStatus === "missing") {
                tokenUsageEl.textContent = sessionCtxMode
                    ? `n_ctx missing for: ${sessionCtxMode}`
                    : "n_ctx value missing for the current llama.cpp mode";
            } else {
                tokenUsageEl.textContent = "Context size unavailable for this model.";
            }
            tokenUsageEl.classList.remove(
                "chat-token-usage--ok",
                "chat-token-usage--warn",
                "chat-token-usage--over",
                "chat-token-usage--loading"
            );
            if (contextStatus === "checking") {
                tokenUsageEl.classList.add("chat-token-usage--loading");
            } else if (contextStatus === "missing") {
                tokenUsageEl.classList.add("chat-token-usage--warn");
            }
            if (contextBarFillEl) {
                contextBarFillEl.style.width = contextStatus === "checking" ? "100%" : "0%";
                contextBarFillEl.classList.remove(
                    "chat-context-bar-fill--ok",
                    "chat-context-bar-fill--warn",
                    "chat-context-bar-fill--over",
                    "chat-context-bar-fill--loading"
                );
                if (contextStatus === "checking") {
                    contextBarFillEl.classList.add("chat-context-bar-fill--loading");
                } else if (contextStatus === "missing") {
                    contextBarFillEl.classList.add("chat-context-bar-fill--warn");
                }
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
        if (!compactBtn || compactRequestActive) return;
        const model = modelSelect?.value || "";
        if (!model) {
            window.alert("Model is required.");
            return;
        }
        compactRequestActive = true;
        compactBtn.disabled = true;
        if (sendBtn) sendBtn.disabled = true;

        const controller = new AbortController();
        let aborted = false;
        const streamResponseContent = Boolean(
            streamResponsesSwitch
            && streamResponsesSwitch.getAttribute("aria-checked") === "true"
        );
        const loadingEl = showLoading(() => {
            aborted = true;
            controller.abort();
        }, { compacted: true, streamContent: streamResponseContent });

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
                            if (streamResponseContent) {
                                renderStreamingBubble(loadingEl, accumulated);
                            } else if (loadingEl && loadingEl.tokenCount) {
                                loadingEl.tokenCount.textContent = `${accumulated.length} chars`;
                            }
                        } else if (data.type === "done") {
                            if (streamResponseContent) {
                                renderStreamingBubble(
                                    loadingEl,
                                    accumulated,
                                    { flush: true }
                                );
                            } else if (loadingEl && loadingEl.tokenCount) {
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
                cancelStreamingBubble(loadingEl);
                if (loadingEl && loadingEl.element) loadingEl.element.remove();
                syncEmptyState();
                try { await api.request("/chat/abort", { method: "POST" }); } catch (error) {}
                return;
            }
            cancelStreamingBubble(loadingEl);
            if (loadingEl && loadingEl.element) loadingEl.element.remove();
            if (finalPayload) {
                chatContext.add({
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
                    message_id: finalPayload.message_id,
                    webpage_previews: finalPayload.webpage_previews || [],
                    capture_webpage_previews: true,
                    compacted: true,
                });
                updateTokenUsage();
            } else if (accumulated) {
                appendMessage("assistant", accumulated, { compacted: true });
            }
        } catch (error) {
            cancelStreamingBubble(loadingEl);
            if (loadingEl && loadingEl.element) loadingEl.element.remove();
            if (aborted || (error && error.name === "AbortError")) {
                if (loadingEl && loadingEl.element) loadingEl.element.remove();
                syncEmptyState();
                try { await api.request("/chat/abort", { method: "POST" }); } catch (error2) {}
                return;
            }
            window.alert(`Compact failed: ${error}`);
        } finally {
            compactRequestActive = false;
            if (compactBtn) compactBtn.disabled = false;
            updateTokenUsage();
        }
    };

    compactBtn?.addEventListener("click", handleCompact);
    toolCapabilityEl?.addEventListener("click", openMcpSettings);
    toolCapabilityEl?.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        void openToolGlobalSettings();
    });
    toolGlobalSwitch?.addEventListener("click", () => {
        setMcpSwitch(
            toolGlobalSwitch,
            toolGlobalSwitch.getAttribute("aria-checked") !== "true"
        );
    });
    toolGuidanceSwitch?.addEventListener("click", () => {
        setMcpSwitch(
            toolGuidanceSwitch,
            toolGuidanceSwitch.getAttribute("aria-checked") !== "true"
        );
    });
    toolWebpagePreviewSwitch?.addEventListener("click", () => {
        const enabled = toolWebpagePreviewSwitch.getAttribute("aria-checked") !== "true";
        setMcpSwitch(toolWebpagePreviewSwitch, enabled);
        if (toolWebpagePreviewTimeoutInput) {
            toolWebpagePreviewTimeoutInput.disabled = !enabled;
        }
    });
    toolGlobalCloseBtns.forEach((button) => {
        button.addEventListener("click", closeToolGlobalSettings);
    });
    toolGlobalSaveBtn?.addEventListener("click", saveToolGlobalSettings);
    toolGlobalSettingsModal?.addEventListener("click", (event) => {
        if (event.target === toolGlobalSettingsModal) closeToolGlobalSettings();
    });
    mcpSettingsCloseBtns.forEach((button) => {
        button.addEventListener("click", closeMcpSettings);
    });
    mcpSettingsSaveBtn?.addEventListener("click", saveMcpSettings);
    mcpToolsRefreshBtn?.addEventListener("click", refreshMcpTools);
    mcpStatusCheckBtn?.addEventListener("click", checkAllMcpStatuses);
    mcpSettingsModal?.addEventListener("click", (event) => {
        if (event.target === mcpSettingsModal) closeMcpSettings();
    });
    compactSwitch?.addEventListener("click", () => {
        const next = compactSwitch.getAttribute("aria-checked") !== "true";
        compactSwitch.setAttribute("aria-checked", next ? "true" : "false");
    });
    compactSwitch?.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        openAutoCompactSettings();
    });
    compactSettingsCloseBtns.forEach((btn) => {
        btn.addEventListener("click", closeAutoCompactSettings);
    });
    compactSettingsSaveBtn?.addEventListener("click", saveAutoCompactSettings);
    compactSettingsModal?.addEventListener("click", (event) => {
        if (event.target === compactSettingsModal) closeAutoCompactSettings();
    });
    updateAutoCompactTooltip();
    streamResponsesSwitch?.addEventListener("click", () => {
        const next = streamResponsesSwitch.getAttribute("aria-checked") !== "true";
        streamResponsesSwitch.setAttribute("aria-checked", next ? "true" : "false");
    });
    updateTokenUsage();
    sendBtn?.addEventListener("click", handleSend);
    saveBtn?.addEventListener("click", handleSave);
    clearBtn?.addEventListener("click", handleClear);
    importBtn?.addEventListener("click", handleImportChat);
    exportBtn?.addEventListener("click", handleExportChat);
    saveOpenBtn?.addEventListener("click", openSaveModal);
    saveConfirmBtn?.addEventListener("click", handleSaveChat);
    saveCloseBtns.forEach((b) => b.addEventListener("click", closeSaveModal));
    reverseImageCloseBtns.forEach((button) => {
        button.addEventListener("click", closeReverseImageModal);
    });
    reverseImageServiceBtns.forEach((button) => {
        button.addEventListener("click", () => openReverseImageProvider(button));
    });
    reverseImageModal?.addEventListener("click", (event) => {
        if (event.target === reverseImageModal) closeReverseImageModal();
    });
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

        await refreshSavedModelState(provider, model);

        const isLocal = provider === "llama.cpp" || provider === "vllm";
        if (!isLocal || !model) {
            if (moreParamsBtn) moreParamsBtn.disabled = true;
            if (moreParamsDisabledSign) moreParamsDisabledSign.hidden = false;
            updateMoreParamsSign();
            return;
        }
        if (moreParamsBtn) moreParamsBtn.disabled = false;
        if (moreParamsDisabledSign) moreParamsDisabledSign.hidden = true;
        updateMoreParamsSign();
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

    // Handle message-header actions and prompt/request-body modals (delegated).
    historyEl?.addEventListener("click", (event) => {
        const useModelButton = event.target.closest("[data-chat-use-model]");
        if (useModelButton) {
            const provider = useModelButton.getAttribute("data-provider")?.trim() || "";
            const model = useModelButton.getAttribute("data-model")?.trim() || "";
            const optionValue = `${provider}::${model}`;
            const option = [...(modelSelect?.options || [])].find(
                (item) => item.value.trim() === optionValue
            );
            if (!option) {
                window.alert(`The selected model ${model} not available on the model selector list`);
                return;
            }
            modelSelect.value = option.value;
            modelSelect.dispatchEvent(new Event("change", { bubbles: true }));
            return;
        }
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
    let modelStateInitialized = false;
    if (savedModel && modelSelect) {
        const option = [...modelSelect.options].find((o) => o.value.trim() === savedModel);
        if (option) {
            modelSelect.value = savedModel;
            modelSelect.dispatchEvent(new Event("change", { bubbles: true }));
            modelStateInitialized = true;
        }
    }

    // Keep the always-available document icon visible from first paint.
    void loadParameterHelp();
    void loadToolGlobalState();
    renderMediaUploads(null);
    document.querySelectorAll("[data-generated-document-name]").forEach((link) => {
        bindGeneratedDocumentPreview(
            link,
            link.dataset.generatedDocumentName || ""
        );
    });
    toolScopeToggle?.addEventListener("click", () => {
        setToolScopeExpanded(
            toolScopeToggle.getAttribute("aria-expanded") !== "true"
        );
    });
    document.addEventListener("click", (event) => {
        if (!toolSubserviceDropdown || toolSubserviceDropdown.hidden) return;
        const target = event.target;
        if (!(target instanceof Element)) return;
        if (
            toolSubserviceDropdown.contains(target)
            || target.closest(".chat-tool-scope-name")
        ) {
            return;
        }
        closeToolSubserviceDropdown();
    });
    toolAutomaticScopeSwitch?.addEventListener("click", () => {
        setMcpSwitch(
            toolAutomaticScopeSwitch,
            toolAutomaticScopeSwitch.getAttribute("aria-checked") !== "true"
        );
    });
    if (!modelStateInitialized) setTimeout(updateMoreParamsButtonState, 0);

    if (historyEl) {
        historyEl.scrollTop = historyEl.scrollHeight;
    }
})();
