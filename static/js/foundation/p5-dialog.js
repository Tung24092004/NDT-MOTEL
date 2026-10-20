(function () {
    "use strict";

    var state = null;

    function root() {
        var dialog = document.querySelector("[data-ndt-f5-dialog]");
        if (dialog && dialog.parentElement !== document.body) {
            document.body.appendChild(dialog);
        }
        return dialog;
    }

    function focusable(dialog) {
        return Array.prototype.slice.call(dialog.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )).filter(function (element) {
            return !element.hasAttribute("hidden");
        });
    }

    function restoreFocus(previousFocus) {
        if (previousFocus && typeof previousFocus.focus === "function") {
            previousFocus.focus({ preventScroll: true });
        }
    }

    function close(result) {
        if (!state) return;
        var closing = state;
        state = null;
        closing.dialog.hidden = true;
        document.removeEventListener("keydown", closing.onKeydown);
        document.body.style.overflow = closing.bodyOverflow;
        restoreFocus(closing.previousFocus);
        window.setTimeout(function () { closing.resolve(Boolean(result)); }, 0);
    }

    function confirm(options) {
        options = options || {};
        var dialog = root();
        if (!dialog) {
            return Promise.resolve(false);
        }
        if (state) close(false);

        var title = dialog.querySelector("[data-ndt-f5-dialog-title]");
        var message = dialog.querySelector("[data-ndt-f5-dialog-message]");
        var confirmButton = dialog.querySelector("[data-ndt-f5-dialog-confirm]");
        var cancelButtons = dialog.querySelectorAll("[data-ndt-f5-dialog-cancel]");
        var previousFocus = options.trigger && typeof options.trigger.focus === "function"
            ? options.trigger
            : document.activeElement;

        title.textContent = options.title || "Xác nhận thao tác";
        message.textContent = options.message || "Bạn có chắc muốn tiếp tục?";
        confirmButton.textContent = options.confirmLabel || "Xác nhận";
        confirmButton.className = "ndt-f5-button " + (
            options.danger === false ? "ndt-f5-button--primary" : "ndt-f5-button--danger"
        );
        dialog.hidden = false;

        return new Promise(function (resolve) {
            function onKeydown(event) {
                if (event.key === "Escape") {
                    event.preventDefault();
                    close(false);
                    return;
                }
                if (event.key !== "Tab") return;
                var items = focusable(dialog);
                if (!items.length) {
                    event.preventDefault();
                    return;
                }
                var first = items[0];
                var last = items[items.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            }

            state = {
                dialog: dialog,
                resolve: resolve,
                previousFocus: previousFocus,
                onKeydown: onKeydown,
                bodyOverflow: document.body.style.overflow,
            };
            document.body.style.overflow = "hidden";
            document.addEventListener("keydown", onKeydown);
            confirmButton.onclick = function () { close(true); };
            Array.prototype.forEach.call(cancelButtons, function (button) {
                button.onclick = function () { close(false); };
            });
            confirmButton.focus();
        });
    }

    window.NDTFoundationDialog = { confirm: confirm, close: close };

    document.addEventListener("click", function (event) {
        var trigger = event.target.closest("[data-ndt-f5-dialog-open]");
        if (!trigger) return;
        event.preventDefault();
        confirm({
            title: trigger.dataset.dialogTitle,
            message: trigger.dataset.dialogMessage,
            confirmLabel: trigger.dataset.dialogConfirmLabel,
            danger: trigger.dataset.dialogDanger !== "false",
            trigger: trigger,
        });
    });
}());
