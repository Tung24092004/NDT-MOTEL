from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import CoSo, DatPhong, HinhAnhPhong, HopDong, NguoiThue, Phong


class PublicRoomDetailTests(TestCase):
    def setUp(self):
        self.facility = CoSo.objects.create(
            ten_co_so="Co so ROOM-02", dia_chi="2 Duong Test", quan="Hai Chau"
        )
        self.room = self.create_room("ROOM-02")
        self.user = User.objects.create_user("room-detail-user", password="Safe-pass-123")

    def create_room(self, number, **overrides):
        values = {
            "co_so": self.facility, "so_phong": number,
            "loai_phong": "phong_tieu_chuan", "gia_thue": Decimal("2500000"),
            "dien_tich": Decimal("24"), "so_nguoi_toi_da": 2,
        }
        values.update(overrides)
        return Phong.objects.create(**values)

    def active_contract(self, room):
        account = User.objects.create_user("private-tenant")
        tenant = NguoiThue.objects.create(
            tai_khoan=account, ho_ten="Nguoi thue rieng tu",
            cccd="012345678901", so_dien_thoai="0900123456",
        )
        booking = DatPhong.objects.create(
            nguoi_thue=tenant, phong=room, ngay_nhan_phong=timezone.localdate(),
            so_thang_thue=1, trang_thai="da_duyet",
        )
        return HopDong.objects.create(
            dat_phong=booking, so_hop_dong=f"ROOM-02-{room.pk}",
            ngay_bat_dau=timezone.localdate(),
            ngay_ket_thuc=timezone.localdate() + timedelta(days=30),
            tien_thue_thang=Decimal("2500000"), trang_thai="dang_hieu_luc",
        )

    def test_public_detail_from_list_and_non_public_or_missing_rooms_are_404(self):
        private_facility = CoSo.objects.create(
            ten_co_so="Co so dong", dia_chi="3 Duong Test", quan="Hai Chau",
            trang_thai="tam_ngung",
        )
        private_room = Phong.objects.create(
            co_so=private_facility, so_phong="PRIVATE-02",
            loai_phong="phong_tieu_chuan", gia_thue=Decimal("2500000"),
            dien_tich=Decimal("24"),
        )
        detail_url = reverse("chi_tiet_phong", args=[self.room.pk])
        list_response = self.client.get(reverse("danh_sach_phong"))
        self.assertContains(list_response, detail_url)
        self.assertContains(list_response, "Xem chi tiết")
        for client in (self.client, Client()):
            if client is not self.client:
                client.force_login(self.user)
            response = client.get(detail_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["phong"].pk, self.room.pk)
            self.assertEqual(response.context["phong"].trang_thai_cong_khai, "trong")
        self.assertEqual(self.client.get(reverse("chi_tiet_phong", args=[999999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("chi_tiet_phong", args=[private_room.pk])).status_code, 404)

    def test_detail_reuses_live_status_without_tenant_data_or_mutation(self):
        first = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertEqual(first.context["phong"].trang_thai_cong_khai, "trong")
        contract = self.active_contract(self.room)
        before = list(Phong.objects.values_list("pk", "trang_thai"))
        list_response = self.client.get(reverse("danh_sach_phong"))
        detail_response = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertEqual(
            list_response.context["phong"][0].trang_thai_cong_khai,
            detail_response.context["phong"].trang_thai_cong_khai,
        )
        self.assertEqual(detail_response.context["phong"].trang_thai_cong_khai, "dang_thue")
        tenant = contract.dat_phong.nguoi_thue
        self.assertNotContains(detail_response, tenant.ho_ten)
        self.assertNotContains(detail_response, tenant.so_dien_thoai)
        self.assertNotContains(detail_response, tenant.cccd)
        self.assertEqual(list(Phong.objects.values_list("pk", "trang_thai")), before)

    def test_detail_prefetches_gallery_and_keeps_admin_detail_branch(self):
        HinhAnhPhong.objects.create(phong=self.room, anh="phong/missing-cover.jpg")
        detail_url = reverse("chi_tiet_phong", args=[self.room.pk])
        with CaptureQueriesContext(connection) as one_image_queries:
            response = self.client.get(detail_url)
        for index in range(4):
            HinhAnhPhong.objects.create(phong=self.room, anh=f"phong/gallery-{index}.jpg")
        with CaptureQueriesContext(connection) as many_image_queries:
            response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "missing-cover.jpg")
        self.assertLessEqual(len(many_image_queries), len(one_image_queries) + 1)
        admin = User.objects.create_user("room-detail-admin", password="Safe-pass-123", is_staff=True)
        self.client.force_login(admin)
        admin_response = self.client.get(detail_url)
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, "data-room-admin-detail")
        self.assertContains(admin_response, "css/room_management_p6a.css")
