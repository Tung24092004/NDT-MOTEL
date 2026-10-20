from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class HelpCenterTests(TestCase):
    def test_public_help_center_renders_without_private_data(self):
        User = get_user_model()
        user = User.objects.create_user("tenant-help", password="unused")

        response = self.client.get(reverse("trung_tam_tro_giup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trung tâm trợ giúp")
        self.assertContains(response, "Tìm và chọn phòng")
        self.assertContains(response, "Đặt phòng và tiền cọc")
        self.assertContains(response, "Hợp đồng và gia hạn")
        self.assertContains(response, "Hóa đơn và thanh toán")
        self.assertContains(response, "Sửa chữa")
        self.assertContains(response, "Smart Room và Face ID")
        self.assertContains(response, reverse("huong_dan_thue_phong"))
        self.assertContains(response, "%s#contact" % reverse("home"))
        self.assertNotContains(response, user.username)

    @override_settings(
        NDT_SUPPORT_PHONE="0900000000",
        NDT_SUPPORT_EMAIL="support@example.test",
        NDT_SUPPORT_HOURS="08:00-17:00",
    )
    def test_help_center_uses_configured_support_contact(self):
        response = self.client.get(reverse("trung_tam_tro_giup"))

        self.assertContains(response, "0900000000")
        self.assertContains(response, "support@example.test")
        self.assertContains(response, "08:00-17:00")

    def test_sidebar_keeps_role_specific_help_center_link(self):
        User = get_user_model()
        tenant = User.objects.create_user("tenant-shell", password="unused")
        admin = User.objects.create_user("admin-shell", password="unused", is_staff=True)

        guest_response = self.client.get(reverse("home"))
        self.assertContains(guest_response, reverse("trung_tam_tro_giup"))
        self.assertContains(guest_response, "ndt-role-public")

        self.client.force_login(tenant)
        tenant_response = self.client.get(reverse("trung_tam_tro_giup"))
        self.assertContains(tenant_response, "ndt-role-tenant")
        self.assertContains(tenant_response, 'data-panel="tenant-support"')
        self.assertNotContains(tenant_response, 'data-panel="admin-system"')

        self.client.force_login(admin)
        admin_response = self.client.get(reverse("trung_tam_tro_giup"))
        self.assertContains(admin_response, "ndt-role-admin")
        self.assertContains(admin_response, 'data-panel="admin-system"')
        self.assertNotContains(admin_response, 'data-panel="tenant-support"')
