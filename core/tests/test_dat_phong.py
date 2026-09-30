"""Business regression tests. ORM mutations run only in Django's test database."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.db import connection, IntegrityError, transaction
from django.test import TestCase, RequestFactory
from django.urls import reverse, resolve, NoReverseMatch
from django.utils import timezone

from core.du_lieu_test import tap_hop_views as views
from core.models import (
    CoSo, Phong, NguoiThue, DatPhong, HopDong, NguoiOCungPhong,
    YeuCauGhepNguoi, HoaDon, LichSuThanhToan, QuyenRaVao, FaceProfile,
    LichSuRaVao, ThongBao, NhatKyThaoTac, LichSuHopDong, ChinhSachHoTro,
)


from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture

class BookingTests(BusinessFixture):
    def payload(self):
        return dict(ho_ten=self.tenant.ho_ten, so_dien_thoai=self.tenant.so_dien_thoai,
            cccd=self.tenant.cccd, ngay_nhan_phong=str(self.today), so_thang_thue='3',
            tien_coc_du_kien='1', so_nguoi_o='1', da_dong_y_dieu_khoan='on',
            **{'companions-TOTAL_FORMS': '0', 'companions-INITIAL_FORMS': '0'})

    def test_guest_requires_login(self):
        response = self.client.post(reverse('dat_phong', args=[self.room.pk]), self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)
        self.assertFalse(DatPhong.objects.exists())

    def test_admin_cannot_book(self):
        self.post(views.dat_phong, self.room, self.payload(), self.admin)
        self.assertFalse(DatPhong.objects.exists())

    def test_zero_capacity_blocked(self):
        self.room.so_nguoi_toi_da=0;self.room.save()
        self.post(views.dat_phong,self.room,self.payload())
        self.assertFalse(DatPhong.objects.exists())

    def test_maintenance_blocked(self):
        self.room.trang_thai='bao_tri';self.room.save()
        self.post(views.dat_phong,self.room,self.payload())
        self.assertFalse(DatPhong.objects.exists())

    def test_valid_booking_server_deposit_and_duplicate(self):
        self.post(views.dat_phong,self.room,self.payload())
        booking=DatPhong.objects.get()
        self.assertEqual(booking.trang_thai,'cho_duyet')
        self.assertEqual(booking.tien_coc_du_kien,Decimal('500000'))
        effects=self.effects()
        self.post(views.dat_phong,self.room,self.payload())
        self.assertEqual(DatPhong.objects.count(),1)
        self.assertEqual(self.effects(),effects)

    def test_approved_or_rented_room_blocked(self):
        self.contract()
        self.post(views.dat_phong,self.room,self.payload(),self.other_user)
        self.assertEqual(DatPhong.objects.count(),1)

    def test_approval_double_submit(self):
        booking=self.booking('cho_duyet')
        self.post(views.xu_ly_dat_phong,booking,{'hanh_dong':'duyet'},self.admin)
        booking.refresh_from_db();self.room.refresh_from_db()
        self.assertEqual(booking.trang_thai,'da_duyet');self.assertIsNotNone(booking.ngay_duyet)
        self.assertEqual(self.room.trang_thai,'da_dat')
        self.assertFalse(HopDong.objects.exists())
        effects=self.effects()
        self.post(views.xu_ly_dat_phong,booking,{'hanh_dong':'duyet'},self.admin)
        self.assertEqual(self.effects(),effects)

    def test_approval_rechecks_zero_capacity(self):
        booking=self.booking('cho_duyet')
        self.room.so_nguoi_toi_da=0;self.room.save()
        self.post(views.xu_ly_dat_phong,booking,{'hanh_dong':'duyet'},self.admin)
        booking.refresh_from_db();self.assertEqual(booking.trang_thai,'cho_duyet')

    def test_reject_and_cancel_idempotent(self):
        for action in ['tu_choi','huy']:
            with self.subTest(action=action):
                booking=self.booking('cho_duyet')
                data={'hanh_dong':action,'ly_do_tu_choi':'Audit','ly_do_huy':'Audit'}
                self.post(views.xu_ly_dat_phong,booking,data,self.admin)
                effects=self.effects();self.post(views.xu_ly_dat_phong,booking,data,self.admin)
                self.assertEqual(self.effects(),effects)

"""Schema checks, legacy compatibility and migration preservation."""
from decimal import Decimal

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from core.models import DatPhong, KhaiBaoNguoiOCungDatPhong, NguoiOCungPhong, ThanhToanCocDatPhong
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


class BookingDepositModelTests(BusinessFixture):
    def pending(self, **changes):
        booking = self.booking(status='cho_duyet')
        for name, value in changes.items():
            setattr(booking, name, value)
        return booking

    def test_legacy_booking_is_readable_without_consent_or_payment(self):
        booking = self.pending()
        self.assertEqual(booking.so_nguoi_o, 1)
        self.assertFalse(booking.da_dong_y_dieu_khoan)
        self.assertIsNone(booking.gia_thue_thang_tai_thoi_diem_dat)
        self.assertEqual(booking.giao_dich_coc.count(), 0)

    def test_booking_validation_rejects_invalid_values(self):
        for changes in [dict(so_nguoi_o=0), dict(so_nguoi_o=4),
                        dict(so_thang_thue=0), dict(so_thang_thue=37),
                        dict(gia_thue_thang_tai_thoi_diem_dat=-1), dict(tien_coc_du_kien=-1),
                        dict(ty_le_hoan_coc_snapshot=-1), dict(ty_le_hoan_coc_snapshot=101),
                        dict(da_dong_y_dieu_khoan=True)]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.pending(**changes).full_clean()

    def test_booking_database_checks_cannot_be_bypassed_by_update(self):
        booking = self.pending()
        for changes in [dict(so_nguoi_o=0), dict(tien_coc_du_kien=-1),
                        dict(gia_thue_thang_tai_thoi_diem_dat=-1),
                        dict(ty_le_hoan_coc_snapshot=101), dict(da_dong_y_dieu_khoan=True)]:
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                DatPhong.objects.filter(pk=booking.pk).update(**changes)

    def test_companion_normalization_duplicate_and_primary_identity(self):
        booking = self.pending(so_nguoi_o=3)
        booking.save()
        person = KhaiBaoNguoiOCungDatPhong.objects.create(dat_phong=booking,
            ho_ten='Companion', cccd='000 000-000.003')
        self.assertEqual(person.cccd, '000000000003')
        for cccd in ['000000000003', self.tenant.cccd, 'invalid']:
            with self.subTest(cccd=cccd), self.assertRaises(ValidationError):
                KhaiBaoNguoiOCungDatPhong.objects.create(dat_phong=booking, ho_ten='Other', cccd=cccd)
        self.assertEqual(NguoiOCungPhong.objects.count(), 0)

    def test_companion_count_respects_selected_people(self):
        booking = self.pending()
        with self.assertRaises(ValidationError):
            KhaiBaoNguoiOCungDatPhong.objects.create(dat_phong=booking, ho_ten='Other', cccd='000000000003')

    def test_companion_identity_unique_is_per_booking_not_global(self):
        for _ in range(2):
            booking = self.pending(so_nguoi_o=2)
            booking.save()
            KhaiBaoNguoiOCungDatPhong.objects.create(dat_phong=booking, ho_ten='Historical', cccd='000000000003')
        self.assertEqual(KhaiBaoNguoiOCungDatPhong.objects.count(), 2)

    def test_deposit_snapshot_validation_and_database_amount_check(self):
        booking = self.pending(tien_coc_du_kien=500000)
        booking.save()
        with self.assertRaises(ValidationError):
            ThanhToanCocDatPhong.objects.create(dat_phong=booking, so_tien=1)
        payment = ThanhToanCocDatPhong.objects.create(dat_phong=booking, so_tien=500000)
        for changes in [dict(so_tien=-1), dict(ma_tham_chieu=''), dict(active_slot=None),
                        dict(trang_thai='cho_xac_nhan'), dict(trang_thai='da_xac_nhan')]:
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                ThanhToanCocDatPhong.objects.filter(pk=payment.pk).update(**changes)

    def test_database_prevents_two_active_attempts_even_with_bulk_create(self):
        booking = self.pending()
        ThanhToanCocDatPhong.objects.create(dat_phong=booking, so_tien=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ThanhToanCocDatPhong.objects.bulk_create([ThanhToanCocDatPhong(
                dat_phong=booking, so_tien=0, noi_dung_chuyen_khoan='SECOND')])

    def test_new_admin_models_are_read_only(self):
        request = self.request(self.admin)
        for model in (KhaiBaoNguoiOCungDatPhong, ThanhToanCocDatPhong):
            instance = admin.site._registry[model]
            self.assertFalse(instance.has_add_permission(request))
            self.assertFalse(instance.has_change_permission(request))
            self.assertFalse(instance.has_delete_permission(request))
            self.assertEqual(set(instance.get_readonly_fields(request)), {field.name for field in model._meta.fields})


class BookingDepositMigrationTests(TransactionTestCase):
    def test_backfill_preserves_all_original_booking_and_room_fields(self):
        self.assertEqual(connection.settings_dict['NAME'], 'test_ndt_motel')
        before = [('core', '0020_quyenravao_contract_provenance')]
        after = [('core', '0021_booking_deposit_foundation')]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(before)
            old_apps = executor.loader.project_state(before).apps
            facility = old_apps.get_model('core', 'CoSo').objects.create(ten_co_so='Backfill')
            room = old_apps.get_model('core', 'Phong').objects.create(co_so=facility,
                so_phong='MIG', gia_thue=2500000, dien_tich=20, tien_coc_mac_dinh=500000)
            tenant = old_apps.get_model('core', 'NguoiThue').objects.create(ho_ten='Legacy', cccd='legacy')
            from django.utils import timezone
            old_bookings = old_apps.get_model('core', 'DatPhong')
            for status, amount in [('cho_duyet', 0), ('da_duyet', 123), ('tu_choi', 500), ('da_huy', 700)]:
                old_bookings.objects.create(phong=room, nguoi_thue=tenant,
                    ngay_nhan_phong=timezone.localdate(), trang_thai=status, tien_coc_du_kien=amount)
            originals = list(old_bookings.objects.order_by('pk').values())
            room_before = old_apps.get_model('core', 'Phong').objects.values().get(pk=room.pk)
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            new_apps = executor.loader.project_state(after).apps
            results = list(new_apps.get_model('core', 'DatPhong').objects.order_by('pk').values())
            self.assertEqual(len(results), len(originals))
            self.assertEqual(len({row['ma_yeu_cau'] for row in results}), len(results))
            for original, result in zip(originals, results):
                self.assertEqual({key: result[key] for key in original}, original)
                self.assertEqual(result['so_nguoi_o'], 1)
                self.assertEqual(result['gia_thue_thang_tai_thoi_diem_dat'], Decimal('2500000'))
                self.assertTrue(result['snapshot_gia_la_backfill'])
                self.assertFalse(result['da_dong_y_dieu_khoan'])
                self.assertIsNone(result['thoi_diem_dong_y_dieu_khoan'])
                self.assertIsNone(result['han_thanh_toan_coc'])
            self.assertEqual(new_apps.get_model('core', 'Phong').objects.values().get(pk=room.pk), room_before)
            for name in ('ThanhToanCocDatPhong', 'KhaiBaoNguoiOCungDatPhong', 'NguoiOCungPhong', 'HopDong'):
                self.assertEqual(new_apps.get_model('core', name).objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(after)

"""Guarded booking/deposit writers; never invoke the real database."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.utils import timezone

