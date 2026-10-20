"""Focused regression coverage for closing an unaccepted contract."""
import threading

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from core.dich_vu.dat_phong import create_booking, room_has_hold
from core.dich_vu.hop_dong import (
    close_pre_activation_contract,
    create_draft_contract,
    respond_to_contract_review,
    send_contract_for_tenant_confirmation,
)
from core.dich_vu.kich_hoat_hop_dong import activate_accepted_contract
from core.dich_vu.tien_coc import confirm_deposit, get_or_create_deposit, report_paid
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import ChungTuThanhToan, HopDong, NhatKyThaoTac, ThongBao


class PreActivationContractCloseTests(Phase5BookingFixture):
    def confirmed_contract(self, state="nhap"):
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction=f"CLOSE-{state}")
        ChungTuThanhToan.objects.create(
            giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh="payment_evidence/close-test.png", mime_type="image/png",
            ma_doi_chieu=payment.ma_tham_chieu,
        )
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        if state != "nhap":
            version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=contract.pk)
            if state == "yeu_cau_chinh_sua":
                respond_to_contract_review(
                    actor=self.user, contract_id=contract.pk, version_id=version.pk,
                    version_hash=version.ma_bam_sha256, action="yeu_cau_chinh_sua", reason="Can sua",
                )
            contract.refresh_from_db()
        return booking, payment, contract

    def assert_closed(self, booking, payment, contract):
        booking.refresh_from_db(); payment.refresh_from_db(); contract.refresh_from_db(); self.room.refresh_from_db()
        self.assertEqual((contract.trang_thai, booking.trang_thai), ("da_huy", "da_huy"))
        self.assertEqual(payment.trang_thai, "da_xac_nhan")
        self.assertIsNotNone(ChungTuThanhToan.objects.get(giao_dich_coc=payment))
        self.assertFalse(room_has_hold(self.room))
        self.assertEqual(self.room.trang_thai, "trong")

    def test_draft_closure_releases_hold_and_preserves_confirmed_financial_history(self):
        booking, payment, contract = self.confirmed_contract()
        _, created = close_pre_activation_contract(actor=self.admin, contract_id=contract.pk, reason="Khong tiep tuc")
        self.assertTrue(created)
        self.assert_closed(booking, payment, contract)
        self.assertTrue(NhatKyThaoTac.objects.filter(doi_tuong_id=contract.pk, hanh_dong="huy").exists())
        self.assertTrue(ThongBao.objects.filter(ma_tham_chieu=f"CONTRACT:{contract.pk}:PRE_ACTIVATION_CLOSED").exists())
        replacement = create_booking(
            actor=self.other_user, room_id=self.room.pk, checkin=self.today, months=3, accept_terms=True,
        )
        self.assertEqual(replacement.trang_thai, "cho_duyet")

    def test_review_pending_and_change_requested_contracts_close_consistently(self):
        for state in ("cho_nguoi_thue_xac_nhan", "yeu_cau_chinh_sua"):
            with self.subTest(state=state):
                booking, payment, contract = self.confirmed_contract(state)
                close_pre_activation_contract(actor=self.admin, contract_id=contract.pk, reason="Admin close")
                self.assert_closed(booking, payment, contract)

    def test_repeat_is_idempotent_but_legacy_inconsistency_is_not_repaired(self):
        booking, payment, contract = self.confirmed_contract()
        close_pre_activation_contract(actor=self.admin, contract_id=contract.pk)
        effects = (NhatKyThaoTac.objects.count(), ThongBao.objects.count())
        _, created = close_pre_activation_contract(actor=self.admin, contract_id=contract.pk)
        self.assertFalse(created)
        self.assertEqual((NhatKyThaoTac.objects.count(), ThongBao.objects.count()), effects)
        booking.trang_thai = "cho_duyet"; booking.save(update_fields=["trang_thai"])
        with self.assertRaises(ValidationError):
            close_pre_activation_contract(actor=self.admin, contract_id=contract.pk)
        payment.refresh_from_db(); self.assertEqual(payment.trang_thai, "da_xac_nhan")

    def test_accepted_contract_and_non_admin_are_rejected(self):
        booking, _payment, contract = self.confirmed_contract("cho_nguoi_thue_xac_nhan")
        version = contract.phien_ban_hien_tai
        self.user.set_password("current-password"); self.user.save(update_fields=["password"])
        respond_to_contract_review(
            actor=self.user, contract_id=contract.pk, version_id=version.pk,
            version_hash=version.ma_bam_sha256, action="chap_thuan", password="current-password",
        )
        with self.assertRaises(ValidationError):
            close_pre_activation_contract(actor=self.admin, contract_id=contract.pk)
        contract.trang_thai = "dang_hieu_luc"; contract.save(update_fields=["trang_thai"])
        with self.assertRaises(ValidationError):
            close_pre_activation_contract(actor=self.admin, contract_id=contract.pk)
        with self.assertRaises(PermissionDenied):
            close_pre_activation_contract(actor=self.user, contract_id=contract.pk)
        booking.refresh_from_db(); contract.refresh_from_db()
        self.assertEqual((booking.trang_thai, contract.trang_thai), ("cho_duyet", "dang_hieu_luc"))


@skipUnlessDBFeature("has_select_for_update")
class PreActivationCloseActivationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        BusinessFixture.setUpTestData.__func__(type(self))
        booking = create_booking(actor=self.user, room_id=self.room.pk, checkin=self.today, months=3, accept_terms=True)
        payment = get_or_create_deposit(actor=self.user, booking_id=booking.pk)
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="CLOSE-RACE")
        ChungTuThanhToan.objects.create(giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh="payment_evidence/close-race.png", mime_type="image/png", ma_doi_chieu=payment.ma_tham_chieu)
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        self.contract, _ = create_draft_contract(actor=self.admin, booking_id=booking.pk)
        version, _ = send_contract_for_tenant_confirmation(actor=self.admin, contract_id=self.contract.pk)
        self.user.set_password("current-password"); self.user.save(update_fields=["password"])
        respond_to_contract_review(actor=self.user, contract_id=self.contract.pk, version_id=version.pk,
            version_hash=version.ma_bam_sha256, action="chap_thuan", password="current-password")

    def test_accepted_contract_cannot_race_into_pre_activation_closure(self):
        barrier, outcomes, outcome_lock = threading.Barrier(2, timeout=10), [], threading.Lock()

        def worker(action):
            close_old_connections()
            try:
                barrier.wait()
                action(type(self.admin).objects.get(pk=self.admin.pk))
                outcome = "ok"
            except ValidationError:
                outcome = "blocked"
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [
            threading.Thread(target=worker, args=(lambda actor: close_pre_activation_contract(actor=actor, contract_id=self.contract.pk),)),
            threading.Thread(target=worker, args=(lambda actor: activate_accepted_contract(actor=actor, contract_id=self.contract.pk),)),
        ]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes), ["blocked", "ok"])
        self.contract.refresh_from_db()
        self.assertIn(self.contract.trang_thai, ("dang_hieu_luc", "sap_het_han"))
