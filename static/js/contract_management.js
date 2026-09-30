(function () {
    "use strict";

    document.querySelectorAll("[data-contract-confirm]").forEach(function (form) {
        form.addEventListener("submit", async function (event) {
            if (form.dataset.confirmed === "true") return;
            event.preventDefault();
            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }

            var submitter = event.submitter;
            var danger = form.dataset.confirmDanger === "true" || (submitter && submitter.dataset.confirmDanger === "true");
            var confirmed = await window.NDTDialog.confirm({
                title: form.dataset.confirmTitle || "Xac nhan thao tac",
                message: form.dataset.confirmMessage || "Ban co chac muon tiep tuc?",
                confirmLabel: danger ? "Xac nhan" : "Tiep tuc",
                danger: danger
            });
            if (confirmed) {
                form.dataset.confirmed = "true";
                if (submitter && submitter.name) {
                    var shadow = document.createElement("input");
                    shadow.type = "hidden";
                    shadow.name = submitter.name;
                    shadow.value = submitter.value;
                    form.appendChild(shadow);
                }
                form.requestSubmit();
            }
        });
    });
}());
