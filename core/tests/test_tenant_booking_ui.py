"""Module 02 presentation contracts for the tenant booking experience."""

from pathlib import Path

from django.conf import settings
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import DatPhong


class TenantBookingFoundationUITests(Phase5BookingFixture):
    foundation_assets = (
        "css/foundation/tokens.css",
        "css/foundation/typography.css",
        "css/foundation/components.css",
        "css/foundation/utilities.css",
    )

    def assert_foundation(self, response):
        for asset in self.foundation_assets:
            self.assertContains(response, asset)
        self.assertContains(response, 'data-tenant-booking-ui="v1"')

    def test_booking_create_renders_six_real_steps_and_display_cover(self):
        response = self.client.get(reverse("dat_phong", args=[self.room.pk]))
        self.assertEqual(response.status_code, 200)
        self.assert_foundation(response)
        self.assertEqual(response.content.count(b"booking-progress-index"), 6)
        self.assertContains(response, "Thông tin thuê")
        self.assertContains(response, "Người đi cùng")
        self.assertContains(response, "Điều khoản")
        self.assertContains(response, "Xác nhận thông tin và chuyển đến thanh toán cọc")
        summary = Path(settings.BASE_DIR, "templates/core/tenant/booking/components/room_summary.html").read_text(encoding="utf-8")
        self.assertIn("anh_dai_dien_hien_thi", summary)

    def test_my_bookings_and_empty_state_use_foundation(self):
        response = self.client.get(reverse("dat_phong_cua_toi"))
        self.assert_foundation(response)
        self.assertContains(response, "ndt-empty-state")
        self.assertContains(response, "Bạn chưa có yêu cầu đặt phòng")
        booking, _ = self.new_booking()
        response = self.client.get(reverse("dat_phong_cua_toi"))
        self.assertContains(response, booking.ma_yeu_cau)
        self.assertContains(response, "Bước tiếp theo")
        self.assertContains(response, "Chuyển khoản tiền cọc")

    def test_detail_uses_labels_and_cancel_dialog_without_changing_condition(self):
        booking, _ = self.new_booking()
        response = self.client.get(reverse("chi_tiet_dat_phong_cua_toi", args=[booking.pk]))
        self.assert_foundation(response)
        self.assertContains(response, "Chờ thanh toán")
        self.assertNotContains(response, ">chua_thanh_toan<")
        self.assertContains(response, "data-cancel-booking-form")
        self.assertContains(response, "ndt-button--danger")
        DatPhong.objects.filter(pk=booking.pk).update(trang_thai="da_duyet")
        response = self.client.get(reverse("chi_tiet_dat_phong_cua_toi", args=[booking.pk]))
        self.assertNotContains(response, "data-cancel-booking-form")

    def test_deposit_copy_and_pending_language_are_explicit(self):
        booking, payment = self.new_booking()
        response = self.client.get(reverse("thanh_toan_coc_cua_toi", args=[booking.pk]))
        self.assert_foundation(response)
        self.assertContains(response, payment.noi_dung_chuyen_khoan)
        self.assertContains(response, 'data-copy-target="transfer-content"')
        self.assertContains(response, "Báo đã chuyển khoản")
        self.assertContains(response, "chờ quản lý xác nhận")
        self.assertNotContains(response, "Thanh toán thành công")

    def test_booking_css_has_no_important_and_js_wires_foundation_dialog(self):
        css = Path(settings.BASE_DIR, "static/css/tenant/booking.css").read_text(encoding="utf-8")
        js = Path(settings.BASE_DIR, "static/js/tenant/booking.js").read_text(encoding="utf-8")
        self.assertNotIn("!important", css)
        self.assertIn("navigator.clipboard.writeText", js)
        self.assertIn("window.NDTDialog.confirm", js)
        self.assertIn("requestSubmit", js)
