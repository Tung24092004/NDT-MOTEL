from pathlib import Path
from decimal import Decimal

from django.conf import settings
from django.test import Client, SimpleTestCase
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import HoaDon


class InvoiceManagementP6DContractTests(SimpleTestCase):
    templates = (
        "quan_ly_hoa_don.html",
        "tao_hoa_don.html",
        "chi_tiet_hoa_don.html",
        "hoa_don_cua_toi.html",
        "chi_tiet_hoa_don_cua_toi.html",
        "thanh_toan_hoa_don_cua_toi.html",
    )

    def source(self, name):
        return (Path(settings.BASE_DIR) / "templates" / "core" / name).read_text(encoding="utf-8")

    def test_exactly_six_invoice_templates_opt_in_to_p5(self):
        for name in self.templates:
            source = self.source(name)
            self.assertIn("css/foundation/p5.css", source, name)
            self.assertIn("css/invoice_management_p6d.css", source, name)
            self.assertIn("ndt-f5 ndt-invoice-management", source, name)

    def test_shared_bases_do_not_load_p5(self):
        for name in ("base.html", "tenant_base.html", "home.html"):
            source = self.source(name)
            self.assertNotIn("css/invoice_management_p6d.css", source, name)
            self.assertNotIn("js/invoice_management_p6d.js", source, name)

    def test_admin_list_uses_p5_filter_table_row_cards_and_semantic_badges(self):
        source = self.source("quan_ly_hoa_don.html")
        for marker in (
            'name="q"',
            'name="trang_thai"',
            "ndt-f5-filter",
            "ndt-f5-table-wrap",
            "ndt-f5-table",
            'data-label="Tổng tiền"',
            'data-label="Trạng thái"',
            'data-label="Thao tác"',
            "ndt-f5-badge--success",
            "ndt-f5-badge--warning",
            "ndt-f5-badge--danger",
            "ndt-f5-badge--pending",
        ):
            self.assertIn(marker, source)

    def test_create_form_preserves_real_payload(self):
        source = self.source("tao_hoa_don.html")
        for field in (
            "hop_dong",
            "thang",
            "nam",
            "han_thanh_toan",
            "tien_phong",
            "tien_dien",
            "tien_nuoc",
            "tien_dich_vu",
            "phi_khac",
            "chi_tiet_phi",
            "ghi_chu",
        ):
            self.assertIn(f'name="{field}"', source)
        self.assertIn("{% csrf_token %}", source)
        self.assertIn("money-input", source)

    def test_tenant_payment_preserves_two_step_payload(self):
        source = self.source("thanh_toan_hoa_don_cua_toi.html")
        for marker in (
            'name="buoc" value="xac_nhan"',
            'name="buoc" value="xac_thuc"',
            'name="phuong_thuc" value="chuyen_khoan"',
            'name="phuong_thuc" value="tien_mat"',
            'name="xac_nhan" value="dong_y"',
            "{{ qr_url }}",
            "{% csrf_token %}",
        ):
            self.assertIn(marker, source)

    def test_admin_action_uses_p5_dialog_and_preserves_payload(self):
        source = self.source("chi_tiet_hoa_don.html")
        self.assertIn("data-invoice-confirm", source)
        self.assertIn('name="hanh_dong" value="xac_nhan_thanh_toan"', source)
        self.assertIn('name="hanh_dong" value="huy_thanh_toan"', source)
        self.assertIn('name="phuong_thuc"', source)
        self.assertIn("core/foundation/p5_dialog_root.html", source)
        self.assertIn("js/foundation/p5-dialog.js", source)
        self.assertIn("js/invoice_management_p6d.js", source)
        self.assertNotIn("js/foundation/dialog.js", source)

    def test_module_assets_are_namespaced_and_dialog_preserves_form_submission(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "invoice_management_p6d.css").read_text(encoding="utf-8")
        js = (Path(settings.BASE_DIR) / "static" / "js" / "invoice_management_p6d.js").read_text(encoding="utf-8")
        self.assertNotIn("!important", css)
        for selector in css.split("{")[:-1]:
            if selector.lstrip().startswith("@"):
                continue
        self.assertIn(".ndt-f5.ndt-invoice-management", css)
        self.assertIn("window.NDTFoundationDialog.confirm", js)
        self.assertIn("form.requestSubmit(submitter", js)
        self.assertIn("event.stopPropagation()", js)
        self.assertIn('form.dataset.submitting === "true"', js)


class InvoiceManagementP6DRequestContractTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.invoice = HoaDon.objects.create(
            hop_dong=self.contract_obj,
            thang=9,
            nam=2026,
            tien_phong=Decimal("2500000"),
            han_thanh_toan=self.today,
        )

    def test_admin_keyword_filter_uses_real_q_field(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("quan_ly_hoa_don"), {"q": self.tenant.ho_ten})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["hoa_don"]), [self.invoice])

    def test_invoice_post_endpoints_reject_missing_csrf(self):
        client = Client(enforce_csrf_checks=True)

        client.force_login(self.admin)
        create_response = client.post(reverse("tao_hoa_don"), {
            "hop_dong": self.contract_obj.pk,
            "thang": 10,
            "nam": 2026,
            "han_thanh_toan": self.today.isoformat(),
        })
        action_response = client.post(
            reverse("xu_ly_hoa_don", args=[self.invoice.pk]),
            {"hanh_dong": "xac_nhan_thanh_toan", "phuong_thuc": "chuyen_khoan"},
        )

        client.force_login(self.user)
        tenant_response = client.post(
            reverse("thanh_toan_hoa_don_cua_toi", args=[self.invoice.pk]),
            {"buoc": "xac_thuc", "phuong_thuc": "chuyen_khoan", "xac_nhan": "dong_y"},
        )

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(action_response.status_code, 403)
        self.assertEqual(tenant_response.status_code, 403)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.trang_thai, "chua_thanh_toan")
