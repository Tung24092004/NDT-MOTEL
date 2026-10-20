import threading

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.dich_vu.hop_dong import (
    create_draft_contract, respond_to_contract_review,
    send_contract_for_tenant_confirmation,
)
from core.models import (
    FaceProfile, HoaDon, HopDong, LichSuHopDong, NhatKyThaoTac,
    PhanHoiHopDong, PhienBanHopDong, QuyenRaVao, ThongBao,
)


class ContractResponseTests(Phase5BookingFixture):
    def setUp(self):
        super().setUp()
        self.user.set_password("current-password")
        self.user.save(update_fields=["password"])

    def review_contract(self):
        booking, payment = self.new_booking(people=1)
        payment.trang_thai = "da_xac_nhan"
        payment.so_tien_thuc_nhan = payment.so_tien
        payment.thoi_diem_admin_xac_nhan = timezone.now()
        payment.nguoi_xac_nhan = self.admin
        payment.save()
        contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=contract.pk)
        return contract, version

    def response_data(self, version, **extra):
        data = {"phien_ban_id": version.pk, "ma_bam_phien_ban": version.ma_bam_sha256}
        data.update(extra)
        return data

    def test_acceptance_requires_checkbox_and_current_password(self):
        contract, version = self.review_contract()
        url = reverse("chap_thuan_hop_dong", args=[contract.pk])
        self.client.force_login(self.user)
        self.client.post(url, self.response_data(version, mat_khau="current-password"))
        self.assertFalse(PhanHoiHopDong.objects.exists())
        self.client.post(url, self.response_data(version, da_doc_va_chap_thuan="on", mat_khau="wrong"))
        self.assertFalse(PhanHoiHopDong.objects.exists())
        self.client.post(url, self.response_data(version, da_doc_va_chap_thuan="on", mat_khau="current-password"))
        contract.refresh_from_db()
        response = PhanHoiHopDong.objects.get(phien_ban=version)
        self.assertEqual(response.hanh_dong, "chap_thuan")
        self.assertEqual(contract.trang_thai, "cho_kich_hoat")
        self.assertIsNone(contract.ngay_ky)
        self.assertEqual(HopDong.objects.get(pk=contract.pk).phien_ban_hien_tai_id, version.pk)
        self.assertContains(
            self.client.get(reverse("chi_tiet_hop_dong_cua_toi", args=[contract.pk])),
            "Kết quả phản hồi hợp đồng",
        )

    def test_revision_is_trimmed_and_admin_can_reopen_only_after_revision(self):
        contract, version = self.review_contract()
        self.client.force_login(self.user)
        url = reverse("yeu_cau_chinh_sua_hop_dong", args=[contract.pk])
        self.client.post(url, self.response_data(version, ly_do="   "))
        self.assertFalse(PhanHoiHopDong.objects.exists())
        self.client.post(url, self.response_data(version, ly_do="  Vui lòng sửa điều khoản.  "))
        contract.refresh_from_db()
        response = PhanHoiHopDong.objects.get(phien_ban=version)
        self.assertEqual(response.ly_do, "Vui lòng sửa điều khoản.")
        self.assertEqual(contract.trang_thai, "yeu_cau_chinh_sua")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("mo_lai_hop_dong_de_sua", args=[contract.pk])).status_code, 405)
        self.client.post(reverse("mo_lai_hop_dong_de_sua", args=[contract.pk]))
        contract.refresh_from_db()
        self.assertEqual(contract.trang_thai, "nhap")
        self.assertEqual(PhanHoiHopDong.objects.get(pk=response.pk).ly_do, "Vui lòng sửa điều khoản.")

    def test_stale_hash_other_tenant_and_double_submit_cannot_mutate_again(self):
        contract, version = self.review_contract()
        url = reverse("chap_thuan_hop_dong", args=[contract.pk])
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.post(url, self.response_data(version, da_doc_va_chap_thuan="on", mat_khau="x")).status_code, 404)
        self.client.force_login(self.user)
        self.client.post(url, self.response_data(version, ma_bam_phien_ban="0" * 64, da_doc_va_chap_thuan="on", mat_khau="current-password"))
        self.assertFalse(PhanHoiHopDong.objects.exists())
        valid = self.response_data(version, da_doc_va_chap_thuan="on", mat_khau="current-password")
        self.client.post(url, valid)
        self.client.post(url, valid)
        self.assertEqual(PhanHoiHopDong.objects.filter(phien_ban=version).count(), 1)

    def test_post_only_csrf_and_admin_cannot_use_tenant_action(self):
        contract, version = self.review_contract()
        url = reverse("chap_thuan_hop_dong", args=[contract.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(url, self.response_data(version, da_doc_va_chap_thuan="on", mat_khau="current-password")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url, self.response_data(version, da_doc_va_chap_thuan="on", mat_khau="current-password")).status_code, 404)

    def test_guest_is_redirected_and_get_has_no_mutation(self):
        contract, version = self.review_contract()
        url = reverse("chap_thuan_hop_dong", args=[contract.pk])
        response = Client().post(url, self.response_data(version))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("dang_nhap"))
        self.client.force_login(self.user)
        before = (PhanHoiHopDong.objects.count(), LichSuHopDong.objects.count(), NhatKyThaoTac.objects.count())
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual((PhanHoiHopDong.objects.count(), LichSuHopDong.objects.count(), NhatKyThaoTac.objects.count()), before)

    def test_acceptance_has_no_sensitive_or_activation_side_effects(self):
        contract, version = self.review_contract()
        self.client.force_login(self.user)
        before = (QuyenRaVao.objects.count(), FaceProfile.objects.count(), HoaDon.objects.count())
        response = self.client.post(
            reverse("chap_thuan_hop_dong", args=[contract.pk]),
            self.response_data(version, da_doc_va_chap_thuan="on", mat_khau="current-password"),
        )
        self.assertNotIn(b"current-password", response.content)
        self.assertFalse(PhanHoiHopDong.objects.filter(ly_do__contains="current-password").exists())
        self.assertFalse(NhatKyThaoTac.objects.filter(noi_dung__contains="current-password").exists())
        self.assertFalse(ThongBao.objects.filter(noi_dung__contains="current-password").exists())
        self.assertEqual((QuyenRaVao.objects.count(), FaceProfile.objects.count(), HoaDon.objects.count()), before)
        contract.refresh_from_db()
        self.assertEqual(contract.trang_thai, "cho_kich_hoat")
        self.assertIsNone(contract.ngay_ky)
        self.assertEqual(contract.dat_phong.phong.trang_thai, self.room.trang_thai)

    def test_revision_boundary_admin_display_and_response_are_immutable(self):
        contract, version = self.review_contract()
        original_payload, original_hash = version.du_lieu.copy(), version.ma_bam_sha256
        self.client.force_login(self.user)
        url = reverse("yeu_cau_chinh_sua_hop_dong", args=[contract.pk])
        self.client.post(url, self.response_data(version, ly_do="x" * 2001))
        self.assertFalse(PhanHoiHopDong.objects.exists())
        self.client.post(url, self.response_data(version, ly_do="  Lý do hiển thị. "))
        feedback = PhanHoiHopDong.objects.get(phien_ban=version)
        self.client.force_login(self.admin)
        detail = self.client.get(reverse("chi_tiet_hop_dong", args=[contract.pk]))
        self.assertContains(detail, "Lý do hiển thị.")
        self.assertContains(detail, "Yêu cầu chỉnh sửa")
        self.client.post(reverse("mo_lai_hop_dong_de_sua", args=[contract.pk]))
        version.refresh_from_db()
        feedback.refresh_from_db()
        self.assertEqual((version.du_lieu, version.ma_bam_sha256), (original_payload, original_hash))
        self.assertEqual(feedback.ly_do, "Lý do hiển thị.")
        feedback.ly_do = "mutated"
        with self.assertRaises(Exception):
            feedback.save()

    def test_old_version_is_rejected_after_resend_and_new_response_is_independent(self):
        contract, old_version = self.review_contract()
        self.client.force_login(self.user)
        self.client.post(reverse("yeu_cau_chinh_sua_hop_dong", args=[contract.pk]), self.response_data(old_version, ly_do="Sửa"))
        self.client.force_login(self.admin)
        self.client.post(reverse("mo_lai_hop_dong_de_sua", args=[contract.pk]))
        contract.dieu_khoan = "Điều khoản đã thay đổi"
        contract.save(update_fields=["dieu_khoan", "ngay_cap_nhat"])
        new_version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=contract.pk)
        self.assertNotEqual(new_version.ma_bam_sha256, old_version.ma_bam_sha256)
        self.client.force_login(self.user)
        self.client.post(reverse("chap_thuan_hop_dong", args=[contract.pk]), self.response_data(old_version, da_doc_va_chap_thuan="on", mat_khau="current-password"))
        self.assertEqual(PhanHoiHopDong.objects.filter(phien_ban=old_version).count(), 1)
        self.client.post(reverse("chap_thuan_hop_dong", args=[contract.pk]), self.response_data(new_version, da_doc_va_chap_thuan="on", mat_khau="current-password"))
        self.assertEqual(PhanHoiHopDong.objects.filter(phien_ban=new_version).count(), 1)

    def test_resend_after_reopen_creates_next_version(self):
        contract, version = self.review_contract()
        self.client.force_login(self.user)
        self.client.post(reverse("yeu_cau_chinh_sua_hop_dong", args=[contract.pk]), self.response_data(version, ly_do="Sửa lại"))
        self.client.force_login(self.admin)
        self.client.post(reverse("mo_lai_hop_dong_de_sua", args=[contract.pk]))
        next_version, created = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=contract.pk)
        self.assertTrue(created)
        self.assertEqual(next_version.so_phien_ban, 2)
        self.assertEqual(PhienBanHopDong.objects.filter(hop_dong=contract).count(), 2)


