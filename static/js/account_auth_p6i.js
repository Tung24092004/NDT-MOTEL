(() => {
    "use strict";

    const root = document.querySelector(".ndt-f5.ndt-account-auth");
    if (!root) return;

    root.querySelectorAll("[data-password-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.passwordToggle);
            if (!input) return;
            const reveal = input.type === "password";
            input.type = reveal ? "text" : "password";
            button.textContent = reveal ? "Ẩn" : "Hiện";
            button.setAttribute("aria-label", reveal ? "Ẩn mật khẩu" : "Hiện mật khẩu");
        });
    });

    root.querySelectorAll("form[data-p6i-form]").forEach((form) => {
        form.addEventListener("invalid", (event) => {
            event.target.setAttribute("aria-invalid", "true");
            window.setTimeout(() => event.target.focus({ preventScroll: false }), 0);
        }, true);

        form.addEventListener("input", (event) => {
            if (event.target.checkValidity()) event.target.removeAttribute("aria-invalid");
        });

        form.addEventListener("submit", (event) => {
            if (event.defaultPrevented || !form.checkValidity()) return;
            if (form.dataset.p6iSubmitting === "true") {
                event.preventDefault();
                return;
            }
            form.dataset.p6iSubmitting = "true";
            const submitter = event.submitter;
            if (submitter && submitter.name) {
                const preserved = document.createElement("input");
                preserved.type = "hidden";
                preserved.name = submitter.name;
                preserved.value = submitter.value;
                form.appendChild(preserved);
            }
            if (submitter) {
                submitter.setAttribute("aria-disabled", "true");
                submitter.setAttribute("aria-busy", "true");
            }
        });
    });

    const summary = root.querySelector("[data-p6i-error-summary]");
    const firstInvalid = root.querySelector('[aria-invalid="true"]');
    if (summary && firstInvalid) firstInvalid.focus({ preventScroll: false });
})();
