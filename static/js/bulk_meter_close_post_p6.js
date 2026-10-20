(function () {
    "use strict";

    const form = document.querySelector("[data-bulk-meter-form]");
    if (!form) return;

    const rows = Array.from(form.querySelectorAll("[data-meter-row]"));
    const selectAll = form.querySelector("[data-select-all]");
    const selectedCount = form.querySelector("[data-selected-count]");
    const submit = form.querySelector("[data-submit-bulk]");
    const formatMoney = (value) => new Intl.NumberFormat("vi-VN").format(value) + " VNĐ";
    const readInteger = (input) => {
        const raw = input && input.value ? String(input.value).trim() : "";
        return /^\d+$/.test(raw) ? BigInt(raw) : null;
    };

    const syncRow = (row) => {
        const checkbox = row.querySelector("[data-row-check]");
        const oldReading = row.querySelector("[data-old-reading]");
        const newReading = row.querySelector("[data-new-reading]");
        const enabled = Boolean(checkbox && checkbox.checked);
        if (oldReading) oldReading.disabled = !enabled;
        if (newReading) newReading.disabled = !enabled;

        const oldValue = readInteger(oldReading);
        const newValue = readInteger(newReading);
        const price = BigInt(row.dataset.unitPrice || "0");
        const fixed = BigInt(row.dataset.fixedTotal || "0");
        const electricity = oldValue !== null && newValue !== null && newValue >= oldValue
            ? (newValue - oldValue) * price
            : 0n;
        row.querySelector("[data-electricity-total]").textContent = "Điện: " + formatMoney(electricity);
        row.querySelector("[data-row-total]").textContent = formatMoney(fixed + electricity);
    };

    const syncForm = () => {
        rows.forEach(syncRow);
        const checkboxes = rows.map((row) => row.querySelector("[data-row-check]")).filter(Boolean);
        const checked = checkboxes.filter((checkbox) => checkbox.checked);
        selectedCount.textContent = String(checked.length);
        submit.disabled = checked.length === 0;
        if (selectAll) {
            selectAll.checked = checkboxes.length > 0 && checked.length === checkboxes.length;
            selectAll.indeterminate = checked.length > 0 && checked.length < checkboxes.length;
        }
    };

    form.addEventListener("input", function (event) {
        if (event.target !== selectAll) syncForm();
    });
    form.addEventListener("change", syncForm);
    if (selectAll) {
        selectAll.addEventListener("change", function () {
            rows.forEach((row) => {
                const checkbox = row.querySelector("[data-row-check]");
                if (checkbox) checkbox.checked = selectAll.checked;
            });
            syncForm();
        });
    }
    form.addEventListener("submit", function () {
        submit.disabled = true;
        submit.setAttribute("aria-disabled", "true");
    });
    syncForm();
})();