from core.models import DatPhong, KhaiBaoNguoiOCungDatPhong, NguoiOCungPhong, ThanhToanCocDatPhong, LichSuThanhToan, NhatKyThaoTac
from core.dich_vu.dat_phong import create_booking, calculate_checkout, room_has_hold
from core.dich_vu.tien_coc import get_or_create_deposit, report_paid, confirm_deposit, reject_deposit, vietqr_data
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


@override_settings(BOOKING_TERMS_TEXT='Test terms: cancellation refund 50%.', BOOKING_REFUND_PERCENT=50,
                   BOOKING_DEPOSIT_BANK_CODE='TEST', BOOKING_DEPOSIT_BANK_ACCOUNT='123', BOOKING_DEPOSIT_ACCOUNT_NAME='TEST ONLY')
class BookingDepositServiceTests(BusinessFixture):
    def create(self, **changes):
        values = dict(actor=self.user, room_id=self.room.pk, checkin=self.today, months=3, accept_terms=True)
        values.update(changes)
        return create_booking(**values)

    def payment(self):
        return get_or_create_deposit(actor=self.user, booking_id=self.create().pk)

    def test_valid_booking_snapshots_and_terms_are_frozen(self):
        booking = self.create(people=2, companions=[dict(ho_ten='Companion', cccd='000000000003')], allow_sharing=True)
        self.assertEqual(booking.gia_thue_thang_tai_thoi_diem_dat, self.room.gia_thue)
        self.assertEqual(booking.tien_coc_du_kien, self.room.tien_coc_mac_dinh)
        self.assertEqual(booking.noi_dung_dieu_khoan_snapshot, 'Test terms: cancellation refund 50%.')
        self.assertEqual(booking.ty_le_hoan_coc_snapshot, Decimal('50'))
        self.assertTrue(booking.da_dong_y_dieu_khoan)
        self.assertTrue(booking.dong_y_nhan_yeu_cau_ghep)
        self.assertIsNotNone(booking.thoi_diem_dong_y_dieu_khoan)
        self.assertGreater(booking.han_thanh_toan_coc, timezone.now())
        self.assertFalse(booking.snapshot_gia_la_backfill)
        self.assertEqual(booking.nguoi_di_cung_khai_bao.count(), 1)
        self.assertEqual(NguoiOCungPhong.objects.count(), 0)
        self.room.gia_thue = 9000000
        self.room.tien_coc_mac_dinh = 8000000
        self.room.save()
        booking.refresh_from_db()
        self.assertEqual(booking.gia_thue_thang_tai_thoi_diem_dat, Decimal('2500000'))
        self.assertEqual(booking.tien_coc_du_kien, Decimal('500000'))

    def test_invalid_people_dates_months_and_terms_leave_no_data(self):
        for changes in [dict(people=0), dict(people=4), dict(people=True), dict(months=0), dict(months=37),
                        dict(checkin=self.today-timedelta(days=1)), dict(accept_terms=False),
                        dict(people=2), dict(companions=[dict(ho_ten='Extra', cccd='000000000003')])]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)
            self.assertEqual(DatPhong.objects.count(), 0)

    def test_invalid_companion_rolls_back_entire_booking(self):
        with self.assertRaises(ValidationError):
            self.create(people=3, companions=[dict(ho_ten='One', cccd='000000000003'), dict(ho_ten='Dup', cccd='000000000003')])
        self.assertEqual(DatPhong.objects.count(), 0)
        self.assertEqual(KhaiBaoNguoiOCungDatPhong.objects.count(), 0)

    def test_client_cannot_inject_verified_companion_state(self):
        with self.assertRaises(ValidationError):
            self.create(people=2, companions=[dict(ho_ten='Forged', cccd='000000000003', trang_thai_xac_minh='da_xac_minh')])

    def test_unique_booking_references_and_existing_hold(self):
        booking = self.create()
        self.assertTrue(room_has_hold(self.room))
        with self.assertRaises(ValidationError):
            self.create()
        booking.trang_thai = 'da_huy'
        booking.save()
        self.assertNotEqual(self.create().ma_yeu_cau, booking.ma_yeu_cau)

    def test_expired_unpaid_hold_is_released_but_reported_payment_is_not(self):
        payment = self.payment()
        DatPhong.objects.filter(pk=payment.dat_phong_id).update(han_thanh_toan_coc=timezone.now()-timedelta(seconds=1))
        self.assertFalse(room_has_hold(self.room))
        with self.assertRaises(ValidationError):
            report_paid(actor=self.user, payment_id=payment.pk)
        DatPhong.objects.filter(pk=payment.dat_phong_id).update(han_thanh_toan_coc=timezone.now()+timedelta(hours=1))
        report_paid(actor=self.user, payment_id=payment.pk)
        DatPhong.objects.filter(pk=payment.dat_phong_id).update(han_thanh_toan_coc=timezone.now()-timedelta(seconds=1))
        self.assertTrue(room_has_hold(self.room))
        self.assertEqual(confirm_deposit(actor=self.admin, payment_id=payment.pk).trang_thai, 'da_xac_nhan')

    def test_checkout_matches_existing_calendar_rule(self):
        from core.dich_vu.ngay_thue import tinh_ngay_ket_thuc_theo_thang
        for start in (date(2026, 1, 31), date(2024, 2, 29), date(2026, 9, 18)):
            for months in (1, 12, 36):
                self.assertEqual(calculate_checkout(start, months), tinh_ngay_ket_thuc_theo_thang(start, months))

    @override_settings(BOOKING_TERMS_TEXT='')
    def test_missing_backend_policy_fails_closed(self):
        with self.assertRaises(ValidationError):
            self.create()

    def test_booking_service_rejects_admin_and_foreign_actor(self):
        with self.assertRaises(PermissionDenied):
            self.create(actor=self.admin)

    def test_deposit_uses_snapshot_and_cannot_accept_client_amount(self):
        booking = self.create()
        self.room.tien_coc_mac_dinh = 999999
        self.room.save()
        with self.assertRaises(TypeError):
            get_or_create_deposit(actor=self.user, booking_id=booking.pk, so_tien=1)
        payment = get_or_create_deposit(actor=self.user, booking_id=booking.pk)
        self.assertEqual(payment.so_tien, Decimal('500000'))
        self.assertEqual(payment.trang_thai, 'chua_thanh_toan')

    def test_deposit_get_or_create_is_idempotent_and_reference_stable(self):
        payment = self.payment()
        again = get_or_create_deposit(actor=self.user, booking_id=payment.dat_phong_id)
        self.assertEqual(payment.pk, again.pk)
        self.assertEqual(payment.noi_dung_chuyen_khoan, again.noi_dung_chuyen_khoan)
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 1)

    def test_user_report_only_enters_pending_and_repeat_is_idempotent(self):
        payment = self.payment()
        pending = report_paid(actor=self.user, payment_id=payment.pk, bank_transaction='TEST-BANK')
        self.assertEqual(pending.trang_thai, 'cho_xac_nhan')
        self.assertIsNone(pending.thoi_diem_admin_xac_nhan)
        self.assertIsNone(pending.nguoi_xac_nhan)
        count = NhatKyThaoTac.objects.count()
        again = report_paid(actor=self.user, payment_id=payment.pk)
        self.assertEqual(again.thoi_diem_user_bao_da_thanh_toan, pending.thoi_diem_user_bao_da_thanh_toan)
        self.assertEqual(NhatKyThaoTac.objects.count(), count)
        self.assertEqual(LichSuThanhToan.objects.count(), 0)

    def test_admin_confirmation_once_and_no_contract_or_resident(self):
        payment = self.payment()
        report_paid(actor=self.user, payment_id=payment.pk)
        confirmed = confirm_deposit(actor=self.admin, payment_id=payment.pk)
        self.assertEqual(confirmed.trang_thai, 'da_xac_nhan')
        self.assertEqual(confirmed.nguoi_xac_nhan, self.admin)
        with self.assertRaises(ValidationError):
            confirm_deposit(actor=self.admin, payment_id=payment.pk)
        self.assertEqual(confirmed.dat_phong.trang_thai, 'cho_duyet')
        self.assertFalse(hasattr(confirmed.dat_phong, 'hop_dong'))
        self.assertEqual(NguoiOCungPhong.objects.count(), 0)

    def test_only_admin_can_confirm_including_superuser_without_staff(self):
        payment = self.payment()
        report_paid(actor=self.user, payment_id=payment.pk)
        for actor in (self.user, self.other_user, AnonymousUser()):
            with self.subTest(actor=str(actor)), self.assertRaises(PermissionDenied):
                confirm_deposit(actor=actor, payment_id=payment.pk)
        superuser = User.objects.create_user('deposit-super', is_superuser=True, is_staff=False)
        self.assertEqual(confirm_deposit(actor=superuser, payment_id=payment.pk).nguoi_xac_nhan, superuser)

    def test_foreign_user_cannot_create_or_report_deposit(self):
        payment = self.payment()
        for actor in (self.other_user, self.admin, AnonymousUser()):
            with self.subTest(actor=str(actor)), self.assertRaises(PermissionDenied):
                get_or_create_deposit(actor=actor, booking_id=payment.dat_phong_id)
            with self.subTest(actor=str(actor)), self.assertRaises(PermissionDenied):
                report_paid(actor=actor, payment_id=payment.pk)
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, 'chua_thanh_toan')

    def test_cancelled_or_rejected_booking_cannot_create_deposit(self):
        booking = self.create()
        for status in ('da_huy', 'tu_choi'):
            DatPhong.objects.filter(pk=booking.pk).update(trang_thai=status)
            with self.subTest(status=status), self.assertRaises(ValidationError):
                get_or_create_deposit(actor=self.user, booking_id=booking.pk)
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 0)

    def test_legacy_booking_cannot_claim_consent_or_payment(self):
        booking = self.booking(status='cho_duyet')
        with self.assertRaises(ValidationError):
            get_or_create_deposit(actor=self.user, booking_id=booking.pk)

    def test_rejected_attempt_keeps_history_and_allows_new_reference(self):
        payment = self.payment()
        report_paid(actor=self.user, payment_id=payment.pk)
        rejected = reject_deposit(actor=self.admin, payment_id=payment.pk, reason='No bank receipt')
        self.assertIsNone(rejected.active_slot)
        retry = get_or_create_deposit(actor=self.user, booking_id=payment.dat_phong_id)
        self.assertNotEqual(retry.ma_tham_chieu, rejected.ma_tham_chieu)
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 2)

    def test_vietqr_payload_uses_backend_snapshot_and_reference(self):
        payment = self.payment()
        payload = vietqr_data(payment)
        self.assertEqual(payload['amount'], 500000)
        self.assertEqual(payload['add_info'], payment.noi_dung_chuyen_khoan)
        self.assertEqual(payload['reference'], payment.ma_tham_chieu)

