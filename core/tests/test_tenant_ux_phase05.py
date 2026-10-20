"""Tenant IA and presentation contracts for Phase 05."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


class TenantNavigationContractTests(SimpleTestCase):
    def test_navigation_uses_the_canonical_tenant_domains(self):
        source = (Path(settings.BASE_DIR) / "templates/core/tenant_base.html").read_text(
            encoding="utf-8"
        )
        for label in (
            "Tổng quan",
            "Đặt phòng",
            "Hợp đồng thuê",
            "Hóa đơn &amp; thanh toán",
            "Lưu trú",
            "Ra vào &amp; Face ID",
            "Thông báo",
            "Tài khoản",
            "Trung tâm trợ giúp",
            "Hồ sơ cá nhân",
            "Mật khẩu &amp; bảo mật",
            "Hướng dẫn thuê phòng",
            "Chính sách hỗ trợ",
        ):
            with self.subTest(label=label):
                self.assertIn(label, source)

        self.assertNotIn("Tài khoản &amp; đặt phòng", source)
        self.assertNotIn("Ở ghép của tôi", source)
        self.assertNotIn("Smart Room", source)

    def test_dashboard_uses_overview_identity_and_distinct_sharing_wording(self):
        dashboard = (Path(settings.BASE_DIR) / "templates/core/tai_khoan.html").read_text(
            encoding="utf-8"
        )
        sharing = (Path(settings.BASE_DIR) / "templates/core/yeu_cau_ghep_cua_toi.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("<h1 class=\"ndt-page-header__title ndt-f5-page-header__title\">Tổng quan</h1>", dashboard)
        self.assertNotIn("Tài khoản &amp; đặt phòng", dashboard)
        self.assertIn("{% url 'dat_phong_cua_toi' %}", dashboard)
        self.assertIn("dat_phong_gan_nhat", dashboard)
        self.assertNotIn("{% for dat_phong in danh_sach_dat_phong %}", dashboard)
        self.assertIn("Yêu cầu ở ghép", sharing)
        self.assertNotIn("Ở ghép của tôi", sharing)


class TenantPrimaryHomesRenderTests(BusinessFixture):
    def test_tenant_primary_homes_remain_available(self):
        self.client.force_login(self.user)
        for route_name in (
            "tai_khoan",
            "dat_phong_cua_toi",
            "hop_dong_cua_toi",
            "hoa_don_cua_toi",
            "yeu_cau_sua_chua_cua_toi",
            "yeu_cau_ghep_cua_toi",
            "thong_bao_cua_toi",
            "quyen_va_lich_su_ra_vao_cua_toi",
            "cap_nhat_thong_tin",
            "doi_mat_khau_user",
        ):
            with self.subTest(route_name=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)

    def test_tenant_dashboard_and_access_page_render_canonical_foundation(self):
        self.client.force_login(self.user)
        dashboard = self.client.get(reverse("tai_khoan"))
        access = self.client.get(reverse("quyen_va_lich_su_ra_vao_cua_toi"))

        self.assertContains(dashboard, "ndt-page-header")
        self.assertContains(dashboard, "Tổng quan")
        self.assertContains(access, "Ra vào &amp; Face ID")
        self.assertContains(access, "ndt-page-header")
