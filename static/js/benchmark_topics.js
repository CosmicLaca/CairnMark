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

    const resetTopics = () => {
        topicList.innerHTML = initialTopicListHTML;
        topicIndex = 1;
        updateTopicCount();
    };

    window.resetBenchmarkTopics = resetTopics;

    if (addButton) {
        addButton.addEventListener("click", addTopicRow);
    }

    topicList.addEventListener("click", (event) => {
        const removeButton = event.target.closest("[data-topic-remove]");
        if (removeButton) removeTopicRow(removeButton);
    });
    topicList.addEventListener("keydown", (event) => {
        if (
            event.target.matches("[data-topic-name]")
            && event.key === "Enter"
            && !event.shiftKey
        ) {
            event.preventDefault();
            addButton?.focus();
        }
    });
    updateTopicCount();
})();
