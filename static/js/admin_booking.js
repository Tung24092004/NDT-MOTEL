(function () {
    "use strict";

    function markSubmitting(form) {
        var button = form.querySelector("button[type=submit]");
        if (!button) return;
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.dataset.originalLabel = button.textContent;
        button.textContent = "Đang xử lý...";
    }

    document.querySelectorAll("[data-admin-booking-confirm]").forEach(function (form) {
        form.addEventListener("submit", async function (event) {
            if (form.dataset.confirmed === "true") {
                markSubmitting(form);
                return;
            }
            event.preventDefault();
            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }
            var trigger = event.submitter || document.activeElement;
            var confirmation = window.NDTFoundationDialog.confirm({
                title: form.dataset.confirmTitle,
                message: form.dataset.confirmMessage,
                confirmLabel: form.dataset.confirmDanger === "true" ? "Xác nhận từ chối" : "Xác nhận",
                danger: form.dataset.confirmDanger === "true",
                trigger: trigger
            });
            var cancel = document.querySelector(".ndt-f5-dialog__actions [data-ndt-f5-dialog-cancel]");
            if (cancel) cancel.focus();
            var confirmed = await confirmation;
            if (confirmed) {
                form.dataset.confirmed = "true";
                form.requestSubmit(trigger && trigger.form === form ? trigger : undefined);
            }
        });
    });
}());
