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
        self.assertContains(response, "ndt-filter-bar")
        self.assertContains(response, "ndt-card")
        self.assertContains(response, "ndt-badge")
        self.assertContains(response, "Phòng trống")
        self.assertNotContains(response, ">trong<")

        room = Phong.objects.get(pk=self.room.pk)
        chuan_bi_gallery_hien_thi([room])
        self.assertContains(response, room.anh_dai_dien_hien_thi.anh.url)

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
        self.assertContains(response, "data-ndt-confirm-form")
        self.assertContains(response, "js/foundation/dialog.js")
        self.assertContains(response, "ndtDialogRoot")
        self.assertNotContains(response, "return confirm(")
        self.assertContains(response, "ndt-table-wrap")
        self.assertContains(response, "ndt-badge")
