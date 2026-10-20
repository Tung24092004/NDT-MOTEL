(function () {
    "use strict";

    const AUTO_PLAY_DELAY = 6500;
    const SWIPE_THRESHOLD = 50;

    function initHomeSlider() {
        const hero = document.querySelector(".ndt-home-hero");

        if (!hero || hero.dataset.sliderReady === "true") {
            return;
        }

        const slides = Array.from(hero.querySelectorAll("[data-home-slide]"));
        const controls = Array.from(hero.querySelectorAll("[data-home-go]"));
        const pauseButton = hero.querySelector(".ndt-home-pause");
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

        if (slides.length !== 4 || controls.length !== 4 || !pauseButton) {
            return;
        }

        const state = {
            currentIndex: 0,
            timer: null,
            paused: false,
            pointerStartX: null,
        };

        hero.dataset.sliderReady = "true";

        function clearTimer() {
            if (state.timer !== null) {
                window.clearTimeout(state.timer);
                state.timer = null;
            }
        }

        function scheduleAutoPlay() {
            clearTimer();

            if (
                state.paused
                || reducedMotion.matches
                || document.hidden
            ) {
                return;
            }

            state.timer = window.setTimeout(function () {
                showSlide(state.currentIndex + 1, true);
            }, AUTO_PLAY_DELAY);
        }

        function showSlide(index, restartTimer) {
            state.currentIndex = (index + slides.length) % slides.length;
            hero.style.setProperty("--home-active-index", state.currentIndex);

            slides.forEach(function (slide, slideIndex) {
                const active = slideIndex === state.currentIndex;
                slide.classList.toggle("is-active", active);
                slide.setAttribute("aria-hidden", String(!active));
                slide.inert = !active;
            });

            controls.forEach(function (control, controlIndex) {
                const active = controlIndex === state.currentIndex;
                control.classList.toggle("is-active", active);
                control.setAttribute("aria-current", String(active));
            });

            if (restartTimer) {
                scheduleAutoPlay();
            }
        }

        function selectAndFocus(index) {
            showSlide(index, true);
            controls[state.currentIndex].focus();
        }

        controls.forEach(function (control, index) {
            control.addEventListener("click", function () {
                showSlide(index, true);
            });

            control.addEventListener("keydown", function (event) {
                const keys = {
                    ArrowDown: index + 1,
                    ArrowRight: index + 1,
                    ArrowUp: index - 1,
                    ArrowLeft: index - 1,
                    Home: 0,
                    End: slides.length - 1,
                };

                if (!(event.key in keys)) {
                    return;
                }

                event.preventDefault();
                selectAndFocus(keys[event.key]);
            });
        });

        pauseButton.addEventListener("click", function () {
            state.paused = !state.paused;
            pauseButton.setAttribute("aria-pressed", String(state.paused));
            pauseButton.setAttribute(
                "aria-label",
                state.paused
                    ? "Tiếp tục trình chiếu tự động"
                    : "Tạm dừng trình chiếu tự động"
            );
            pauseButton.textContent = state.paused ? "Tiếp tục" : "Tạm dừng";
            scheduleAutoPlay();
        });

        hero.addEventListener("pointerdown", function (event) {
            if (event.target.closest("a, button")) {
                state.pointerStartX = null;
                return;
            }

            state.pointerStartX = event.clientX;
        });

        hero.addEventListener("pointerup", function (event) {
            if (state.pointerStartX === null) {
                return;
            }

            const distance = event.clientX - state.pointerStartX;
            state.pointerStartX = null;

            if (Math.abs(distance) < SWIPE_THRESHOLD) {
                return;
            }

            showSlide(
                state.currentIndex + (distance < 0 ? 1 : -1),
                true
            );
        });

        hero.addEventListener("pointercancel", function () {
            state.pointerStartX = null;
        });

        reducedMotion.addEventListener("change", scheduleAutoPlay);
        document.addEventListener("visibilitychange", scheduleAutoPlay);

        showSlide(0, false);
        scheduleAutoPlay();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initHomeSlider, {once: true});
    } else {
        initHomeSlider();
    }
}());
