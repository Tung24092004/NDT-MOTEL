from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong


class HomeSectionsP4Tests(TestCase):
    def setUp(self):
        self.facility = CoSo.objects.create(
            ten_co_so="Cơ sở P4",
            dia_chi="01 Bạch Đằng",
            quan="Hải Châu",
            tien_ich_chung="Wifi, bãi giữ xe",
        )

    def room(self, number=1, kind="phong_tieu_chuan"):
        return Phong.objects.create(
            co_so=self.facility,
            so_phong=f"P4-{number:02d}",
            loai_phong=kind,
            gia_thue=Decimal("2800000"),
            dien_tich=Decimal("24"),
            so_nguoi_toi_da=2,
        )

    def test_guest_sections_use_real_catalog_and_routes(self):
        kinds = ("phong_tieu_chuan", "phong_cao_cap", "phong_gac_lung", "can_ho_mini")
        for number in range(1, 8):
            self.room(number, kinds[(number - 1) % 4])

        response = self.client.get(reverse("home"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["phong_goi_y"]), 6)
        self.assertEqual(html.count("data-p4-room>"), 6)
        self.assertEqual(html.count("data-p4-room-type>"), 4)
        self.assertEqual(html.count("data-p4-step>"), 5)
        self.assertEqual(html.count("data-p4-section="), 6)
        self.assertContains(response, "css/home-sections.css")
        self.assertContains(response, reverse("danh_sach_phong"))
        self.assertContains(response, reverse("huong_dan_thue_phong"))
        self.assertContains(response, reverse("trung_tam_tro_giup"))
        self.assertContains(response, reverse("chinh_sach_ho_tro"))
        self.assertContains(response, "Đăng nhập để đặt")
        self.assertNotContains(response, "?loai_phong=")
        self.assertContains(response, "Admin xác nhận")
        self.assertContains(response, "Sau khi cọc được xác nhận")
        self.assertContains(response, "không khởi động camera")

    def test_featured_room_actions_follow_guest_tenant_admin_roles(self):
        room = self.room()

        guest = self.client.get(reverse("home"))
        login_booking = f'{reverse("dang_nhap")}?next={reverse("dat_phong", args=[room.pk])}'
        self.assertContains(guest, login_booking)

        tenant_user = User.objects.create_user("p4-tenant")
        NguoiThue.objects.create(
            tai_khoan=tenant_user,
            ho_ten="Tenant P4",
            cccd="000000010406",
            so_dien_thoai="0900010406",
        )
        self.client.force_login(tenant_user)
        tenant = self.client.get(reverse("home"))
        self.assertContains(tenant, reverse("dat_phong", args=[room.pk]))
        self.assertNotContains(tenant, login_booking)

        admin = User.objects.create_user("p4-admin", is_staff=True)
        self.client.force_login(admin)
        admin_response = self.client.get(reverse("home"))
        self.assertContains(admin_response, reverse("chi_tiet_phong", args=[room.pk]))
        self.assertNotContains(admin_response, reverse("dat_phong", args=[room.pk]))

    def test_smart_and_support_actions_follow_existing_conditions(self):
        room = self.room()
        user = User.objects.create_user("p4-resident")
        tenant = NguoiThue.objects.create(
            tai_khoan=user,
            ho_ten="Resident P4",
            cccd="000000010407",
            so_dien_thoai="0900010407",
        )
        today = timezone.localdate()
        booking = DatPhong.objects.create(
            nguoi_thue=tenant,
            phong=room,
            ngay_nhan_phong=today,
            ngay_tra_du_kien=today + timedelta(days=90),
            so_thang_thue=3,
            trang_thai="da_duyet",
        )
        HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong="P4-HD",
            ngay_bat_dau=today,
            ngay_ket_thuc=today + timedelta(days=90),
            tien_thue_thang=Decimal("2800000"),
            trang_thai="dang_hieu_luc",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("nhan_dien_su_dung_phong"))
        self.assertContains(response, reverse("yeu_cau_sua_chua_cua_toi"))
        self.assertContains(response, reverse("tao_yeu_cau_sua_chua"))

        admin = User.objects.create_user("p4-smart-admin", is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("smart_room_dashboard"))
        self.assertContains(response, reverse("quan_ly_sua_chua"))
        self.assertNotContains(response, reverse("nhan_dien_su_dung_phong"))

    def test_empty_state_keeps_catalog_destination(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["phong_goi_y"], [])
        self.assertContains(response, "Hiện chưa có phòng để hiển thị.")
        self.assertContains(response, "Mở danh sách phòng")
        self.assertEqual(response.content.decode().count("data-p4-room>"), 0)
