(function () {
    function normalize(value) {
        return (value || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/đ/g, "d");
    }

    document.addEventListener("DOMContentLoaded", function () {
        const input = document.getElementById("helpSearch");
        const clear = document.getElementById("helpClearSearch");
        const empty = document.getElementById("helpEmpty");
        const emptyClear = document.getElementById("helpEmptyClear");
        const status = document.getElementById("helpSearchStatus");
        const items = Array.from(document.querySelectorAll("[data-help-search], .help-faq details"));
        if (!input || !items.length) return;

        function textFor(item) {
            return normalize([item.textContent, item.dataset.helpSearch].join(" "));
        }

        function applySearch() {
            const query = normalize(input.value.trim());
            let visible = 0;
            items.forEach(function (item) {
                const match = !query || textFor(item).includes(query);
                item.hidden = !match;
                if (match) visible += 1;
            });
            if (clear) clear.hidden = !query;
            if (empty) empty.hidden = !query || visible > 0;
            if (status) status.textContent = query ? visible + " kết quả phù hợp." : "";
        }

        function clearSearch() {
            input.value = "";
            applySearch();
            input.focus();
        }

        input.addEventListener("input", applySearch);
        if (clear) clear.addEventListener("click", clearSearch);
        if (emptyClear) emptyClear.addEventListener("click", clearSearch);
        applySearch();
        function openLinkedTopic() {
            const target = document.getElementById(location.hash.slice(1));
            if (!target || !target.matches(".help-faq details")) return;
            input.value = "";
            applySearch();
            target.open = true;
            target.scrollIntoView({block: "start"});
        }
        window.addEventListener("hashchange", openLinkedTopic);
        openLinkedTopic();
    });
})();
