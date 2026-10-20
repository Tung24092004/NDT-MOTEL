"""UI Foundation V1 contracts and pilot-page regressions."""

from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from core.dich_vu.gallery_phong import _gallery_tren_dia, chuan_bi_gallery_hien_thi
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import Phong


FOUNDATION_CSS = (
    "css/foundation/tokens.css",
    "css/foundation/typography.css",
    "css/foundation/components.css",
    "css/foundation/utilities.css",
)


class FoundationAssetTests(SimpleTestCase):
    def test_foundation_assets_and_partials_exist(self):
        static_root = Path(settings.BASE_DIR) / "static"
        for asset in (*FOUNDATION_CSS, "js/foundation/dialog.js"):
            with self.subTest(asset=asset):
                self.assertTrue((static_root / asset).is_file())

        for template in (
            "core/foundation/breadcrumb.html",
            "core/foundation/contextual_back.html",
            "core/foundation/page_header.html",
            "core/foundation/empty_state.html",
            "core/foundation/dialog_root.html",
        ):
            with self.subTest(template=template):
                get_template(template)

    def test_component_contracts_cover_required_states(self):
        css = (Path(settings.BASE_DIR) / "static/css/foundation/components.css").read_text(
            encoding="utf-8"
        )
        for selector in (
            ".ndt-button--primary",
            ".ndt-button--secondary",
            ".ndt-button--danger",
            ".ndt-button--ghost",
            ".ndt-button--icon",
            ".ndt-badge--neutral",
            ".ndt-badge--success",
            ".ndt-control",
            ".ndt-page-header",
            ".ndt-filter-bar",
            ".ndt-table-wrap",
            ".ndt-empty-state",
            ".ndt-dialog",
            ".ndt-card",
            ":focus-visible",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)

        dialog = (Path(settings.BASE_DIR) / "static/js/foundation/dialog.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('event.key === "Escape"', dialog)
        self.assertIn('event.key !== "Tab"', dialog)
        self.assertIn("window.NDTDialog", dialog)

    def test_page_header_primitives_render_semantic_navigation_status_and_actions(self):
        rendered = get_template("core/foundation/page_header.html").render({
            "breadcrumb_root_url": "/",
            "breadcrumb_root_label": "Home",
            "breadcrumb_parent_url": "/rooms/",
            "breadcrumb_parent_label": "Rooms",
            "breadcrumb_current": "Room A1",
            "back_url": "/rooms/",
            "back_label": "Back to rooms",
            "title": "Room A1",
            "subtitle": "Available now",
            "metadata": "Updated today",
            "status_label": "Available",
            "status_variant": "success",
            "secondary_action_url": "/contact/",
            "secondary_action_label": "Contact",
            "action_url": "/book/",
            "action_label": "Book room",
        })

        self.assertIn('aria-label="Đường dẫn"', rendered)
        self.assertIn('href="/">Home</a>', rendered)
        self.assertIn('aria-current="page">Room A1', rendered)
        self.assertIn('class="ndt-contextual-back" href="/rooms/"', rendered)
        self.assertIn("ndt-badge--success", rendered)
        self.assertIn("Available", rendered)
        self.assertIn("ndt-button--secondary", rendered)
        self.assertIn("ndt-button--primary", rendered)

        for variant in ("neutral", "info", "success", "warning", "danger"):
            with self.subTest(variant=variant):
                status = get_template("core/foundation/page_header.html").render({
                    "title": "Status example",
                    "status_label": f"{variant} status",
                    "status_variant": variant,
                })
                self.assertIn(f"ndt-badge--{variant}", status)
                self.assertIn(f"{variant} status", status)

    def test_empty_state_handles_primary_secondary_and_no_actions(self):
        template = get_template("core/foundation/empty_state.html")
        with_actions = template.render({
            "title": "Nothing here",
            "action_url": "/create/",
            "action_label": "Create",
            "secondary_action_url": "/help/",
            "secondary_action_label": "Help",
        })
        without_actions = template.render({"title": "Nothing here"})

        self.assertIn("ndt-button--secondary", with_actions)
        self.assertIn("ndt-empty-state__secondary", with_actions)
        self.assertNotIn("ndt-empty-state__action", without_actions)


@override_settings(MEDIA_ROOT=Path(settings.BASE_DIR) / "media")
class FoundationPilotRenderTests(BusinessFixture):
    def setUp(self):
        super().setUp()
        _gallery_tren_dia.cache_clear()

    def tearDown(self):
        _gallery_tren_dia.cache_clear()
        super().tearDown()

    def assert_foundation_assets(self, response):
        for asset in FOUNDATION_CSS:
            self.assertContains(response, asset)

    def test_public_room_pilot_renders_foundation_and_gallery_cover(self):
        self.client.logout()
        response = self.client.get(reverse("danh_sach_phong"))

        self.assertEqual(response.status_code, 200)
        self.assert_foundation_assets(response)
        self.assertContains(response, 'data-foundation-pilot="rooms-public"')
        self.assertContains(response, 'class="ndt-page-header"')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "ndt-breadcrumb__list")
        self.assertContains(response, "ndt-filter-bar")
        self.assertContains(response, "ndt-card")
        self.assertContains(response, "ndt-badge")
        self.assertContains(response, "Phòng trống")
        self.assertNotContains(response, ">trong<")

        room = Phong.objects.get(pk=self.room.pk)
        chuan_bi_gallery_hien_thi([room])
        self.assertContains(response, room.anh_dai_dien_hien_thi.anh.url)

    def test_invoice_representatives_load_canonical_foundation_components(self):
        self.client.force_login(self.user)
        tenant_response = self.client.get(reverse("hoa_don_cua_toi"))
        self.assertEqual(tenant_response.status_code, 200)
        self.assertContains(tenant_response, "css/foundation/components.css")
        self.assertContains(tenant_response, "ndt-page-header")
        self.assertContains(tenant_response, "ndt-empty-state")

        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse("quan_ly_hoa_don"))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, "css/foundation/components.css")
        self.assertContains(admin_response, "ndt-page-header")
        self.assertContains(admin_response, "ndt-empty-state")

    def test_public_room_back_link_preserves_selected_period(self):
        source = (Path(settings.BASE_DIR) / "templates/core/chi_tiet_phong.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("ndt-contextual-back", source)
        self.assertIn("{% if availability_query %}?{{ availability_query }}{% endif %}", source)

    def test_admin_room_pilot_keeps_filters_actions_and_permissions(self):
        guest = self.client.get(reverse("quan_ly_phong"))
        self.assertEqual(guest.status_code, 302)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("quan_ly_phong"), {"q": self.room.so_phong})

        self.assertEqual(response.status_code, 200)
        self.assert_foundation_assets(response)
        self.assertContains(response, 'data-room-management-page="list"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="trang_thai"')
        self.assertContains(response, reverse("tao_phong"))
        self.assertContains(response, reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertContains(response, reverse("sua_phong", args=[self.room.pk]))
        self.assertContains(response, reverse("xoa_phong", args=[self.room.pk]))
        self.assertContains(response, "data-room-delete-form")
        self.assertContains(response, "data-ndt-f5-dialog")
        self.assertContains(response, "js/foundation/p5-dialog.js")
        self.assertNotContains(response, "return confirm(")
        self.assertContains(response, "ndt-f5-table-wrap")
        self.assertContains(response, "ndt-f5-badge")
