"""Regression coverage for finalized invoice financial snapshots."""
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from core.admin import HoaDonAdmin
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import ChungTuThanhToan, HoaDon, LichSuThanhToan


class InvoiceAmountImmutabilityTests(BusinessFixture):
    def invoice(self, *, month=1, status="draft"):
        return HoaDon.objects.create(
            hop_dong=self.contract(), thang=month, nam=2026,
            tien_phong=Decimal("2500000"), tien_dien=Decimal("100000"),
            chi_so_dien_cu=Decimal("100"), chi_so_dien_moi=Decimal("120"),
            don_gia_dien=Decimal("5000"), tien_nuoc=Decimal("50000"),
            tien_dich_vu=Decimal("25000"), phi_khac=Decimal("10000"),
            chi_tiet_phi="Snapshot test", han_thanh_toan=self.today,
            trang_thai=status,
        )

    def attempt(self, invoice):
        return ChungTuThanhToan.objects.create(
            hoa_don=invoice, so_lan=1, nguoi_tai_len=self.user,
            anh="payment_evidence/immutability.png", mime_type="image/png",
            ma_doi_chieu=f"NDTMOTEL HD{invoice.pk}",
        )

    def test_draft_snapshot_can_change_before_any_attempt(self):
        invoice = self.invoice()
        invoice.tien_dien = Decimal("125000")
        invoice.chi_so_dien_moi = Decimal("125")
        invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.tien_dien, Decimal("125000"))
        self.assertEqual(invoice.chi_so_dien_moi, Decimal("125"))

    def test_finalized_invoice_snapshot_cannot_change(self):
        invoice = self.invoice(status="chua_thanh_toan")
        invoice.tien_phong = Decimal("2600000")
        with self.assertRaises(ValidationError):
            invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.tien_phong, Decimal("2500000"))

    def test_payment_attempt_locks_draft_snapshot(self):
        invoice = self.invoice()
        self.attempt(invoice)
        invoice.han_thanh_toan = self.today.replace(day=min(self.today.day + 1, 28))
        with self.assertRaises(ValidationError):
            invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "draft")

    def test_status_and_amount_same_save_cannot_bypass_finalization_lock(self):
        invoice = self.invoice()
        invoice.trang_thai = "chua_thanh_toan"
        invoice.tien_phong = Decimal("2600000")
        with self.assertRaises(ValidationError):
            invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(
            (invoice.trang_thai, invoice.tien_phong),
            ("draft", Decimal("2500000")),
        )

    def test_paid_invoice_rejects_snapshot_edit_but_allows_payment_metadata(self):
        invoice = self.invoice(month=2, status="da_thanh_toan")
        history = LichSuThanhToan.objects.create(
            hoa_don=invoice, so_tien=invoice.tong_tien, phuong_thuc="tien_mat",
            nguoi_thuc_hien=self.admin,
        )
        invoice.tien_dich_vu = Decimal("99999")
        with self.assertRaises(ValidationError):
            invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.tong_tien, history.so_tien)
        invoice.ghi_chu = "Reconciliation note"
        invoice.save(update_fields=["ghi_chu", "ngay_cap_nhat"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.ghi_chu, "Reconciliation note")

    def test_admin_makes_snapshot_fields_readonly_only_when_locked(self):
        invoice_admin = HoaDonAdmin(HoaDon, AdminSite())
        request = RequestFactory().get("/admin/core/hoadon/")
        draft = self.invoice(month=3)
        locked = self.invoice(month=4, status="chua_thanh_toan")
        self.assertNotIn("tien_phong", invoice_admin.get_readonly_fields(request, draft))
        readonly = invoice_admin.get_readonly_fields(request, locked)
        self.assertTrue(set(HoaDon.FINANCIAL_SNAPSHOT_FIELDS).issubset(readonly))
