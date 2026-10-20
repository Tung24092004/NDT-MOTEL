import threading

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import Client
from django.urls import reverse

from core.models import ChungTuThanhToan, HoaDon, LichSuThanhToan, NhatKyThaoTac, ThongBao
from core.tests.test_invoice_payment_attempt_tenant_concurrency import (
    TenantInvoiceAttemptConcurrencyTests,
    receipt,
)


class AdminInvoiceAttemptConcurrencyTests(TenantInvoiceAttemptConcurrencyTests):
    """Admin reconciliation races use real MySQL locks and isolated clients."""

    def setUp(self):
        super().setUp()
        self.admins = [
            User.objects.create_user(f"invoice-race-admin-{index}", is_staff=True)
            for index in (1, 2)
        ]

    def _pending_attempt(self):
        self._concurrent_report(receipt("pending-a.png", "red"), receipt("pending-b.png", "blue"))
        return ChungTuThanhToan.objects.get(hoa_don=self.invoice)

    def _counts(self):
        return {
            "history": LichSuThanhToan.objects.filter(hoa_don=self.invoice).count(),
            "audit": NhatKyThaoTac.objects.filter(doi_tuong="HoaDon", doi_tuong_id=self.invoice.pk).count(),
            "notice": ThongBao.objects.filter(nguoi_thue=self.invoice.hop_dong.dat_phong.nguoi_thue).count(),
        }

    def _race(self, actions, attempt_id=""):
        barrier = threading.Barrier(2, timeout=10)
        outcomes, outcome_lock = [], threading.Lock()

        def worker(action, admin_id, reason):
            close_old_connections()
            try:
                client = Client()
                client.force_login(User.objects.get(pk=admin_id))
                barrier.wait()
                data = {"hanh_dong": action, "phuong_thuc": "chuyen_khoan"}
                if attempt_id:
                    data["attempt_id"] = attempt_id
                if action == "tu_choi_thanh_toan":
                    data["ly_do_tu_choi"] = reason
                response = client.post(reverse("xu_ly_hoa_don", args=[self.invoice.pk]), data)
                outcome = ("response", response.status_code)
            except Exception as exc:
                outcome = ("error", repr(exc))
            finally:
                with outcome_lock:
                    outcomes.append(outcome)
                close_old_connections()

        threads = [
            threading.Thread(target=worker, args=(action, self.admins[index].pk, f"reason-{index}"))
            for index, action in enumerate(actions)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads), "An admin race worker hung.")
        self.assertEqual(sorted(outcomes), [("response", 302), ("response", 302)])

    def test_confirm_vs_reject_has_one_terminal_outcome(self):
        attempt = self._pending_attempt()
        before = self._counts()
        self._race(("xac_nhan_thanh_toan", "tu_choi_thanh_toan"), str(attempt.pk))
        self.invoice.refresh_from_db(); attempt.refresh_from_db()
        delta = {key: self._counts()[key] - before[key] for key in before}
        self.assertIn(attempt.trang_thai, ("da_chap_nhan", "tu_choi"))
        if attempt.trang_thai == "da_chap_nhan":
            self.assertEqual(self.invoice.trang_thai, "da_thanh_toan"); self.assertEqual(delta["history"], 1)
        else:
            self.assertIn(self.invoice.trang_thai, ("chua_thanh_toan", "qua_han")); self.assertEqual(delta["history"], 0)
        self.assertEqual(delta["notice"], 1)

    def test_confirm_vs_confirm_is_exactly_once(self):
        attempt = self._pending_attempt(); before = self._counts()
        self._race(("xac_nhan_thanh_toan", "xac_nhan_thanh_toan"), str(attempt.pk))
        self.invoice.refresh_from_db(); attempt.refresh_from_db()
        self.assertEqual((self.invoice.trang_thai, attempt.trang_thai), ("da_thanh_toan", "da_chap_nhan"))
        self.assertEqual(self._counts()["history"] - before["history"], 1)
        self.assertEqual(self._counts()["notice"] - before["notice"], 1)

    def test_reject_vs_reject_preserves_winner_reason_once(self):
        attempt = self._pending_attempt(); before = self._counts()
        self._race(("tu_choi_thanh_toan", "tu_choi_thanh_toan"), str(attempt.pk))
        self.invoice.refresh_from_db(); attempt.refresh_from_db()
        self.assertEqual(attempt.trang_thai, "tu_choi")
        self.assertIn(attempt.ghi_chu_doi_soat, ("reason-0", "reason-1"))
        self.assertIn(self.invoice.trang_thai, ("chua_thanh_toan", "qua_han"))
        self.assertEqual(self._counts()["history"] - before["history"], 0)
        self.assertEqual(self._counts()["notice"] - before["notice"], 1)

    def test_stale_attempt_id_does_not_fallback_to_current_attempt(self):
        first = self._pending_attempt()
        ChungTuThanhToan.objects.filter(pk=first.pk).update(trang_thai="tu_choi", ghi_chu_doi_soat="old")
        HoaDon.objects.filter(pk=self.invoice.pk).update(trang_thai="chua_thanh_toan", phuong_thuc="")
        self._concurrent_report(receipt("retry-a.png", "green"), receipt("retry-b.png", "yellow"))
        second = ChungTuThanhToan.objects.get(hoa_don=self.invoice, so_lan=2); before = self._counts()
        self._race(("xac_nhan_thanh_toan", "tu_choi_thanh_toan"), str(first.pk))
        self.invoice.refresh_from_db(); first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual((first.trang_thai, second.trang_thai, self.invoice.trang_thai), ("tu_choi", "cho_doi_soat", "cho_xac_nhan"))
        self.assertEqual(self._counts(), before)

    def test_delayed_action_after_paid_is_idempotent(self):
        attempt = self._pending_attempt()
        self._race(("xac_nhan_thanh_toan", "xac_nhan_thanh_toan"), str(attempt.pk))
        before = self._counts()
        self._race(("xac_nhan_thanh_toan", "tu_choi_thanh_toan"), str(attempt.pk))
        self.invoice.refresh_from_db(); attempt.refresh_from_db()
        self.assertEqual((self.invoice.trang_thai, attempt.trang_thai), ("da_thanh_toan", "da_chap_nhan"))
        self.assertEqual(self._counts(), before)

    def test_multiple_pending_attempts_fail_closed_for_admin_actions(self):
        first = ChungTuThanhToan.objects.create(hoa_don=self.invoice, so_lan=1, nguoi_tai_len=self.user, anh=receipt("bad-a.png", "red"), mime_type="image/png", ma_doi_chieu="BAD-A")
        second = ChungTuThanhToan.objects.create(hoa_don=self.invoice, so_lan=2, nguoi_tai_len=self.user, anh=receipt("bad-b.png", "blue"), mime_type="image/png", ma_doi_chieu="BAD-B")
        HoaDon.objects.filter(pk=self.invoice.pk).update(trang_thai="cho_xac_nhan", phuong_thuc="chuyen_khoan")
        before = self._counts(); self._race(("xac_nhan_thanh_toan", "tu_choi_thanh_toan"))
        self.invoice.refresh_from_db(); first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(self.invoice.trang_thai, "cho_xac_nhan")
        self.assertEqual((first.trang_thai, second.trang_thai), ("cho_doi_soat", "cho_doi_soat"))
        self.assertEqual(self._counts(), before)
