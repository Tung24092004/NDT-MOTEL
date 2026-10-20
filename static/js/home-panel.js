(function () {
    "use strict";

    function initHomeTools() {
        const root = document.querySelector("[data-home-tools]");

        if (!root || root.dataset.tabsReady === "true") {
            return;
        }

        const tabs = Array.from(root.querySelectorAll('[role="tab"]'));
        const panels = Array.from(root.querySelectorAll('[role="tabpanel"]'));

        if (!tabs.length || tabs.length !== panels.length) {
            return;
        }

        function activate(index, moveFocus) {
            const normalized = (index + tabs.length) % tabs.length;

            tabs.forEach(function (tab, tabIndex) {
                const active = tabIndex === normalized;
                tab.classList.toggle("is-active", active);
                tab.setAttribute("aria-selected", String(active));
                tab.tabIndex = active ? 0 : -1;
            });

            panels.forEach(function (panel, panelIndex) {
                const active = panelIndex === normalized;
                panel.classList.toggle("is-active", active);
                panel.hidden = !active;
                panel.inert = !active;
            });

            if (moveFocus) {
                tabs[normalized].focus();
            }
        }

        tabs.forEach(function (tab, index) {
            tab.addEventListener("click", function () {
                activate(index, false);
            });

            tab.addEventListener("keydown", function (event) {
                const targets = {
                    ArrowRight: index + 1,
                    ArrowDown: index + 1,
                    ArrowLeft: index - 1,
                    ArrowUp: index - 1,
                    Home: 0,
                    End: tabs.length - 1,
                };

                if (!(event.key in targets)) {
                    return;
                }

                event.preventDefault();
                activate(targets[event.key], true);
            });
        });

        root.dataset.tabsReady = "true";
        activate(0, false);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initHomeTools, {once: true});
    } else {
        initHomeTools();
    }
}());
