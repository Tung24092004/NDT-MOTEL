from io import StringIO
import threading
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from core.dich_vu.ra_soat_thanh_toan_cu import reconcile_legacy_paid_invoice
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import HoaDon, LichSuThanhToan, NhatKyThaoTac, RaSoatThanhToanHoaDonCu


class LegacyInvoiceReviewTests(BusinessFixture):
    def invoice(self, *, canonical=False, status='da_thanh_toan'):
        invoice = HoaDon.objects.create(hop_dong=self.contract(), thang=1, nam=2026, tien_phong=100,
            han_thanh_toan=timezone.localdate(), trang_thai=status, ngay_thanh_toan=timezone.now(), phuong_thuc='tien_mat')
        if canonical:
            invoice.ma_giao_dich = 'CANONICAL-1'; invoice.nguoi_xac_nhan = self.admin; invoice.save(update_fields=['ma_giao_dich','nguoi_xac_nhan'])
            LichSuThanhToan.objects.create(hoa_don=invoice, so_tien=invoice.tong_tien, phuong_thuc='tien_mat', ma_giao_dich='CANONICAL-1', nguoi_thuc_hien=self.admin)
        return invoice

    def review(self, invoice, actor=None):
        return reconcile_legacy_paid_invoice(actor=actor or self.admin, invoice_id=invoice.pk, evidence_grade='partial_evidence', note='Ho so cu khong du bang chung')

    def test_admin_only_and_only_incomplete_paid_invoices_are_eligible(self):
        invoice = self.invoice()
        with self.assertRaises(PermissionDenied): self.review(invoice, self.user)
        with self.assertRaises(ValidationError): self.review(self.invoice(canonical=True))
        with self.assertRaises(ValidationError): self.review(self.invoice(status='chua_thanh_toan'))

    def test_review_is_immutable_and_never_reconstructs_payment(self):
        invoice = self.invoice(); before = HoaDon.objects.values().get(pk=invoice.pk)
        review = self.review(invoice)
        self.assertEqual(HoaDon.objects.values().get(pk=invoice.pk), before)
        self.assertFalse(LichSuThanhToan.objects.filter(hoa_don=invoice).exists())
        self.assertIn('transaction_reference', review.truong_canonical_con_thieu)
        self.assertEqual(invoice.ma_giao_dich, '')
        with self.assertRaises(ValidationError): self.review(invoice)
        audit = NhatKyThaoTac.objects.get(doi_tuong='RaSoatThanhToanHoaDonCu', doi_tuong_id=review.pk)
        self.assertIn('Ra soat', audit.tieu_de)
        self.assertNotEqual(audit.hanh_dong, 'thanh_toan')

    def test_integrity_command_still_flags_reviewed_invoice(self):
        invoice = self.invoice(); self.review(invoice); out = StringIO()
        call_command('kiem_tra_toan_ven_du_lieu', stdout=out)
        self.assertIn(str(invoice.pk), out.getvalue())

    def test_admin_review_get_shows_stored_facts_missing_provenance_and_warning(self):
        invoice = self.invoice()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:core_hoadon_legacy_review', args=[invoice.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, timezone.localtime(invoice.ngay_thanh_toan).strftime('%Y-%m-%d'))
        self.assertContains(response, 'tien_mat')
        self.assertContains(response, 'Không có / UNKNOWN')
        self.assertContains(response, 'transaction_reference')
        self.assertContains(response, 'admin_confirmer')
        self.assertContains(response, 'payment_history')
        self.assertContains(response, 'không xác nhận đã nhận tiền')
        invoice.ma_giao_dich = 'LEGACY-REF-1'; invoice.save(update_fields=['ma_giao_dich'])
        response = self.client.get(reverse('admin:core_hoadon_legacy_review', args=[invoice.pk]))
        self.assertContains(response, 'LEGACY-REF-1')


@skipUnlessDBFeature('has_select_for_update')
class LegacyInvoiceReviewConcurrencyTests(TransactionTestCase):
    def setUp(self):
        BusinessFixture.setUpTestData.__func__(type(self))
        self.booking = BusinessFixture.booking.__get__(self)
        self.contract = BusinessFixture.contract.__get__(self)
        self.invoice = HoaDon.objects.create(hop_dong=self.contract(), thang=2, nam=2026, tien_phong=100,
            han_thanh_toan=timezone.localdate(), trang_thai='da_thanh_toan', ngay_thanh_toan=timezone.now(), phuong_thuc='tien_mat')

    def test_concurrent_reviews_create_at_most_one_record_without_payment_mutation(self):
        barrier, outcomes, guard = threading.Barrier(2, timeout=10), [], threading.Lock()
        before = HoaDon.objects.values().get(pk=self.invoice.pk)
        def worker():
            close_old_connections()
            try:
                barrier.wait(); actor = type(self.admin).objects.get(pk=self.admin.pk)
                reconcile_legacy_paid_invoice(actor=actor, invoice_id=self.invoice.pk, evidence_grade='no_evidence', note='Concurrent legacy review')
                result = 'ok'
            except ValidationError: result = 'blocked'
            finally: close_old_connections()
            with guard: outcomes.append(result)
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes), ['blocked', 'ok'])
        self.assertEqual(RaSoatThanhToanHoaDonCu.objects.filter(hoa_don=self.invoice).count(), 1)
        self.assertEqual(HoaDon.objects.values().get(pk=self.invoice.pk), before)
        self.assertFalse(LichSuThanhToan.objects.filter(hoa_don=self.invoice).exists())
