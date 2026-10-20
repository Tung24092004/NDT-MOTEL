(function () {
    function init() {
        const root = document.getElementById("ndtSupport");
        if (!root || root.dataset.initialized) return;
        root.dataset.initialized = "true";
        const toggle = document.getElementById("ndtSupportToggle");
        const panel = document.getElementById("ndtSupportPanel");
        const closeButton = document.getElementById("ndtSupportClose");
        const body = document.body;
        let previousFocus = null;
        let scheduled = false;

        function close(restoreFocus) {
            if (panel.hidden) return;
            panel.hidden = true;
            toggle.setAttribute("aria-expanded", "false");
            if (restoreFocus && previousFocus && previousFocus.isConnected) previousFocus.focus({preventScroll: true});
        }
        function shellOpen() {
            return body.matches(".ndt-mobile-nav-open, .ndt-auth-opened") ||
                !!document.querySelector('.ndt-flyout.is-open') ||
                !!document.querySelector('.ndt-toast.is-visible') ||
                [...document.querySelectorAll('[aria-modal="true"]')].some(function (el) {
                    return el.getClientRects().length && getComputedStyle(el).visibility === "visible" &&
                        !el.closest('[hidden], [aria-hidden="true"]');
                });
        }
        function updateAvailability() {
            scheduled = false;
            const blocked = shellOpen();
            if (blocked) close(false);
            toggle.hidden = blocked;
            if (blocked || !panel.hidden) return;
            // Keep the launcher away from visible form actions and media controls.
            const controls = [...document.querySelectorAll('button, a, input, select, textarea, video')]
                .filter(el => !root.contains(el) && getComputedStyle(el).visibility === "visible")
                .map(function (el) { return el.getBoundingClientRect(); });
            let overlaps = true;
            const sidebar = document.getElementById("ndtSidebar");
            const contentLeft = window.innerWidth > 900 && sidebar
                ? Math.ceil(sidebar.getBoundingClientRect().right + 12)
                : 12;
            const defaultRight = window.innerWidth <= 520 ? 12 : 20;
            const maxRight = Math.max(
                defaultRight,
                Math.floor(window.innerWidth - contentLeft - toggle.offsetWidth)
            );
            const maxLift = Math.max(
                180,
                Math.floor(window.innerHeight - toggle.offsetHeight - 32)
            );
            for (let lift = 0; lift <= maxLift && overlaps; lift += 12) {
                for (let right = defaultRight; right <= maxRight; right += 24) {
                    root.style.setProperty("--ndt-support-lift", lift + "px");
                    root.style.setProperty("--ndt-support-right", right + "px");
                    const bounds = toggle.getBoundingClientRect();
                    overlaps = controls.some(function (rect) {
                        return rect.width && rect.height && rect.left < bounds.right && rect.right > bounds.left && rect.top < bounds.bottom && rect.bottom > bounds.top;
                    });
                    if (!overlaps) break;
                }
            }
            toggle.hidden = overlaps;
        }
        function schedule() {
            if (!scheduled) { scheduled = true; requestAnimationFrame(updateAvailability); }
        }
        toggle.addEventListener("click", function () {
            if (!panel.hidden) { close(true); return; }
            if (shellOpen()) return;
            previousFocus = document.activeElement;
            panel.hidden = false;
            toggle.setAttribute("aria-expanded", "true");
            closeButton.focus({preventScroll: true});
        });
        closeButton.addEventListener("click", function () { close(true); });
        document.addEventListener("keydown", function (event) {
            if (panel.hidden) return;
            if (event.key === "Escape") { event.preventDefault(); close(true); }
        });
        document.addEventListener("pointerdown", function (event) {
            if (!root.contains(event.target)) close(false);
        });
        document.addEventListener("focusin", function (event) {
            if (!root.contains(event.target)) close(false);
        });
        panel.addEventListener("click", function (event) {
            if (event.target.closest("a")) close(false);
        });
        new MutationObserver(schedule).observe(body, {attributes: true, attributeFilter: ["class"]});
        document.querySelectorAll('.ndt-flyout, [aria-modal="true"]').forEach(function (el) {
            new MutationObserver(schedule).observe(el, {attributes: true, attributeFilter: ["class", "hidden", "aria-hidden"]});
        });
        const toastRegion = document.getElementById("ndtToastRegion");
        if (toastRegion) {
            new MutationObserver(schedule).observe(toastRegion, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ["class"]
            });
        }
        window.addEventListener("scroll", schedule, {passive: true});
        window.addEventListener("resize", schedule);
        body.classList.add("ndt-support-ready");
        updateAvailability();
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once: true});
    else init();
})();
