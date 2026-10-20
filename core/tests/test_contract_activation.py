"""CONTRACT-02C activation boundary tests."""
import threading
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from core.dich_vu.hop_dong import create_draft_contract, respond_to_contract_review, send_contract_for_tenant_confirmation
from core.dich_vu.kich_hoat_hop_dong import activate_accepted_contract
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import FaceProfile, HoaDon, HopDong, LichSuHopDong, NhatKyThaoTac, PhanHoiHopDong, PhienBanHopDong, QuyenRaVao, ThongBao


class ContractActivationTests(Phase5BookingFixture):
    def accepted_contract(self):
        booking, payment = self.new_booking(people=1)
        payment.trang_thai = "da_xac_nhan"
        payment.so_tien_thuc_nhan = payment.so_tien
        payment.thoi_diem_admin_xac_nhan = timezone.now()
        payment.nguoi_xac_nhan = self.admin
        payment.save()
        contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=contract.pk)
        self.user.set_password("current-password")
        self.user.save(update_fields=["password"])
        respond_to_contract_review(actor=self.user, contract_id=contract.pk, version_id=version.pk,
            version_hash=version.ma_bam_sha256, action="chap_thuan", password="current-password")
        return contract, version, booking, payment

    def activate_url(self, contract):
        return reverse("kich_hoat_hop_dong", args=[contract.pk])

    def test_permissions_http_and_ui(self):
        contract, version, _, _ = self.accepted_contract()
        url = self.activate_url(contract)
        self.assertEqual(Client().post(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.admin)
        self.assertEqual(csrf.post(url).status_code, 403)
        self.client.force_login(self.admin)
        page = self.client.get(reverse("chi_tiet_hop_dong", args=[contract.pk]))
        self.assertContains(page, "Kích hoạt hợp đồng đã được chấp thuận")
        self.assertContains(page, version.ma_bam_sha256[:12])
        self.assertContains(page, "Kích hoạt hợp đồng")

    def test_success_is_idempotent_and_has_only_contract_side_effects(self):
        contract, version, booking, _ = self.accepted_contract()
        self.client.force_login(self.admin)
        before = (QuyenRaVao.objects.count(), FaceProfile.objects.count(), HoaDon.objects.count())
        self.client.post(self.activate_url(contract))
        contract.refresh_from_db(); booking.refresh_from_db(); self.room.refresh_from_db()
        self.assertIn(contract.trang_thai, ("dang_hieu_luc", "sap_het_han"))
        self.assertIsNotNone(contract.ngay_ky)
        self.assertEqual(booking.trang_thai, "da_duyet")
        self.assertEqual(self.room.trang_thai, "dang_thue")
        self.assertEqual(LichSuHopDong.objects.filter(hop_dong=contract, hanh_dong="kich_hoat").count(), 1)
        self.assertEqual(NhatKyThaoTac.objects.filter(doi_tuong="HopDong", doi_tuong_id=contract.pk, hanh_dong="kich_hoat").count(), 1)
        self.assertEqual(ThongBao.objects.filter(ma_tham_chieu=f"CONTRACT:{contract.pk}:ACTIVATED").count(), 1)
        self.assertEqual((QuyenRaVao.objects.count(), FaceProfile.objects.count(), HoaDon.objects.count()), before)
        original = (version.du_lieu, version.ma_bam_sha256, PhanHoiHopDong.objects.get(phien_ban=version).ma_bam_phien_ban, contract.ngay_ky)
        self.client.post(self.activate_url(contract))
        contract.refresh_from_db(); version.refresh_from_db()
        self.assertEqual(contract.ngay_ky, original[3])
        self.assertEqual((version.du_lieu, version.ma_bam_sha256, PhanHoiHopDong.objects.get(phien_ban=version).ma_bam_phien_ban), original[:3])
        self.assertEqual(LichSuHopDong.objects.filter(hop_dong=contract, hanh_dong="kich_hoat").count(), 1)

    def test_rejects_review_proof_and_date_failures_without_mutation(self):
        contract, version, _, _ = self.accepted_contract()
        response = PhanHoiHopDong.objects.get(phien_ban=version)
        PhanHoiHopDong.objects.filter(pk=response.pk).update(ma_bam_phien_ban="0" * 64)
        with self.assertRaises(ValidationError): activate_accepted_contract(actor=self.admin, contract_id=contract.pk)
        contract.refresh_from_db(); self.assertEqual(contract.trang_thai, "cho_kich_hoat"); self.assertIsNone(contract.ngay_ky)
        PhanHoiHopDong.objects.filter(pk=response.pk).update(ma_bam_phien_ban=version.ma_bam_sha256)
        contract.ngay_bat_dau = timezone.localdate() + timedelta(days=1)
        contract.save(update_fields=["ngay_bat_dau", "ngay_cap_nhat"])
        with self.assertRaises(ValidationError): activate_accepted_contract(actor=self.admin, contract_id=contract.pk)
        contract.refresh_from_db(); self.assertEqual(contract.trang_thai, "cho_kich_hoat"); self.assertIsNone(contract.ngay_ky)

    def test_rejects_invalid_deposit_room_conflict_and_legacy_hole(self):
        contract, _, booking, payment = self.accepted_contract()
        payment.trang_thai = "tu_choi"; payment.save()
        with self.assertRaises(ValidationError): activate_accepted_contract(actor=self.admin, contract_id=contract.pk)
        payment.trang_thai = "da_xac_nhan"; payment.save()
        other = self.contract(tenant=self.other)
        with self.assertRaises(ValidationError): activate_accepted_contract(actor=self.admin, contract_id=contract.pk)
        other.trang_thai = "da_huy"; other.save(update_fields=["trang_thai"])
        self.client.force_login(self.admin)
        self.client.post(reverse("xu_ly_hop_dong", args=[contract.pk]), {"hanh_dong": "kich_hoat"})
        contract.refresh_from_db(); booking.refresh_from_db()
        self.assertEqual(contract.trang_thai, "cho_kich_hoat")
        self.assertIsNone(contract.ngay_ky)
        self.assertEqual(booking.trang_thai, "cho_duyet")

    def test_rollback_after_downstream_failure(self):
        contract, _, booking, _ = self.accepted_contract()
        with patch("core.dich_vu.kich_hoat_hop_dong.Phong.dong_bo_trang_thai", side_effect=RuntimeError("forced")):
            with self.assertRaises(RuntimeError):
                activate_accepted_contract(actor=self.admin, contract_id=contract.pk)
        contract.refresh_from_db(); booking.refresh_from_db()
        self.assertEqual(contract.trang_thai, "cho_kich_hoat")
        self.assertIsNone(contract.ngay_ky)
        self.assertEqual(booking.trang_thai, "cho_duyet")
        self.assertFalse(LichSuHopDong.objects.filter(hop_dong=contract, hanh_dong="kich_hoat").exists())


class ContractActivationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        BusinessFixture.setUpTestData.__func__(type(self))
        booking, payment = Phase5BookingFixture.new_booking(self, people=1)
        payment.trang_thai = "da_xac_nhan"; payment.so_tien_thuc_nhan = payment.so_tien
        payment.thoi_diem_admin_xac_nhan = timezone.now(); payment.nguoi_xac_nhan = self.admin; payment.save()
        self.contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        self.version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=self.contract.pk)
        self.user.set_password("current-password"); self.user.save(update_fields=["password"])
        respond_to_contract_review(actor=self.user, contract_id=self.contract.pk, version_id=self.version.pk,
            version_hash=self.version.ma_bam_sha256, action="chap_thuan", password="current-password")

    def test_two_admins_create_one_activation_side_effect_set(self):
        barrier = threading.Barrier(2, timeout=10); outcomes = []; outcome_lock = threading.Lock()
        connections.close_all()
        def worker():
            close_old_connections()
            try:
                actor = type(self.admin).objects.get(pk=self.admin.pk); barrier.wait()
                _, created = activate_accepted_contract(actor=actor, contract_id=self.contract.pk)
                outcome = ("ok", created)
            except Exception as error:
                outcome = ("error", type(error).__name__)
            finally:
                close_old_connections()
            with outcome_lock: outcomes.append(outcome)
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads:
            thread.join(timeout=15); self.assertFalse(thread.is_alive(), "activation race timed out")
        close_old_connections()
        self.assertEqual(sorted(outcomes), [("ok", False), ("ok", True)], outcomes)
        self.contract.refresh_from_db()
        self.assertEqual(LichSuHopDong.objects.filter(hop_dong=self.contract, hanh_dong="kich_hoat").count(), 1)
        self.assertEqual(NhatKyThaoTac.objects.filter(doi_tuong_id=self.contract.pk, hanh_dong="kich_hoat").count(), 1)
        self.assertEqual(ThongBao.objects.filter(ma_tham_chieu=f"CONTRACT:{self.contract.pk}:ACTIVATED").count(), 1)
