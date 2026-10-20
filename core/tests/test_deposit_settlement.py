"""Focused safety coverage for the final booking-deposit settlement record."""
import threading

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from core.dich_vu.hop_dong import close_pre_activation_contract, create_draft_contract
from core.dich_vu.tien_coc import confirm_deposit, report_paid, settle_confirmed_deposit
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import ChungTuThanhToan, QuyetToanCocDatPhong


class DepositSettlementTests(Phase5BookingFixture):
    def confirmed_contract(self, closed=True):
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction='SETTLEMENT-TEST')
        evidence = ChungTuThanhToan.objects.create(
            giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh='payment_evidence/settlement.png', mime_type='image/png',
            ma_doi_chieu=payment.ma_tham_chieu,
        )
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        payment.refresh_from_db()
        contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        if closed:
            close_pre_activation_contract(actor=self.admin, contract_id=contract.pk, reason='Ket thuc thue')
        return booking, payment, contract, evidence

    def settle(self, payment, outcome='hoan_tien', amount=None):
        return settle_confirmed_deposit(
            actor=self.admin, payment_id=payment.pk, outcome=outcome,
            amount=payment.so_tien if amount is None else amount, reason='Da xu ly ben ngoai',
        )

    def test_non_admin_unconfirmed_and_live_lifecycle_are_denied(self):
        unconfirmed_booking, unconfirmed_payment = self.new_booking()
        unconfirmed_booking.trang_thai = 'da_huy'; unconfirmed_booking.save(update_fields=['trang_thai'])
        with self.assertRaises(ValidationError):
            self.settle(unconfirmed_payment)
        booking, payment, _contract, _evidence = self.confirmed_contract(closed=False)
        with self.assertRaises(PermissionDenied):
            settle_confirmed_deposit(actor=self.user, payment_id=payment.pk, outcome='hoan_tien', amount=1, reason='No')
        with self.assertRaises(ValidationError):
            self.settle(payment)

    def test_refund_is_final_and_preserves_receipt_and_evidence(self):
        _booking, payment, _contract, evidence = self.confirmed_contract()
        before = (payment.so_tien, payment.so_tien_thuc_nhan, payment.nguoi_xac_nhan_id, payment.thoi_diem_admin_xac_nhan)
        settlement = self.settle(payment)
        payment.refresh_from_db(); evidence.refresh_from_db()
        self.assertEqual(settlement.ket_qua, 'hoan_tien')
        self.assertEqual(payment.trang_thai, 'da_hoan_tien')
        self.assertEqual((payment.so_tien, payment.so_tien_thuc_nhan, payment.nguoi_xac_nhan_id, payment.thoi_diem_admin_xac_nhan), before)
        self.assertEqual(evidence.giao_dich_coc_id, payment.pk)
        with self.assertRaises(ValidationError):
            self.settle(payment, outcome='giu_lai')

    def test_retained_never_marks_the_receipt_refunded(self):
        _booking, payment, _contract, _evidence = self.confirmed_contract()
        settlement = self.settle(payment, outcome='giu_lai')
        payment.refresh_from_db()
        self.assertEqual(settlement.ket_qua, 'giu_lai')
        self.assertEqual(payment.trang_thai, 'da_xac_nhan')

    def test_settlement_amount_must_be_positive_and_within_received_amount(self):
        _booking, payment, _contract, _evidence = self.confirmed_contract()
        for amount in (0, -1, payment.so_tien + 1):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.settle(payment, amount=amount)
        self.assertFalse(QuyetToanCocDatPhong.objects.filter(giao_dich_coc=payment).exists())


@skipUnlessDBFeature('has_select_for_update')
class DepositSettlementConcurrencyTests(TransactionTestCase):
    def setUp(self):
        BusinessFixture.setUpTestData.__func__(type(self))
        from core.dich_vu.dat_phong import create_booking
        from core.dich_vu.tien_coc import get_or_create_deposit
        booking = create_booking(actor=self.user, room_id=self.room.pk, checkin=self.today, months=3, accept_terms=True)
        payment = get_or_create_deposit(actor=self.user, booking_id=booking.pk)
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction='SETTLEMENT-RACE')
        ChungTuThanhToan.objects.create(giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh='payment_evidence/settlement-race.png', mime_type='image/png', ma_doi_chieu=payment.ma_tham_chieu)
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        close_pre_activation_contract(actor=self.admin, contract_id=contract.pk, reason='Ket thuc')
        self.payment_id = payment.pk

    def test_concurrent_settlement_creates_at_most_one_record(self):
        barrier, outcomes, outcome_lock = threading.Barrier(2, timeout=10), [], threading.Lock()

        def worker(outcome):
            close_old_connections()
            try:
                barrier.wait()
                actor = type(self.admin).objects.get(pk=self.admin.pk)
                settle_confirmed_deposit(actor=actor, payment_id=self.payment_id, outcome=outcome, amount=100, reason='Race')
                result = 'ok'
            except ValidationError:
                result = 'blocked'
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(result)

        threads = [threading.Thread(target=worker, args=(outcome,)) for outcome in ('hoan_tien', 'giu_lai')]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes), ['blocked', 'ok'])
        self.assertEqual(QuyetToanCocDatPhong.objects.filter(giao_dich_coc_id=self.payment_id).count(), 1)
