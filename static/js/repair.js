(function () {
    const form = document.querySelector('[data-repair-submit]');
    if (!form) {
        return;
    }

    form.addEventListener('submit', function () {
        const submit = form.querySelector('button[type="submit"]');
        if (!submit || submit.disabled) {
            return;
        }
        form.classList.add('is-submitting');
        submit.dataset.originalText = submit.textContent;
        submit.textContent = 'Đang gửi...';
        submit.disabled = true;
    });
})();
