(function () {
    "use strict";

    function markSubmitting(form, submitter) {
        if (form.dataset.submitting === "true") return false;
        form.dataset.submitting = "true";
        if (submitter) {
            submitter.setAttribute("aria-busy", "true");
        }
        return true;
    }

    function attachConfirmation(form) {
        form.addEventListener("submit", function (event) {
            if (form.dataset.confirmed === "true") {
                event.stopPropagation();
                if (!markSubmitting(form, event.submitter)) event.preventDefault();
                return;
            }
            event.preventDefault();
            var submitter = event.submitter;
            window.NDTFoundationDialog.confirm({
                title: form.dataset.dialogTitle,
                message: form.dataset.dialogMessage,
                confirmLabel: form.dataset.dialogConfirmLabel,
                danger: form.dataset.dialogDanger !== "false",
                trigger: submitter || form,
            }).then(function (confirmed) {
                if (!confirmed) return;
                form.dataset.confirmed = "true";
                form.requestSubmit(submitter && submitter.form === form ? submitter : undefined);
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (window.NDTFoundationDialog) {
            document.querySelectorAll("[data-invoice-confirm]").forEach(attachConfirmation);
        }
        document.querySelectorAll(".ndt-invoice-management form:not([data-invoice-confirm])").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                event.stopPropagation();
                if (!markSubmitting(form, event.submitter)) event.preventDefault();
            });
        });
    });
}());
