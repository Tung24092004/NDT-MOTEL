from decimal import Decimal
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import resolve, reverse

from core.models import CoSo, Phong
from core.views_quan_tri import chi_tiet_co_so, quan_ly_co_so, tao_co_so, xu_ly_co_so


class AdminFacilitiesPostP6Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("facility-admin", is_staff=True)
        self.tenant = User.objects.create_user("facility-tenant")
        self.facility = CoSo.objects.create(
            ten_co_so="NDT Motel Sơn Trà",
            dia_chi="125 Ngô Quyền",
            quan="Sơn Trà",
            so_tang=4,
            so_phong=8,
            trang_thai="hoat_dong",
        )

    def test_route_view_template_matrix_is_stable(self):
        cases = (
            ("quan_ly_co_so", [], quan_ly_co_so, "core/quan_ly_co_so.html"),
            ("tao_co_so", [], tao_co_so, "core/tao_co_so.html"),
            ("chi_tiet_co_so", [self.facility.pk], chi_tiet_co_so, "core/chi_tiet_co_so.html"),
            ("xu_ly_co_so", [self.facility.pk], xu_ly_co_so, None),
        )
        self.client.force_login(self.admin)
        for name, args, handler, template in cases:
            with self.subTest(name=name):
                path = reverse(name, args=args)
                self.assertIs(resolve(path).func, handler)
                response = self.client.get(path)
                if template:
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, template)
                else:
                    self.assertRedirects(response, reverse("chi_tiet_co_so", args=[self.facility.pk]))

    def test_render_contexts_are_admin_only(self):
        routes = (
            reverse("quan_ly_co_so"),
            reverse("tao_co_so"),
            reverse("chi_tiet_co_so", args=[self.facility.pk]),
        )
        for path in routes:
            with self.subTest(path=path, role="guest"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("dang_nhap"))
        self.client.force_login(self.tenant)
        for path in routes:
            with self.subTest(path=path, role="tenant"):
                self.assertRedirects(
                    self.client.get(path),
                    reverse("tai_khoan"),
                    fetch_redirect_response=False,
                )

    def test_list_query_contract_and_annotated_counts_are_preserved(self):
        other = CoSo.objects.create(ten_co_so="NDT Motel Cẩm Lệ", dia_chi="1 Test", quan="Cẩm Lệ")
        self._room(self.facility, "AF-01", "trong")
        self._room(self.facility, "AF-02", "dang_thue")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("quan_ly_co_so"), {"q": "Sơn Trà"})
        self.assertContains(response, self.facility.ten_co_so)
        self.assertNotContains(response, other.ten_co_so)
        row = response.context["co_so"].get(pk=self.facility.pk)
        self.assertEqual((row.so_luong_phong, row.so_phong_trong, row.so_phong_dang_thue), (2, 1, 1))

    def test_create_preserves_field_payload_validation_and_redirect(self):
        payload = {
            "ten_co_so": "NDT Motel Hải Châu",
            "dia_chi": "10 Bạch Đằng",
            "quan": "Hải Châu",
            "so_tang": "5",
            "so_phong": "20",
            "trang_thai": "tam_ngung",
            "so_dien_thoai": "02363888888",
            "email": "haichau@example.com",
            "nguoi_quan_ly": "Nguyễn Minh An",
            "sdt_quan_ly": "0905123456",
            "tien_ich_chung": "Bãi xe, Wi-Fi",
            "mo_ta": "Cơ sở kiểm chứng",
        }
        self.client.force_login(self.admin)
        response = self.client.post(reverse("tao_co_so"), payload)
        self.assertRedirects(response, reverse("quan_ly_co_so"))
        created = CoSo.objects.get(ten_co_so=payload["ten_co_so"])
        for field in payload:
            expected = int(payload[field]) if field in {"so_tang", "so_phong"} else payload[field]
            self.assertEqual(getattr(created, field), expected)

        invalid = payload | {"ten_co_so": "Không được tạo", "so_tang": "0"}
        response = self.client.post(reverse("tao_co_so"), invalid)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CoSo.objects.filter(ten_co_so="Không được tạo").exists())

    def test_update_action_preserves_payload_and_side_effect(self):
        self.client.force_login(self.admin)
        payload = {
            "hanh_dong": "cap_nhat",
            "ten_co_so": "NDT Motel đã cập nhật",
            "dia_chi": "126 Ngô Quyền",
            "quan": "Sơn Trà",
            "so_tang": "6",
            "so_phong": "12",
            "so_dien_thoai": "02363999999",
            "email": "updated@example.com",
            "nguoi_quan_ly": "Trần Minh",
            "sdt_quan_ly": "0905000000",
            "tien_ich_chung": "Wi-Fi",
            "mo_ta": "Đã cập nhật",
        }
        response = self.client.post(reverse("xu_ly_co_so", args=[self.facility.pk]), payload)
        self.assertRedirects(response, reverse("chi_tiet_co_so", args=[self.facility.pk]))
        self.facility.refresh_from_db()
        for field in payload:
            if field == "hanh_dong":
                continue
            expected = int(payload[field]) if field in {"so_tang", "so_phong"} else payload[field]
            self.assertEqual(getattr(self.facility, field), expected)

    def test_state_actions_and_delete_guard_keep_current_side_effects(self):
        self.client.force_login(self.admin)
        action_url = reverse("xu_ly_co_so", args=[self.facility.pk])
        for action in ("tam_ngung", "dong_cua", "hoat_dong"):
            with self.subTest(action=action):
                self.client.post(action_url, {"hanh_dong": action})
                self.facility.refresh_from_db()
                self.assertEqual(self.facility.trang_thai, action)

        self._room(self.facility, "AF-03", "trong")
        self.client.post(action_url, {"hanh_dong": "xoa"})
        self.assertTrue(CoSo.objects.filter(pk=self.facility.pk).exists())
        empty = CoSo.objects.create(ten_co_so="Cơ sở rỗng", dia_chi="Test", quan="Test")
        response = self.client.post(reverse("xu_ly_co_so", args=[empty.pk]), {"hanh_dong": "xoa"})
        self.assertRedirects(response, reverse("quan_ly_co_so"))
        self.assertFalse(CoSo.objects.filter(pk=empty.pk).exists())

    def test_action_endpoint_rejects_cross_site_post_without_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(reverse("xu_ly_co_so", args=[self.facility.pk]), {"hanh_dong": "tam_ngung"})
        self.assertEqual(response.status_code, 403)
        self.facility.refresh_from_db()
        self.assertEqual(self.facility.trang_thai, "hoat_dong")

    def test_p5_assets_and_module_contract_are_isolated(self):
        template_dir = Path(settings.BASE_DIR) / "templates" / "core"
        names = ("quan_ly_co_so.html", "tao_co_so.html", "chi_tiet_co_so.html")
        for name in names:
            source = (template_dir / name).read_text(encoding="utf-8")
            self.assertIn('class="ndt-f5 ndt-f5-page ndt-admin-facilities"', source)
            self.assertIn("foundation/p5.css", source)
            self.assertIn("admin_facilities_post_p6.css", source)
            self.assertNotIn("room_management.css", source)
            self.assertNotIn("foundation/dialog.js", source)
            self.assertNotIn("style=", source)

        detail = (template_dir / "chi_tiet_co_so.html").read_text(encoding="utf-8")
        self.assertIn("foundation/p5-dialog.js", detail)
        self.assertIn("admin_facilities_post_p6.js", detail)
        self.assertIn("data-facility-confirm", detail)
        self.assertNotIn("<details", detail)
        self.assertNotIn("window.confirm", detail)
        for name in names[:2]:
            source = (template_dir / name).read_text(encoding="utf-8")
            self.assertNotIn("p5-dialog.js", source)

    def test_module_css_is_strictly_scoped_to_admin_facilities(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "admin_facilities_post_p6.css").read_text(
            encoding="utf-8"
        )
        selector_headers = re.findall(r"(?m)^\s*([^@}\n][^{\n]*)\{", css)
        selectors = [selector.strip() for header in selector_headers for selector in header.split(",")]
        self.assertTrue(selectors)
        self.assertEqual(
            [selector for selector in selectors if not selector.startswith(".ndt-f5.ndt-admin-facilities")],
            [],
        )
        self.assertNotIn("!important", css)

    @staticmethod
    def _room(facility, number, status):
        return Phong.objects.create(
            co_so=facility,
            so_phong=number,
            tang=1,
            trang_thai=status,
            gia_thue=Decimal("3500000"),
            dien_tich=Decimal("25"),
            so_nguoi_toi_da=2,
            tien_coc_mac_dinh=Decimal("1000000"),
        )