from unittest.mock import patch
from datetime import timedelta
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse, resolve
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import DatPhong, KhaiBaoNguoiOCungDatPhong, ThanhToanCocDatPhong, NguoiOCungPhong, HopDong, NhatKyThaoTac


class TenantBookingUITests(Phase5BookingFixture):
    def test_guest_redirects_to_login(self):
        self.client.logout()
        self.assertIn(reverse('dang_nhap'), self.submit().url)
        self.assertFalse(DatPhong.objects.exists())

    def test_staff_and_super_without_staff_cannot_use_any_booking_view(self):
        booking, payment = self.new_booking()
        superuser = User.objects.create_user('phase5-super', is_superuser=True, is_staff=False)
        for actor in (self.admin, superuser):
            self.client.force_login(actor)
            for name, args in [('dat_phong', [self.room.pk]), ('dat_phong_cua_toi', []),
                               ('chi_tiet_dat_phong_cua_toi', [booking.pk]), ('thanh_toan_coc_cua_toi', [booking.pk]),
                               ('huy_dat_phong_cua_toi', [booking.pk])]:
                for method in ('get', 'post'):
                    with self.subTest(actor=actor.username, route=name, method=method):
                        self.assertRedirects(getattr(self.client, method)(reverse(name, args=args)), reverse('dashboard_admin'), fetch_redirect_response=False)
        self.assertEqual(payment.trang_thai, 'chua_thanh_toan')

    def test_missing_identity_redirects_to_profile(self):
        self.tenant.cccd = ''
        self.tenant.save()
        self.assertRedirects(self.submit(), reverse('cap_nhat_thong_tin'), fetch_redirect_response=False)

    def test_no_tenant_profile_is_handled_safely(self):
        user = User.objects.create_user('phase5-no-profile')
        self.client.force_login(user)
        self.assertRedirects(self.submit(), reverse('cap_nhat_thong_tin'), fetch_redirect_response=False)

    def test_unavailable_room_and_zero_capacity_are_blocked(self):
        for field, value in [('trang_thai', 'bao_tri'), ('so_nguoi_toi_da', 0)]:
            setattr(self.room, field, value)
            self.room.save()
            self.assertEqual(self.submit().status_code, 302)
            self.assertFalse(DatPhong.objects.exists())
            self.room.trang_thai, self.room.so_nguoi_toi_da = 'trong', 3

    def test_people_bounds_are_validated_without_js(self):
        for people in ('0', '4', '-1', 'invalid'):
            with self.subTest(people=people):
                self.assertEqual(self.submit(so_nguoi_o=people).status_code, 200)
                self.assertFalse(DatPhong.objects.exists())

    def test_companion_count_must_match(self):
        self.assertEqual(self.submit(so_nguoi_o='3').status_code, 200)
        self.assertFalse(DatPhong.objects.exists())

    def test_no_js_can_prepare_companion_rows_without_writing_booking(self):
        response = self.submit(so_nguoi_o='3', action='prepare_occupants')
        self.assertEqual(len(response.context['companions'].forms), 2)
        self.assertFalse(DatPhong.objects.exists())

    def test_wrong_primary_and_duplicate_cccd_are_rejected(self):
        for values in [('bad', '000000000004'), (self.tenant.cccd, '000000000004'), ('000000000003', '000000000003')]:
            data = self.payload(3)
            data['companions-0-cccd'], data['companions-1-cccd'] = values
            with self.subTest(values=values):
                self.client.post(reverse('dat_phong', args=[self.room.pk]), data)
                self.assertFalse(DatPhong.objects.exists())
                self.assertFalse(KhaiBaoNguoiOCungDatPhong.objects.exists())

    def test_unaccepted_terms_are_rejected(self):
        data = self.payload()
        del data['da_dong_y_dieu_khoan']
        self.client.post(reverse('dat_phong', args=[self.room.pk]), data)
        self.assertFalse(DatPhong.objects.exists())

    def test_dates_and_months_are_validated(self):
        for changes in [{'ngay_nhan_phong': 'bad'}, {'ngay_nhan_phong': str(self.today-timedelta(days=1))}, {'so_thang_thue': '0'}, {'so_thang_thue': '37'}]:
            with self.subTest(changes=changes):
                self.submit(**changes)
                self.assertFalse(DatPhong.objects.exists())

    def test_client_prices_identity_room_and_terms_cannot_override_backend(self):
        response = self.submit(nguoi_thue=self.other.pk, phong=99999, ho_ten='IMPERSONATE',
            cccd=self.other.cccd, so_dien_thoai='0900999999', gia_thue='1', tien_coc_du_kien='1',
            noi_dung_dieu_khoan_snapshot='FORGED', ty_le_hoan_coc_snapshot='100')
        booking = DatPhong.objects.get()
        self.assertRedirects(response, reverse('thanh_toan_coc_cua_toi', args=[booking.pk]), fetch_redirect_response=False)
        self.assertEqual(booking.nguoi_thue_id, self.tenant.pk)
        self.assertEqual(booking.phong_id, self.room.pk)
        self.assertEqual(booking.gia_thue_thang_tai_thoi_diem_dat, self.room.gia_thue)
        self.assertEqual(booking.tien_coc_du_kien, self.room.tien_coc_mac_dinh)
        self.assertEqual(booking.ty_le_hoan_coc_snapshot, 80)
        self.assertIn('hoàn 80%', booking.noi_dung_dieu_khoan_snapshot)
        self.tenant.refresh_from_db()
        self.assertNotEqual(self.tenant.ho_ten, 'IMPERSONATE')

    def test_valid_companions_deposit_created_not_residents_contract(self):
        data = self.payload(3)
        data['dong_y_nhan_yeu_cau_ghep'] = 'on'
        self.client.post(reverse('dat_phong', args=[self.room.pk]), data)
        booking = DatPhong.objects.get()
        self.assertEqual(booking.so_nguoi_o, 3)
        self.assertEqual(booking.nguoi_di_cung_khai_bao.count(), 2)
        self.assertEqual(booking.giao_dich_coc.count(), 1)
        self.assertEqual(booking.giao_dich_coc.get().trang_thai, 'chua_thanh_toan')
        self.assertTrue(booking.dong_y_nhan_yeu_cau_ghep)
        self.assertFalse(NguoiOCungPhong.objects.exists())
        self.assertFalse(HopDong.objects.exists())

    def test_deposit_failure_rolls_back_booking_and_companions(self):
        with patch('core.views_dat_phong.tien_coc.get_or_create_deposit', side_effect=IntegrityError('synthetic')):
            self.client.post(reverse('dat_phong', args=[self.room.pk]), self.payload(2))
        for model in (DatPhong, KhaiBaoNguoiOCungDatPhong, ThanhToanCocDatPhong, NhatKyThaoTac):
            self.assertFalse(model.objects.exists())

    def test_double_click_creates_one_booking_and_one_deposit(self):
        self.submit()
        counts = (DatPhong.objects.count(), ThanhToanCocDatPhong.objects.count(), NhatKyThaoTac.objects.count())
        self.submit()
        self.assertEqual((DatPhong.objects.count(), ThanhToanCocDatPhong.objects.count(), NhatKyThaoTac.objects.count()), counts)

    def test_only_own_booking_in_list_and_detail(self):
        booking, payment = self.new_booking()
        other = self.booking(status='cho_duyet', tenant=self.other)
        response = self.client.get(reverse('dat_phong_cua_toi'))
        self.assertContains(response, booking.ma_yeu_cau)
        self.assertNotContains(response, other.ma_yeu_cau)
        self.assertEqual(self.client.get(reverse('chi_tiet_dat_phong_cua_toi', args=[other.pk])).status_code, 404)

    def test_status_filter_and_snapshot_detail(self):
        booking, payment = self.new_booking(2)
        response = self.client.get(reverse('dat_phong_cua_toi'), {'status': 'unpaid'})
        self.assertContains(response, booking.ma_yeu_cau)
        response = self.client.get(reverse('dat_phong_cua_toi'), {'status': 'pending'})
        self.assertNotContains(response, booking.ma_yeu_cau)
        response = self.client.get(reverse('chi_tiet_dat_phong_cua_toi', args=[booking.pk]))
        self.assertContains(response, 'Companion 0')
        self.assertContains(response, '80')

    def test_csrf_required_on_booking_submit(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('dat_phong', args=[self.room.pk]), self.payload()).status_code, 403)

    def test_old_important_urls_and_cancel_alias_still_resolve(self):
        for name in ('dat_phong', 'huy_dat_phong_cua_toi', 'chi_tiet_dat_phong_cua_toi', 'thanh_toan_coc_cua_toi'):
            self.assertIsNotNone(resolve(reverse(name, args=[self.room.pk])))
        self.assertIsNotNone(resolve('/tai-khoan/dat-phong/1/huy/'))

    def test_create_long_error_list_detail_snapshots(self):
        response = self.client.get(reverse('dat_phong', args=[self.room.pk]))
        self.assertEqual(response.status_code, 200)
        data = self.payload(3)
        data['ghi_chu'] = '<script>alert(1)</script>' + ' Nội dung dài' * 80
        data['companions-1-cccd'] = 'bad'
        response = self.client.post(reverse('dat_phong', args=[self.room.pk]), data)
        self.assertContains(response, '&lt;script&gt;')
        booking, payment = self.new_booking(2)
