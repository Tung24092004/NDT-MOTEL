"""BILLING-01 first rent-only draft tests."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError

from core.dich_vu.hoa_don import create_invoice_draft, due_date_for_period
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import HoaDon, ThongBao


class FirstInvoiceDraftTests(BusinessFixture):
    def test_current_full_month_creates_authoritative_rent_only_draft(self):
        contract = self.contract(start=self.today.replace(day=1), end=self.today + timedelta(days=90))
        invoice = create_invoice_draft(actor=self.admin, contract_id=contract.pk, year=self.today.year, month=self.today.month)
        self.assertEqual(invoice.trang_thai, "draft")
        self.assertEqual(invoice.tien_phong, contract.tien_thue_thang)
        self.assertEqual(invoice.tong_tien, contract.tien_thue_thang)
        self.assertEqual(invoice.han_thanh_toan, due_date_for_period(contract, self.today.replace(day=1)))
        self.assertFalse(ThongBao.objects.exists())

    def test_duplicate_and_partial_or_inactive_contracts_are_blocked(self):
        contract = self.contract(start=self.today.replace(day=1), end=self.today + timedelta(days=90))
        create_invoice_draft(actor=self.admin, contract_id=contract.pk, year=self.today.year, month=self.today.month)
        with self.assertRaises(ValidationError):
            create_invoice_draft(actor=self.admin, contract_id=contract.pk, year=self.today.year, month=self.today.month)
        self.assertEqual(HoaDon.objects.count(), 1)

        contract2 = self.contract(start=self.today + timedelta(days=1), end=self.today + timedelta(days=90), tenant=self.other)
        with self.assertRaises(ValidationError):
            create_invoice_draft(actor=self.admin, contract_id=contract2.pk, year=self.today.year, month=self.today.month)

    def test_due_date_clamps_to_following_month_end(self):
        contract = self.contract(start=date(2026, 1, 1), end=date(2026, 12, 31))
        contract.ngay_thanh_toan_hang_thang = 31
        self.assertEqual(due_date_for_period(contract, date(2026, 1, 1)), date(2026, 2, 28))
