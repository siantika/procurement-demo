(() => {
    "use strict";

    const container = document.querySelector("#tender-items");
    const addButton = document.querySelector("#add-tender-item");
    const template = document.querySelector("#tender-item-template");
    const totalForms = document.querySelector("#id_items-TOTAL_FORMS");
    const maxForms = document.querySelector("#id_items-MAX_NUM_FORMS");

    if (!container || !addButton || !template || !totalForms) {
        return;
    }

    const items = () => [...container.querySelectorAll("[data-formset-item]")];
    const activeItems = () => items().filter((item) => !item.hidden);

    const deleteInput = (item) =>
        item.querySelector('input[name$="-DELETE"]');

    const isDeleted = (item) => {
        const value = deleteInput(item)?.value.toLowerCase();
        return ["1", "on", "true"].includes(value);
    };

    const setRemoved = (item, removed) => {
        const deletion = deleteInput(item);
        if (deletion) {
            deletion.value = removed ? "on" : "";
        }
        item.hidden = removed;
        item.querySelectorAll("input, select, textarea").forEach((field) => {
            if (field !== deletion) {
                field.disabled = removed;
            }
        });
    };

    const refresh = () => {
        const active = activeItems();
        active.forEach((item, index) => {
            const legend = item.querySelector("[data-item-legend]");
            const removeButton = item.querySelector("[data-remove-item]");
            if (legend) {
                legend.textContent = `Item ${index + 1}`;
            }
            if (removeButton) {
                removeButton.hidden = false;
                removeButton.disabled = active.length === 1;
                removeButton.setAttribute(
                    "aria-label",
                    `Hapus item ${index + 1}`,
                );
            }
        });

        const maximum = Number.parseInt(maxForms?.value || "1000", 10);
        addButton.disabled = Number.parseInt(totalForms.value, 10) >= maximum;
    };

    items().forEach((item) => setRemoved(item, isDeleted(item)));
    if (activeItems().length === 0 && items().length > 0) {
        setRemoved(items()[0], false);
    }
    addButton.hidden = false;
    refresh();

    addButton.addEventListener("click", () => {
        const index = Number.parseInt(totalForms.value, 10);
        const existingLines = activeItems()
            .map((item) => item.querySelector('input[name$="-line_number"]'))
            .map((input) => Number.parseInt(input?.value || "0", 10));
        const nextLine = Math.max(0, ...existingLines) + 1;
        const markup = template.innerHTML.replaceAll("__prefix__", index);
        container.insertAdjacentHTML("beforeend", markup);
        totalForms.value = index + 1;

        const item = items().at(-1);
        const lineInput = item.querySelector('input[name$="-line_number"]');
        if (lineInput && !lineInput.value) {
            lineInput.value = nextLine;
        }
        refresh();
        item.querySelector(
            'select, input:not([type="hidden"]), textarea',
        )?.focus();
    });

    container.addEventListener("click", (event) => {
        const removeButton = event.target.closest("[data-remove-item]");
        if (!removeButton || activeItems().length === 1) {
            return;
        }
        setRemoved(removeButton.closest("[data-formset-item]"), true);
        refresh();
    });
})();
