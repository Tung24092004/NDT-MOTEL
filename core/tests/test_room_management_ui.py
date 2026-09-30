"""Room Management module UI contracts and non-mutating validation tests."""

from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import Phong


class RoomManagementUITests(BusinessFixture):
    foundation_assets = (
        "css/foundation/tokens.css",
        "css/foundation/typography.css",
        "css/foundation/components.css",
        "css/foundation/utilities.css",
        "css/room_management.css",
    )

    def setUp(self):
        self.client.force_login(self.admin)

    def assert_module_assets(self, response):
        for asset in self.foundation_assets:
            self.assertContains(response, asset)

    def test_list_renders_filters_status_and_actions(self):
        response = self.client.get(
            reverse("quan_ly_phong"),
            {"q": self.room.so_phong, "trang_thai": self.room.trang_thai},
        )
        self.assertEqual(response.status_code, 200)
        self.assert_module_assets(response)
        self.assertContains(response, 'data-room-management-page="list"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="trang_thai"')
        self.assertContains(response, "ndt-table-wrap")
        self.assertContains(response, "ndt-badge")
        self.assertContains(response, reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertContains(response, reverse("sua_phong", args=[self.room.pk]))
        self.assertContains(response, reverse("xoa_phong", args=[self.room.pk]))
        self.assertContains(response, "data-ndt-confirm-form")
        self.assertContains(response, "js/foundation/dialog.js")
        self.assertContains(response, "ndtDialogRoot")
        self.assertNotContains(response, "return confirm(")
        self.assertNotContains(response, f">{self.room.trang_thai}<")

    def test_create_and_edit_share_form_contract(self):
        cases = (
            ("tao_phong", [], "create"),
            ("sua_phong", [self.room.pk], "edit"),
        )
        fields = (
            "co_so",
            "so_phong",
            "tang",
            "loai_phong",
            "dien_tich",
            "so_nguoi_toi_da",
            "gia_thue",
            "tien_coc_mac_dinh",
            "tien_dien_moi_so",
            "tien_nuoc_moi_khoi",
            "phi_dich_vu",
            "trang_thai",
            "tien_ich",
            "mo_ta",
            "hinh_anh",
        )
        for route, args, page in cases:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assert_module_assets(response)
                self.assertContains(response, f'data-room-management-page="{page}"')
                self.assertContains(response, 'class="room-form"')
                self.assertContains(response, 'enctype="multipart/form-data"')
                self.assertContains(response, "csrfmiddlewaretoken")
                for field in fields:
                    self.assertContains(response, f'name="{field}"')

    def test_invalid_create_keeps_data_unchanged_and_shows_error(self):
        before = Phong.objects.count()
        response = self.client.post(reverse("tao_phong"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vui lòng chọn cơ sở.")
        self.assertEqual(Phong.objects.count(), before)

    def test_invalid_edit_keeps_room_unchanged_and_shows_error(self):
        original_number = self.room.so_phong
        response = self.client.post(reverse("sua_phong", args=[self.room.pk]), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vui lòng chọn cơ sở.")
        self.room.refresh_from_db()
        self.assertEqual(self.room.so_phong, original_number)

    def test_room_admin_routes_keep_permissions(self):
        self.client.logout()
        for route, args in (
            ("quan_ly_phong", []),
            ("tao_phong", []),
            ("sua_phong", [self.room.pk]),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("dang_nhap"), response.url)
