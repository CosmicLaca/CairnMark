(() => {
    "use strict";

    const closeAll = () => {
        document.querySelectorAll(".searchable-select.is-open").forEach((widget) => {
            widget.classList.remove("is-open");
            const panel = widget.querySelector(".searchable-select-panel");
            if (panel) panel.hidden = true;
            widget.querySelector(".searchable-select-toggle")
                ?.setAttribute("aria-expanded", "false");
        });
    };

    const buildWidget = (select) => {
        if (select.dataset.searchableReady === "true") return;
        select.dataset.searchableReady = "true";
        select.classList.add("searchable-select-source");

        const wrapper = document.createElement("div");
        wrapper.className = "searchable-select";

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "searchable-select-toggle";
        toggle.setAttribute("aria-haspopup", "listbox");
        toggle.setAttribute("aria-expanded", "false");

        const panel = document.createElement("div");
        panel.className = "searchable-select-panel";
        panel.hidden = true;

        const search = document.createElement("input");
        search.type = "search";
        search.className = "searchable-select-search";
        search.placeholder = "Filter model names…";
        search.setAttribute("aria-label", "Filter model names");

        const list = document.createElement("div");
        list.className = "searchable-select-list";
        list.setAttribute("role", "listbox");

        panel.append(search, list);
        wrapper.append(toggle, panel);
        select.insertAdjacentElement("afterend", wrapper);

        const syncToggle = () => {
            const selected = select.selectedOptions && select.selectedOptions[0];
            toggle.textContent = selected ? selected.textContent.trim() : "Select a model";
        };

        const renderList = (query) => {
            const needle = String(query || "").trim().toLowerCase();
            list.replaceChildren();
            Array.from(select.options).forEach((option) => {
                if (option.disabled) return;
                const text = (option.textContent || "").trim();
                const value = option.value || "";
                if (needle && !text.toLowerCase().includes(needle) && !value.toLowerCase().includes(needle)) {
                    return;
                }
                const item = document.createElement("button");
                item.type = "button";
                item.className = "searchable-select-option";
                item.textContent = text;
                item.dataset.value = value;
                if (value === select.value) item.classList.add("is-selected");
                item.addEventListener("click", () => {
                    select.value = value;
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                    syncToggle();
                    closeAll();
                });
                list.appendChild(item);
            });
            if (!list.children.length) {
                const empty = document.createElement("div");
                empty.className = "searchable-select-empty";
                empty.textContent = "No matching models.";
                list.appendChild(empty);
            }
        };

        toggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const isOpen = wrapper.classList.contains("is-open");
            closeAll();
            if (!isOpen) {
                wrapper.classList.add("is-open");
                panel.hidden = false;
                toggle.setAttribute("aria-expanded", "true");
                search.value = "";
                renderList("");
                setTimeout(() => search.focus(), 0);
            } else {
                toggle.setAttribute("aria-expanded", "false");
            }
        });

        search.addEventListener("input", () => renderList(search.value));
        search.addEventListener("click", (event) => event.stopPropagation());

        select.addEventListener("change", syncToggle);

        // Keep panel clicks from closing immediately.
        panel.addEventListener("click", (event) => event.stopPropagation());

        syncToggle();
        renderList("");
    };

    const init = () => {
        document.querySelectorAll("select[data-model-filter]").forEach(buildWidget);
        document.addEventListener("click", closeAll);
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeAll();
        });
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
