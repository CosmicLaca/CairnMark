(() => {
    "use strict";

    const api = window.CairnmarkApi;
    const model = document.querySelector("#model");
    const fields = {
        temperature: document.querySelector("[data-benchmark-temperature]"),
        top_p: document.querySelector("[data-benchmark-top-p]"),
        top_k: document.querySelector("[data-benchmark-top-k]"),
        seed: document.querySelector("[data-benchmark-seed]"),
        min_p: document.querySelector("[data-benchmark-min-p]"),
    };
    const seedSwitch = document.querySelector("[data-benchmark-seed-switch]");
    const createLog = document.querySelector("[data-benchmark-create-log]");
    const saveButton = document.querySelector("[data-benchmark-save-settings]");
    const message = document.querySelector("[data-benchmark-setup-message]");
    const moreButton = document.querySelector("[data-benchmark-more-params]");
    const moreState = document.querySelector("[data-benchmark-more-state]");
    const modal = document.querySelector("[data-benchmark-more-modal]");
    const modalContent = document.querySelector("[data-benchmark-more-content]");
    const setButton = document.querySelector("[data-benchmark-more-set]");
    const unsetButtons = document.querySelectorAll("[data-benchmark-more-unset]");
    let extraParameters = {};
    let loadedModel = "";

    const numberValue = (input) => {
        const raw = String(input?.value ?? "").trim();
        if (!raw) return null;
        const value = Number(raw);
        return Number.isFinite(value) ? value : null;
    };

    const values = (forRequest = false) => {
        const result = {};
        Object.entries(fields).forEach(([name, input]) => {
            result[name] = numberValue(input);
        });
        const randomize = seedSwitch?.getAttribute("aria-checked") === "true";
        result.randomize_seed = randomize;
        result.create_log = Boolean(createLog?.checked);
        if (forRequest && randomize) {
            result.seed = Math.floor(Math.random() * 4294967296);
            if (fields.seed) fields.seed.value = String(result.seed);
        }
        return result;
    };

    const updateState = () => {
        if (!moreState || moreButton?.disabled) {
            if (moreState) moreState.hidden = true;
            return;
        }
        const active = Object.keys(extraParameters).length > 0;
        moreState.textContent = active ? "SET" : "UNSET";
        moreState.hidden = false;
    };

    const modelParts = () => {
        const parts = String(model?.value || "").split("::");
        return { provider: parts[0] || "", name: parts.slice(1).join("::") };
    };

    const updateMoreButton = () => {
        const selected = modelParts();
        const local = ["llama.cpp", "vllm"].includes(selected.provider);
        if (loadedModel && loadedModel !== model?.value) extraParameters = {};
        moreButton.disabled = !local || !selected.name;
        updateState();
    };

    const createInput = (name, value) => {
        const group = document.createElement("div");
        group.className = "field-group more-params-field";
        const labelRow = document.createElement("div");
        labelRow.className = "more-params-label";
        const label = document.createElement("label");
        label.textContent = name.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
        label.htmlFor = `benchmark-more-param-${name}`;
        labelRow.appendChild(label);
        group.appendChild(labelRow);
        const input = document.createElement("input");
        input.id = `benchmark-more-param-${name}`;
        input.dataset.benchmarkMoreParam = name;
        if (typeof value === "boolean") {
            const switchWrap = document.createElement("label");
            switchWrap.className = "more-params-switch";
            input.type = "checkbox";
            input.checked = value;
            input.className = "more-params-switch-input";
            const knob = document.createElement("span");
            knob.className = "more-params-switch-knob";
            switchWrap.append(input, knob);
            group.appendChild(switchWrap);
            return group;
        } else if (typeof value === "number") {
            input.type = "number";
            input.step = "any";
            input.value = String(value);
        } else {
            input.type = "text";
            input.value = Array.isArray(value) ? JSON.stringify(value) : String(value ?? "");
        }
        group.appendChild(input);
        return group;
    };

    const openMore = async () => {
        const selected = modelParts();
        if (!modal || !selected.name) return;
        modal.hidden = false;
        modalContent.textContent = "Loading parameters…";
        try {
            const payload = await api.request(
                `/setup_models/model_params?provider=${encodeURIComponent(selected.provider)}&model=${encodeURIComponent(selected.name)}`
            );
            const ignored = new Set(["temperature", "top_p", "top_k", "seed", "min_p", "stream", "samplers"]);
            const params = payload?.params || {};
            modalContent.replaceChildren();
            const grid = document.createElement("div");
            grid.className = "more-params-grid";
            Object.entries(params).forEach(([name, value]) => {
                if (!ignored.has(name) && value !== null) grid.appendChild(createInput(name, value));
            });
            if (!grid.children.length) {
                modalContent.textContent = "No additional parameters were returned by this model.";
            } else {
                modalContent.appendChild(grid);
            }
            loadedModel = model.value;
        } catch (error) {
            modalContent.textContent = `Failed to load parameters: ${error}`;
        }
    };

    const collectExtra = () => {
        const collected = {};
        modalContent?.querySelectorAll("[data-benchmark-more-param]").forEach((input) => {
            const name = input.dataset.benchmarkMoreParam;
            if (input.type === "checkbox") {
                collected[name] = input.checked;
                return;
            }
            const raw = input.value.trim();
            if (!raw) return;
            if (input.type === "number") {
                const numeric = Number(raw);
                if (Number.isFinite(numeric)) collected[name] = numeric;
                return;
            }
            try { collected[name] = JSON.parse(raw); }
            catch (_error) { collected[name] = raw; }
        });
        return collected;
    };

    seedSwitch?.addEventListener("click", () => {
        const enabled = seedSwitch.getAttribute("aria-checked") !== "true";
        seedSwitch.setAttribute("aria-checked", String(enabled));
    });
    saveButton?.addEventListener("click", async () => {
        saveButton.disabled = true;
        try {
            await api.json("/create_benchmark/settings", { method: "POST", body: values() });
            message.textContent = "Benchmark setup saved.";
        } catch (error) {
            message.textContent = `Save failed: ${error}`;
        } finally {
            saveButton.disabled = false;
        }
    });
    moreButton?.addEventListener("click", openMore);
    setButton?.addEventListener("click", () => {
        extraParameters = collectExtra();
        modal.hidden = true;
        updateState();
    });
    unsetButtons.forEach((button) => button.addEventListener("click", () => {
        extraParameters = {};
        modal.hidden = true;
        updateState();
    }));
    modal?.addEventListener("click", (event) => {
        if (event.target === modal) modal.hidden = true;
    });
    model?.addEventListener("change", updateMoreButton);
    updateMoreButton();

    window.CairnmarkBenchmarkSetup = {
        requestValues: () => ({ ...values(true), model_params: extraParameters }),
    };
})();