class ContractResponseConcurrencyTests(TransactionTestCase):
    """Exercise the real MySQL row locks using two independent worker connections."""

    def setUp(self):
        BusinessFixture.setUpTestData.__func__(type(self))
        self.client = Client()
        booking, payment = Phase5BookingFixture.new_booking(self, people=1)
        payment.trang_thai = "da_xac_nhan"
        payment.so_tien_thuc_nhan = payment.so_tien
        payment.thoi_diem_admin_xac_nhan = timezone.now()
        payment.nguoi_xac_nhan = self.admin
        payment.save()
        self.contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        self.version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=self.contract.pk)
        self.user.set_password("current-password")
        self.user.save(update_fields=["password"])

    def test_accept_and_revision_race_has_one_winner_and_one_side_effect_set(self):
        barrier = threading.Barrier(2, timeout=10)
        outcomes = []
        outcome_lock = threading.Lock()

        # TransactionTestCase shares the main test-runner connection with the
        # preceding TestCase class.  Release it before workers take InnoDB row
        # locks; each worker then creates and closes its own connection.
        connections.close_all()

        def worker(action):
            close_old_connections()
            try:
                actor = type(self.user).objects.get(pk=self.user.pk)
                barrier.wait()
                result = respond_to_contract_review(
                    actor=actor, contract_id=self.contract.pk, version_id=self.version.pk,
                    version_hash=self.version.ma_bam_sha256, action=action,
                    password="current-password" if action == "chap_thuan" else "",
                    reason="Cần sửa" if action == "yeu_cau_chinh_sua" else "",
                )
                outcome = ("won", result.hanh_dong)
            except ValidationError:
                outcome = ("lost", action)
            except Exception as error:  # Preserve unexpected database failures as test evidence.
                outcome = ("error", type(error).__name__)
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=worker, args=(action,)) for action in ("chap_thuan", "yeu_cau_chinh_sua")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive(), "worker race timed out")

        close_old_connections()
        self.assertEqual(sorted(item[0] for item in outcomes), ["lost", "won"], outcomes)
        self.contract.refresh_from_db()
        feedback = PhanHoiHopDong.objects.get(phien_ban=self.version)
        self.assertEqual(PhanHoiHopDong.objects.filter(phien_ban=self.version).count(), 1)
        self.assertEqual(self.contract.trang_thai, "cho_kich_hoat" if feedback.hanh_dong == "chap_thuan" else "yeu_cau_chinh_sua")
        self.assertEqual(LichSuHopDong.objects.filter(hop_dong=self.contract, noi_dung__contains="phien ban 1").count(), 1)
        self.assertEqual(NhatKyThaoTac.objects.filter(doi_tuong="HopDong", doi_tuong_id=self.contract.pk, tieu_de__contains="Phan hoi").count(), 1)
        self.assertEqual(ThongBao.objects.filter(ma_tham_chieu__startswith=f"CONTRACT:{self.contract.pk}:RESPONSE:").count(), 1)
        self.assertIsNone(self.contract.ngay_ky)
        self.assertFalse(QuyenRaVao.objects.filter(hop_dong=self.contract).exists())
        self.assertFalse(FaceProfile.objects.filter(nguoi_thue=self.contract.dat_phong.nguoi_thue).exists())
        self.assertFalse(HoaDon.objects.filter(hop_dong=self.contract).exists())
