"""Focused domain tests; all writes use Django's isolated test database."""
from unittest.mock import patch

from django.contrib.auth.models import User

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.dich_vu.yeu_cau_nguoi_o_cung import (
    approve_request, cancel_request, create_request, reject_request,
    request_supplement, resubmit_request,
)
from core.models import NguoiOCungPhong, PhuLucHopDong, ThongBao, YeuCauNguoiOCung


class RequestFoundationTests(BusinessFixture):
    def request(self, contract, key="request-1", cccd="000000000777"):
        return YeuCauNguoiOCung.objects.create(
            hop_dong=contract, nguoi_yeu_cau=self.tenant, ho_ten="Candidate",
            cccd=cccd, ngay_vao=self.today, ma_idempotency=key,
        )

    def candidate(self, cccd="000000000777"):
        return {"ho_ten": "Candidate", "cccd": cccd, "ngay_vao": self.today}

    def test_submit_retry_is_idempotent_and_does_not_create_residency(self):
        contract = self.contract()
        first, created = create_request(contract_id=contract.pk, actor=self.user, idempotency_key="submit-1", **self.candidate())
        second, retried = create_request(contract_id=contract.pk, actor=self.user, idempotency_key="submit-1", **self.candidate())
        self.assertTrue(created)
        self.assertFalse(retried)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(YeuCauNguoiOCung.objects.count(), 1)
        self.assertFalse(NguoiOCungPhong.objects.exists())

    def test_pending_lifecycle_revision_and_terminal_immutability(self):
        request = self.request(self.contract())
        supplement, changed = request_supplement(request_id=request.pk, actor=self.admin, expected_revision=1, reason="Can CCCD ro hon")
        self.assertTrue(changed)
        self.assertEqual((supplement.trang_thai, supplement.revision), ("cho_bo_sung", 2))
        resubmitted, changed = resubmit_request(request_id=request.pk, actor=self.user, expected_revision=2, ho_ten="Updated")
        self.assertTrue(changed)
        self.assertEqual((resubmitted.trang_thai, resubmitted.revision, resubmitted.ly_do), ("cho_xac_minh", 3, ""))
        rejected, changed = reject_request(request_id=request.pk, actor=self.admin, expected_revision=3, reason="Khong du dieu kien")
        self.assertTrue(changed)
        self.assertEqual(rejected.trang_thai, "tu_choi")
        terminal, changed = resubmit_request(request_id=request.pk, actor=self.user, expected_revision=4)
        self.assertFalse(changed)
        self.assertEqual(terminal.trang_thai, "tu_choi")

    def test_stale_and_cancel_vs_approve_have_one_winner_and_zero_extra_writes(self):
        request = self.request(self.contract())
        cancelled, changed = cancel_request(request_id=request.pk, actor=self.user, expected_revision=1)
        self.assertTrue(changed)
        before = (NguoiOCungPhong.objects.count(), PhuLucHopDong.objects.count(), ThongBao.objects.count())
        stale, changed = approve_request(request_id=request.pk, actor=self.admin, expected_revision=1)
        self.assertFalse(changed)
        self.assertEqual(stale.trang_thai, "da_huy")
        self.assertEqual(before, (NguoiOCungPhong.objects.count(), PhuLucHopDong.objects.count(), ThongBao.objects.count()))

    def test_resubmit_wins_over_stale_admin_reject(self):
        request = self.request(self.contract())
        _, changed = request_supplement(request_id=request.pk, actor=self.admin, expected_revision=1, reason="Bo sung")
        self.assertTrue(changed)
        resubmitted, changed = resubmit_request(request_id=request.pk, actor=self.user, expected_revision=2)
        self.assertTrue(changed)
        stale, changed = reject_request(request_id=request.pk, actor=self.admin, expected_revision=2, reason="Too late")
        self.assertFalse(changed)
        self.assertEqual((stale.trang_thai, stale.revision), ("cho_xac_minh", 3))

    def test_approval_is_idempotent_and_creates_effective_residency_once(self):
        request = self.request(self.contract())
        approved, changed = approve_request(request_id=request.pk, actor=self.admin, expected_revision=1)
        again, changed_again = approve_request(request_id=request.pk, actor=self.admin, expected_revision=1)
        self.assertTrue(changed)
        self.assertFalse(changed_again)
        self.assertEqual(NguoiOCungPhong.objects.filter(pk=approved.residency_id).count(), 1)
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 1)
        self.assertEqual(ThongBao.objects.filter(ma_tham_chieu=f"COTENANT_REQUEST:{request.pk}:APPROVED").count(), 1)

    def test_two_admin_approvals_have_one_winner(self):
        request = self.request(self.contract(), "two-admins")
        second_admin = User.objects.create_user("second-reviewer", is_staff=True)
        _, changed = approve_request(request_id=request.pk, actor=self.admin, expected_revision=1)
        self.assertTrue(changed)
        approved, changed = approve_request(request_id=request.pk, actor=second_admin, expected_revision=1)
        self.assertFalse(changed)
        self.assertEqual(approved.trang_thai, "da_duyet")
        self.assertEqual(NguoiOCungPhong.objects.count(), 1)

    def test_two_requests_same_identity_only_one_can_be_approved(self):
        contract = self.contract()
        first = self.request(contract, "same-1", "000000000888")
        second = self.request(contract, "same-2", "000000000888")
        approved, changed = approve_request(request_id=first.pk, actor=self.admin, expected_revision=1)
        self.assertTrue(changed)
        with self.assertRaises(Exception):
            approve_request(request_id=second.pk, actor=self.admin, expected_revision=1)
        second.refresh_from_db()
        self.assertEqual(second.trang_thai, "cho_xac_minh")
        self.assertEqual(NguoiOCungPhong.objects.filter(identity_id=approved.identity_id, trang_thai="dang_o").count(), 1)

    def test_critical_appendix_failure_rolls_back_domain_core(self):
        request = self.request(self.contract())
        with patch("core.dich_vu.yeu_cau_nguoi_o_cung.ghi_nhan_thay_doi_cu_tru", side_effect=RuntimeError("appendix failed")):
            with self.assertRaises(RuntimeError):
                approve_request(request_id=request.pk, actor=self.admin, expected_revision=1)
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision, request.residency_id), ("cho_xac_minh", 1, None))
        self.assertFalse(NguoiOCungPhong.objects.exists())
        self.assertFalse(PhuLucHopDong.objects.exists())

    def test_audit_failure_is_best_effort_but_notification_failure_is_transactional(self):
        request = self.request(self.contract(), "audit-failure")
        with patch("core.tien_ich.NhatKyThaoTac.objects.create", side_effect=RuntimeError("audit offline")):
            approved, changed = approve_request(request_id=request.pk, actor=self.admin, expected_revision=1)
        self.assertTrue(changed)
        self.assertEqual(approved.trang_thai, "da_duyet")
        self.assertEqual(NguoiOCungPhong.objects.count(), 1)

        request2 = self.request(self.contract(), "notification-failure", "000000000999")
        with patch("core.dich_vu.yeu_cau_nguoi_o_cung.ThongBao.objects.get_or_create", side_effect=RuntimeError("notification failed")):
            with self.assertRaises(RuntimeError):
                approve_request(request_id=request2.pk, actor=self.admin, expected_revision=1)
        request2.refresh_from_db()
        self.assertEqual((request2.trang_thai, request2.revision, request2.residency_id), ("cho_xac_minh", 1, None))
        self.assertEqual(NguoiOCungPhong.objects.filter(trang_thai="dang_o").count(), 1)

    def test_stale_revision_has_zero_writes(self):
        request = self.request(self.contract())
        result, changed = approve_request(request_id=request.pk, actor=self.admin, expected_revision=9)
        self.assertFalse(changed)
        self.assertEqual(result.trang_thai, "cho_xac_minh")
        self.assertFalse(NguoiOCungPhong.objects.exists())
