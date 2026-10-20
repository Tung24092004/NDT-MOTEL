from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import YeuCauSuaChua


class RepairManagementP6EContractTests(SimpleTestCase):
    templates = (
        "quan_ly_sua_chua.html",
        "chi_tiet_sua_chua.html",
        "tao_sua_chua.html",
        "yeu_cau_sua_chua_cua_toi.html",
        "tao_yeu_cau_sua_chua.html",
        "chi_tiet_yeu_cau_sua_chua_cua_toi.html",
    )

    def source(self, name):
        return (Path(settings.BASE_DIR) / "templates" / "core" / name).read_text(encoding="utf-8")

    def test_exactly_six_repair_templates_opt_in_to_p5(self):
        for name in self.templates:
            source = self.source(name)
            self.assertIn("css/foundation/p5.css", source, name)
            self.assertIn("css/repair_management_p6e.css", source, name)
            self.assertIn("ndt-f5 ndt-f5-page ndt-repair-management", source, name)

    def test_shared_bases_do_not_load_p6e_assets(self):
        for name in ("base.html", "tenant_base.html", "home.html"):
            source = self.source(name)
            self.assertNotIn("repair_management_p6e.css", source, name)
            self.assertNotIn("repair_management_p6e.js", source, name)

    def test_list_filters_and_mobile_table_contract_are_preserved(self):
        admin = self.source("quan_ly_sua_chua.html")
        tenant = self.source("yeu_cau_sua_chua_cua_toi.html")
        self.assertIn('name="q"', admin)
        self.assertIn('name="trang_thai"', admin)
        self.assertIn('name="trang_thai"', tenant)
        body = admin.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        self.assertEqual(body.count("<td"), body.count("data-label="))

    def test_create_and_update_forms_keep_real_payloads(self):
        expected = {
            "tao_sua_chua.html": (
                "nguoi_thue", "phong", "tieu_de", "noi_dung", "loai_su_co",
                "muc_do", "hinh_anh", "chi_phi", "chi_tiet_chi_phi", "ghi_chu_admin",
            ),
            "tao_yeu_cau_sua_chua.html": (
                "phong", "tieu_de", "noi_dung", "loai_su_co", "muc_do", "hinh_anh",
            ),
            "chi_tiet_sua_chua.html": (
                "trang_thai", "nguoi_xu_ly", "chi_phi", "chi_tiet_chi_phi", "ghi_chu_admin",
            ),
        }
        for name, fields in expected.items():
            source = self.source(name)
            self.assertIn("{% csrf_token %}", source)
            for field in fields:
                self.assertIn(f'name="{field}"', source, f"{name}: {field}")
        for name in ("tao_sua_chua.html", "tao_yeu_cau_sua_chua.html"):
            self.assertIn('enctype="multipart/form-data"', self.source(name))

    def test_admin_update_uses_p5_dialog_and_module_js(self):
        source = self.source("chi_tiet_sua_chua.html")
        self.assertIn("data-repair-confirm", source)
        self.assertIn("core/foundation/p5_dialog_root.html", source)
        self.assertIn("js/foundation/p5-dialog.js", source)
        self.assertIn("js/repair_management_p6e.js", source)
        self.assertNotIn("window.confirm", source)
        self.assertNotIn("js/foundation/dialog.js", source)

    def test_module_assets_are_namespaced_and_preserve_native_submission(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "repair_management_p6e.css").read_text(encoding="utf-8")
        js = (Path(settings.BASE_DIR) / "static" / "js" / "repair_management_p6e.js").read_text(encoding="utf-8")
        self.assertIn(".ndt-f5.ndt-repair-management", css)
        self.assertNotIn("!important", css)
        self.assertIn("window.NDTFoundationDialog.confirm", js)
        self.assertIn("form.requestSubmit(submitter", js)
        self.assertIn("event.stopPropagation()", js)
        self.assertIn('form.dataset.submitting === "true"', js)
        self.assertNotIn("window.confirm", js)


class RepairManagementP6ERequestContractTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            tieu_de="P6E repair",
            noi_dung="Repair request contract",
            loai_su_co="dien",
            muc_do="cao",
        )

    def test_admin_and_tenant_filters_use_existing_query_parameters(self):
        self.client.force_login(self.admin)
        admin = self.client.get(reverse("quan_ly_sua_chua"), {"q": "P6E", "trang_thai": "moi"})
        self.assertEqual(admin.status_code, 200)
        self.assertEqual(list(admin.context["yeu_cau"]), [self.repair])

        self.client.force_login(self.user)
        tenant = self.client.get(reverse("yeu_cau_sua_chua_cua_toi"), {"trang_thai": "moi"})
        self.assertEqual(tenant.status_code, 200)
        self.assertEqual(list(tenant.context["yeu_cau"]), [self.repair])

    def test_role_and_ownership_contract_remains_enforced(self):
        self.assertEqual(self.client.get(reverse("quan_ly_sua_chua")).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("quan_ly_sua_chua")).status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("yeu_cau_sua_chua_cua_toi")).status_code, 302)
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(reverse("chi_tiet_yeu_cau_sua_chua_cua_toi", args=[self.repair.pk])).status_code,
            404,
        )

    def test_get_action_is_read_only(self):
        self.client.force_login(self.admin)
        before = list(YeuCauSuaChua.objects.values("id", "trang_thai", "nguoi_xu_ly", "chi_phi"))
        response = self.client.get(reverse("xu_ly_sua_chua", args=[self.repair.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(YeuCauSuaChua.objects.values("id", "trang_thai", "nguoi_xu_ly", "chi_phi")), before)

    def test_repair_post_endpoints_reject_missing_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        admin_create = client.post(reverse("tao_sua_chua"), {
            "nguoi_thue": self.tenant.pk,
            "phong": self.room.pk,
            "tieu_de": "No CSRF admin",
            "noi_dung": "Denied",
            "loai_su_co": "dien",
            "muc_do": "cao",
        })
        update = client.post(reverse("xu_ly_sua_chua", args=[self.repair.pk]), {"trang_thai": "hoan_thanh"})
        client.force_login(self.user)
        tenant_create = client.post(reverse("tao_yeu_cau_sua_chua"), {
            "phong": self.room.pk,
            "tieu_de": "No CSRF tenant",
            "noi_dung": "Denied",
            "loai_su_co": "dien",
            "muc_do": "cao",
        })
        self.assertEqual((admin_create.status_code, update.status_code, tenant_create.status_code), (403, 403, 403))
        self.assertEqual(YeuCauSuaChua.objects.count(), 1)
