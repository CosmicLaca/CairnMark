(() => {
    "use strict";

    const navigationListeners = new AbortController();
    document.addEventListener("cairnmark:navigation-before", () => {
        navigationListeners.abort();
    }, { once: true });

    const speedometerNeedles = {
        "very-fast": "M10 13 L17 9",
        fast: "M10 13 L15 6",
        "medium-fast": "M10 13 L12 5",
        regular: "M10 13 L8 5",
        "very-slow": "M10 13 L4 8",
    };

    const createSpeedometerIcon = (tier, tooltip = "") => {
        const needle = speedometerNeedles[tier];
        if (!needle) return null;
        const icon = document.createElement("span");
        icon.className = `model-speedometer model-speedometer--${tier}`;
        if (tooltip) {
            icon.dataset.tooltip = tooltip;
            icon.setAttribute("aria-label", tooltip);
        } else {
            icon.setAttribute("aria-hidden", "true");
        }
        icon.innerHTML = `
            <svg viewBox="0 0 20 16" aria-hidden="true" focusable="false">
                <path class="model-speedometer-dial" d="M2 13 A8 8 0 0 1 18 13"></path>
                <path class="model-speedometer-ticks" d="M3.1 10.2l1.4.5M5.5 6.5l1.1 1M10 5v1.6M14.5 6.5l-1.1 1M16.9 10.2l-1.4.5"></path>
                <path class="model-speedometer-needle" d="${needle}"></path>
                <circle cx="10" cy="13" r="1.25" fill="currentColor"></circle>
            </svg>`;
        return icon;
    };

    const createSpeedometer = (option) => {
        const tier = String(option?.dataset.speedTier || "");
        const average = Number(option?.dataset.averageTokensPerSecond);
        if (!speedometerNeedles[tier] || !Number.isFinite(average)) return null;
        return createSpeedometerIcon(
            tier,
            `Average speed: ${average.toFixed(2)} tokens/sec`,
        );
    };

    const setOptionContent = (target, option, fallback) => {
        const label = document.createElement("span");
        label.className = "searchable-select-option-label";
        label.textContent = option ? option.textContent.trim() : fallback;
        target.replaceChildren(label);
        const speedometer = createSpeedometer(option);
        if (speedometer) target.appendChild(speedometer);
    };

    class SearchableModelSelect {
        static instances = [];

        constructor(select) {
            this.select = select;
            this.wrapper = document.createElement("div");
            this.toggle = document.createElement("button");
            this.panel = document.createElement("div");
            this.search = document.createElement("input");
            this.list = document.createElement("div");
            this.providerFilter = "all";
            this.featureFilters = new Set();
            this.speedFilters = new Set();
            this.build();
            this.bind();
            this.sync();
            this.render();
        }

        build() {
            this.select.dataset.searchableReady = "true";
            this.select.classList.add("searchable-select-source");
            this.wrapper.className = "searchable-select";

            this.toggle.type = "button";
            this.toggle.className = "searchable-select-toggle";
            this.toggle.setAttribute("aria-haspopup", "listbox");
            this.toggle.setAttribute("aria-expanded", "false");

            this.panel.className = "searchable-select-panel";
            this.panel.hidden = true;
            this.search.type = "search";
            this.search.className = "searchable-select-search";
            this.search.placeholder = "Filter model names…";
            this.search.setAttribute("aria-label", "Filter model names");
            this.list.className = "searchable-select-list";
            this.list.setAttribute("role", "listbox");

            this.panel.append(this.search, this.list);
            this.wrapper.append(this.toggle, this.panel);
            this.select.insertAdjacentElement("afterend", this.wrapper);
        }

        bind() {
            this.toggle.addEventListener("click", (event) => {
                event.stopPropagation();
                const shouldOpen = !this.wrapper.classList.contains("is-open");
                SearchableModelSelect.closeAll();
                if (shouldOpen) this.open();
            });
            this.search.addEventListener("input", () => this.render(this.search.value));
            this.search.addEventListener("click", (event) => event.stopPropagation());
            this.panel.addEventListener("click", (event) => event.stopPropagation());
            this.select.addEventListener("change", () => this.sync());
        }

        open() {
            this.wrapper.classList.add("is-open");
            this.panel.hidden = false;
            this.toggle.setAttribute("aria-expanded", "true");
            this.search.value = "";
            this.render();
            window.setTimeout(() => this.search.focus(), 0);
        }

        close() {
            this.wrapper.classList.remove("is-open");
            this.panel.hidden = true;
            this.toggle.setAttribute("aria-expanded", "false");
        }

        sync() {
            const selected = this.select.selectedOptions?.[0];
            setOptionContent(this.toggle, selected, "Select a model");
        }

        setProviderFilter(provider) {
            this.providerFilter = provider || "all";
            this.render(this.search.value);
        }

        toggleFeatureFilter(feature) {
            if (this.featureFilters.has(feature)) this.featureFilters.delete(feature);
            else this.featureFilters.add(feature);
            this.render(this.search.value);
        }

        toggleSpeedFilter(tier) {
            if (this.speedFilters.has(tier)) this.speedFilters.delete(tier);
            else this.speedFilters.add(tier);
            this.render(this.search.value);
        }

        render(query = "") {
            const needle = String(query).trim().toLocaleLowerCase();
            this.list.replaceChildren();
            Array.from(this.select.options).forEach((option) => {
                if (option.disabled) return;
                const text = (option.textContent || "").trim();
                const value = option.value || "";
                if (this.providerFilter && this.providerFilter !== "all"
                    && !value.startsWith(`${this.providerFilter}::`)) {
                    return;
                }
                const hasAllFeatures = [...this.featureFilters].every(
                    (feature) => option.getAttribute(`data-model-feature-${feature}`) === "true",
                );
                if (!hasAllFeatures) return;
                const filtersBySpeed = this.speedFilters.size > 0
                    && this.speedFilters.size < Object.keys(speedometerNeedles).length;
                if (filtersBySpeed && !this.speedFilters.has(option.dataset.speedTier || "")) {
                    return;
                }
                const matches = text.toLocaleLowerCase().includes(needle)
                    || value.toLocaleLowerCase().includes(needle);
                if (needle && !matches) return;

                const item = document.createElement("button");
                item.type = "button";
                item.className = "searchable-select-option";
                setOptionContent(item, option, text);
                item.dataset.value = value;
                item.classList.toggle("is-selected", value === this.select.value);
                item.addEventListener("click", () => this.selectValue(value));
                this.list.appendChild(item);
            });
            if (!this.list.children.length) {
                const empty = document.createElement("div");
                empty.className = "searchable-select-empty";
                empty.textContent = "No matching models.";
                this.list.appendChild(empty);
            }
        }

        selectValue(value) {
            this.select.value = value;
            this.select.dispatchEvent(new Event("change", {bubbles: true}));
            this.sync();
            SearchableModelSelect.closeAll();
        }

        static closeAll() {
            this.instances.forEach((instance) => instance.close());
        }

        static init() {
            document.querySelectorAll("select[data-model-filter]").forEach((select) => {
                if (select.dataset.searchableReady !== "true") {
                    this.instances.push(new SearchableModelSelect(select));
                }
            });
            document.addEventListener("click", () => this.closeAll(), {
                signal: navigationListeners.signal,
            });
            document.addEventListener("keydown", (event) => {
                if (event.key === "Escape") this.closeAll();
            }, { signal: navigationListeners.signal });
            window.CairnmarkModelSelects = this.instances;
            this.initSubfilters();
            this.initProviderFilters();
        }

        static initSubfilters() {
            document.querySelectorAll("[data-model-subfilters]").forEach((container) => {
                const select = document.getElementById(container.dataset.modelSubfiltersFor || "");
                const instance = this.instances.find((item) => item.select === select);
                if (!instance) return;

                container.querySelectorAll("[data-model-feature-filter]").forEach((button) => {
                    button.addEventListener("click", () => {
                        instance.toggleFeatureFilter(button.dataset.modelFeatureFilter);
                        const active = instance.featureFilters.has(button.dataset.modelFeatureFilter);
                        button.classList.toggle("is-active", active);
                        button.setAttribute("aria-pressed", String(active));
                    });
                });

                container.querySelectorAll("[data-model-speed-filter]").forEach((button) => {
                    const tier = button.dataset.modelSpeedFilter;
                    const icon = createSpeedometerIcon(tier);
                    if (icon) button.appendChild(icon);
                    button.addEventListener("click", () => {
                        instance.toggleSpeedFilter(tier);
                        const active = instance.speedFilters.has(tier);
                        button.classList.toggle("is-active", active);
                        button.setAttribute("aria-pressed", String(active));
                    });
                });
            });
        }

        static async initProviderFilters() {
            const api = window.CairnmarkApi;
            const path = window.location.pathname || "/";
            const page = path === "/" ? "chat"
                : path.startsWith("/create_benchmark") ? "create"
                : path.startsWith("/run_benchmark") ? "run"
                : "all";
            let saved = "all";
            try {
                const response = await (api
                    ? api.request(`/model_selector/filter?page=${encodeURIComponent(page)}`)
                    : fetch(`/model_selector/filter?page=${encodeURIComponent(page)}`).then((r) => r.json()));
                saved = (response && response.provider) || "all";
            } catch (error) {
                saved = "all";
            }
            document.querySelectorAll("[data-model-provider-filter]").forEach((bar) => {
                const group = bar.closest(".field-group") || bar.parentElement;
                const select = group
                    ? group.querySelector("select[data-model-filter]")
                    : null;
                const instance = this.instances.find((item) => item.select === select);
                const buttons = [...bar.querySelectorAll("[data-provider-filter]")];
                const apply = (provider) => {
                    if (instance) instance.setProviderFilter(provider);
                    buttons.forEach((button) => {
                        button.classList.toggle(
                            "is-active",
                            button.dataset.providerFilter === provider,
                        );
                    });
                };
                buttons.forEach((button) => {
                    button.addEventListener("click", async () => {
                        const provider = button.dataset.providerFilter;
                        apply(provider);
                        try {
                            if (api) {
                                await api.json("/model_selector/filter", {
                                    method: "POST",
                                    body: {page, provider},
                                });
                            } else {
                                await fetch("/model_selector/filter", {
                                    method: "POST",
                                    headers: {"Content-Type": "application/json"},
                                    body: JSON.stringify({page, provider}),
                                });
                            }
                        } catch (error) {
                            console.error("Could not save model selector filter:", error);
                        }
                    });
                });
                const initial = buttons.some(
                    (button) => button.dataset.providerFilter === saved,
                )
                    ? saved
                    : "all";
                apply(initial);
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            () => SearchableModelSelect.init(),
            { once: true, signal: navigationListeners.signal }
        );
    } else {
        SearchableModelSelect.init();
    }
})();
