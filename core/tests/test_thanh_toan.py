from datetime import timedelta
from decimal import Decimal
from io import BytesIO
import threading
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import ChungTuThanhToan, CoSo, DatPhong, ThanhToanCocDatPhong, ThongBao, NhatKyThaoTac, HopDong, NguoiThue, Phong
from core.dich_vu.dat_phong import create_booking
from core.dich_vu.tien_coc import get_or_create_deposit, report_paid, confirm_deposit, reject_deposit
from core.private_storage import private_payment_evidence_storage


def evidence_upload():
    payload = BytesIO()
    Image.new('RGB', (8, 8), 'white').save(payload, format='PNG')
    return SimpleUploadedFile('receipt.png', payload.getvalue(), content_type='image/png')


class DepositPaymentUITests(Phase5BookingFixture):
    def payment_url(self, booking):
        return reverse('thanh_toan_coc_cua_toi', args=[booking.pk])

    def test_qr_get_is_read_only_and_backend_amount_content(self):
        booking, payment = self.new_booking()
        before = list(ThanhToanCocDatPhong.objects.values())
        for _ in range(2):
            response = self.client.get(self.payment_url(booking), {'amount': 1, 'addInfo': 'FORGED'})
            self.assertEqual(response.status_code, 200)
            query = parse_qs(urlparse(response.context['qr']['url']).query)
            self.assertEqual(query['amount'], ['500000'])
            self.assertEqual(query['addInfo'], [payment.noi_dung_chuyen_khoan])
            self.assertIn(booking.ma_yeu_cau, payment.noi_dung_chuyen_khoan)
            self.assertNotContains(response, 'FORGED')
        self.assertEqual(list(ThanhToanCocDatPhong.objects.values()), before)

    def test_foreign_booking_payment_get_post_and_cancel_are_denied(self):
        booking, payment = self.new_booking()
        self.client.force_login(self.other_user)
        before = list(ThanhToanCocDatPhong.objects.values())
        for name, data in [('thanh_toan_coc_cua_toi', {'action': 'start'}), ('thanh_toan_coc_cua_toi', {'action': 'report'}), ('huy_dat_phong_cua_toi', {'ly_do_huy': 'Attack'})]:
            for method in ('get', 'post'):
                with self.subTest(route=name, method=method):
                    self.assertEqual(getattr(self.client, method)(reverse(name, args=[booking.pk]), data).status_code, 404)
        self.assertEqual(list(ThanhToanCocDatPhong.objects.values()), before)

    def test_start_creates_one_authoritative_pending_attempt(self):
        booking = create_booking(actor=self.user, room_id=self.room.pk, checkin=self.today,
            months=3, people=1, companions=[], accept_terms=True)
        url = self.payment_url(booking)
        response = self.client.get(url)
        self.assertContains(response, 'Tạo giao dịch cọc')
        response = self.client.post(url, {'action': 'start', 'amount': '1', 'payment_id': '99999'})
        self.assertRedirects(response, url, fetch_redirect_response=False)
        payment = ThanhToanCocDatPhong.objects.get(dat_phong=booking)
        self.assertEqual(payment.so_tien, booking.tien_coc_du_kien)
        self.assertEqual(payment.trang_thai, 'chua_thanh_toan')
        self.assertEqual(payment.phuong_thuc, 'chuyen_khoan')
        self.assertFalse(HopDong.objects.exists())
        self.client.post(url, {'action': 'start'})
        self.assertEqual(ThanhToanCocDatPhong.objects.filter(dat_phong=booking).count(), 1)

    def test_start_after_deadline_is_blocked_without_attempt(self):
        booking = create_booking(actor=self.user, room_id=self.room.pk, checkin=self.today,
            months=3, people=1, companions=[], accept_terms=True)
        DatPhong.objects.filter(pk=booking.pk).update(han_thanh_toan_coc=timezone.now() - timedelta(seconds=1))
        response = self.client.post(self.payment_url(booking), {'action': 'start'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ThanhToanCocDatPhong.objects.filter(dat_phong=booking).exists())

    def test_report_pending_not_confirmed_and_notification_deduplicated(self):
        booking, payment = self.new_booking()
        superuser = User.objects.create_user('notify-super', is_superuser=True, is_staff=False)
        User.objects.create_user('inactive-staff', is_staff=True, is_active=False)
        url = self.payment_url(booking)
        with patch.object(private_payment_evidence_storage, 'save', side_effect=lambda name, content, max_length=None: name):
            self.client.post(url, {
                'action': 'report', 'amount': 1, 'payment_id': 99999,
                'anh_chung_tu': evidence_upload(),
            })
        payment.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(payment.trang_thai, 'cho_xac_nhan')
        self.assertIsNone(payment.thoi_diem_admin_xac_nhan)
        self.assertEqual(booking.trang_thai, 'cho_duyet')
        self.assertEqual(set(ThongBao.objects.filter(nguoi_nhan_user__isnull=False).values_list('nguoi_nhan_user_id', flat=True)), {self.admin.pk, superuser.pk})
        self.assertFalse(ThongBao.objects.filter(nguoi_nhan_user__isnull=False, nguoi_thue__isnull=False).exists())
        for notice in ThongBao.objects.filter(nguoi_nhan_user__isnull=False):
            self.assertEqual(notice.url_lien_ket, reverse('chi_tiet_dat_phong', args=[booking.pk]))
        counts = (ThongBao.objects.count(), NhatKyThaoTac.objects.count())
        self.client.post(url, {'action': 'report'})
        self.assertEqual((ThongBao.objects.count(), NhatKyThaoTac.objects.count()), counts)

    def test_expired_unpaid_cannot_report_and_has_no_qr(self):
        booking, payment = self.new_booking()
        DatPhong.objects.filter(pk=booking.pk).update(han_thanh_toan_coc=timezone.now()-timedelta(seconds=1))
        response = self.client.post(self.payment_url(booking), {'action': 'report'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['qr'])
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, 'chua_thanh_toan')

    def test_cancelled_booking_or_attempt_cannot_report(self):
        booking, payment = self.new_booking()
        self.client.post(reverse('huy_dat_phong_cua_toi', args=[booking.pk]), {'ly_do_huy': 'Change plan'})
        self.client.post(self.payment_url(booking), {'action': 'report'})
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, 'da_huy')

    def test_rejected_attempt_get_no_writes_retry_is_post_only(self):
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk)
        reject_deposit(actor=self.admin, payment_id=payment.pk, reason='No receipt')
        response = self.client.get(self.payment_url(booking))
        self.assertContains(response, 'Tạo lại giao dịch cọc')
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 1)
        self.client.post(self.payment_url(booking), {'action': 'report'})
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 1)
        self.client.post(self.payment_url(booking), {'action': 'retry'})
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 2)
        current = ThanhToanCocDatPhong.objects.get(active_slot=1)
        self.assertNotEqual(current.ma_tham_chieu, payment.ma_tham_chieu)

    def test_cancel_unpaid_retains_history_and_releases_room(self):
        booking, payment = self.new_booking(2)
        self.client.post(reverse('huy_dat_phong_cua_toi', args=[booking.pk]), {'ly_do_huy': 'Change plan'})
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.trang_thai, 'da_huy')
        self.assertEqual(payment.trang_thai, 'da_huy')
        self.assertIsNone(payment.active_slot)
        self.assertEqual(booking.nguoi_di_cung_khai_bao.get().trang_thai_xac_minh, 'da_huy')
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 1)
        from core.dich_vu.dat_phong import room_has_hold
        self.assertFalse(room_has_hold(self.room))

    def test_cancel_get_cannot_mutate(self):
        booking, payment = self.new_booking()
        self.client.get(reverse('huy_dat_phong_cua_toi', args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.trang_thai, 'cho_duyet')
        self.assertFalse(NhatKyThaoTac.objects.exists())

    def test_pending_and_confirmed_deposit_cancel_only_requests_admin_no_refund(self):
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk)
        url = reverse('huy_dat_phong_cua_toi', args=[booking.pk])
        self.client.post(url, {'ly_do_huy': 'Request refund'})
        counts = (ThongBao.objects.count(), NhatKyThaoTac.objects.count())
        self.client.post(url, {'ly_do_huy': 'Request refund again'})
        self.assertEqual((ThongBao.objects.count(), NhatKyThaoTac.objects.count()), counts)
        ChungTuThanhToan.objects.create(
            giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh='payment_evidence/cancel-test.png', mime_type='image/png',
            ma_doi_chieu=payment.ma_tham_chieu,
        )
        confirm_deposit(actor=self.admin, payment_id=payment.pk, actual_amount=payment.so_tien)
        self.client.post(url, {'ly_do_huy': 'Refund'})
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.trang_thai, 'cho_duyet')
        self.assertEqual(payment.trang_thai, 'da_xac_nhan')
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 1)

    def test_booking_with_contract_cannot_cancel_even_if_pending(self):
        booking, payment = self.new_booking()
        HopDong.objects.create(dat_phong=booking, so_hop_dong='PHASE5', ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today+timedelta(days=90), tien_thue_thang=2500000)
        self.client.post(reverse('huy_dat_phong_cua_toi', args=[booking.pk]), {'ly_do_huy': 'Attack'})
        booking.refresh_from_db()
        self.assertEqual(booking.trang_thai, 'cho_duyet')

    def test_csrf_on_report_and_cancel(self):
        booking, payment = self.new_booking()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for name in ('thanh_toan_coc_cua_toi', 'huy_dat_phong_cua_toi'):
            self.assertEqual(client.post(reverse(name, args=[booking.pk]), {'action': 'report', 'ly_do_huy': 'Attack'}).status_code, 403)

    def test_legacy_detail_and_payment_never_create_fake_deposit(self):
        booking = self.booking(status='cho_duyet')
        response = self.client.get(self.payment_url(booking))
        self.assertIsNone(response.context['qr'])
        self.assertFalse(ThanhToanCocDatPhong.objects.exists())
        self.assertContains(self.client.get(reverse('chi_tiet_dat_phong_cua_toi', args=[booking.pk])), 'Đơn cũ chưa có bằng chứng')


