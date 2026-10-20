from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import ChinhSachHoTro, FaceProfile, NguoiThue, Phong


class PublicDiscoverySupportSourceContractTests(SimpleTestCase):
    template_names = (
        "home.html",
        "danh_sach_phong.html",
        "chi_tiet_phong.html",
        "huong_dan_thue_phong.html",
        "trung_tam_tro_giup.html",
        "chinh_sach_ho_tro.html",
    )

    def setUp(self):
        self.template_dir = Path(settings.BASE_DIR) / "templates" / "core"
        self.css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "public_discovery_support_post_p6.css"
        )

    def test_six_contexts_opt_into_p5_and_the_public_module(self):
        for name in self.template_names:
            with self.subTest(template=name):
                source = (self.template_dir / name).read_text(encoding="utf-8")
                self.assertIn("foundation/p5.css", source)
                self.assertIn("public_discovery_support_post_p6.css", source)
                self.assertIn("ndt-f5", source)
                self.assertIn("ndt-public-discovery", source)
                self.assertIn("data-public-context", source)

    def test_room_detail_keeps_the_admin_p6a_branch(self):
        source = (self.template_dir / "chi_tiet_phong.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("room_management_p6a.css", source)
        self.assertIn("data-room-admin-detail", source)
        self.assertIn("ndt-room-admin-detail", source)
        self.assertIn("{% else %}", source)

    def test_room_list_keeps_filter_and_pagination_contract(self):
        source = (self.template_dir / "danh_sach_phong.html").read_text(
            encoding="utf-8"
        )
        for contract in (
            'name="q"',
            'name="gia_max"',
            "pagination_query",
            "page_obj.has_previous",
            "page_obj.has_next",
        ):
            self.assertIn(contract, source)

    def test_help_search_uses_the_p5_screen_reader_utility(self):
        source = (self.template_dir / "trung_tam_tro_giup.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('class="ndt-f5-sr-only"', source)
        self.assertNotIn('class="sr-only"', source)

    def test_public_module_is_scoped_and_has_no_overflow_mask_or_important(self):
        css = self.css_path.read_text(encoding="utf-8")
        self.assertIn(".ndt-public-discovery", css)
        self.assertNotIn("!important", css)
        self.assertNotIn("overflow-x: hidden", css)
        self.assertNotIn("overflow-x:hidden", css)

        selector_headers = [
            line.strip()
            for line in css.splitlines()
            if line.strip().endswith("{") and not line.lstrip().startswith("@")
        ]
        for selector in selector_headers:
            with self.subTest(selector=selector):
                self.assertTrue(
                    selector.startswith(".ndt-public-discovery")
                    or selector.startswith(".ndt-public-"),
                    selector,
                )

    def test_shared_shells_are_still_p5_free(self):
        for name in ("base.html", "tenant_base.html"):
            source = (self.template_dir / name).read_text(encoding="utf-8")
            self.assertNotIn("public_discovery_support_post_p6.css", source)
            self.assertNotIn("foundation/p5.css", source)


class PublicDiscoverySupportRenderTests(BusinessFixture):
    public_asset = "css/public_discovery_support_post_p6.css"

    def assert_public_context(self, response, context_name):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "css/foundation/p5.css")
        self.assertContains(response, self.public_asset)
        self.assertContains(response, f'data-public-context="{context_name}"')

    def test_six_guest_render_contexts_use_the_public_foundation(self):
        cases = (
            ("home", (), "home"),
            ("danh_sach_phong", (), "room-list"),
            ("chi_tiet_phong", (self.room.pk,), "room-detail"),
            ("huong_dan_thue_phong", (), "rental-guide"),
            ("trung_tam_tro_giup", (), "help-center"),
            ("chinh_sach_ho_tro", (), "support-policy"),
        )
        for route, args, context_name in cases:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assert_public_context(response, context_name)

    def test_tenant_room_detail_uses_public_branch_without_admin_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assert_public_context(response, "room-detail")
        self.assertNotContains(response, "data-room-admin-detail")
        self.assertNotContains(response, "css/room_management_p6a.css")
        self.assertNotContains(response, "Sửa thông tin phòng")

    def test_admin_room_detail_keeps_the_p6a_branch_isolated(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-room-admin-detail")
        self.assertContains(response, "css/room_management_p6a.css")
        self.assertNotContains(response, self.public_asset)
        self.assertNotContains(response, "data-public-context")

    def test_room_filters_keep_query_context_and_pagination_query(self):
        response = self.client.get(
            reverse("danh_sach_phong"),
            {"q": self.room.so_phong, "gia_max": "3000000", "page": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tu_khoa"], self.room.so_phong)
        self.assertEqual(response.context["gia_max"], "3000000")
        self.assertEqual(
            response.context["pagination_query"],
            f"q={self.room.so_phong}&gia_max=3000000",
        )
        self.assertContains(response, self.room.so_phong)

    def test_public_gets_do_not_mutate_owned_business_rows(self):
        before = (
            Phong.objects.count(),
            NguoiThue.objects.count(),
            ChinhSachHoTro.objects.count(),
            FaceProfile.objects.count(),
        )
        routes = (
            reverse("home"),
            reverse("danh_sach_phong"),
            reverse("chi_tiet_phong", args=[self.room.pk]),
            reverse("huong_dan_thue_phong"),
            reverse("trung_tam_tro_giup"),
            reverse("chinh_sach_ho_tro"),
        )
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(
            before,
            (
                Phong.objects.count(),
                NguoiThue.objects.count(),
                ChinhSachHoTro.objects.count(),
                FaceProfile.objects.count(),
            ),
        )

    def test_support_policy_rejects_post(self):
        self.assertEqual(
            self.client.post(reverse("chinh_sach_ho_tro")).status_code,
            405,
        )
