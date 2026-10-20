from django.urls import reverse
from django.test import Client
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import BanChupHopDong, HopDong, HoaDon, QuyenRaVao


class ContractDraftTests(Phase5BookingFixture):
    def confirmed_booking(self):
        booking, payment = self.new_booking(people=1)
        payment.trang_thai = "da_xac_nhan"
        payment.so_tien_thuc_nhan = payment.so_tien
        payment.thoi_diem_admin_xac_nhan = timezone.now()
        payment.nguoi_xac_nhan = self.admin
        payment.save()
        return booking, payment

    def test_only_confirmed_deposit_shows_and_creates_one_draft(self):
        booking, payment = self.confirmed_booking()
        self.client.force_login(self.admin)
        detail = self.client.get(reverse("chi_tiet_dat_phong", args=[booking.pk]))
        self.assertTrue(detail.context["dat_phong"].co_the_tao_hop_dong)
        response = self.client.post(reverse("tao_hop_dong", args=[booking.pk]))
        self.assertEqual(response.status_code, 302)
        contract = HopDong.objects.get(dat_phong=booking)
        self.assertEqual(response.url, reverse("chi_tiet_hop_dong", args=[contract.pk]))
        self.assertEqual(contract.trang_thai, "nhap")
        self.assertEqual(contract.tien_coc, booking.tien_coc_du_kien)
        self.assertEqual(contract.tien_coc_thuc_nhan, payment.so_tien_thuc_nhan)
        self.assertIsNone(contract.ngay_ky)
        self.assertTrue(BanChupHopDong.objects.filter(hop_dong=contract).exists())
        self.assertEqual(HoaDon.objects.filter(hop_dong=contract).count(), 0)
        self.assertEqual(QuyenRaVao.objects.filter(hop_dong=contract).count(), 0)
        self.client.post(reverse("tao_hop_dong", args=[booking.pk]))
        self.assertEqual(HopDong.objects.filter(dat_phong=booking).count(), 1)

    def test_unconfirmed_deposit_and_get_do_not_create(self):
        booking, _ = self.new_booking()
        self.client.force_login(self.admin)
        self.assertNotContains(
            self.client.get(reverse("chi_tiet_dat_phong", args=[booking.pk])), "Tạo hợp đồng"
        )
        self.assertEqual(self.client.get(reverse("tao_hop_dong", args=[booking.pk])).status_code, 405)
        self.client.post(reverse("tao_hop_dong", args=[booking.pk]))
        self.assertFalse(HopDong.objects.filter(dat_phong=booking).exists())

    def test_guest_and_tenant_cannot_create(self):
        booking, _ = self.confirmed_booking()
        url = reverse("tao_hop_dong", args=[booking.pk])
        self.client.logout()
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(HopDong.objects.filter(dat_phong=booking).exists())

    def test_post_requires_csrf(self):
        booking, _ = self.confirmed_booking()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse("tao_hop_dong", args=[booking.pk])).status_code, 403)
        self.assertFalse(HopDong.objects.filter(dat_phong=booking).exists())
