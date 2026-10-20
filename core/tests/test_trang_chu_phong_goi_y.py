from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import CoSo, Phong


class HomeSuggestedRoomsTests(TestCase):
    def setUp(self):
        self.facility = CoSo.objects.create(
            ten_co_so="Co so phong goi y",
            dia_chi="1 Duong Goi Y",
            quan="Hai Chau",
        )

    def _create_room(self, number, status="trong"):
        return Phong.objects.create(
            co_so=self.facility,
            so_phong=f"GY-{number:03d}",
            loai_phong="phong_tieu_chuan",
            tang=number % 8 + 1,
            gia_thue=Decimal("2500000"),
            dien_tich=Decimal("24"),
            so_nguoi_toi_da=2,
            trang_thai=status,
        )

    def test_home_renders_at_most_six_suggestions_when_rooms_exist(self):
        for number in range(1, 87):
            self._create_room(number)

        response = self.client.get(reverse("home"))
        suggestions = response.context["phong_goi_y"]

        self.assertEqual(Phong.objects.count(), 86)
        self.assertEqual(len(suggestions), 6)
        self.assertNotContains(response, "Hiện chưa có phòng để hiển thị.")
        html = response.content.decode()
        self.assertEqual(html.count("data-room="), 6)
        self.assertIn(f'href="{reverse("danh_sach_phong")}"', html)
        for room in suggestions:
            self.assertIn(reverse("chi_tiet_phong", args=[room.pk]), html)
        self.assertNotContains(response, "Đang hiển thị")

    def test_home_empty_state_only_renders_without_rooms(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.context["phong_goi_y"], [])
        self.assertContains(response, "Hiện chưa có phòng để hiển thị.")
        self.assertEqual(response.content.decode().count("data-room="), 0)
