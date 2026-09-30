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

class InvoiceTests(BusinessFixture):
    def invoice(self):
        return HoaDon.objects.create(hop_dong=self.contract(),thang=9,nam=2026,
            tien_phong=Decimal('2500000'),tien_dien=Decimal('100000'),tien_nuoc=Decimal('50000'),
            tien_dich_vu=Decimal('25000'),phi_khac=Decimal('10000'),han_thanh_toan=self.today)

    def invoice_for_contract(self, hop_dong, month, status='chua_thanh_toan', due_date=None):
        return HoaDon.objects.create(
            hop_dong=hop_dong, thang=month, nam=2026,
            tien_phong=Decimal('2500000'), trang_thai=status,
            han_thanh_toan=due_date or self.today,
        )

    def test_decimal_total_and_unique_period(self):
        invoice=self.invoice();self.assertEqual(invoice.tong_tien,Decimal('2685000'))
        with self.assertRaises(IntegrityError),transaction.atomic():
            HoaDon.objects.create(hop_dong=invoice.hop_dong,thang=9,nam=2026,han_thanh_toan=self.today)

    def test_payment_double_submit(self):
        invoice=self.invoice();invoice.trang_thai='cho_xac_nhan';invoice.save(update_fields=['trang_thai'])
        data={'hanh_dong':'xac_nhan_thanh_toan','phuong_thuc':'chuyen_khoan'}
        self.post(views.xu_ly_hoa_don,invoice,data,self.admin)
        invoice.refresh_from_db();self.assertEqual(invoice.trang_thai,'da_thanh_toan')
        self.assertIsNotNone(invoice.ngay_thanh_toan);self.assertTrue(invoice.ma_giao_dich)
        self.assertEqual(LichSuThanhToan.objects.get().so_tien,invoice.tong_tien)
        effects=self.effects();self.post(views.xu_ly_hoa_don,invoice,data,self.admin)
        self.assertEqual(self.effects(),effects)

    def test_tenant_payment_double_submit(self):
        invoice=self.invoice()
        data={'buoc':'xac_thuc','phuong_thuc':'chuyen_khoan','xac_nhan':'dong_y'}
        self.post(views.thanh_toan_hoa_don_cua_toi,invoice,data)
        invoice.refresh_from_db();self.assertEqual(invoice.trang_thai,'cho_xac_nhan')
        self.assertIsNone(invoice.ngay_thanh_toan)
        self.assertIsNone(invoice.nguoi_xac_nhan)
        self.assertEqual(invoice.ma_giao_dich, '')
        self.assertFalse(LichSuThanhToan.objects.exists())
        self.assertTrue(ThongBao.objects.exists())
        self.assertTrue(NhatKyThaoTac.objects.exists())
        effects=self.effects();self.post(views.thanh_toan_hoa_don_cua_toi,invoice,data)
        self.assertEqual(self.effects(),effects)
        # Only the guarded admin action records settlement.
        self.post(views.xu_ly_hoa_don, invoice,
                  {'hanh_dong': 'xac_nhan_thanh_toan'}, self.user)
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, 'cho_xac_nhan')
        self.assertEqual(self.effects(), effects)
        self.post(views.xu_ly_hoa_don, invoice,
                  {'hanh_dong': 'xac_nhan_thanh_toan'}, self.admin)
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, 'da_thanh_toan')
        self.assertIsNotNone(invoice.ngay_thanh_toan)
        self.assertEqual(invoice.nguoi_xac_nhan, self.admin)
        self.assertTrue(invoice.ma_giao_dich)
        self.assertEqual(LichSuThanhToan.objects.get().so_tien, invoice.tong_tien)
        self.assertGreater(ThongBao.objects.count(), effects[0])
        self.assertGreater(NhatKyThaoTac.objects.count(), effects[1])
        effects = self.effects()
        self.post(views.xu_ly_hoa_don, invoice,
                  {'hanh_dong': 'xac_nhan_thanh_toan'}, self.admin)
        self.assertEqual(self.effects(), effects)

    def test_other_tenant_cannot_pay_invoice(self):
        invoice=self.invoice();effects=self.effects()
        from django.http import Http404
        try:
            self.post(views.thanh_toan_hoa_don_cua_toi,invoice,
                {'buoc':'xac_thuc','phuong_thuc':'chuyen_khoan','xac_nhan':'dong_y'},self.other_user)
        except Http404:
            pass
        invoice.refresh_from_db();self.assertEqual(invoice.trang_thai,'chua_thanh_toan')
        self.assertEqual(self.effects(),effects)

    def test_create_invoice_double_submit(self):
        hd=self.contract()
        data={'hop_dong':str(hd.pk),'thang':'9','nam':'2026','han_thanh_toan':str(self.today),
            'tien_phong':'2500000','tien_dien':'100000','tien_nuoc':'0','tien_dich_vu':'0','phi_khac':'0'}
        views.tao_hoa_don(self.request(self.admin,data))
        self.assertEqual(HoaDon.objects.count(),1)
        effects=self.effects();views.tao_hoa_don(self.request(self.admin,data))
        self.assertEqual(HoaDon.objects.count(),1);self.assertEqual(self.effects(),effects)

    def test_payment_reversal_double_submit(self):
        invoice=self.invoice()
        invoice.trang_thai='cho_xac_nhan';invoice.save(update_fields=['trang_thai'])
        self.post(views.xu_ly_hoa_don,invoice,{'hanh_dong':'xac_nhan_thanh_toan','phuong_thuc':'tien_mat'},self.admin)
        self.post(views.xu_ly_hoa_don,invoice,{'hanh_dong':'huy_thanh_toan'},self.admin)
        invoice.refresh_from_db();self.assertEqual(invoice.trang_thai,'chua_thanh_toan')
        self.assertIsNone(invoice.ngay_thanh_toan);self.assertEqual(invoice.ma_giao_dich,'')
        effects=self.effects();self.post(views.xu_ly_hoa_don,invoice,{'hanh_dong':'huy_thanh_toan'},self.admin)
        self.assertEqual(self.effects(),effects)

    def test_admin_invoice_filter_accepts_pending_confirmation(self):
        pending = self.invoice()
        pending.trang_thai = 'cho_xac_nhan'
        pending.save(update_fields=['trang_thai'])
        paid = HoaDon.objects.create(hop_dong=pending.hop_dong, thang=10, nam=2026,
            trang_thai='da_thanh_toan', han_thanh_toan=self.today)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('quan_ly_hoa_don'), {'trang_thai':'cho_xac_nhan'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['trang_thai'], 'cho_xac_nhan')
        self.assertEqual(list(response.context['hoa_don']), [pending])
        self.assertContains(response, 'Chờ xác nhận')
        self.assertNotContains(response, f'HĐ-{paid.id}')

    def test_legacy_admin_payment_route_is_not_available(self):
        self.assertFalse(hasattr(views, 'thanh_toan_hoa_don'))
        with self.assertRaises(NoReverseMatch):
            reverse('thanh_toan_hoa_don', args=[1])

    def test_overdue_service_updates_only_past_unpaid_invoices(self):
        hd = self.contract()
        past = self.today - timedelta(days=1)
        future = self.today + timedelta(days=1)
        past_unpaid = self.invoice_for_contract(hd, 1, 'chua_thanh_toan', past)
        future_unpaid = self.invoice_for_contract(hd, 2, 'chua_thanh_toan', future)
        pending = self.invoice_for_contract(hd, 3, 'cho_xac_nhan', past)
        paid = self.invoice_for_contract(hd, 4, 'da_thanh_toan', past)
        cancelled = self.invoice_for_contract(hd, 5, 'huy', past)
        already_overdue = self.invoice_for_contract(hd, 6, 'qua_han', past)

        from core.quy_tac_nghiep_vu import dong_bo_hoa_don_qua_han

        self.assertEqual(dong_bo_hoa_don_qua_han(today=self.today), 1)

        past_unpaid.refresh_from_db()
        future_unpaid.refresh_from_db()
        pending.refresh_from_db()
        paid.refresh_from_db()
        cancelled.refresh_from_db()
        already_overdue.refresh_from_db()

        self.assertEqual(past_unpaid.trang_thai, 'qua_han')
        self.assertEqual(future_unpaid.trang_thai, 'chua_thanh_toan')
        self.assertEqual(pending.trang_thai, 'cho_xac_nhan')
        self.assertEqual(paid.trang_thai, 'da_thanh_toan')
        self.assertEqual(cancelled.trang_thai, 'huy')
        self.assertEqual(already_overdue.trang_thai, 'qua_han')
        self.assertEqual(dong_bo_hoa_don_qua_han(today=self.today), 0)

    def test_overdue_command_is_idempotent(self):
        hd = self.contract()
        invoice = self.invoice_for_contract(
            hd, 1, 'chua_thanh_toan', self.today - timedelta(days=1)
        )

        output = StringIO()
        call_command('dong_bo_hoa_don_qua_han', stdout=output, stderr=StringIO())
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, 'qua_han')
        self.assertIn('1', output.getvalue())

        output = StringIO()
        call_command('dong_bo_hoa_don_qua_han', stdout=output, stderr=StringIO())
        self.assertIn('0', output.getvalue())

    def test_admin_invoice_list_get_does_not_mutate_overdue_status(self):
        invoice = self.invoice()
        invoice.han_thanh_toan = self.today - timedelta(days=1)
        invoice.save(update_fields=['han_thanh_toan'])
        self.client.force_login(self.admin)

        response = self.client.get(reverse('quan_ly_hoa_don'))
        invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.trang_thai, 'chua_thanh_toan')

    def test_admin_invoice_detail_get_does_not_mutate_overdue_status(self):
        invoice = self.invoice()
        invoice.han_thanh_toan = self.today - timedelta(days=1)
        invoice.save(update_fields=['han_thanh_toan'])
        self.client.force_login(self.admin)

        response = self.client.get(reverse('chi_tiet_hoa_don', args=[invoice.pk]))
        invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.trang_thai, 'chua_thanh_toan')

    def test_tenant_invoice_list_get_does_not_mutate_overdue_status(self):
        invoice = self.invoice()
        invoice.han_thanh_toan = self.today - timedelta(days=1)
        invoice.save(update_fields=['han_thanh_toan'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('hoa_don_cua_toi'))
        invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.trang_thai, 'chua_thanh_toan')

    def test_tenant_invoice_detail_get_does_not_mutate_overdue_status(self):
        invoice = self.invoice()
        invoice.han_thanh_toan = self.today - timedelta(days=1)
        invoice.save(update_fields=['han_thanh_toan'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('chi_tiet_hoa_don_cua_toi', args=[invoice.pk]))
        invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.trang_thai, 'chua_thanh_toan')

    def test_tenant_payment_get_does_not_mutate_overdue_status(self):
        invoice = self.invoice()
        invoice.han_thanh_toan = self.today - timedelta(days=1)
        invoice.save(update_fields=['han_thanh_toan'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('thanh_toan_hoa_don_cua_toi', args=[invoice.pk]))
        invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.trang_thai, 'chua_thanh_toan')
