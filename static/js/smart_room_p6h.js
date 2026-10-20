(function () {
    "use strict";

    function csrfToken(root) {
        var input = root.querySelector('[name="csrfmiddlewaretoken"]') || document.querySelector('[name="csrfmiddlewaretoken"]');
        return input ? input.value : "";
    }

    function setBusy(button, busy) {
        if (!button) return;
        if (busy) {
            button.dataset.smartLabel = button.textContent;
            button.textContent = button.dataset.busyLabel || "Đang xử lý…";
            button.disabled = true;
            button.setAttribute("aria-busy", "true");
        } else {
            button.textContent = button.dataset.smartLabel || button.textContent;
            button.disabled = false;
            button.removeAttribute("aria-busy");
        }
    }

    function initSubjectPicker(root) {
        var radios = root.querySelectorAll('[data-smart-subject] input[type="radio"]');
        if (!radios.length) return;
        var tenant = root.querySelector('[data-subject-field="nguoi_thue"]');
        var companion = root.querySelector('[data-subject-field="nguoi_o_cung"]');
        var tenantSelect = tenant && tenant.querySelector("select");
        var companionSelect = companion && companion.querySelector("select");
        var permissionType = root.querySelector('[name="loai_quyen"]');
        function sync() {
            var checked = root.querySelector('[data-smart-subject] input[type="radio"]:checked');
            var isTenant = !checked || checked.value === "nguoi_thue";
            if (tenant) tenant.hidden = !isTenant;
            if (companion) companion.hidden = isTenant;
            if (tenantSelect) { tenantSelect.required = isTenant; if (!isTenant) tenantSelect.value = ""; }
            if (companionSelect) { companionSelect.required = !isTenant; if (isTenant) companionSelect.value = ""; }
            if (permissionType) permissionType.value = isTenant ? "chu_phong" : "nguoi_o_cung";
        }
        radios.forEach(function (radio) { radio.addEventListener("change", sync); });
        sync();
    }

    function initConfirm(form) {
        form.addEventListener("submit", function (event) {
            if (form.dataset.smartConfirmed === "1") return;
            event.preventDefault();
            var submitter = event.submitter;
            var title = form.dataset.smartConfirmTitle || "Xác nhận thao tác?";
            var message = form.dataset.smartConfirmMessage || "Thao tác này sẽ thay đổi trạng thái dữ liệu.";
            if (!window.NDTFoundationDialog || !window.NDTFoundationDialog.confirm) return;
            window.NDTFoundationDialog.confirm({ title: title, message: message, trigger: submitter }).then(function (ok) {
                if (!ok) return;
                form.dataset.smartConfirmed = "1";
                form.requestSubmit(submitter || undefined);
            });
        });
    }

    function initSubmitLock(form) {
        form.addEventListener("submit", function (event) {
            if (event.defaultPrevented) return;
            var button = event.submitter || form.querySelector('button[type="submit"]');
            if (button && !button.disabled) setBusy(button, true);
        });
    }

    function cameraMessage(root, text, state) {
        var status = root.querySelector("[data-camera-status]");
        if (!status) return;
        status.textContent = text;
        status.dataset.state = state || "";
        status.setAttribute("aria-live", state === "error" ? "assertive" : "polite");
    }

    function initCamera(root) {
        var video = root.querySelector("video");
        var canvas = root.querySelector("canvas");
        var start = root.querySelector("[data-camera-start]");
        var stop = root.querySelector("[data-camera-stop]");
        var submit = root.querySelector("[data-camera-submit]");
        var placeholder = root.querySelector("[data-camera-placeholder]");
        var stream = null;
        var processing = false;
        var destroyed = false;
        var observer = null;

        function setCameraState(state, message, tone) {
            root.dataset.cameraState = state;
            cameraMessage(root, message, tone || (state === "denied" || state === "error" ? "error" : state === "ready" ? "success" : ""));

            if (start) {
                var startVisible = state !== "ready" && state !== "processing";
                start.hidden = !startVisible;
                start.disabled = state === "opening";
                start.textContent = state === "opening"
                    ? (start.dataset.busyLabel || "Đang mở…")
                    : (state === "idle" ? (start.dataset.startLabel || "Mở camera") : (start.dataset.restartLabel || "Mở lại camera"));
                if (state === "opening") start.setAttribute("aria-busy", "true");
                else start.removeAttribute("aria-busy");
            }
            if (stop) {
                stop.hidden = state !== "ready" && state !== "processing";
                stop.disabled = state !== "ready";
            }
            if (submit) {
                if (!submit.dataset.cameraLabel) submit.dataset.cameraLabel = submit.textContent;
                submit.disabled = state !== "ready";
                submit.textContent = state === "processing"
                    ? (submit.dataset.busyLabel || "Đang xử lý…")
                    : submit.dataset.cameraLabel;
                if (state === "processing") submit.setAttribute("aria-busy", "true");
                else submit.removeAttribute("aria-busy");
            }
        }

        function stopCamera() {
            var activeStream = stream;
            stream = null;
            if (activeStream && activeStream.getTracks) {
                activeStream.getTracks().forEach(function (track) { track.stop(); });
            }
            if (video) {
                if (typeof video.pause === "function") video.pause();
                video.srcObject = null;
                video.hidden = true;
            }
            if (placeholder) placeholder.hidden = false;
        }

        function handleRuntimeStop() {
            if (!stream || destroyed) return;
            stopCamera();
            setCameraState("error", "Camera đã dừng ngoài dự kiến. Hãy mở lại camera để tiếp tục.", "error");
        }

        if (start) start.addEventListener("click", async function () {
            if (processing || root.dataset.cameraState === "opening") return;
            if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                stopCamera();
                setCameraState("error", "Trình duyệt không hỗ trợ camera trong ngữ cảnh hiện tại.", "error");
                return;
            }
            stopCamera();
            setCameraState("opening", "Đang yêu cầu quyền và mở camera…");
            try {
                var nextStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
                if (destroyed || !root.isConnected) {
                    nextStream.getTracks().forEach(function (track) { track.stop(); });
                    return;
                }
                stream = nextStream;
                stream.getTracks().forEach(function (track) {
                    if (track.addEventListener) track.addEventListener("ended", handleRuntimeStop, { once: true });
                });
                video.srcObject = stream;
                await video.play();
                if (placeholder) placeholder.hidden = true;
                video.hidden = false;
                setCameraState("ready", "Camera đã sẵn sàng. Bản xem trước được lật gương; ảnh gửi nhận diện giữ nguyên hướng nguồn.", "success");
            } catch (error) {
                stopCamera();
                if (error && error.name === "NotAllowedError") {
                    setCameraState("denied", "Bạn chưa cấp quyền sử dụng camera.", "error");
                } else {
                    setCameraState("error", "Không thể mở camera. Hãy kiểm tra thiết bị và thử lại.", "error");
                }
            }
        });

        if (stop) stop.addEventListener("click", function () {
            if (processing) return;
            stopCamera();
            setCameraState("stopped", "Camera đã dừng. Bạn có thể mở lại khi sẵn sàng.");
            if (start) start.focus();
        });

        if (submit) submit.addEventListener("click", async function () {
            if (processing || !stream || !video.videoWidth) {
                setCameraState(stream ? "ready" : "stopped", "Hãy mở camera và chờ hình ảnh sẵn sàng.", "error");
                return;
            }
            var consent = root.closest("main").querySelector("[data-face-consent]");
            if (consent && !consent.checked) {
                cameraMessage(root, "Bạn cần đồng ý xử lý dữ liệu khuôn mặt.", "error");
                consent.focus();
                return;
            }
            var room = root.closest("main").querySelector("[data-camera-room]");
            if (room && !room.value) { cameraMessage(root, "Hãy chọn phòng cần xác thực.", "error"); room.focus(); return; }
            processing = true;
            setBusy(submit, true);
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
            var payload = new FormData();
            payload.append("image", canvas.toDataURL("image/jpeg", 0.9));
            if (consent) payload.append("dong_y_du_lieu_khuon_mat", "1");
            if (room) payload.append("phong", room.value);
            var eventType = root.closest("main").querySelector('[name="loai_su_kien"]:checked');
            if (eventType) payload.append("loai_su_kien", eventType.value);
            setCameraState("processing", "Đang xử lý dữ liệu nhận diện…");
            try {
                var controller = new AbortController();
                var timer = window.setTimeout(function () { controller.abort(); }, 30000);
                var response = await fetch(root.dataset.endpoint, { method: "POST", body: payload, headers: { "X-CSRFToken": csrfToken(root.closest("main")) }, signal: controller.signal });
                window.clearTimeout(timer);
                var data = await response.json();
                var granted = data.duoc_phep === true || data.access === "granted" || (data.success === true && root.dataset.mode === "enroll");
                setCameraState("ready", data.message || (granted ? "Thao tác thành công." : "Không thể xác thực khuôn mặt."), granted ? "success" : "error");
                var result = root.closest("main").querySelector("[data-camera-result]");
                if (result) { result.hidden = false; result.dataset.state = granted ? "success" : "error"; result.textContent = data.message || (granted ? "Đã cho phép truy cập." : "Truy cập bị từ chối."); }
                if (response.ok && data.success && root.dataset.mode === "enroll") window.setTimeout(function () { window.location.reload(); }, 900);
            } catch (error) {
                stopCamera();
                setCameraState("error", error && error.name === "AbortError" ? "Yêu cầu quá thời gian. Vui lòng thử lại." : "Không thể kết nối dịch vụ xác thực.", "error");
            } finally {
                processing = false;
                if (root.dataset.cameraState === "processing") {
                    setCameraState(stream ? "ready" : "error", stream ? "Camera đã sẵn sàng." : "Camera đã dừng ngoài dự kiến.", stream ? "success" : "error");
                }
            }
        });

        if (video) video.addEventListener("error", handleRuntimeStop);

        function teardownCamera() {
            destroyed = true;
            if (observer) observer.disconnect();
            stopCamera();
        }

        window.addEventListener("pagehide", teardownCamera, { once: true });
        if (window.MutationObserver && document.documentElement) {
            observer = new MutationObserver(function () {
                if (!root.isConnected) teardownCamera();
            });
            observer.observe(document.documentElement, { childList: true, subtree: true });
        }
        setCameraState("idle", "Camera chưa được mở.");
    }

    document.addEventListener("DOMContentLoaded", function () {
        var moduleRoot = document.querySelector(".ndt-smart-room-management");
        if (!moduleRoot) return;
        initSubjectPicker(moduleRoot);
        moduleRoot.querySelectorAll("form[data-smart-confirm]").forEach(initConfirm);
        moduleRoot.querySelectorAll('form[method="post"]:not([data-camera-form])').forEach(initSubmitLock);
        moduleRoot.querySelectorAll("[data-smart-camera]").forEach(initCamera);
    });
}());
