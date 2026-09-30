/* Progressive enhancement for tenant pages. */
(() => {
    const root = document.querySelector('.tenant-ui');
    if (!root) return;

    const navigationShell = root.querySelector('.tenant-navigation-shell');
    const navigation = root.querySelector('.tenant-navigation');

    function syncNavigationMode() {
        if (!navigationShell) return;

        if (window.matchMedia('(max-width: 700px)').matches) {
            navigationShell.removeAttribute('open');
        } else {
            navigationShell.setAttribute('open', '');
        }
    }

    if (navigationShell) {
        syncNavigationMode();
        window.addEventListener('resize', syncNavigationMode);

        navigationShell.addEventListener('toggle', () => {
            const toggle = navigationShell.querySelector(
                '.tenant-navigation-shell__toggle'
            );

            if (toggle) {
                toggle.setAttribute(
                    'aria-label',
                    navigationShell.open ? 'Thu gọn menu' : 'Mở menu'
                );
            }
        });
    }

    if (navigation) {
        const currentPath = location.pathname;

        navigation.querySelectorAll('a').forEach(link => {
            const linkPath = new URL(link.href, location.origin).pathname;

            if (
                currentPath === linkPath ||
                (
                    link.dataset.match === 'prefix' &&
                    currentPath.startsWith(linkPath) &&
                    linkPath !== '/'
                )
            ) {
                link.setAttribute('aria-current', 'page');
            }
        });
    }

    root.querySelectorAll('table').forEach(table => {
        if (table.parentElement.classList.contains('tenant-table-scroll')) {
            return;
        }

        const wrap = document.createElement('div');
        wrap.className = 'tenant-table-scroll';
        wrap.tabIndex = 0;
        wrap.setAttribute('role', 'region');
        wrap.setAttribute(
            'aria-label',
            'Bảng dữ liệu, cuộn ngang để xem thêm'
        );

        table.before(wrap);
        wrap.append(table);
    });

    root.addEventListener('submit', event => {
        const form = event.target;

        if (
            form.method.toLowerCase() !== 'post' ||
            event.defaultPrevented
        ) {
            return;
        }

        if (form.dataset.submitting === 'true') {
            event.preventDefault();
            return;
        }

        form.dataset.submitting = 'true';
        form.setAttribute('aria-busy', 'true');

        setTimeout(() => {
            if (event.defaultPrevented) {
                delete form.dataset.submitting;
                form.removeAttribute('aria-busy');
            }
        }, 0);
    });

    window.addEventListener('pageshow', () => {
        root.querySelectorAll('form').forEach(form => {
            delete form.dataset.submitting;
            form.removeAttribute('aria-busy');
        });
    });
})();