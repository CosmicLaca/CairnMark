(() => {
    "use strict";

    const topics = document.querySelector("[data-topics]");
    const topicList = topics?.querySelector("[data-topic-list]");
    const addButton = topics?.querySelector("[data-topic-add]");
    const topicCountLabel = topics?.querySelector("[data-topic-count-label]");
    let topicIndex = 1;

    if (!topics || !topicList) {
        return;
    }

    const initialTopicListHTML = topicList.innerHTML;

    const updateTopicCount = () => {
        const rows = topicList.querySelectorAll("[data-topic-row]");
        const count = rows.length;
        const countEl = topics.querySelector("[data-topic-count]");
        if (countEl) {
            countEl.textContent = count;
        }
        topicCountLabel.textContent = count === 1 ? "topic" : "topics";
    };

    const renderTopicTemplate = () => {
        const template = topics.querySelector("[data-topic-template]");
        if (!template) return null;
        return document.importNode(template.content, true);
    };

    const addTopicRow = () => {
        if (!topicList) return;
        const fragment = renderTopicTemplate();
        if (fragment) {
            const row = fragment.querySelector("[data-topic-row]");
            if (row) {
                row.setAttribute("data-topic-row", "");
                const orderEl = row.querySelector("[data-topic-order]");
                if (orderEl) {
                    orderEl.textContent = String(topicIndex + 1).padStart(2, "0");
                }
                const removeBtn = row.querySelector("[data-topic-remove]");
                if (removeBtn) {
                    removeBtn.disabled = false;
                }
                const nameInput = row.querySelector("[data-topic-name]");
                const pairsInput = row.querySelector("[data-topic-pairs]");
                const orderInput = row.querySelector("[data-topic-order]");

                row.setAttribute("tabindex", "0");
                if (nameInput) nameInput.focus();
                topicList.appendChild(fragment);

                // Wire up the dynamically added row's controls so its trash
                // button and Enter-on-name behave like the initial row.
                const newRemoveBtn = row.querySelector("[data-topic-remove]");
                const newNameInput = row.querySelector("[data-topic-name]");
                if (newRemoveBtn) {
                    newRemoveBtn.addEventListener("click", () => removeTopicRow(newRemoveBtn));
                }
                if (newNameInput) {
                    newNameInput.addEventListener("keydown", (e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            addButton?.focus();
                        }
                    });
                }

                topicIndex++;
                updateTopicCount();
            }
        }
    };

    const removeTopicRow = (button) => {
        const row = button.closest("[data-topic-row]");
        if (!row || topicList.querySelectorAll("[data-topic-row]").length <= 1) return;

        const nextRow = row.nextElementSibling || row.previousElementSibling;
        if (nextRow && nextRow.querySelector("[data-topic-remove]")) {
            nextRow.querySelector("[data-topic-remove]").disabled = false;
        }

        row.remove();

        const orderEls = topicList.querySelectorAll("[data-topic-order]");
        orderEls.forEach((el, i) => {
            el.textContent = String(i + 1).padStart(2, "0");
        });

        topicIndex = Math.max(1, topicList.querySelectorAll("[data-topic-row]").length);
        updateTopicCount();
    };

    const bindTopicRowEvents = () => {
        topicList.querySelectorAll("[data-topic-remove]").forEach((button) => {
            button.addEventListener("click", () => removeTopicRow(button));
        });
        topicList.querySelectorAll("[data-topic-name]").forEach((input) => {
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    addButton?.focus();
                }
            });
        });
    };

    const resetTopics = () => {
        topicList.innerHTML = initialTopicListHTML;
        topicIndex = 1;
        bindTopicRowEvents();
        updateTopicCount();
    };

    window.resetBenchmarkTopics = resetTopics;

    if (addButton) {
        addButton.addEventListener("click", addTopicRow);
    }

    bindTopicRowEvents();
    updateTopicCount();
})();
