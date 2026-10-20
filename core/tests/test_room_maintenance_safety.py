"""Focused regressions for the atomic maintenance room-state transition."""
import threading

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from core.dich_vu.dat_phong import create_booking
from core.dich_vu.hop_dong import (
    create_draft_contract,
    respond_to_contract_review,
    send_contract_for_tenant_confirmation,
)
from core.dich_vu.kich_hoat_hop_dong import activate_accepted_contract
from core.dich_vu.tien_coc import confirm_deposit, get_or_create_deposit, report_paid
from core.dich_vu.trang_thai_phong import transition_room_maintenance
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import ChungTuThanhToan, HopDong, LichSuHopDong, NhatKyThaoTac, ThongBao


class RoomMaintenanceSafetyTests(Phase5BookingFixture):
    def _confirmed_booking(self):
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="MAINTENANCE")
        ChungTuThanhToan.objects.create(
            giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh="payment_evidence/maintenance.png", mime_type="image/png",
            ma_doi_chieu=payment.ma_tham_chieu,
        )
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        booking.refresh_from_db()
        payment.refresh_from_db()
        return booking, payment

    def _assert_rejected(self):
        with self.assertRaises(ValidationError):
            transition_room_maintenance(actor=self.admin, room_id=self.room.pk, entering=True)
        self.room.refresh_from_db()
        self.assertNotEqual(self.room.trang_thai, "bao_tri")

    def test_empty_room_enters_and_leaves_maintenance(self):
        transition_room_maintenance(actor=self.admin, room_id=self.room.pk, entering=True)
        self.room.refresh_from_db(); self.assertEqual(self.room.trang_thai, "bao_tri")
        transition_room_maintenance(actor=self.admin, room_id=self.room.pk, entering=False)
        self.room.refresh_from_db(); self.assertEqual(self.room.trang_thai, "trong")

    def test_maintenance_room_still_rejects_new_booking(self):
        transition_room_maintenance(actor=self.admin, room_id=self.room.pk, entering=True)
        with self.assertRaises(ValidationError):
            create_booking(actor=self.user, room_id=self.room.pk, checkin=self.today,
                           months=3, accept_terms=True)

    def test_booking_and_pending_evidence_holds_reject_maintenance(self):
        booking, payment = self.new_booking()
        self._assert_rejected()
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="MAINT-PENDING")
        self._assert_rejected()
        booking.refresh_from_db(); payment.refresh_from_db()
        self.assertEqual((booking.trang_thai, payment.trang_thai), ("cho_duyet", "cho_xac_nhan"))

    def test_confirmed_deposit_rejection_preserves_financial_history(self):
        booking, payment = self._confirmed_booking()
        before = (booking.trang_thai, payment.trang_thai, payment.so_tien_thuc_nhan,
                  ChungTuThanhToan.objects.filter(giao_dich_coc=payment).count(),
                  NhatKyThaoTac.objects.count(), ThongBao.objects.count())
        self._assert_rejected()
        booking.refresh_from_db(); payment.refresh_from_db()
        after = (booking.trang_thai, payment.trang_thai, payment.so_tien_thuc_nhan,
                 ChungTuThanhToan.objects.filter(giao_dich_coc=payment).count(),
                 NhatKyThaoTac.objects.count(), ThongBao.objects.count())
        self.assertEqual(after, before)

    def test_pre_activation_contract_states_reject_maintenance(self):
        booking, payment = self._confirmed_booking()
        contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        self._assert_rejected()
        version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=contract.pk)
        self._assert_rejected()
        self.user.set_password("maintenance-password")
        self.user.save(update_fields=["password"])
        respond_to_contract_review(actor=self.user, contract_id=contract.pk, version_id=version.pk,
            version_hash=version.ma_bam_sha256, action="chap_thuan", password="maintenance-password")
        booking.refresh_from_db(); payment.refresh_from_db(); contract.refresh_from_db()
        before = (
            booking.trang_thai, payment.trang_thai, contract.trang_thai,
            LichSuHopDong.objects.filter(hop_dong=contract).count(),
            NhatKyThaoTac.objects.count(), ThongBao.objects.count(),
        )
        self._assert_rejected()
        booking.refresh_from_db(); payment.refresh_from_db(); contract.refresh_from_db()
        after = (
            booking.trang_thai, payment.trang_thai, contract.trang_thai,
            LichSuHopDong.objects.filter(hop_dong=contract).count(),
            NhatKyThaoTac.objects.count(), ThongBao.objects.count(),
        )
        self.assertEqual(after, before)

    def test_active_contract_rejects_maintenance(self):
        self.contract()
        self._assert_rejected()

    def test_non_admin_cannot_call_service(self):
        with self.assertRaises(PermissionDenied):
            transition_room_maintenance(actor=self.user, room_id=self.room.pk, entering=True)


@skipUnlessDBFeature("has_select_for_update")
class RoomMaintenanceConcurrencyTests(TransactionTestCase):
    def setUp(self):
        BusinessFixture.setUpTestData.__func__(type(self))

    def _race(self, maintenance_action, other_action):
        barrier, outcomes, outcome_lock = threading.Barrier(2, timeout=10), [], threading.Lock()

        def worker(label, action):
            close_old_connections()
            try:
                barrier.wait()
                action()
                outcome = (label, "ok")
            except ValidationError:
                outcome = (label, "blocked")
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=worker, args=("maintenance", maintenance_action)),
                   threading.Thread(target=worker, args=("other", other_action))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive(), "maintenance race timed out")
        connections.close_all()
        return outcomes

    def test_booking_and_maintenance_cannot_both_succeed(self):
        outcomes = self._race(
            lambda: transition_room_maintenance(
                actor=type(self.admin).objects.get(pk=self.admin.pk), room_id=self.room.pk, entering=True),
            lambda: create_booking(
                actor=type(self.user).objects.get(pk=self.user.pk), room_id=self.room.pk,
                checkin=self.today, months=3, accept_terms=True),
        )
        self.room.refresh_from_db()
        has_hold = self.room.dat_phong.filter(trang_thai="cho_duyet").exists()
        self.assertFalse(has_hold and self.room.trang_thai == "bao_tri", outcomes)

    def test_activation_and_maintenance_cannot_leave_active_contract_in_maintenance(self):
        booking = create_booking(actor=self.user, room_id=self.room.pk, checkin=self.today, months=3,
                                 accept_terms=True)
        payment = get_or_create_deposit(actor=self.user, booking_id=booking.pk)
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="MAINT-ACTIVATION")
        ChungTuThanhToan.objects.create(giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh="payment_evidence/maintenance-activation.png", mime_type="image/png",
            ma_doi_chieu=payment.ma_tham_chieu)
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=contract.pk)
        self.user.set_password("maintenance-activation-password")
        self.user.save(update_fields=["password"])
        respond_to_contract_review(actor=self.user, contract_id=contract.pk, version_id=version.pk,
            version_hash=version.ma_bam_sha256, action="chap_thuan", password="maintenance-activation-password")
        outcomes = self._race(
            lambda: transition_room_maintenance(
                actor=type(self.admin).objects.get(pk=self.admin.pk), room_id=self.room.pk, entering=True),
            lambda: activate_accepted_contract(
                actor=type(self.admin).objects.get(pk=self.admin.pk), contract_id=contract.pk),
        )
        contract.refresh_from_db(); self.room.refresh_from_db()
        active = contract.trang_thai in ("dang_hieu_luc", "sap_het_han")
        self.assertFalse(active and self.room.trang_thai == "bao_tri", outcomes)
