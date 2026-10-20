from django.test import TestCase
from django.urls import reverse


class GuestSidebarTests(TestCase):
    def test_guest_sidebar_links_only_to_available_public_destinations(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'data-panel="public-discovery"')
        self.assertContains(response, 'data-panel-id="public-discovery"')
        self.assertContains(response, 'href="%s"' % reverse("danh_sach_phong"))
        self.assertContains(response, 'href="%s#features"' % reverse("home"))
        self.assertContains(response, 'href="%s#contact"' % reverse("home"))
        self.assertContains(response, 'href="%s"' % reverse("huong_dan_thue_phong"))
        self.assertContains(response, 'href="%s"' % reverse("trung_tam_tro_giup"))
        self.assertNotContains(response, 'trang_thai=trong')
        self.assertNotContains(response, 'ndt-public-nav-group')
        self.assertNotContains(response, 'ndt-public-nav-links')
        self.assertContains(response, 'data-auth-mode="login"')
        self.assertContains(response, 'data-auth-mode="register"')

    def test_room_list_marks_discovery_and_its_room_link_active(self):
        response = self.client.get(reverse("danh_sach_phong"))

        self.assertContains(response, 'class="ndt-public-flyout-link is-active"')
