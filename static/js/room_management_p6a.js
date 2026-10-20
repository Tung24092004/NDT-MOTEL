(function () {
    "use strict";

    function setupDialogLayer() {
        var dialog = document.querySelector("[data-ndt-f5-dialog]");
        if (dialog && dialog.parentElement !== document.body) {
            document.body.appendChild(dialog);
        }
    }

    function setupDeleteDialogs() {
        document.querySelectorAll("[data-room-delete-form]").forEach(function (form) {
            form.addEventListener("submit", async function (event) {
                if (form.dataset.confirmed === "true") return;
                event.preventDefault();
                var trigger = event.submitter || form.querySelector("[data-room-delete-trigger]");
                var decision = window.NDTFoundationDialog.confirm({
                    title: form.dataset.confirmTitle,
                    message: form.dataset.confirmMessage,
                    confirmLabel: form.dataset.confirmLabel,
                    danger: true,
                    trigger: trigger,
                });
                var cancel = document.querySelector("[data-ndt-f5-dialog] .ndt-f5-dialog__actions [data-ndt-f5-dialog-cancel]");
                if (cancel) cancel.focus();
                if (await decision) {
                    form.dataset.confirmed = "true";
                    trigger.setAttribute("aria-busy", "true");
                    trigger.setAttribute("aria-disabled", "true");
                    form.requestSubmit(trigger);
                }
            });
        });
    }

    function setupSubmitLock() {
        document.querySelectorAll("[data-room-save-form]").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                if (form.dataset.submitting === "true") {
                    event.preventDefault();
                    return;
                }
                form.dataset.submitting = "true";
                var submitter = event.submitter;
                if (submitter) {
                    submitter.setAttribute("aria-busy", "true");
                    submitter.disabled = true;
                }
            });
        });
    }

    function setupMaintenanceState() {
        var maintenance = document.getElementById("bat_bao_tri");
        var status = document.querySelector('input[name="trang_thai"][data-business-status]');
        if (!maintenance || !status) return;
        maintenance.addEventListener("change", function () {
            status.value = this.checked ? "bao_tri" : status.dataset.businessStatus;
        });
    }

    function setupImagePreview() {
        var input = document.getElementById("hinh_anh");
        var grid = document.getElementById("image-preview-grid");
        if (!input || !grid) return;
        input.addEventListener("change", function () {
            grid.innerHTML = "";
            Array.prototype.forEach.call(this.files, function (file) {
                if (!file.type.startsWith("image/")) return;
                var item = document.createElement("div");
                var image = document.createElement("img");
                var name = document.createElement("div");
                var reader = new FileReader();
                item.className = "ndt-room-image-preview-item";
                image.alt = file.name;
                name.className = "ndt-room-image-preview-name";
                name.textContent = file.name;
                item.append(image, name);
                grid.appendChild(item);
                reader.onload = function (event) { image.src = event.target.result; };
                reader.readAsDataURL(file);
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        setupDialogLayer();
        setupDeleteDialogs();
        setupSubmitLock();
        setupMaintenanceState();
        setupImagePreview();
    });
}());
