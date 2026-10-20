from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.dich_vu.ngay_thue import tinh_ngay_ket_thuc_theo_thang
from core.models import CoSo, DatPhong, HopDong, NguoiThue, NhatKyThaoTac, Phong, ThanhToanCocDatPhong


class LeaseSelectionQuoteTests(TestCase):
    def setUp(self):
        self.facility = CoSo.objects.create(ten_co_so='Lease facility', dia_chi='Test', quan='Hai Chau')
        self.room = Phong.objects.create(
            co_so=self.facility, so_phong='LEASE-01', loai_phong='phong_tieu_chuan',
            gia_thue=Decimal('2500000'), tien_coc_mac_dinh=Decimal('700000'), dien_tich=Decimal('24'),
        )
        self.user = User.objects.create_user('lease-user', password='Safe-pass-123')
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.user, ho_ten='Lease tenant', cccd='012345678901', so_dien_thoai='0900123456',
        )
        self.url = reverse('dat_phong', args=[self.room.pk])
        self.client.force_login(self.user)

    def preview(self, **data):
        values = {
            'action': 'preview_quote',
            'ngay_nhan_phong': (timezone.localdate() + timedelta(days=2)).isoformat(),
            'so_thang_thue': '3',
        }
        values.update(data)
        return self.client.post(self.url, values)

    def business_counts(self):
        return (DatPhong.objects.count(), ThanhToanCocDatPhong.objects.count(), HopDong.objects.count(), NhatKyThaoTac.objects.count())

    def test_valid_preview_uses_server_room_values_and_calculates_dates(self):
        start = timezone.localdate() + timedelta(days=2)
        before = self.business_counts()
        response = self.preview(
            ngay_nhan_phong=start.isoformat(), so_thang_thue='3',
            gia_thue='1', tien_coc='1', total='1', ngay_tra_du_kien='2000-01-01',
        )
        self.assertEqual(response.status_code, 200)
        quote = response.context['quote']
        self.assertEqual(quote['checkin'], start)
        self.assertEqual(quote['checkout'], tinh_ngay_ket_thuc_theo_thang(start, 3))
        self.assertEqual(quote['monthly_rent'], self.room.gia_thue)
        self.assertEqual(quote['deposit'], self.room.tien_coc_mac_dinh)
        self.assertEqual(quote['estimated_rent'], Decimal('7500000'))
        self.assertEqual(quote['estimated_term_total'], Decimal('8200000'))
        self.assertEqual(self.business_counts(), before)

    def test_invalid_or_past_terms_are_rejected_without_mutation(self):
        before = self.business_counts()
        for values in (
            {'ngay_nhan_phong': 'not-a-date'},
            {'ngay_nhan_phong': (timezone.localdate() - timedelta(days=1)).isoformat()},
            {'so_thang_thue': '0'},
            {'so_thang_thue': '37'},
        ):
            with self.subTest(values=values):
                response = self.preview(**values)
                self.assertIsNone(response.context['quote'])
                self.assertContains(response, 'Không thể xem dự tính')
                self.assertEqual(self.business_counts(), before)

    def test_stale_room_is_blocked_and_preview_never_creates_a_hold(self):
        self.room.trang_thai = 'bao_tri'
        self.room.save(update_fields=['trang_thai'])
        before = self.business_counts()
        response = self.preview(follow=True)
        self.assertRedirects(response, reverse('chi_tiet_phong', args=[self.room.pk]))
        self.assertIn('Phòng hiện không thể thuê', ' '.join(map(str, get_messages(response.wsgi_request))))
        self.assertEqual(self.business_counts(), before)

    def test_repeated_preview_keeps_the_confirmed_room_and_is_read_only(self):
        before = self.business_counts()
        first = self.preview(so_thang_thue='1')
        second = self.preview(so_thang_thue='6')
        self.assertEqual(first.context['phong'].pk, self.room.pk)
        self.assertEqual(second.context['phong'].pk, self.room.pk)
        self.assertEqual(second.context['quote']['months'], 6)
        self.room.refresh_from_db()
        self.assertEqual(self.room.trang_thai, 'trong')
        self.assertEqual(self.business_counts(), before)
