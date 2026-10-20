import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import DatPhong, HopDong, NguoiThue, Phong


class AdminDashboardP6GTests(BusinessFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.superuser = User.objects.create_superuser("p6g-superuser", password="test-only")

    def setUp(self):
        self.bookings = [
            self.booking(status, tenant=(self.tenant if index % 2 == 0 else self.other))
            for index, status in enumerate(
                ("cho_duyet", "da_duyet", "tu_choi", "da_huy", "da_duyet", "cho_duyet")
            )
        ]

    def test_role_contract(self):
        guest = self.client.get(reverse("dashboard_admin"))
        self.assertRedirects(guest, reverse("dang_nhap"), fetch_redirect_response=False)

        self.client.force_login(self.user)
        tenant = self.client.get(reverse("dashboard_admin"))
        self.assertRedirects(tenant, reverse("tai_khoan"), fetch_redirect_response=False)

        for admin in (self.admin, self.superuser):
            with self.subTest(admin=admin.username):
                self.client.force_login(admin)
                self.assertEqual(self.client.get(reverse("dashboard_admin")).status_code, 200)

    def test_template_uses_only_p5_and_the_p6g_asset(self):
        source = (
            Path(settings.BASE_DIR) / "templates" / "core" / "dashboard_admin.html"
        ).read_text(encoding="utf-8")

        self.assertEqual(source.count('class="ndt-f5 ndt-f5-page ndt-admin-dashboard"'), 1)
        self.assertIn("css/foundation/p5.css", source)
        self.assertIn("css/admin_dashboard_p6g.css", source)
        for legacy in (
            "css/foundation/tokens.css",
            "css/foundation/typography.css",
            "css/foundation/components.css",
            "css/foundation/utilities.css",
            "css/admin_dashboard.css",
        ):
            self.assertNotIn(legacy, source)
        self.assertNotIn("p5-dialog.js", source)
        self.assertNotIn("<form", source)
        self.assertNotIn("<script", source)
        self.assertNotIn("<style", source)
        self.assertNotIn("window.confirm", source)

    def test_context_metrics_latest_booking_order_and_get_non_mutation(self):
        before = {
            "rooms": list(Phong.objects.order_by("pk").values_list("pk", "trang_thai")),
            "bookings": list(DatPhong.objects.order_by("pk").values_list("pk", "trang_thai")),
            "contracts": list(HopDong.objects.order_by("pk").values_list("pk", "trang_thai")),
        }
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard_admin"))

        expected_metrics = {
            "tong_phong": Phong.objects.count(),
            "phong_trong": Phong.objects.filter(trang_thai="trong").count(),
            "phong_da_dat": Phong.objects.filter(trang_thai="da_dat").count(),
            "phong_dang_thue": Phong.objects.filter(trang_thai="dang_thue").count(),
            "phong_bao_tri": Phong.objects.filter(trang_thai="bao_tri").count(),
            "tong_nguoi_thue": NguoiThue.objects.count(),
            "tong_dat_phong": DatPhong.objects.count(),
            "dat_phong_cho_duyet": DatPhong.objects.filter(trang_thai="cho_duyet").count(),
            "dat_phong_da_duyet": DatPhong.objects.filter(trang_thai="da_duyet").count(),
            "dat_phong_tu_choi": DatPhong.objects.filter(trang_thai="tu_choi").count(),
            "dat_phong_da_huy": DatPhong.objects.filter(trang_thai="da_huy").count(),
            "tong_hop_dong": HopDong.objects.count(),
            "hop_dong_dang_hieu_luc": HopDong.objects.filter(trang_thai="dang_hieu_luc").count(),
            "hop_dong_sap_het_han": HopDong.objects.filter(trang_thai="sap_het_han").count(),
            "hop_dong_cho_hieu_luc": HopDong.objects.filter(trang_thai="cho_hieu_luc").count(),
            "hop_dong_da_het_han": HopDong.objects.filter(trang_thai="da_het_han").count(),
        }
        for name, expected in expected_metrics.items():
            with self.subTest(metric=name):
                self.assertEqual(response.context[name], expected)

        latest_ids = list(DatPhong.objects.order_by("-id").values_list("id", flat=True)[:5])
        self.assertEqual(
            [booking.id for booking in response.context["danh_sach_dat_phong"]],
            latest_ids,
        )
        after = {
            "rooms": list(Phong.objects.order_by("pk").values_list("pk", "trang_thai")),
            "bookings": list(DatPhong.objects.order_by("pk").values_list("pk", "trang_thai")),
            "contracts": list(HopDong.objects.order_by("pk").values_list("pk", "trang_thai")),
        }
        self.assertEqual(after, before)

    def test_real_links_display_labels_and_semantic_statuses(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard_admin"))
        shortcuts = (
            "quan_ly_phong", "quan_ly_dat_phong", "quan_ly_hop_dong", "quan_ly_hoa_don",
            "quan_ly_nguoi_thue", "quan_ly_sua_chua", "quan_ly_thong_bao", "smart_room_dashboard",
        )
        for route_name in shortcuts:
            self.assertContains(response, f'href="{reverse(route_name)}"', html=False)
        for booking in DatPhong.objects.order_by("-id")[:5]:
            self.assertContains(response, reverse("chi_tiet_dat_phong", args=[booking.pk]))
            self.assertContains(response, booking.get_trang_thai_display())
        for raw in (">cho_duyet<", ">da_duyet<", ">tu_choi<", ">da_huy<"):
            self.assertNotContains(response, raw)
        self.assertContains(response, "ndt-f5-badge--success")
        self.assertContains(response, "ndt-f5-badge--pending")
        self.assertContains(response, "ndt-f5-badge--danger")

    def test_booking_cells_have_mobile_labels_and_empty_state_is_real(self):
        source = (
            Path(settings.BASE_DIR) / "templates" / "core" / "dashboard_admin.html"
        ).read_text(encoding="utf-8")
        body = source.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        self.assertEqual(body.count("<td"), body.count("data-label="))

        DatPhong.objects.all().delete()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard_admin"))
        self.assertContains(response, 'class="ndt-f5-empty"', html=False)
        self.assertContains(response, "Chưa có dữ liệu đặt phòng")
        self.assertNotContains(response, "data-booking-id")

    def test_module_css_is_scoped_and_does_not_duplicate_foundation(self):
        css = (
            Path(settings.BASE_DIR) / "static" / "css" / "admin_dashboard_p6g.css"
        ).read_text(encoding="utf-8")
        selector_headers = re.findall(r"(?m)^\s*([^@}\n][^{\n]*)\{", css)
        selectors = []
        for header in selector_headers:
            selectors.extend(part.strip() for part in header.split(","))
        self.assertTrue(selectors)
        self.assertEqual(
            [selector for selector in selectors if not selector.startswith(".ndt-f5.ndt-admin-dashboard")],
            [],
        )
        self.assertNotIn("!important", css)
        self.assertNotRegex(
            css,
            r"(?m)^\.ndt-f5-(?:button|table|badge)\s*\{",
        )
