from pathlib import Path

from django.conf import settings
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture


class BookingManagementP6BTests(Phase5BookingFixture):
    def test_booking_screens_opt_in_without_shared_base_assets(self):
        self.client.force_login(self.user)
        booking, _ = self.new_booking()
        tenant_urls = (
            reverse("dat_phong_cua_toi"),
            reverse("chi_tiet_dat_phong_cua_toi", args=[booking.pk]),
            reverse("thanh_toan_coc_cua_toi", args=[booking.pk]),
        )
        for url in tenant_urls:
            response = self.client.get(url)
            self.assertContains(response, "css/foundation/p5.css")
            self.assertContains(response, "css/booking_management_p6b.css")
            self.assertContains(response, "ndt-booking-management")

        self.client.force_login(self.admin)
        for url in (reverse("quan_ly_dat_phong"), reverse("chi_tiet_dat_phong", args=[booking.pk])):
            response = self.client.get(url)
            self.assertContains(response, "css/foundation/p5.css")
            self.assertContains(response, "ndt-booking-management")

        for base in ("templates/core/base.html", "templates/core/tenant_base.html"):
            self.assertNotIn("foundation/p5.css", Path(settings.BASE_DIR, base).read_text(encoding="utf-8"))

    def test_list_mobile_contract_has_label_for_every_cell(self):
        self.client.force_login(self.user)
        self.new_booking()
        html = self.client.get(reverse("dat_phong_cua_toi")).content.decode()
        body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        self.assertEqual(body.count("<td"), body.count("data-label="))

        self.client.force_login(self.admin)
        html = self.client.get(reverse("quan_ly_dat_phong")).content.decode()
        body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        self.assertEqual(body.count("<td"), body.count("data-label="))

    def test_danger_actions_use_p5_dialog_and_keep_payload_names(self):
        self.client.force_login(self.user)
        booking, _ = self.new_booking()
        tenant = self.client.get(reverse("chi_tiet_dat_phong_cua_toi", args=[booking.pk]))
        self.assertContains(tenant, "data-ndt-f5-dialog")
        self.assertContains(tenant, 'name="ly_do_huy"')
        self.assertNotContains(tenant, "window.confirm")

        self.client.force_login(self.admin)
        admin = self.client.get(reverse("chi_tiet_dat_phong", args=[booking.pk]))
        self.assertContains(admin, "data-ndt-f5-dialog")
        self.assertContains(admin, "js/foundation/p5-dialog.js")
        self.assertNotContains(admin, "js/foundation/dialog.js")
