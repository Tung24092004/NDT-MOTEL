"""Room Management module UI contracts and isolated database regression tests."""

from decimal import Decimal

from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import Phong


class RoomManagementUITests(BusinessFixture):
    foundation_assets = (
        "css/foundation/p5.css",
        "css/room_management_p6a.css",
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
        self.assertContains(response, "ndt-f5-table-wrap")
        self.assertContains(response, "ndt-f5-badge")
        self.assertContains(response, 'data-label="Phòng"')
        self.assertContains(response, 'data-label="Thao tác"')
        self.assertContains(response, reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertContains(response, reverse("sua_phong", args=[self.room.pk]))
        self.assertContains(response, reverse("xoa_phong", args=[self.room.pk]))
        self.assertContains(response, "data-room-delete-form")
        self.assertContains(response, "js/foundation/p5-dialog.js")
        self.assertContains(response, "data-ndt-f5-dialog")
        self.assertContains(response, "js/room_management_p6a.js")
        self.assertNotContains(response, "confirm(")
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
                self.assertContains(response, "room-form ndt-room-form")
                self.assertContains(response, 'enctype="multipart/form-data"')
                self.assertContains(response, "csrfmiddlewaretoken")
                for field in fields:
                    self.assertContains(response, f'name="{field}"')

    def test_admin_detail_opts_in_without_changing_guest_detail(self):
        admin_response = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertEqual(admin_response.status_code, 200)
        self.assert_module_assets(admin_response)
        self.assertContains(admin_response, "data-room-admin-detail")
        self.assertContains(admin_response, "Sửa thông tin phòng")
        self.assertContains(admin_response, "ndt-f5-button ndt-f5-button--primary")

        self.client.logout()
        guest_response = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertEqual(guest_response.status_code, 200)
        self.assertContains(guest_response, "css/foundation/p5.css")
        self.assertContains(
            guest_response,
            "css/public_discovery_support_post_p6.css",
        )
        self.assertContains(guest_response, 'data-public-context="room-detail"')
        self.assertNotContains(guest_response, "css/room_management_p6a.css")
        self.assertNotContains(guest_response, "data-room-admin-detail")

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

    def test_valid_create_and_edit_keep_post_contract(self):
        payload = {
            "co_so": str(self.facility.pk),
            "so_phong": "P6A-NEW",
            "tang": "2",
            "loai_phong": "phong_tieu_chuan",
            "dien_tich": "26.5",
            "so_nguoi_toi_da": "2",
            "gia_thue": "3100000",
            "tien_coc_mac_dinh": "1000000",
            "tien_dien_moi_so": "3500",
            "tien_nuoc_moi_khoi": "18000",
            "phi_dich_vu": "150000",
            "trang_thai": "trong",
            "tien_ich": "WiFi, máy lạnh",
            "mo_ta": "Phòng tạo bởi test P6A.",
        }
        create_response = self.client.post(reverse("tao_phong"), payload)
        self.assertRedirects(create_response, reverse("quan_ly_phong"))
        created = Phong.objects.get(so_phong="P6A-NEW")

        payload.update({"so_phong": "P6A-UPDATED", "gia_thue": "3300000"})
        edit_response = self.client.post(reverse("sua_phong", args=[created.pk]), payload)
        self.assertRedirects(edit_response, reverse("quan_ly_phong"))
        created.refresh_from_db()
        self.assertEqual(created.so_phong, "P6A-UPDATED")
        self.assertEqual(created.gia_thue, Decimal("3300000"))

    def test_delete_remains_post_only_and_uses_existing_endpoint(self):
        get_response = self.client.get(reverse("xoa_phong", args=[self.room.pk]))
        self.assertRedirects(get_response, reverse("quan_ly_phong"))
        self.assertTrue(Phong.objects.filter(pk=self.room.pk).exists())

        post_response = self.client.post(reverse("xoa_phong", args=[self.room.pk]))
        self.assertRedirects(post_response, reverse("quan_ly_phong"))
        self.assertFalse(Phong.objects.filter(pk=self.room.pk).exists())

    def test_room_admin_routes_keep_permissions(self):
        self.client.logout()
        for route, args in (
            ("quan_ly_phong", []),
            ("tao_phong", []),
            ("sua_phong", [self.room.pk]),
            ("xoa_phong", [self.room.pk]),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("dang_nhap"), response.url)
