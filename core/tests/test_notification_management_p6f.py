import re
from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import ThongBao


TEMPLATES = (
    "quan_ly_thong_bao.html",
    "tao_thong_bao.html",
    "chi_tiet_thong_bao.html",
    "thong_bao_admin.html",
    "chi_tiet_thong_bao_admin.html",
    "thong_bao_cua_toi.html",
    "chi_tiet_thong_bao_cua_toi.html",
)


class NotificationManagementP6FSourceTests(SimpleTestCase):
    def setUp(self):
        self.template_root = Path(settings.BASE_DIR) / "templates" / "core"
        self.sources = {
            name: (self.template_root / name).read_text(encoding="utf-8")
            for name in TEMPLATES
        }
        self.css = (
            Path(settings.BASE_DIR) / "static" / "css" / "notification_management_p6f.css"
        ).read_text(encoding="utf-8")
        self.js = (
            Path(settings.BASE_DIR) / "static" / "js" / "notification_management_p6f.js"
        ).read_text(encoding="utf-8")

    def test_all_seven_screens_opt_in_to_p5_and_p6f_namespace(self):
        self.assertEqual(len(self.sources), 7)
        for source in self.sources.values():
            self.assertIn("css/foundation/p5.css", source)
            self.assertIn("css/notification_management_p6f.css", source)
            self.assertIn("ndt-f5 ndt-f5-page ndt-notification-management", source)
            self.assertNotIn("css/notification.css", source)
            self.assertNotIn("ndt-foundation", source)

    def test_module_assets_are_not_loaded_by_shared_bases(self):
        for name in ("base.html", "tenant_base.html"):
            source = (self.template_root / name).read_text(encoding="utf-8")
            self.assertNotIn("notification_management_p6f.css", source)
            self.assertNotIn("notification_management_p6f.js", source)

    def test_filter_and_form_payload_contracts_are_preserved(self):
        for name in ("quan_ly_thong_bao.html", "thong_bao_cua_toi.html"):
            source = self.sources[name]
            for field in ('name="q"', 'name="loai"', 'name="muc_do"', 'name="da_doc"'):
                self.assertIn(field, source)

        create = self.sources["tao_thong_bao.html"]
        for field in ('name="nguoi_thue"', 'name="tieu_de"', 'name="noi_dung"', 'name="loai"', 'name="muc_do"'):
            self.assertIn(field, create)
        detail = self.sources["chi_tiet_thong_bao.html"]
        for action in ("cap_nhat", "da_doc", "chua_doc", "xoa"):
            self.assertIn(f'value="{action}"', detail)

    def test_delete_uses_accessible_p5_dialog_and_request_submit(self):
        detail = self.sources["chi_tiet_thong_bao.html"]
        self.assertIn("data-notification-confirm", detail)
        self.assertIn("core/foundation/p5_dialog_root.html", detail)
        self.assertIn("js/foundation/p5-dialog.js", detail)
        self.assertNotIn("onsubmit=", detail)
        self.assertNotIn("confirm(", detail)
        self.assertIn("window.NDTFoundationDialog.confirm", self.js)
        self.assertIn("form.requestSubmit", self.js)
        self.assertIn("event.submitter", self.js)
        self.assertNotIn("window.confirm", self.js)

    def test_p6f_css_is_namespaced_and_has_no_important(self):
        selector_headers = re.findall(r"(?m)^\s*([^@}\n][^{\n]*)\{", self.css)
        selectors = []
        for header in selector_headers:
            selectors.extend(part.strip() for part in header.split(","))
        unscoped = [selector for selector in selectors if not selector.startswith(".ndt-f5.ndt-notification-management")]
        self.assertEqual(unscoped, [])
        self.assertNotIn("!important", self.css)

    def test_semantic_badges_are_shared_by_admin_and_tenant(self):
        status = (self.template_root / "partials" / "notification_status_badge.html").read_text(encoding="utf-8")
        priority = (self.template_root / "partials" / "notification_priority_badge.html").read_text(encoding="utf-8")
        self.assertIn("ndt-f5-badge--success", status)
        self.assertIn("ndt-f5-badge--pending", status)
        self.assertIn("ndt-f5-badge--danger", priority)
        self.assertIn("ndt-f5-badge--warning", priority)


