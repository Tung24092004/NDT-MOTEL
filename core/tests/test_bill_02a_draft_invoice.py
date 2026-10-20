"""BILL-02A draft invoice boundary tests; all ORM work uses test_ndt_motel."""
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import HoaDon, NhatKyThaoTac, ThongBao
from core.quy_tac_nghiep_vu import dong_bo_hoa_don_qua_han


class DraftInvoiceBoundaryTests(BusinessFixture):
    def create_invoice(self, month, status="draft", due_date=None):
        return HoaDon.objects.create(
            hop_dong=self.contract(),
            thang=month,
            nam=2026,
            tien_phong=Decimal("2500000"),
            han_thanh_toan=due_date or self.today,
            trang_thai=status,
        )

    def test_draft_is_valid_and_default_is_unchanged(self):
        self.assertIn(("draft", "Bản nháp"), HoaDon.TRANG_THAI)
        draft = self.create_invoice(1)
        draft.full_clean()
        current = HoaDon.objects.create(
            hop_dong=self.contract(), thang=2, nam=2026,
            han_thanh_toan=self.today,
        )
        self.assertEqual(draft.trang_thai, "draft")
        self.assertEqual(current.trang_thai, "chua_thanh_toan")

    def test_unique_contract_period_is_preserved_for_draft(self):
        draft = self.create_invoice(1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HoaDon.objects.create(
                hop_dong=draft.hop_dong, thang=1, nam=2026,
                han_thanh_toan=self.today, trang_thai="chua_thanh_toan",
            )

    def test_tenant_list_and_payable_count_hide_draft(self):
        draft = self.create_invoice(1)
        payable = HoaDon.objects.create(
            hop_dong=draft.hop_dong, thang=2, nam=2026,
            tien_phong=Decimal("2500000"), han_thanh_toan=self.today,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("hoa_don_cua_toi"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["hoa_don"]), [payable])
        self.assertEqual(response.context["tong_hoa_don"], 1)
        self.assertNotContains(response, f"HĐ-{draft.pk}")

    def test_tenant_detail_and_payment_are_not_available_for_draft(self):
        draft = self.create_invoice(1)
        self.client.force_login(self.user)
        detail = reverse("chi_tiet_hoa_don_cua_toi", args=[draft.pk])
        payment = reverse("thanh_toan_hoa_don_cua_toi", args=[draft.pk])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(payment).status_code, 404)
        self.assertEqual(
            self.client.post(payment, {
                "buoc": "xac_thuc", "phuong_thuc": "tien_mat", "xac_nhan": "dong_y",
            }).status_code,
            404,
        )
        draft.refresh_from_db()
        self.assertEqual(draft.trang_thai, "draft")
        self.assertFalse(ThongBao.objects.exists())
        self.assertFalse(NhatKyThaoTac.objects.exists())

    def test_draft_is_not_overdue_or_receivable(self):
        draft = self.create_invoice(1, due_date=self.today - timedelta(days=1))
        self.assertEqual(dong_bo_hoa_don_qua_han(today=self.today), 0)
        draft.refresh_from_db()
        self.assertEqual(draft.trang_thai, "draft")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("bao_cao_cong_no"))
        self.assertEqual(response.context["thong_ke"]["tong_so"], 0)
        self.assertNotIn(draft.pk, {item.pk for item in response.context["hoa_don"]})

    def test_admin_can_filter_and_read_draft_without_payment_action(self):
        draft = self.create_invoice(1)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("quan_ly_hoa_don"), {"trang_thai": "draft"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["hoa_don"]), [draft])
        self.assertContains(response, "Bản nháp")
        detail = self.client.get(reverse("chi_tiet_hoa_don", args=[draft.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Bản nháp")
        self.assertNotContains(detail, "Xác nhận đã nhận thanh toán")

    def test_manual_and_bulk_defaults_remain_payable(self):
        manual = HoaDon.objects.create(
            hop_dong=self.contract(), thang=1, nam=2026, han_thanh_toan=self.today,
        )
        bulk = HoaDon.objects.create(
            hop_dong=self.contract(), thang=2, nam=2026, han_thanh_toan=self.today,
        )
        self.assertEqual(manual.trang_thai, "chua_thanh_toan")
        self.assertEqual(bulk.trang_thai, "chua_thanh_toan")

    def test_guest_and_non_owner_cannot_access_draft(self):
        draft = self.create_invoice(1)
        detail = reverse("chi_tiet_hoa_don_cua_toi", args=[draft.pk])
        self.assertEqual(self.client.get(detail).status_code, 302)
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(detail).status_code, 404)