@skipUnlessDBFeature('has_select_for_update')
class DepositPendingConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_two_simultaneous_starts_reuse_one_active_pending_attempt(self):
        facility = CoSo.objects.create(ten_co_so='Deposit race', dia_chi='Test', quan='Hai Chau')
        room = Phong.objects.create(co_so=facility, so_phong='DEPOSIT-RACE', loai_phong='phong_tieu_chuan',
            gia_thue=Decimal('2500000'), tien_coc_mac_dinh=Decimal('700000'), dien_tich=Decimal('24'))
        user = User.objects.create_user('deposit-race')
        NguoiThue.objects.create(tai_khoan=user, ho_ten='Deposit race', cccd='012345678901', so_dien_thoai='0900123456')
        booking = create_booking(actor=user, room_id=room.pk, checkin=timezone.localdate() + timedelta(days=2),
            months=3, people=1, companions=[], accept_terms=True)
        barrier, results, result_lock = threading.Barrier(2, timeout=10), [], threading.Lock()

        def start_pending():
            close_old_connections()
            try:
                barrier.wait()
                payment = get_or_create_deposit(actor=User.objects.get(pk=user.pk), booking_id=booking.pk)
                with result_lock:
                    results.append(payment.pk)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=start_pending) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        payment = ThanhToanCocDatPhong.objects.get(pk=results[0])
        self.assertEqual(payment.so_tien, booking.tien_coc_du_kien)
        self.assertEqual(ThanhToanCocDatPhong.objects.filter(dat_phong=booking, active_slot=1).count(), 1)

    def test_confirm_and_reject_race_has_one_terminal_reconciliation(self):
        facility = CoSo.objects.create(ten_co_so='Deposit reconcile race', dia_chi='Test', quan='Hai Chau')
        room = Phong.objects.create(co_so=facility, so_phong='DREC-RACE', loai_phong='phong_tieu_chuan',
            gia_thue=Decimal('2500000'), tien_coc_mac_dinh=Decimal('700000'), dien_tich=Decimal('24'))
        tenant_user = User.objects.create_user('deposit-reconcile-tenant')
        NguoiThue.objects.create(tai_khoan=tenant_user, ho_ten='Deposit reconcile tenant', cccd='012345678902', so_dien_thoai='0900123457')
        admins = [User.objects.create_user(f'deposit-reconcile-admin-{index}', is_staff=True) for index in (1, 2)]
        booking = create_booking(actor=tenant_user, room_id=room.pk, checkin=timezone.localdate() + timedelta(days=2),
            months=3, people=1, companions=[], accept_terms=True)
        payment = get_or_create_deposit(actor=tenant_user, booking_id=booking.pk)
        report_paid(actor=tenant_user, payment_id=payment.pk, bank_transaction='RACE-RECONCILE')
        ChungTuThanhToan.objects.create(giao_dich_coc=payment, nguoi_tai_len=tenant_user,
            anh='payment_evidence/reconcile-race.png', mime_type='image/png', ma_doi_chieu=payment.ma_tham_chieu)
        audit_count = NhatKyThaoTac.objects.filter(doi_tuong='ThanhToanCocDatPhong', doi_tuong_id=payment.pk).count()
        barrier, outcomes, outcome_lock = threading.Barrier(2, timeout=10), [], threading.Lock()

        def reconcile(kind, admin_id):
            close_old_connections()
            try:
                barrier.wait()
                admin = User.objects.get(pk=admin_id)
                if kind == 'confirm':
                    confirm_deposit(actor=admin, payment_id=payment.pk, actual_amount=payment.so_tien)
                else:
                    reject_deposit(actor=admin, payment_id=payment.pk, reason='Race review')
                outcome = kind
            except ValidationError:
                outcome = 'blocked'
            finally:
                with outcome_lock:
                    outcomes.append(outcome)
                close_old_connections()

        threads = [
            threading.Thread(target=reconcile, args=('confirm', admins[0].pk)),
            threading.Thread(target=reconcile, args=('reject', admins[1].pk)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes), ['blocked', 'confirm'] if 'confirm' in outcomes else ['blocked', 'reject'])
        payment.refresh_from_db()
        evidence = payment.chung_tu
        self.assertIn(payment.trang_thai, ('da_xac_nhan', 'tu_choi'))
        self.assertEqual(evidence.trang_thai, 'da_chap_nhan' if payment.trang_thai == 'da_xac_nhan' else 'tu_choi')
        self.assertEqual(HopDong.objects.count(), 0)
        self.assertEqual(NhatKyThaoTac.objects.filter(doi_tuong='ThanhToanCocDatPhong', doi_tuong_id=payment.pk).count(), audit_count + 1)
