"""Failure-atomicity coverage for the Admin invoice payment reconciliation.

The reconciliation entry point is intentionally called directly: a view-level
redirect/error handler must never make a failed transaction look successful.
"""
from unittest.mock import patch
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connections
from django.test import Client, TransactionTestCase
from django.urls import reverse

from core.models import (
    ChungTuThanhToan, CoSo, DatPhong, HoaDon, HopDong, LichSuThanhToan,
    NguoiThue, NhatKyThaoTac, Phong, ThongBao,
)


class AdminInvoiceAttemptFailureAtomicityTests(TransactionTestCase):
    """Each injected error must roll back the invoice, attempt, and DB effects."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("invoice-atomicity-owner")
        facility = CoSo.objects.create(ten_co_so="Invoice atomicity", dia_chi="Test", quan="Hai Chau")
        room = Phong.objects.create(
            co_so=facility, so_phong="INVOICE-ATOMICITY", gia_thue=Decimal("2500000"), dien_tich=Decimal("24")
        )
        tenant = NguoiThue.objects.create(
            tai_khoan=self.user, ho_ten="Invoice atomicity owner", cccd="012345670035", so_dien_thoai="0900000035"
        )
        booking = DatPhong.objects.create(
            nguoi_thue=tenant, phong=room, ngay_nhan_phong=date(2026, 1, 1),
            trang_thai="da_duyet", ma_yeu_cau="INVOICE-ATOMICITY-0034",
        )
        contract = HopDong.objects.create(
            dat_phong=booking, so_hop_dong="HD-INVOICE-ATOMICITY", ngay_bat_dau=date(2026, 1, 1),
            ngay_ket_thuc=date(2027, 1, 1), tien_thue_thang=Decimal("2500000"),
        )
        self.invoice = HoaDon.objects.create(
            hop_dong=contract, thang=1, nam=2026, tien_phong=Decimal("2500000"),
            han_thanh_toan=date(2026, 1, 5), trang_thai="chua_thanh_toan",
        )
        self.admin = User.objects.create_user("invoice-atomicity-admin", is_staff=True)
        self.client = Client()
        self.client.force_login(self.admin)

    def _pending(self):
        attempt = ChungTuThanhToan.objects.create(
            hoa_don=self.invoice, so_lan=1, nguoi_tai_len=self.user,
            # A pre-existing immutable evidence reference; reconciliation must
            # only review it and must never write/delete the file itself.
            anh="payment_evidence/admin-atomicity.png", mime_type="image/png",
            ma_doi_chieu=f"NDTMOTEL HD{self.invoice.pk}",
        )
        self.invoice.trang_thai = "cho_xac_nhan"
        self.invoice.phuong_thuc = "chuyen_khoan"
        self.invoice.save(update_fields=["trang_thai", "phuong_thuc"])
        return attempt

    def _effects(self):
        return {
            "history": LichSuThanhToan.objects.filter(hoa_don_id=self.invoice.pk).count(),
            "audit": NhatKyThaoTac.objects.filter(
                doi_tuong="HoaDon", doi_tuong_id=self.invoice.pk
            ).count(),
            "confirm_notice": ThongBao.objects.filter(
                nguoi_thue_id=self.invoice.hop_dong.dat_phong.nguoi_thue_id,
                loai="thanh_toan", tieu_de="Thanh toán hóa đơn thành công",
            ).count(),
            "reject_notice": ThongBao.objects.filter(
                nguoi_thue_id=self.invoice.hop_dong.dat_phong.nguoi_thue_id,
                ma_tham_chieu__startswith=f"INVOICE:{self.invoice.pk}:PAYMENT_REJECTED:",
            ).count(),
        }

    def _fresh(self, attempt):
        # Force the assertions to read through a newly opened DB connection.
        connections["default"].close()
        invoice = type(self.invoice).objects.get(pk=self.invoice.pk)
        attempt = type(attempt).objects.get(pk=attempt.pk)
        return invoice, attempt

    def _assert_pending_unchanged(self, attempt, before, *, reason=""):
        invoice, attempt = self._fresh(attempt)
        self.assertEqual((invoice.trang_thai, invoice.phuong_thuc), ("cho_xac_nhan", "chuyen_khoan"))
        self.assertEqual(attempt.trang_thai, "cho_doi_soat")
        self.assertIsNone(attempt.nguoi_xu_ly_id)
        self.assertIsNone(attempt.thoi_diem_xu_ly)
        self.assertEqual(attempt.ghi_chu_doi_soat, "")
        self.assertEqual(self._effects(), before)
        self.assertEqual(attempt.anh.name, "payment_evidence/admin-atomicity.png")
        if reason:
            self.assertNotEqual(attempt.ghi_chu_doi_soat, reason)

    def _post(self, action, attempt, **extra):
        data = {"hanh_dong": action, "attempt_id": str(attempt.pk), **extra}
        return self.client.post(reverse("xu_ly_hoa_don", args=[self.invoice.pk]), data)

    def test_confirm_failure_after_domain_mutation_rolls_back_everything(self):
        attempt, before = self._pending(), self._effects()
        from core.dich_vu import chung_tu_thanh_toan

        original = chung_tu_thanh_toan.mark_reviewed
        def fail_after_attempt_mutation(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("forced confirm failure after domain mutation")

        with patch.object(chung_tu_thanh_toan, "mark_reviewed", side_effect=fail_after_attempt_mutation):
            with self.assertRaisesRegex(RuntimeError, "after domain mutation"):
                self._post("xac_nhan_thanh_toan", attempt, phuong_thuc="chuyen_khoan")
        self._assert_pending_unchanged(attempt, before)

    def test_confirm_failure_between_history_and_remaining_side_effects_rolls_back(self):
        attempt, before = self._pending(), self._effects()
        original = ThongBao.objects.create
        def create_notice_then_fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("forced confirm failure after history and notice")

        with patch.object(ThongBao.objects, "create", side_effect=create_notice_then_fail):
            with self.assertRaisesRegex(RuntimeError, "after history and notice"):
                self._post("xac_nhan_thanh_toan", attempt, phuong_thuc="chuyen_khoan")
        self._assert_pending_unchanged(attempt, before)

    def test_reject_failure_after_domain_mutation_rolls_back_and_keeps_retry_closed(self):
        attempt, before = self._pending(), self._effects()
        from core.dich_vu import chung_tu_thanh_toan

        original = chung_tu_thanh_toan.mark_reviewed
        def fail_after_attempt_rejection(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("forced reject failure after domain mutation")

        with patch.object(chung_tu_thanh_toan, "mark_reviewed", side_effect=fail_after_attempt_rejection):
            with self.assertRaisesRegex(RuntimeError, "after domain mutation"):
                self._post("tu_choi_thanh_toan", attempt, ly_do_tu_choi="reject reason")
        self._assert_pending_unchanged(attempt, before, reason="reject reason")

    def test_reject_failure_after_notice_create_rolls_back_everything(self):
        attempt, before = self._pending(), self._effects()
        original = ThongBao.objects.get_or_create
        def create_rejection_notice_then_fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("forced reject failure after notice")

        with patch.object(ThongBao.objects, "get_or_create", side_effect=create_rejection_notice_then_fail):
            with self.assertRaisesRegex(RuntimeError, "after notice"):
                self._post("tu_choi_thanh_toan", attempt, ly_do_tu_choi="reject reason")
        self._assert_pending_unchanged(attempt, before, reason="reject reason")

    def test_exception_after_committed_outcome_never_compensates_or_duplicates(self):
        attempt, before = self._pending(), self._effects()
        response = self._post("xac_nhan_thanh_toan", attempt, phuong_thuc="chuyen_khoan")
        self.assertEqual(response.status_code, 302)
        committed = self._effects()

        # Deliberately outside the reconciliation atomic block: no rollback or
        # compensating cleanup is allowed to own this completed transaction.
        with self.assertRaisesRegex(RuntimeError, "outer"):
            raise RuntimeError("forced outer exception after commit")

        invoice, attempt = self._fresh(attempt)
        self.assertEqual((invoice.trang_thai, attempt.trang_thai), ("da_thanh_toan", "da_chap_nhan"))
        self.assertEqual(committed["history"] - before["history"], 1)
        self.assertEqual(committed["confirm_notice"] - before["confirm_notice"], 1)
        self.assertGreaterEqual(committed["audit"] - before["audit"], 1)
        self.assertEqual(attempt.anh.name, "payment_evidence/admin-atomicity.png")

        retry = self._post("xac_nhan_thanh_toan", attempt, phuong_thuc="chuyen_khoan")
        self.assertEqual(retry.status_code, 302)
        self.assertEqual(self._effects(), committed)
