from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from core.dich_vu.dat_phong import create_booking, rental_quote
from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong, ThanhToanCocDatPhong


class BookingConfirmationTests(TestCase):
    def setUp(self):
        facility = CoSo.objects.create(ten_co_so='Booking confirmation', dia_chi='Test', quan='Hai Chau')
        self.room = Phong.objects.create(co_so=facility, so_phong='BOOKING-01', loai_phong='phong_tieu_chuan',
            gia_thue=Decimal('2500000'), tien_coc_mac_dinh=Decimal('700000'), dien_tich=Decimal('24'))
        self.user = User.objects.create_user('booking-confirm', password='Safe-pass-123')
        NguoiThue.objects.create(tai_khoan=self.user, ho_ten='Booking user', cccd='012345678901', so_dien_thoai='0900123456')
        self.checkin = timezone.localdate() + timedelta(days=2)

    def confirm(self, **changes):
        values = dict(actor=self.user, room_id=self.room.pk, checkin=self.checkin, months=3, accept_terms=True)
        values.update(changes)
        return create_booking(**values)

    def test_confirmation_snapshots_locked_authoritative_quote_once(self):
        quote = rental_quote(room=self.room, checkin=self.checkin, months=3)
        booking = self.confirm(reviewed_quote={
            'quote_monthly_rent': str(quote['monthly_rent']), 'quote_deposit': str(quote['deposit']),
            'quote_checkout': quote['checkout'].isoformat(),
        })
        self.assertEqual(booking.gia_thue_thang_tai_thoi_diem_dat, Decimal('2500000'))
        self.assertEqual(booking.tien_coc_du_kien, Decimal('700000'))
        self.assertEqual(booking.ngay_tra_du_kien, quote['checkout'])
        self.assertEqual(booking.trang_thai, 'cho_duyet')
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 0)
        self.assertEqual(HopDong.objects.count(), 0)
        with self.assertRaises(ValidationError):
            self.confirm()
        self.assertEqual(DatPhong.objects.count(), 1)

    def test_stale_or_tampered_review_is_rejected_without_booking(self):
        with self.assertRaises(ValidationError):
            self.confirm(reviewed_quote={
                'quote_monthly_rent': '1', 'quote_deposit': '1', 'quote_checkout': '2000-01-01',
            })
        self.assertEqual(DatPhong.objects.count(), 0)
        self.room.trang_thai = 'bao_tri'
        self.room.save(update_fields=['trang_thai'])
        with self.assertRaises(ValidationError):
            self.confirm()
        self.assertEqual(DatPhong.objects.count(), 0)


@skipUnlessDBFeature('has_select_for_update')
class BookingConfirmationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_two_users_racing_for_one_room_create_at_most_one_active_booking(self):
        import threading

        facility = CoSo.objects.create(ten_co_so='Booking race', dia_chi='Test', quan='Hai Chau')
        room = Phong.objects.create(co_so=facility, so_phong='BOOKING-RACE', loai_phong='phong_tieu_chuan',
            gia_thue=Decimal('2500000'), tien_coc_mac_dinh=Decimal('700000'), dien_tich=Decimal('24'))
        users = []
        for index in (1, 2):
            user = User.objects.create_user(f'booking-race-{index}')
            NguoiThue.objects.create(tai_khoan=user, ho_ten=f'Race {index}', cccd=f'0123456789{index:02d}', so_dien_thoai=f'090012345{index}')
            users.append(user.pk)
        start, results = threading.Barrier(2), []

        def confirm(user_id):
            close_old_connections()
            try:
                start.wait(timeout=5)
                create_booking(actor=User.objects.get(pk=user_id), room_id=room.pk,
                    checkin=timezone.localdate() + timedelta(days=2), months=3, accept_terms=True)
                results.append('created')
            except ValidationError:
                results.append('blocked')
            finally:
                close_old_connections()

        threads = [threading.Thread(target=confirm, args=(user_id,)) for user_id in users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(results), ['blocked', 'created'])
        self.assertEqual(DatPhong.objects.filter(phong=room, trang_thai='cho_duyet').count(), 1)
