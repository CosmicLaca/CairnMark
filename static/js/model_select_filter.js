(() => {
    "use strict";

    class SearchableModelSelect {
        static instances = [];

        constructor(select) {
            this.select = select;
            this.wrapper = document.createElement("div");
            this.toggle = document.createElement("button");
            this.panel = document.createElement("div");
            this.search = document.createElement("input");
            this.list = document.createElement("div");
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
            this.toggle.textContent = selected
                ? selected.textContent.trim()
                : "Select a model";
        }

        render(query = "") {
            const needle = String(query).trim().toLocaleLowerCase();
            this.list.replaceChildren();
            Array.from(this.select.options).forEach((option) => {
                if (option.disabled) return;
                const text = (option.textContent || "").trim();
                const value = option.value || "";
                const matches = text.toLocaleLowerCase().includes(needle)
                    || value.toLocaleLowerCase().includes(needle);
                if (needle && !matches) return;

                const item = document.createElement("button");
                item.type = "button";
                item.className = "searchable-select-option";
                item.textContent = text;
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
            document.addEventListener("click", () => this.closeAll());
            document.addEventListener("keydown", (event) => {
                if (event.key === "Escape") this.closeAll();
            });
            window.CairnmarkModelSelects = this.instances;
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => SearchableModelSelect.init());
    } else {
        SearchableModelSelect.init();
    }
})();
