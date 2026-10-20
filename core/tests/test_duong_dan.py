"""Phase 8B-2 route regressions for dead-code cleanup.

These tests intentionally stay at the URL/auth boundary. They protect the
routes that made nearby dead-code removal risky without duplicating the deeper
business-rule tests.
"""
from django.urls import resolve, reverse
from django.utils import timezone

from core.du_lieu_test import tap_hop_views as views
from core.models import HoaDon, LichSuRaVao, FaceProfile, ThongBao, ChinhSachHoTro
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


class Phase8B2RouteRegressionTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.invoice = HoaDon.objects.create(
            hop_dong=self.contract_obj,
            thang=9,
            nam=2026,
            tien_phong=2500000,
            han_thanh_toan=self.today,
        )
        self.notice = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Phase 8B2 notice",
            noi_dung="Route regression fixture",
        )
        self.policy = ChinhSachHoTro.objects.create(
            ten_chinh_sach="Phase 8B2 policy",
            loai_ho_tro="so_tien",
            gia_tri_ho_tro=100000,
            ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today,
        )
        self.face_profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
        )
        self.access_log = LichSuRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.tenant,
            loai_su_kien="vao",
            nguon="thu_cong",
            thoi_diem=timezone.now(),
        )

    def assert_resolves_to(self, name, view, args=None):
        match = resolve(reverse(name, args=args or []))
        self.assertIs(match.func, view)

    def assert_redirects_guest_to_login(self, name, args=None):
        self.client.logout()
        response = self.client.get(reverse(name, args=args or []))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dang_nhap"), response.url)

    def assert_redirects_tenant_to_account(self, name, args=None):
        self.client.logout()
        self.client.force_login(self.user)
        response = self.client.get(reverse(name, args=args or []))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("tai_khoan"), response.url)

    def assert_admin_page_ok(self, name, args=None):
        self.client.logout()
        self.client.force_login(self.admin)
        response = self.client.get(reverse(name, args=args or []))
        self.assertEqual(response.status_code, 200)

    def test_admin_core_routes_resolve_and_enforce_admin_access(self):
        routes = [
            ("quan_ly_phong", views.quan_ly_phong, []),
            ("quan_ly_hop_dong", views.quan_ly_hop_dong, []),
            ("chi_tiet_hop_dong", views.chi_tiet_hop_dong, [self.contract_obj.pk]),
            ("quan_ly_hoa_don", views.quan_ly_hoa_don, []),
            ("chi_tiet_hoa_don", views.chi_tiet_hoa_don, [self.invoice.pk]),
            ("quan_ly_thong_bao", views.quan_ly_thong_bao, []),
            ("quan_ly_chinh_sach", views.quan_ly_chinh_sach, []),
            ("quan_ly_co_so", views.quan_ly_co_so, []),
        ]

        for name, view, args in routes:
            with self.subTest(route=name, actor="resolve"):
                self.assert_resolves_to(name, view, args)
            with self.subTest(route=name, actor="guest"):
                self.assert_redirects_guest_to_login(name, args)
            with self.subTest(route=name, actor="tenant"):
                self.assert_redirects_tenant_to_account(name, args)
            with self.subTest(route=name, actor="admin"):
                self.assert_admin_page_ok(name, args)

    def test_public_room_detail_route_resolves_and_renders(self):
        self.assert_resolves_to("chi_tiet_phong", views.chi_tiet_phong, [self.room.pk])
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("chi_tiet_phong", args=[self.room.pk])).status_code,
            200,
        )
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(reverse("chi_tiet_phong", args=[self.room.pk])).status_code,
            200,
        )

    def test_tenant_invoice_and_account_routes_resolve_and_render_for_tenant(self):
        routes = [
            ("tai_khoan", views.tai_khoan, []),
            ("hoa_don_cua_toi", views.hoa_don_cua_toi, []),
            ("chi_tiet_hoa_don_cua_toi", views.chi_tiet_hoa_don_cua_toi, [self.invoice.pk]),
        ]

        for name, view, args in routes:
            with self.subTest(route=name, actor="resolve"):
                self.assert_resolves_to(name, view, args)
            with self.subTest(route=name, actor="guest"):
                self.assert_redirects_guest_to_login(name, args)
            with self.subTest(route=name, actor="tenant"):
                self.client.force_login(self.user)
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("hoa_don_cua_toi")).status_code, 302)
        self.assertIn(reverse("dashboard_admin"), self.client.get(reverse("hoa_don_cua_toi")).url)

    def test_smart_room_and_access_history_routes_remain_live(self):
        routes = [
            ("smart_room_dashboard", views.smart_room_dashboard, []),
            ("quan_ly_face_profile", views.quan_ly_face_profile, []),
            ("chi_tiet_face_profile", views.chi_tiet_face_profile, [self.face_profile.pk]),
            ("quan_ly_lich_su_ra_vao", views.quan_ly_lich_su_ra_vao, []),
            ("tao_lich_su_ra_vao", views.tao_lich_su_ra_vao, []),
        ]

        for name, view, args in routes:
            with self.subTest(route=name, actor="resolve"):
                self.assert_resolves_to(name, view, args)
            with self.subTest(route=name, actor="guest"):
                self.client.logout()
                response = self.client.get(reverse(name, args=args))
                if name == "chi_tiet_face_profile":
                    self.assertEqual(response.status_code, 404)
                else:
                    self.assertEqual(response.status_code, 302)
                    self.assertIn(reverse("dang_nhap"), response.url)
            with self.subTest(route=name, actor="admin"):
                self.assert_admin_page_ok(name, args)

        self.assert_resolves_to(
            "xu_ly_lich_su_ra_vao",
            views.xu_ly_lich_su_ra_vao,
            [self.access_log.pk],
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("xu_ly_lich_su_ra_vao", args=[self.access_log.pk]),
            {"hanh_dong": "xoa"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LichSuRaVao.objects.filter(pk=self.access_log.pk).exists())
