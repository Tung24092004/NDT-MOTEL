"""P6J Community Management UI and security-boundary contracts."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from core.models import NguoiThue


TEMPLATES = (
    "quan_ly_nguoi_thue.html",
    "chi_tiet_nguoi_thue.html",
    "quan_ly_nguoi_o_cung.html",
    "tao_nguoi_o_cung.html",
    "chi_tiet_nguoi_o_cung.html",
    "dang_ky_ghep_phong.html",
    "yeu_cau_ghep_cua_toi.html",
    "chi_tiet_yeu_cau_ghep.html",
)


class CommunityManagementP6JStaticTests(SimpleTestCase):
    def test_exact_eight_templates_opt_in_p5_and_p6j(self):
        root = Path(settings.BASE_DIR) / "templates/core"
        owners = {
            path.name for path in root.glob("*.html")
            if "ndt-community-management" in path.read_text(encoding="utf-8")
        }
        self.assertEqual(owners, set(TEMPLATES))
        for name in TEMPLATES:
            source = (root / name).read_text(encoding="utf-8")
            self.assertEqual(source.count("foundation/p5.css"), 1, name)
            self.assertEqual(source.count("community_management_p6j.css"), 1, name)
            self.assertEqual(source.count("ndt-f5 ndt-community-management"), 1, name)
            self.assertNotIn("foundation/tokens.css", source)
            self.assertNotIn("css/community.css", source)
            self.assertNotIn("bill_smart_full_refresh.css", source)

    def test_assets_are_scoped_and_shared_shell_does_not_load_them(self):
        base = Path(settings.BASE_DIR)
        css = (base / "static/css/community_management_p6j.css").read_text(encoding="utf-8")
        js = (base / "static/js/community_management_p6j.js").read_text(encoding="utf-8")
        self.assertNotIn("!important", css)
        for selector in [line.strip() for line in css.splitlines() if line.strip().startswith(".")]:
            self.assertTrue(selector.startswith(".ndt-f5.ndt-community-management"), selector)
        self.assertIn("event.submitter", js)
        self.assertIn("NDTFoundationDialog", js)
        self.assertIn("requestSubmit", js)
        for shell in ("base.html", "tenant_base.html"):
            source = (base / "templates/core" / shell).read_text(encoding="utf-8")
            self.assertNotIn("community_management_p6j", source)

    def test_p5_dialog_replaces_legacy_dialog_on_action_screens(self):
        root = Path(settings.BASE_DIR) / "templates/core"
        for name in ("chi_tiet_nguoi_o_cung.html", "yeu_cau_ghep_cua_toi.html", "chi_tiet_yeu_cau_ghep.html"):
            source = (root / name).read_text(encoding="utf-8")
            self.assertIn("p5_dialog_root.html", source)
            self.assertIn("p5-dialog.js", source)
            self.assertIn("community_management_p6j.js", source)
            self.assertNotIn("foundation/dialog.js", source)


class CommunityManagementP6JAccessTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"P6J_FUNCTIONAL_DATABASE={connection.settings_dict['NAME']}")
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("P6J tests require isolated test_ndt_motel.")

    def setUp(self):
        self.admin = User.objects.create_user("p6j-admin", is_staff=True)
        self.tenant_user = User.objects.create_user("p6j-tenant")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="P6J Tenant",
            cccd="000000006510",
            so_dien_thoai="0900006510",
        )

    def test_route_inventory_has_twelve_patterns_and_eight_templates(self):
        names = (
            "quan_ly_nguoi_thue", "chi_tiet_nguoi_thue",
            "quan_ly_nguoi_o_cung", "tao_nguoi_o_cung",
            "chi_tiet_nguoi_o_cung", "xu_ly_nguoi_o_cung",
            "dang_ky_ghep_phong", "bat_tat_cho_phep_ghep",
            "yeu_cau_ghep_cua_toi", "quan_ly_yeu_cau_ghep",
            "chi_tiet_yeu_cau_ghep", "xu_ly_yeu_cau_ghep",
        )
        self.assertEqual(len(names), 12)
        self.assertEqual(len(TEMPLATES), 8)
        for name in names:
            self.assertTrue(reverse(name, args=[1]) if name in {
                "chi_tiet_nguoi_thue", "chi_tiet_nguoi_o_cung", "xu_ly_nguoi_o_cung",
                "dang_ky_ghep_phong", "bat_tat_cho_phep_ghep",
                "chi_tiet_yeu_cau_ghep", "xu_ly_yeu_cau_ghep",
            } else reverse(name))

    def test_admin_lists_require_admin_and_render_for_staff(self):
        routes = ("quan_ly_nguoi_thue", "quan_ly_nguoi_o_cung", "quan_ly_yeu_cau_ghep")
        for name in routes:
            with self.subTest(name=name, role="guest"):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        self.client.force_login(self.tenant_user)
        for name in routes:
            with self.subTest(name=name, role="tenant"):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        self.client.force_login(self.admin)
        for name in routes:
            with self.subTest(name=name, role="admin"):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_mutation_endpoints_reject_missing_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for name in ("xu_ly_nguoi_o_cung", "xu_ly_yeu_cau_ghep", "bat_tat_cho_phep_ghep"):
            with self.subTest(name=name):
                self.assertEqual(client.post(reverse(name, args=[999999]), {}).status_code, 403)
