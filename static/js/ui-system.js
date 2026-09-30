(function () {
    "use strict";

    document.addEventListener("submit", function (event) {
        if (event.defaultPrevented) return;
        var form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.checkValidity()) return;

        var submitter = event.submitter;
        if (!submitter || submitter.dataset.keepEnabled === "true") return;

        submitter.disabled = true;
        submitter.setAttribute("aria-disabled", "true");
        submitter.setAttribute("aria-busy", "true");
        if (!submitter.dataset.originalLabel) {
            submitter.dataset.originalLabel = submitter.textContent.trim();
        }
        submitter.textContent = submitter.dataset.loadingLabel || "Đang xử lý...";
    });
})();
