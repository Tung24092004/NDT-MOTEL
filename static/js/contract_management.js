(function () {
    "use strict";

    function attachConfirmation(form) {
        form.addEventListener("submit", function (event) {
            if (form.dataset.confirmed === "true") return;
            event.preventDefault();
            var submitter = event.submitter;
            var isDanger = submitter && submitter.dataset.dialogDanger === "true";
            window.NDTFoundationDialog.confirm({
                title: (submitter && submitter.dataset.dialogTitle) || form.dataset.dialogTitle || "Xác nhận thao tác hợp đồng",
                message: (submitter && submitter.dataset.dialogMessage) || form.dataset.dialogMessage || "Hệ thống sẽ xử lý hợp đồng theo dữ liệu hiện tại.",
                confirmLabel: (submitter && submitter.dataset.dialogConfirmLabel) || form.dataset.dialogConfirmLabel || "Xác nhận",
                danger: isDanger,
                trigger: submitter || form,
            }).then(function (confirmed) {
                if (!confirmed) return;
                form.dataset.confirmed = "true";
                if (submitter && submitter.name) {
                    var hidden = document.createElement("input");
                    hidden.type = "hidden";
                    hidden.name = submitter.name;
                    hidden.value = submitter.value;
                    form.appendChild(hidden);
                }
                form.submit();
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!window.NDTFoundationDialog) return;
        document.querySelectorAll("[data-contract-confirm]").forEach(attachConfirmation);
    });
}());
