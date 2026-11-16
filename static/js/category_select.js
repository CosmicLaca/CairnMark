(() => {
    "use strict";

    const categorySelect = document.querySelector("[data-category-select]");
    if (!categorySelect) {
        return;
    }

    const newCategoryField = document.querySelector("[data-new-category]");
    if (!newCategoryField) {
        return;
    }

    const newCategoryInput = newCategoryField.querySelector("input");

    const updateCategoryField = () => {
        const creatingCategory = categorySelect.value === "__new__";
        newCategoryField.hidden = !creatingCategory;
        newCategoryInput.required = creatingCategory;
        if (creatingCategory) {
            newCategoryInput.focus();
        }
    };

    categorySelect.addEventListener("change", updateCategoryField);
    updateCategoryField();
})();
