from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import DatPhong, HoaDon, HopDong, NhatKyThaoTac, QuyenRaVao, YeuCauSuaChua


class HomePanelP3Tests(BusinessFixture):
    def test_guest_uses_real_public_routes_and_supported_get_filters(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["home_panel"]["vai_tro"], "guest")
        self.assertContains(response, 'role="tablist"')
        self.assertEqual(response.content.decode().count('role="tab"'), 5)
        self.assertEqual(response.content.decode().count('role="tabpanel"'), 5)
        self.assertContains(response, 'action="%s"' % reverse("danh_sach_phong"))
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="gia_max"')
        self.assertNotContains(response, 'name="co_so"')
        self.assertNotContains(response, 'name="loai_phong"')
        self.assertContains(response, reverse("trung_tam_tro_giup"))
        self.assertContains(response, reverse("huong_dan_thue_phong"))
        self.assertContains(response, "css/home-panel.css")
        self.assertContains(response, "js/home-panel.js")

    def test_home_get_is_read_only_and_tenant_latest_booking_is_owned(self):
        own_booking = self.booking(status="cho_duyet")
        other_booking = self.booking(status="tu_choi", tenant=self.other)
        before = {
            "bookings": DatPhong.objects.count(),
            "contracts": HopDong.objects.count(),
            "invoices": HoaDon.objects.count(),
            "permissions": QuyenRaVao.objects.count(),
            "repairs": YeuCauSuaChua.objects.count(),
            "audit": NhatKyThaoTac.objects.count(),
        }

        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))

        panel = response.context["home_panel"]
        self.assertEqual(panel["vai_tro"], "tenant")
        self.assertEqual(panel["nguoi_thue"], self.tenant)
        self.assertEqual(panel["dat_phong_gan_nhat"], own_booking)
        self.assertContains(response, own_booking.ma_yeu_cau)
        self.assertNotContains(response, other_booking.ma_yeu_cau)
        self.assertEqual(before, {
            "bookings": DatPhong.objects.count(),
            "contracts": HopDong.objects.count(),
            "invoices": HoaDon.objects.count(),
            "permissions": QuyenRaVao.objects.count(),
            "repairs": YeuCauSuaChua.objects.count(),
            "audit": NhatKyThaoTac.objects.count(),
        })

    def test_tenant_contract_invoice_and_access_permission_are_scoped(self):
        contract = self.contract()
        own_permission = self.permission(hop_dong=contract)
        invoice = HoaDon.objects.create(
            hop_dong=contract,
            thang=self.today.month,
            nam=self.today.year,
            tien_phong=Decimal("2500000"),
            han_thanh_toan=self.today + timedelta(days=5),
        )

        other_booking = self.booking(tenant=self.other)
        other_contract = HopDong.objects.create(
            dat_phong=other_booking,
            so_hop_dong="OTHER-P3",
            ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today + timedelta(days=60),
            tien_thue_thang=Decimal("3100000"),
            trang_thai="dang_hieu_luc",
        )
        other_permission = QuyenRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.other,
            hop_dong=other_contract,
            nguon_cap="face_id",
            loai_quyen="chu_phong",
            trang_thai="hoat_dong",
            ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today + timedelta(days=60),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        panel = response.context["home_panel"]

        self.assertEqual(panel["hop_dong_hien_tai"], contract)
        self.assertEqual(panel["hoa_don_gan_nhat"], invoice)
        self.assertEqual(panel["quyen_ra_vao"], own_permission)
        self.assertNotEqual(panel["quyen_ra_vao"], other_permission)
        self.assertContains(response, reverse("chi_tiet_hop_dong_cua_toi", args=[contract.pk]))
        self.assertContains(response, reverse("chi_tiet_hoa_don_cua_toi", args=[invoice.pk]))

    def test_tenant_without_data_and_authenticated_user_without_profile_have_safe_empty_states(self):
        self.client.force_login(self.user)
        tenant_response = self.client.get(reverse("home"))
        self.assertContains(tenant_response, "Bạn chưa gửi yêu cầu đặt phòng nào")
        self.assertContains(tenant_response, "Không có hợp đồng lưu trú đang hiệu lực")

        account_only = User.objects.create_user("p3-account-only")
        self.client.force_login(account_only)
        profile_response = self.client.get(reverse("home"))
        self.assertContains(profile_response, "Tài khoản chưa có hồ sơ người thuê hoạt động")
        self.assertContains(profile_response, reverse("cap_nhat_thong_tin"))

    def test_admin_gets_only_aggregate_admin_actions(self):
        self.booking(status="cho_duyet")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("home"))
        panel = response.context["home_panel"]

        self.assertEqual(panel["vai_tro"], "admin")
        self.assertIsNone(panel["nguoi_thue"])
        self.assertIsNone(panel["dat_phong_gan_nhat"])
        self.assertContains(response, reverse("quan_ly_dat_phong"))
        self.assertContains(response, reverse("smart_room_dashboard"))
        self.assertContains(response, reverse("quan_ly_sua_chua"))
        self.assertContains(response, reverse("quan_ly_phong"))

    def test_room_search_form_reaches_existing_backend_filters(self):
        response = Client().get(
            reverse("danh_sach_phong"),
            {"q": self.room.so_phong, "gia_max": "2500000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.room.so_phong)
