(() => {
    "use strict";

    const root = document.querySelector(".ndt-f5.ndt-community-management");
    if (!root) return;

    root.querySelectorAll("form[data-community-confirm]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            if (form.dataset.p6jConfirmed === "true") return;
            event.preventDefault();
            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }

            const submitter = event.submitter;
            const danger = form.dataset.confirmDanger === "true" ||
                (submitter && submitter.dataset.confirmDanger === "true");
            const confirmed = await window.NDTFoundationDialog.confirm({
                title: form.dataset.confirmTitle || "Xác nhận thao tác",
                message: form.dataset.confirmMessage || "Bạn có chắc muốn tiếp tục?",
                confirmLabel: danger ? "Xác nhận" : "Tiếp tục",
                danger,
                trigger: submitter,
            });
            if (!confirmed) return;

            form.dataset.p6jConfirmed = "true";
            if (submitter && submitter.name) {
                const preserved = document.createElement("input");
                preserved.type = "hidden";
                preserved.name = submitter.name;
                preserved.value = submitter.value;
                form.appendChild(preserved);
            }
            form.requestSubmit();
        });
    });
})();
