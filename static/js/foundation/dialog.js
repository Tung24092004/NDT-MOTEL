(function () {
    "use strict";

    var activeDialog = null;

    function getRoot() {
        var root = document.getElementById("ndtDialogRoot");
        if (root) return root;

        root = document.createElement("div");
        root.id = "ndtDialogRoot";
        root.innerHTML = [
            '<div class="ndt-dialog" data-ndt-dialog hidden>',
            '<div class="ndt-dialog__overlay" data-ndt-dialog-cancel></div>',
            '<div class="ndt-dialog__panel" role="dialog" aria-modal="true" aria-labelledby="ndtDialogTitle" aria-describedby="ndtDialogMessage">',
            '<h2 class="ndt-dialog__title" id="ndtDialogTitle"></h2>',
            '<p class="ndt-dialog__message" id="ndtDialogMessage"></p>',
            '<div class="ndt-dialog__actions">',
            '<button class="ndt-button ndt-button--secondary" type="button" data-ndt-dialog-cancel>Hủy</button>',
            '<button class="ndt-button ndt-button--primary" type="button" data-ndt-dialog-confirm>Xác nhận</button>',
            '</div></div></div>'
        ].join("");
        document.body.appendChild(root);
        return root;
    }

    function focusable(dialog) {
        return Array.prototype.slice.call(dialog.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ));
    }

    function restoreFocus(dialogState) {
        if (
            dialogState.previousFocus
            && typeof dialogState.previousFocus.focus === "function"
        ) {
            dialogState.previousFocus.focus({ preventScroll: true });
        }
    }

    function close(result) {
        if (!activeDialog) return;
        var closingDialog = activeDialog;
        closingDialog.dialog.hidden = true;
        document.removeEventListener("keydown", closingDialog.onKeydown);
        activeDialog = null;
        restoreFocus(closingDialog);
        window.setTimeout(function () {
            if (!activeDialog) restoreFocus(closingDialog);
            closingDialog.resolve(result);
        }, 0);
    }

    function open(options) {
        options = options || {};
        if (activeDialog) close(false);
        var root = getRoot();
        var dialog = root.querySelector("[data-ndt-dialog]");
        var title = root.querySelector("#ndtDialogTitle");
        var message = root.querySelector("#ndtDialogMessage");
        var confirmButton = root.querySelector("[data-ndt-dialog-confirm]");
        var cancelButtons = root.querySelectorAll("[data-ndt-dialog-cancel]");

        title.textContent = options.title || "Xác nhận";
        message.textContent = options.message || "Bạn có muốn tiếp tục?";
        confirmButton.textContent = options.confirmLabel || "Xác nhận";
        confirmButton.className = "ndt-button " + (options.danger ? "ndt-button--danger" : "ndt-button--primary");
        var previousFocus = (
            options.trigger
            && typeof options.trigger.focus === "function"
        ) ? options.trigger : document.activeElement;
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
                if (!items.length) return;
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

            activeDialog = {
                dialog: dialog,
                resolve: resolve,
                onKeydown: onKeydown,
                previousFocus: previousFocus,
            };
            document.addEventListener("keydown", onKeydown);
            confirmButton.onclick = function () { close(true); };
            Array.prototype.forEach.call(cancelButtons, function (button) {
                button.onclick = function () { close(false); };
            });
            confirmButton.focus();
        });
    }

    window.NDTDialog = { confirm: open, close: close };

    document.querySelectorAll("[data-ndt-confirm-form]").forEach(function (form) {
        function rememberTrigger(event) {
            var trigger = event.target.closest("button[type=submit], input[type=submit]");
            if (trigger && form.contains(trigger)) form.ndtDialogTrigger = trigger;
        }

        form.addEventListener("focusin", rememberTrigger);
        form.addEventListener("pointerdown", rememberTrigger);
        form.addEventListener("click", rememberTrigger);
        form.addEventListener("submit", async function (event) {
            if (form.dataset.confirmed === "true") return;
            event.preventDefault();
            var confirmed = await open({
                title: form.dataset.confirmTitle,
                message: form.dataset.confirmMessage,
                confirmLabel: form.dataset.confirmLabel || "Xác nhận",
                danger: true,
                trigger: form.ndtDialogTrigger || event.submitter || document.activeElement,
            });
            if (confirmed) {
                form.dataset.confirmed = "true";
                form.requestSubmit();
            }
        });
    });
}());
