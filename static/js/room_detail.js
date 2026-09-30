document.addEventListener("DOMContentLoaded", function () {
    const mainImage = document.getElementById("stay-main-image");
    const thumbnails = Array.from(document.querySelectorAll("[data-gallery-src]"));

    if (!mainImage || thumbnails.length === 0) {
        return;
    }

    // Đồng bộ ảnh lớn và trạng thái truy cập bàn phím của thumbnail đang chọn.
    thumbnails.forEach(function (button) {
        button.addEventListener("click", function () {
            mainImage.src = button.dataset.gallerySrc;
            thumbnails.forEach(function (item) {
                const isActive = item === button;
                item.classList.toggle("is-active", isActive);
                item.setAttribute("aria-pressed", String(isActive));
            });
        });
    });
});
