from datetime import timedelta
from urllib.parse import urlparse, parse_qs
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import DatPhong, ThanhToanCocDatPhong, ThongBao, NhatKyThaoTac, HopDong
from core.dich_vu.tien_coc import report_paid, confirm_deposit, reject_deposit


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
        for name, data in [('thanh_toan_coc_cua_toi', {'action': 'report'}), ('huy_dat_phong_cua_toi', {'ly_do_huy': 'Attack'})]:
            for method in ('get', 'post'):
                with self.subTest(route=name, method=method):
                    self.assertEqual(getattr(self.client, method)(reverse(name, args=[booking.pk]), data).status_code, 404)
        self.assertEqual(list(ThanhToanCocDatPhong.objects.values()), before)

    def test_report_pending_not_confirmed_and_notification_deduplicated(self):
        booking, payment = self.new_booking()
        superuser = User.objects.create_user('notify-super', is_superuser=True, is_staff=False)
        User.objects.create_user('inactive-staff', is_staff=True, is_active=False)
        url = self.payment_url(booking)
        self.client.post(url, {'action': 'report', 'amount': 1, 'payment_id': 99999})
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
        confirm_deposit(actor=self.admin, payment_id=payment.pk)
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
