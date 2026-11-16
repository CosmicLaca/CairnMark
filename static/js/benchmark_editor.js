(() => {
    "use strict";

    const form = document.querySelector("[data-category-form]");
    if (!form) {
        return;
    }

    const notes = form.querySelector("[data-notes]");
    const noteCount = form.querySelector("[data-note-count]");
    if (!notes || !noteCount) {
        return;
    }

    const updateNoteCount = () => {
        noteCount.value = notes.value.length;
    };

    notes.addEventListener("input", updateNoteCount);
    updateNoteCount();
})();
