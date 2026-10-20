from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import HopDong, PhienBanHopDong


class ContractReviewTests(Phase5BookingFixture):
    def draft(self):
        booking, payment = self.new_booking(people=1)
        payment.trang_thai = "da_xac_nhan"
        payment.so_tien_thuc_nhan = payment.so_tien
        payment.thoi_diem_admin_xac_nhan = timezone.now()
        payment.nguoi_xac_nhan = self.admin
        payment.save()
        from core.dich_vu.hop_dong import create_draft_contract
        return create_draft_contract(actor=self.admin, booking_id=booking.pk)[0]

    def test_admin_sends_one_immutable_review_version(self):
        contract = self.draft()
        self.client.force_login(self.admin)
        url = reverse("gui_hop_dong_xac_nhan", args=[contract.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        contract.refresh_from_db()
        version = contract.phien_ban_hien_tai
        self.assertEqual(contract.trang_thai, "cho_nguoi_thue_xac_nhan")
        self.assertEqual(version.so_phien_ban, 1)
        self.assertRegex(version.ma_bam_sha256, r"^[0-9a-f]{64}$")
        self.assertNotIn("cccd", version.du_lieu["nguoi_thue"])
        self.assertNotIn("so_dien_thoai", version.du_lieu["nguoi_thue"])
        self.client.post(url)
        self.assertEqual(PhienBanHopDong.objects.filter(hop_dong=contract).count(), 1)
        self.assertIsNone(contract.ngay_ky)

    def test_unconfirmed_payment_and_non_admin_cannot_send(self):
        booking, _ = self.new_booking(people=1)
        from core.dich_vu.hop_dong import create_draft_contract
        # A manually created draft proves the send action still rejects unconfirmed deposit.
        contract = HopDong.objects.create(dat_phong=booking, so_hop_dong="HD-TEST-REVIEW", ngay_bat_dau=booking.ngay_nhan_phong,
            ngay_ket_thuc=booking.ngay_tra_du_kien, tien_thue_thang=booking.gia_thue_thang_tai_thoi_diem_dat,
            tien_coc=booking.tien_coc_du_kien, trang_thai="nhap")
        url = reverse("gui_hop_dong_xac_nhan", args=[contract.pk])
        self.client.force_login(self.user)
        self.client.post(url)
        self.assertFalse(PhienBanHopDong.objects.filter(hop_dong=contract).exists())
        self.client.force_login(self.admin)
        self.client.post(url)
        self.assertFalse(PhienBanHopDong.objects.filter(hop_dong=contract).exists())

    def test_post_requires_csrf_and_tenant_view_uses_review(self):
        contract = self.draft()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(reverse("gui_hop_dong_xac_nhan", args=[contract.pk])).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(reverse("gui_hop_dong_xac_nhan", args=[contract.pk]))
        self.client.force_login(self.user)
        response = self.client.get(reverse("chi_tiet_hop_dong_cua_toi", args=[contract.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["phien_ban_review"])
