(() => {
    "use strict";

    class BenchmarkTopicEditor {
        constructor(root) {
            this.root = root;
            this.list = root.querySelector("[data-topic-list]");
            this.addButton = root.querySelector("[data-topic-add]");
            this.countLabel = root.querySelector("[data-topic-count-label]");
            this.initialHTML = this.list.innerHTML;
            this.bind();
            this.update();
        }

        bind() {
            this.addButton?.addEventListener("click", () => this.add());
            this.list.addEventListener("click", (event) => {
                const button = event.target.closest("[data-topic-remove]");
                if (button) this.remove(button);
            });
            this.list.addEventListener("keydown", (event) => {
                if (
                    event.target.matches("[data-topic-name]")
                    && event.key === "Enter"
                    && !event.shiftKey
                ) {
                    event.preventDefault();
                    this.addButton?.focus();
                }
            });
        }

        rows() {
            return [...this.list.querySelectorAll("[data-topic-row]")];
        }

        update() {
            const rows = this.rows();
            rows.forEach((row, index) => {
                const order = row.querySelector("[data-topic-order]");
                if (order) order.textContent = String(index + 1).padStart(2, "0");
            });
            const count = rows.length;
            const countElement = this.root.querySelector("[data-topic-count]");
            if (countElement) countElement.textContent = count;
            if (this.countLabel) {
                this.countLabel.textContent = count === 1 ? "topic" : "topics";
            }
        }

        add() {
            const template = this.root.querySelector("[data-topic-template]");
            if (!template) return;
            const fragment = document.importNode(template.content, true);
            const row = fragment.querySelector("[data-topic-row]");
            if (!row) return;
            row.tabIndex = 0;
            const removeButton = row.querySelector("[data-topic-remove]");
            if (removeButton) removeButton.disabled = false;
            this.list.appendChild(fragment);
            this.update();
            row.querySelector("[data-topic-name]")?.focus();
        }

        remove(button) {
            const row = button.closest("[data-topic-row]");
            if (!row || this.rows().length <= 1) return;
            const focusTarget = row.nextElementSibling || row.previousElementSibling;
            row.remove();
            this.update();
            focusTarget?.querySelector("[data-topic-name]")?.focus();
        }

        reset() {
            this.list.innerHTML = this.initialHTML;
            this.update();
        }
    }

    const root = document.querySelector("[data-topics]");
    if (!root?.querySelector("[data-topic-list]")) return;
    const editor = new BenchmarkTopicEditor(root);
    window.CairnmarkBenchmarkTopics = editor;
    window.resetBenchmarkTopics = () => editor.reset();
})();