class NotificationManagementP6FRequestTests(Phase5BookingFixture):
    def setUp(self):
        super().setUp()
        self.tenant_notice = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Bao tri P6F",
            noi_dung="Thong bao thuoc dung nguoi thue.",
            loai="bao_tri",
            muc_do="quan_trong",
        )
        self.foreign_notice = ThongBao.objects.create(
            nguoi_thue=self.other,
            tieu_de="Thong bao ben ngoai",
            noi_dung="Khong duoc hien thi.",
            loai="he_thong",
        )
        self.admin_notice = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Admin P6F",
            noi_dung="Thong bao inbox admin.",
            loai="he_thong",
        )

    def test_admin_and_tenant_filters_keep_existing_query_contract(self):
        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse("quan_ly_thong_bao"), {"q": "P6F", "loai": "bao_tri", "muc_do": "quan_trong", "da_doc": "chua_doc"})
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, self.tenant_notice.tieu_de)
        self.assertNotContains(admin_response, self.foreign_notice.tieu_de)

        self.client.force_login(self.user)
        tenant_response = self.client.get(reverse("thong_bao_cua_toi"), {"q": "P6F", "loai": "bao_tri", "muc_do": "quan_trong", "da_doc": "chua_doc"})
        self.assertEqual(tenant_response.status_code, 200)
        self.assertContains(tenant_response, self.tenant_notice.tieu_de)
        self.assertNotContains(tenant_response, self.foreign_notice.tieu_de)

    def test_tenant_detail_keeps_get_read_mutation_and_ownership(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chi_tiet_thong_bao_cua_toi", args=[self.tenant_notice.pk]))
        self.assertEqual(response.status_code, 200)
        self.tenant_notice.refresh_from_db()
        self.assertTrue(self.tenant_notice.da_doc)
        self.assertIsNotNone(self.tenant_notice.ngay_doc)
        self.assertEqual(self.client.get(reverse("chi_tiet_thong_bao_cua_toi", args=[self.foreign_notice.pk])).status_code, 404)

    def test_supporting_get_endpoints_do_not_mutate_admin_notices(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("doc_thong_bao_admin", args=[self.admin_notice.pk]))
        self.assertEqual(response.status_code, 405)
        self.admin_notice.refresh_from_db()
        self.assertFalse(self.admin_notice.da_doc)

        response = self.client.get(reverse("xu_ly_thong_bao", args=[self.tenant_notice.pk]))
        self.assertEqual(response.status_code, 302)
        self.tenant_notice.refresh_from_db()
        self.assertFalse(self.tenant_notice.da_doc)

    def test_notification_post_endpoints_reject_missing_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        create_payload = {"nguoi_thue": self.tenant.pk, "tieu_de": "CSRF", "noi_dung": "Body", "loai": "he_thong", "muc_do": "binh_thuong"}
        self.assertEqual(client.post(reverse("tao_thong_bao"), create_payload).status_code, 403)
        self.assertEqual(client.post(reverse("xu_ly_thong_bao", args=[self.tenant_notice.pk]), {"hanh_dong": "xoa"}).status_code, 403)
        self.assertEqual(client.post(reverse("doc_thong_bao_admin", args=[self.admin_notice.pk])).status_code, 403)
        self.assertEqual(client.post(reverse("doc_tat_ca_thong_bao_admin")).status_code, 403)
        self.assertTrue(ThongBao.objects.filter(pk=self.tenant_notice.pk).exists())
        self.admin_notice.refresh_from_db()
        self.assertFalse(self.admin_notice.da_doc)
