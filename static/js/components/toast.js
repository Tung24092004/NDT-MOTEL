(function () {
    const region = document.getElementById("ndtToastRegion");
    if (!region) return;

    const duration = { success: 5000, info: 6000, warning: 8000, error: 10000 };
    const icons = { success: "✓", info: "i", warning: "!", error: "!" };

    function normalize(kind) {
        if (!kind) return "info";
        if (kind.indexOf("success") >= 0) return "success";
        if (kind.indexOf("error") >= 0 || kind.indexOf("danger") >= 0) return "error";
        if (kind.indexOf("warning") >= 0) return "warning";
        return "info";
    }

    function showToast(options) {
        const kind = normalize(options.kind);
        const toast = document.createElement("div");
        toast.className = "ndt-toast ndt-toast-" + kind;
        toast.setAttribute("role", kind === "error" ? "alert" : "status");
        toast.innerHTML =
            '<span class="ndt-toast-icon" aria-hidden="true">' + (icons[kind] || "i") + '</span>' +
            '<div><p class="ndt-toast-title"></p><p class="ndt-toast-body"></p></div>' +
            '<button type="button" class="ndt-toast-close" aria-label="Dong thong bao">×</button>';
        toast.querySelector(".ndt-toast-title").textContent = options.title || "Thong bao";
        toast.querySelector(".ndt-toast-body").textContent = options.body || "";
        if (options.url) {
            toast.style.cursor = "pointer";
            toast.addEventListener("click", function (event) {
                if (!event.target.closest("button")) window.location.href = options.url;
            });
        }
        region.appendChild(toast);
        requestAnimationFrame(function () { toast.classList.add("is-visible"); });
        function close() {
            toast.classList.remove("is-visible");
            setTimeout(function () { toast.remove(); }, 220);
        }
        toast.querySelector("button").addEventListener("click", close);
        setTimeout(close, duration[kind] || 6000);
    }

    window.NDTToast = { show: showToast };

    region.querySelectorAll(".ndt-toast-seed").forEach(function (seed) {
        showToast({ kind: seed.dataset.kind, title: seed.dataset.title, body: seed.dataset.body });
        seed.remove();
    });

    const pollUrl = window.NDT_NOTIFICATION_POLL_URL;
    if (!pollUrl) return;
    const status = document.querySelector("[data-notification-status]");
    function updateStatus(message, failed) {
        if (!status) return;
        status.hidden = !message;
        status.textContent = message;
        status.classList.toggle("notification-error", !!failed);
        status.setAttribute("role", failed ? "alert" : "status");
    }

    function alreadyShown(id) {
        const key = "ndtToastShown:" + id;
        if (sessionStorage.getItem(key)) return true;
        sessionStorage.setItem(key, "1");
        return false;
    }

    function updateBadge(count) {
        document.querySelectorAll("[data-notification-badge]").forEach(function (badge) {
            if (count > 0) {
                badge.textContent = count > 99 ? "99+" : String(count);
                badge.hidden = false;
            } else {
                badge.hidden = true;
            }
        });
    }

    function poll() {
        if (document.hidden) return;
        updateStatus("Đang kiểm tra thông báo mới...", false);
        fetch(pollUrl, { headers: { "Accept": "application/json" } })
            .then(function (response) {
                if (!response.ok) throw new Error("Notification polling failed");
                return response.json();
            })
            .then(function (data) {
                if (!data) return;
                updateStatus("", false);
                updateBadge(data.so_chua_doc || 0);
                (data.items || []).forEach(function (item) {
                    if (alreadyShown(item.id)) return;
                    showToast({ kind: item.muc_do === "quan_trong" ? "warning" : "info", title: item.tieu_de, body: item.noi_dung, url: item.detail_url });
                });
            })
            .catch(function () { updateStatus("Không thể cập nhật thông báo. Hệ thống sẽ thử lại; bạn có thể tải lại trang.", true); });
    }

    setTimeout(poll, 1000);
    setInterval(poll, 20000);
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) poll();
    });
})();
