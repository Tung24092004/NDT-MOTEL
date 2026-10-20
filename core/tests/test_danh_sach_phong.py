from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.dich_vu.ngay_thue import tinh_ngay_ket_thuc_theo_thang
from core.models import CoSo, DatPhong, HinhAnhPhong, HopDong, NguoiThue, Phong


class PublicRoomListTests(TestCase):
    def setUp(self):
        self.facility = CoSo.objects.create(
            ten_co_so="Cơ sở ROOM-01", dia_chi="1 Đường Test", quan="Hải Châu"
        )
        self.user = User.objects.create_user("room-list-user", password="Safe-pass-123")

    def room(self, number, **overrides):
        values = {
            "co_so": self.facility,
            "so_phong": number,
            "loai_phong": "phong_tieu_chuan",
            "gia_thue": Decimal("2500000"),
            "dien_tich": Decimal("24"),
            "so_nguoi_toi_da": 2,
        }
        values.update(overrides)
        return Phong.objects.create(**values)

    def tenant(self, suffix):
        user = User.objects.create_user(f"tenant-{suffix}")
        return NguoiThue.objects.create(
            tai_khoan=user,
            ho_ten=f"Tenant {suffix}",
            cccd=f"00000000{suffix:04d}",
            so_dien_thoai=f"0900{suffix:06d}",
        )

    def booking(self, room, suffix, status="da_duyet"):
        return DatPhong.objects.create(
            nguoi_thue=self.tenant(suffix),
            phong=room,
            ngay_nhan_phong=timezone.localdate() + timedelta(days=1),
            so_thang_thue=1,
            trang_thai=status,
        )

    def active_contract(self, room, suffix):
        booking = self.booking(room, suffix)
        HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong=f"ROOM-01-{room.so_phong}",
            ngay_bat_dau=timezone.localdate(),
            ngay_ket_thuc=timezone.localdate() + timedelta(days=30),
            tien_thue_thang=Decimal("2500000"),
            trang_thai="dang_hieu_luc",
        )

    def test_guest_and_authenticated_users_see_database_rooms_in_stable_order(self):
        room_b = self.room("B-02")
        room_a = self.room("A-01")
        for client in (self.client, Client()):
            if client is not self.client:
                client.force_login(self.user)
            response = client.get(reverse("danh_sach_phong"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                [room.pk for room in response.context["phong"]],
                [room_a.pk, room_b.pk],
            )

    def test_status_comes_from_live_booking_data_without_writing_rooms(self):
        available = self.room("A-01")
        held = self.room("B-01")
        rented = self.room("C-01")
        maintenance = self.room("D-01", trang_thai="bao_tri")
        not_ready = self.room("E-01", so_nguoi_toi_da=0)
        held_booking = self.booking(held, 2)
        self.active_contract(rented, 3)
        states_before = dict(Phong.objects.values_list("pk", "trang_thai"))
        response = self.client.get(reverse("danh_sach_phong"))
        states = {
            room.so_phong: room.trang_thai_cong_khai
            for room in response.context["phong"]
        }
        self.assertEqual(states[available.so_phong], "trong")
        self.assertEqual(states[held.so_phong], "da_dat")
        self.assertEqual(states[rented.so_phong], "dang_thue")
        self.assertEqual(states[maintenance.so_phong], "bao_tri")
        self.assertEqual(states[not_ready.so_phong], "chua_san_sang")
        self.assertEqual(dict(Phong.objects.values_list("pk", "trang_thai")), states_before)
        self.assertTrue(held_booking.pk)

    def test_filters_pagination_and_missing_images_are_read_only_without_n_plus_one(self):
        rooms = [self.room(f"P-{index:02d}") for index in range(13)]
        for index, room in enumerate(rooms, start=1):
            self.active_contract(room, index + 10)
        HinhAnhPhong.objects.create(phong=rooms[0], anh="phong/missing-cover.jpg")
        states_before = list(Phong.objects.values_list("pk", "trang_thai"))
        with CaptureQueriesContext(connection) as one_room_queries:
            self.client.get(reverse("danh_sach_phong"), {"q": "P-00"})
        with CaptureQueriesContext(connection) as many_room_queries:
            response = self.client.get(reverse("danh_sach_phong"), {"page": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["phong"]), 12)
        self.assertContains(response, "missing-cover.jpg")
        self.assertLessEqual(len(many_room_queries), len(one_room_queries) + 2)
        self.assertEqual(list(Phong.objects.values_list("pk", "trang_thai")), states_before)

    def test_period_search_only_returns_rooms_bookable_for_that_period(self):
        free = self.room("A-AVAILABLE")
        maintenance = self.room("B-MAINTENANCE", trang_thai="bao_tri")
        contract_conflict = self.room("C-CONTRACT")
        hold_conflict = self.room("D-HOLD")
        later_contract = self.room("E-LATER")
        unbounded_hold = self.room("F-OPEN-HOLD")
        today = timezone.localdate()
        requested_start = today + timedelta(days=1)
        requested_end = tinh_ngay_ket_thuc_theo_thang(requested_start, 1)

        contract_booking = self.booking(contract_conflict, 10)
        HopDong.objects.create(
            dat_phong=contract_booking, so_hop_dong="PERIOD-CONFLICT",
            ngay_bat_dau=requested_start, ngay_ket_thuc=requested_end,
            tien_thue_thang=Decimal("2500000"), trang_thai="cho_hieu_luc",
        )
        held_booking = self.booking(hold_conflict, 11, status="cho_duyet")
        held_booking.han_thanh_toan_coc = timezone.now() + timedelta(hours=1)
        held_booking.ngay_tra_du_kien = requested_end
        held_booking.save(update_fields=["han_thanh_toan_coc", "ngay_tra_du_kien"])
        later_booking = self.booking(later_contract, 12)
        later_start = today + timedelta(days=90)
        later_end = tinh_ngay_ket_thuc_theo_thang(later_start, 1)
        later_booking.ngay_nhan_phong = later_start
        later_booking.ngay_tra_du_kien = later_end
        later_booking.save(update_fields=["ngay_nhan_phong", "ngay_tra_du_kien"])
        HopDong.objects.create(
            dat_phong=later_booking, so_hop_dong="PERIOD-LATER",
            ngay_bat_dau=later_start, ngay_ket_thuc=later_end,
            tien_thue_thang=Decimal("2500000"), trang_thai="cho_hieu_luc",
        )
        self.booking(unbounded_hold, 13)

        response = self.client.get(reverse("danh_sach_phong"), {
            "ngay_nhan_phong": requested_start.isoformat(), "so_thang_thue": "1",
        })
        result_ids = [room.pk for room in response.context["phong"]]
        self.assertIn(free.pk, result_ids)
        self.assertIn(later_contract.pk, result_ids)
        self.assertNotIn(maintenance.pk, result_ids)
        self.assertNotIn(contract_conflict.pk, result_ids)
        self.assertNotIn(hold_conflict.pk, result_ids)
        self.assertNotIn(unbounded_hold.pk, result_ids)
        self.assertContains(response, "ngay_nhan_phong=" + requested_start.isoformat())
        detail = self.client.get(reverse("chi_tiet_phong", args=[free.pk]), {
            "ngay_nhan_phong": requested_start.isoformat(), "so_thang_thue": "1",
        })
        self.assertContains(
            detail,
            reverse("dat_phong", args=[free.pk])
            + "?ngay_nhan_phong=" + requested_start.isoformat() + "&amp;so_thang_thue=1",
        )

    def test_period_search_uses_inclusive_contract_boundaries_and_handles_bad_input(self):
        room = self.room("A-BOUNDARY")
        today = timezone.localdate()
        contract_end = today + timedelta(days=10)
        booking = self.booking(room, 20)
        HopDong.objects.create(
            dat_phong=booking, so_hop_dong="PERIOD-BOUNDARY",
            ngay_bat_dau=today, ngay_ket_thuc=contract_end,
            tien_thue_thang=Decimal("2500000"), trang_thai="dang_hieu_luc",
        )

        boundary = self.client.get(reverse("danh_sach_phong"), {
            "ngay_nhan_phong": contract_end.isoformat(), "so_thang_thue": "1",
        })
        self.assertNotIn(room.pk, [item.pk for item in boundary.context["phong"]])
        after_boundary = self.client.get(reverse("danh_sach_phong"), {
            "ngay_nhan_phong": (contract_end + timedelta(days=1)).isoformat(), "so_thang_thue": "1",
        })
        self.assertIn(room.pk, [item.pk for item in after_boundary.context["phong"]])

        for query in (
            {"ngay_nhan_phong": "not-a-date", "so_thang_thue": "1"},
            {"ngay_nhan_phong": today.isoformat()},
            {"so_thang_thue": "1"},
            {"ngay_nhan_phong": today.isoformat(), "so_thang_thue": "0"},
            {"ngay_nhan_phong": (today - timedelta(days=1)).isoformat(), "so_thang_thue": "1"},
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("danh_sach_phong"), query)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["availability_errors"])
