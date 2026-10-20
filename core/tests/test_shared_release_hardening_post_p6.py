from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


class SharedReleaseHardeningContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(settings.BASE_DIR)
        cls.base = (root / "templates/core/base.html").read_text(encoding="utf-8")
        cls.sidebar_css = (root / "static/css/sidebar-shell.css").read_text(encoding="utf-8")
        cls.support_css = (root / "static/css/support-panel.css").read_text(encoding="utf-8")
        cls.support_js = (root / "static/js/support-panel.js").read_text(encoding="utf-8")

    def test_admin_shared_navigation_exposes_every_owned_management_route(self):
        for route in (
            "quan_ly_co_so",
            "quan_ly_yeu_cau_ghep",
            "smart_access_control",
            "quan_ly_chinh_sach",
            "nhat_ky_thao_tac",
        ):
            with self.subTest(route=route):
                self.assertIn("{% url '" + route + "' %}", self.base)

    def test_shared_shell_has_skip_target_and_named_navigation(self):
        self.assertIn('class="ndt-skip-link" href="#ndtMainContent"', self.base)
        self.assertIn('id="ndtMainContent" class="site-main" tabindex="-1"', self.base)
        self.assertIn('id="ndtSidebar" class="ndt-sidebar" aria-label=', self.base)
        self.assertIn(".ndt-skip-link:focus-visible", self.sidebar_css)

    def test_flyouts_get_dialog_names_current_state_and_keyboard_containment(self):
        for contract in (
            'panel.setAttribute("role", "dialog")',
            'panel.setAttribute("aria-modal", "true")',
            'panel.setAttribute("aria-labelledby", title.id)',
            'link.setAttribute("aria-current", "page")',
            'if (event.key === "Tab" && activePanel)',
            'closeButton.focus({preventScroll: true})',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.base)
        self.assertIn("flex: 0 0 44px", self.sidebar_css)

    def test_mobile_drawer_manages_focus_and_escape(self):
        self.assertIn('mobileClose.focus({preventScroll: true})', self.base)
        self.assertIn('body.classList.contains("ndt-mobile-nav-open")', self.base)
        self.assertIn('mobile.focus({preventScroll: true})', self.base)

    def test_support_launcher_yields_to_shell_dialogs_and_toasts(self):
        self.assertIn(".ndt-toast.is-visible", self.support_js)
        self.assertIn('const toastRegion = document.getElementById("ndtToastRegion")', self.support_js)
        self.assertIn("MutationObserver(schedule)", self.support_js)
        self.assertIn("min-height: 44px", self.support_css)
        self.assertNotIn("overflow-x: hidden", self.support_css)

    def test_base_shared_static_assets_resolve(self):
        for asset in (
            "favicon.svg",
            "css/style.css",
            "css/ui-system.css",
            "css/sidebar-shell.css",
            "css/support-panel.css",
            "css/components/toast.css",
            "js/ui-system.js",
            "js/support-panel.js",
            "js/components/toast.js",
        ):
            with self.subTest(asset=asset):
                self.assertTrue(finders.find(asset), asset)
