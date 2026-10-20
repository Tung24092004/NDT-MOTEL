"""Contract bridge: only a reconciled deposit may enter the draft lifecycle."""
import threading

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from core.dich_vu.hop_dong import create_draft_contract
from core.dich_vu.tien_coc import confirm_deposit, reject_deposit, report_paid
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import ChungTuThanhToan, HopDong, ThanhToanCocDatPhong


class ContractBridgeTests(Phase5BookingFixture):
    def confirmed_booking(self):
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction='BRIDGE-TEST')
        ChungTuThanhToan.objects.create(giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh='payment_evidence/bridge-test.png', mime_type='image/png', ma_doi_chieu=payment.ma_tham_chieu)
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        return booking, payment

    def test_confirmed_deposit_creates_one_snapshot_authoritative_draft(self):
        booking, payment = self.confirmed_booking()
        self.room.gia_thue = 9999999
        self.room.tien_coc_mac_dinh = 8888888
        self.room.save()
        contract, created = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        again, created_again = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        payment.refresh_from_db()
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(contract.pk, again.pk)
        self.assertEqual(contract.tien_thue_thang, booking.gia_thue_thang_tai_thoi_diem_dat)
        self.assertEqual(contract.tien_coc, booking.tien_coc_du_kien)
        self.assertEqual(contract.tien_coc_thuc_nhan, payment.so_tien_thuc_nhan)
        self.assertEqual(contract.ngay_bat_dau, booking.ngay_nhan_phong)
        self.assertEqual(contract.ngay_ket_thuc, booking.ngay_tra_du_kien)
        self.assertEqual(contract.trang_thai, 'nhap')
        booking.refresh_from_db()
        self.assertEqual(booking.trang_thai, 'cho_duyet')
        self.assertEqual(HopDong.objects.filter(dat_phong=booking).count(), 1)

    def test_unreconciled_or_rejected_deposit_cannot_enter_bridge(self):
        booking, payment = self.new_booking()
        with self.assertRaises(ValidationError):
            create_draft_contract(actor=self.admin, booking_id=booking.pk)
        report_paid(actor=self.user, payment_id=payment.pk)
        with self.assertRaises(ValidationError):
            create_draft_contract(actor=self.admin, booking_id=booking.pk)
        reject_deposit(actor=self.admin, payment_id=payment.pk, reason='Bridge rejection')
        with self.assertRaises(ValidationError):
            create_draft_contract(actor=self.admin, booking_id=booking.pk)
        self.assertFalse(HopDong.objects.filter(dat_phong=booking).exists())


@skipUnlessDBFeature('has_select_for_update')
class ContractBridgeConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        Phase5BookingFixture.setUpTestData.__func__(type(self))
        booking, payment = Phase5BookingFixture.new_booking(self)
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction='BRIDGE-RACE')
        ChungTuThanhToan.objects.create(giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh='payment_evidence/bridge-race.png', mime_type='image/png', ma_doi_chieu=payment.ma_tham_chieu)
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        self.booking_id, self.payment_id = booking.pk, payment.pk

    def _run_two(self, first, second):
        barrier, outcomes, outcome_lock = threading.Barrier(2, timeout=10), [], threading.Lock()

        def worker(action):
            close_old_connections()
            try:
                barrier.wait()
                outcome = action()
            except ValidationError:
                outcome = 'blocked'
            finally:
                with outcome_lock:
                    outcomes.append(outcome)
                close_old_connections()

        threads = [threading.Thread(target=worker, args=(action,)) for action in (first, second)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        return outcomes

    def test_two_admin_creates_reuse_one_draft(self):
        def create():
            contract, created = create_draft_contract(actor=type(self.admin).objects.get(pk=self.admin.pk), booking_id=self.booking_id)
            return contract.pk, created

        outcomes = self._run_two(create, create)
        self.assertEqual(sorted(created for _, created in outcomes), [False, True])
        self.assertEqual(HopDong.objects.filter(dat_phong_id=self.booking_id).count(), 1)

    def test_create_and_reject_do_not_cross_a_confirmed_deposit_gate(self):
        def create():
            contract, _ = create_draft_contract(actor=type(self.admin).objects.get(pk=self.admin.pk), booking_id=self.booking_id)
            return ('draft', contract.pk)

        def reject():
            reject_deposit(actor=type(self.admin).objects.get(pk=self.admin.pk), payment_id=self.payment_id, reason='Concurrent review')
            return ('rejected', self.payment_id)

        outcomes = self._run_two(create, reject)
        self.assertEqual(len([outcome for outcome in outcomes if outcome != 'blocked']), 1)
        payment = ThanhToanCocDatPhong.objects.get(pk=self.payment_id)
        if HopDong.objects.filter(dat_phong_id=self.booking_id).exists():
            self.assertEqual(payment.trang_thai, 'da_xac_nhan')
        else:
            self.assertEqual(payment.trang_thai, 'tu_choi')
