"""Module 03 UI contracts for Admin booking and deposit reconciliation."""

from pathlib import Path

from django.conf import settings
from django.urls import reverse

from core.dich_vu.hop_dong import confirm_deposit_and_create_contract
from core.dich_vu.tien_coc import report_paid
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture


class AdminBookingPaymentUITests(Phase5BookingFixture):
    foundation_assets = (
        "css/foundation/tokens.css",
        "css/foundation/typography.css",
        "css/foundation/components.css",
        "css/foundation/utilities.css",
        "css/foundation/v2.css",
    )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def assert_foundation(self, response):
        for asset in self.foundation_assets:
            self.assertContains(response, asset)
        self.assertContains(response, "css/admin_booking.css")
        self.assertContains(response, "js/admin_booking.js")

    def pending_report(self):
        self.client.force_login(self.user)
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="BANK-UI-001")
        self.client.force_login(self.admin)
        return booking, payment

    def test_list_renders_real_filters_foundation_and_empty_state(self):
        response = self.client.get(reverse("quan_ly_dat_phong"))
        self.assertEqual(response.status_code, 200)
        self.assert_foundation(response)
        for field in ("q", "trang_thai", "coc", "hop_dong"):
            self.assertContains(response, f'name="{field}"')
        self.assertContains(response, "ndt-empty-state")
        self.assertContains(response, "Chưa có yêu cầu đặt phòng")

    def test_list_separates_booking_and_payment_labels_without_raw_enum(self):
        booking, _ = self.pending_report()
        response = self.client.get(reverse("quan_ly_dat_phong"), {"coc": "cho_xac_nhan"})
        self.assertContains(response, booking.ma_yeu_cau)
        self.assertContains(response, "Chờ đối soát")
        self.assertContains(response, "Chờ duyệt")
        self.assertNotContains(response, ">cho_xac_nhan<")
        self.assertNotContains(response, ">cho_duyet<")
        self.assertContains(response, "Xem xét và xác nhận")

    def test_detail_payment_review_and_confirm_form_keep_endpoint_csrf(self):
        booking, payment = self.pending_report()
        response = self.client.get(reverse("chi_tiet_dat_phong", args=[booking.pk]))
        self.assert_foundation(response)
        self.assertContains(response, payment.ma_tham_chieu)
        self.assertContains(response, payment.noi_dung_chuyen_khoan)
        self.assertContains(response, "BANK-UI-001")
        self.assertContains(response, "Xác nhận cọc và tạo hợp đồng")
        self.assertContains(response, reverse("xac_nhan_dat_phong_va_tao_hop_dong", args=[booking.pk]))
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, "data-admin-booking-confirm")

    def test_reject_forms_keep_required_reason_names_and_actions(self):
        booking, _ = self.pending_report()
        response = self.client.get(reverse("chi_tiet_dat_phong", args=[booking.pk]))
        self.assertContains(response, reverse("tu_choi_thanh_toan_coc", args=[booking.pk]))
        self.assertContains(response, reverse("tu_choi_yeu_cau_dat_phong", args=[booking.pk]))
        self.assertContains(response, 'name="ly_do"', count=2)
        self.assertContains(response, 'data-confirm-danger="true"', count=2)

    def test_contract_cta_only_after_contract_exists(self):
        booking, _ = self.pending_report()
        response = self.client.get(reverse("chi_tiet_dat_phong", args=[booking.pk]))
        self.assertNotContains(response, ">Xem hợp đồng<")
        contract = confirm_deposit_and_create_contract(actor=self.admin, booking_id=booking.pk)
        response = self.client.get(reverse("chi_tiet_dat_phong", args=[booking.pk]))
        self.assertContains(response, reverse("chi_tiet_hop_dong", args=[contract.pk]))
        self.assertNotContains(response, "Xác nhận cọc và tạo hợp đồng")

    def test_module_assets_have_no_important_raw_enum_or_browser_confirm(self):
        css = Path(settings.BASE_DIR, "static/css/admin_booking.css").read_text(encoding="utf-8")
        js = Path(settings.BASE_DIR, "static/js/admin_booking.js").read_text(encoding="utf-8")
        templates = "\n".join(
            Path(settings.BASE_DIR, name).read_text(encoding="utf-8")
            for name in ("templates/core/quan_ly_dat_phong.html", "templates/core/chi_tiet_dat_phong.html")
        )
        self.assertNotIn("!important", css)
        self.assertNotIn("return confirm(", templates)
        self.assertIn("window.NDTDialog.confirm", js)
        self.assertIn("requestSubmit", js)
