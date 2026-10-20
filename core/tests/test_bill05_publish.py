from datetime import timedelta

from core.dich_vu.hoa_don import create_invoice_draft, publish_invoice_draft
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import NhatKyThaoTac, ThongBao
from django.urls import reverse


class InvoiceDraftPublishTests(BusinessFixture):
    def create_publishable_draft(self):
        contract = self.contract(start=self.today.replace(day=1), end=self.today + timedelta(days=90))
        return create_invoice_draft(
            actor=self.admin,
            contract_id=contract.pk,
            year=self.today.year,
            month=self.today.month,
        )

    def test_publish_once_creates_one_audit_and_notification(self):
        invoice = self.create_publishable_draft()
        invoice, published = publish_invoice_draft(actor=self.admin, invoice_id=invoice.pk)
        self.assertTrue(published); self.assertEqual(invoice.trang_thai, "chua_thanh_toan")
        _, published = publish_invoice_draft(actor=self.admin, invoice_id=invoice.pk)
        self.assertFalse(published)
        self.assertEqual(NhatKyThaoTac.objects.filter(doi_tuong_id=invoice.pk, tieu_de__startswith="Phat hanh").count(), 1)
        self.assertEqual(ThongBao.objects.filter(ma_tham_chieu=f"INVOICE:{invoice.pk}:PUBLISHED").count(), 1)

    def test_admin_can_review_draft_and_post_publish_form(self):
        invoice = self.create_publishable_draft()
        publish_url = reverse("phat_hanh_hoa_don", args=[invoice.pk])
        self.client.force_login(self.admin)

        listing = self.client.get(reverse("quan_ly_hoa_don"), {"trang_thai": "draft"})
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, reverse("chi_tiet_hoa_don", args=[invoice.pk]))

        response = self.client.get(reverse("chi_tiet_hoa_don", args=[invoice.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hóa đơn nháp")
        self.assertContains(response, "Tenant chưa nhìn thấy và chưa thể thanh toán")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, publish_url)
        self.assertContains(response, "Phát hành hóa đơn")
        self.assertNotContains(response, "Tiền điện")
        self.assertNotContains(response, "Tiền nước")

        response = self.client.post(publish_url)
        self.assertRedirects(response, reverse("chi_tiet_hoa_don", args=[invoice.pk]))
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "chua_thanh_toan")

        published_detail = self.client.get(reverse("chi_tiet_hoa_don", args=[invoice.pk]))
        self.assertContains(published_detail, "Chưa thanh toán")
        self.assertContains(published_detail, "Tenant đã có thể xem hóa đơn")
        self.assertNotContains(published_detail, publish_url)
        self.assertNotContains(published_detail, "data-bill05-publish-form")

    def test_blocked_draft_explains_reason_without_active_publish_action(self):
        invoice = self.create_publishable_draft()
        invoice.han_thanh_toan += timedelta(days=1)
        invoice.save(update_fields=["han_thanh_toan"])
        self.client.force_login(self.admin)
        publish_url = reverse("phat_hanh_hoa_don", args=[invoice.pk])

        response = self.client.get(reverse("chi_tiet_hoa_don", args=[invoice.pk]))
        self.assertContains(response, "Chưa đủ điều kiện phát hành")
        self.assertContains(response, "Hạn thanh toán draft không khớp quy tắc hợp đồng")
        self.assertNotContains(response, publish_url)
        self.assertNotContains(response, "data-bill05-publish-form")

        response = self.client.post(publish_url)
        self.assertRedirects(response, reverse("chi_tiet_hoa_don", args=[invoice.pk]))
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "draft")

    def test_non_admin_cannot_open_or_submit_admin_review(self):
        invoice = self.create_publishable_draft()
        detail_url = reverse("chi_tiet_hoa_don", args=[invoice.pk])
        publish_url = reverse("phat_hanh_hoa_don", args=[invoice.pk])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(detail_url).status_code, 302)
        self.assertEqual(self.client.post(publish_url).status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "draft")

    def test_tenant_visibility_changes_only_after_publish_and_is_owner_scoped(self):
        invoice = self.create_publishable_draft()
        tenant_detail = reverse("chi_tiet_hoa_don_cua_toi", args=[invoice.pk])
        payment_url = reverse("thanh_toan_hoa_don_cua_toi", args=[invoice.pk])

        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse("hoa_don_cua_toi")), f"HĐ-{invoice.pk}")
        self.assertEqual(self.client.get(tenant_detail).status_code, 404)
        self.assertEqual(self.client.get(payment_url).status_code, 404)

        publish_invoice_draft(actor=self.admin, invoice_id=invoice.pk)
        tenant_list = self.client.get(reverse("hoa_don_cua_toi"))
        self.assertContains(tenant_list, f"HĐ-{invoice.pk}")
        tenant_response = self.client.get(tenant_detail)
        self.assertEqual(tenant_response.status_code, 200)
        self.assertContains(tenant_response, "Chưa thanh toán")
        self.assertContains(tenant_response, f"{invoice.thang}/{invoice.nam}")
        self.assertContains(tenant_response, invoice.han_thanh_toan.strftime("%d/%m/%Y"))
        self.assertNotContains(tenant_response, "Đã thanh toán")
        self.assertEqual(self.client.get(payment_url).status_code, 200)

        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(tenant_detail).status_code, 404)
        self.assertEqual(self.client.get(payment_url).status_code, 404)
