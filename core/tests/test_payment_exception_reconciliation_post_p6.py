from datetime import timedelta
from io import BytesIO
from pathlib import Path
import shutil
from uuid import uuid4

from PIL import Image
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase
from django.urls import resolve, reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import (
    ChungTuThanhToan,
    HoaDon,
    LichSuThanhToan,
    NhatKyThaoTac,
    ThanhToanCocDatPhong,
    ThongBao,
)
from core.private_storage import private_payment_evidence_storage
from core.views_doi_soat_thanh_toan import doi_soat_ngoai_le_thanh_toan


def image_upload(name="receipt.png"):
    payload = BytesIO()
    Image.new("RGB", (8, 8), "white").save(payload, format="PNG")
    return SimpleUploadedFile(name, payload.getvalue(), content_type="image/png")


class PaymentExceptionReconciliationSourceTests(SimpleTestCase):
    def source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def test_route_template_and_asset_are_scoped_read_only(self):
        url = reverse("doi_soat_ngoai_le_thanh_toan")
        self.assertEqual(url, "/quan-ly-thanh-toan/doi-soat-ngoai-le/")
        self.assertIs(resolve(url).func, doi_soat_ngoai_le_thanh_toan)
        template = self.source("templates/core/doi_soat_ngoai_le_thanh_toan.html")
        self.assertIn('method="get"', template)
        self.assertNotIn('method="post"', template.lower())
        self.assertNotIn("{% csrf_token %}", template)
        self.assertNotIn("anh.name", template)
        self.assertNotIn("/media/", template)
        css = self.source("static/css/payment_exception_reconciliation_post_p6.css")
        self.assertIn(".ndt-f5.ndt-payment-reconciliation", css)
        self.assertNotIn("!important", css)
        self.assertNotIn("url(", css)


class PaymentExceptionReconciliationTests(Phase5BookingFixture):
    def setUp(self):
        super().setUp()
        # Avoid TemporaryDirectory's restrictive Windows ACL; this normal
        # runner-owned child remains an isolated writable evidence store.
        self.private_directory = settings.BASE_DIR / ".test-media" / f"evidence-{uuid4().hex}"
        self.private_directory.mkdir()
        self.storage_state = dict(private_payment_evidence_storage.__dict__)
        private_payment_evidence_storage._location = str(self.private_directory)
        private_payment_evidence_storage.__dict__.pop("base_location", None)
        private_payment_evidence_storage.__dict__.pop("location", None)
        self.superuser = User.objects.create_user("pay04-super", is_superuser=True, is_staff=False)
        self.invoice_counter = 0

    def tearDown(self):
        private_payment_evidence_storage.__dict__.clear()
        private_payment_evidence_storage.__dict__.update(self.storage_state)
        shutil.rmtree(self.private_directory)
        super().tearDown()

    def invoice(self, *, status="cho_xac_nhan", method="chuyen_khoan"):
        self.invoice_counter += 1
        return HoaDon.objects.create(
            hop_dong=self.contract(),
            thang=self.invoice_counter,
            nam=2028,
            tien_phong=2500000,
            han_thanh_toan=self.today + timedelta(days=5),
            trang_thai=status,
            phuong_thuc=method,
        )

    def evidence_for_invoice(self, invoice, *, status="cho_doi_soat", note=""):
        return ChungTuThanhToan.objects.create(
            hoa_don=invoice,
            nguoi_tai_len=self.user,
            anh=image_upload(),
            mime_type="image/png",
            ma_doi_chieu=f"NDTMOTEL HD{invoice.pk}",
            so_lan=1,
            trang_thai=status,
            ghi_chu_doi_soat=note,
        )

    def pending_deposit(self, *, with_evidence=True):
        booking, payment = self.new_booking()
        payment.trang_thai = "cho_xac_nhan"
        payment.thoi_diem_user_bao_da_thanh_toan = timezone.now()
        payment.save()
        evidence = None
        if with_evidence:
            evidence = ChungTuThanhToan.objects.create(
                giao_dich_coc=payment,
                nguoi_tai_len=self.user,
                anh=image_upload(),
                mime_type="image/png",
                ma_doi_chieu=payment.ma_tham_chieu,
            )
        return booking, payment, evidence

    def get_as_admin(self, params=None):
        self.client.force_login(self.admin)
        return self.client.get(reverse("doi_soat_ngoai_le_thanh_toan"), params or {})

    def state_snapshot(self):
        return {
            "invoice": list(HoaDon.objects.order_by("pk").values()),
            "deposit": list(ThanhToanCocDatPhong.objects.order_by("pk").values()),
            "evidence": list(ChungTuThanhToan.objects.order_by("pk").values()),
            "history": LichSuThanhToan.objects.count(),
            "notice": ThongBao.objects.count(),
            "audit": NhatKyThaoTac.objects.count(),
        }

    def test_access_roles_methods_and_get_are_read_only(self):
        invoice = self.invoice()
        self.evidence_for_invoice(invoice)
        url = reverse("doi_soat_ngoai_le_thanh_toan")
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(url), reverse("tai_khoan"))
        self.client.force_login(self.admin)
        before = self.state_snapshot()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.head(url).status_code, 200)
        self.assertEqual(self.state_snapshot(), before)
        self.assertEqual(self.client.post(url).status_code, 405)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_unified_queue_has_deposit_and_invoice_with_deterministic_order(self):
        booking, _payment, deposit_evidence = self.pending_deposit()
        invoice = self.invoice()
        invoice_evidence = self.evidence_for_invoice(invoice)
        old = timezone.now() - timedelta(days=4)
        ChungTuThanhToan.objects.filter(pk=invoice_evidence.pk).update(ngay_tao=old)
        response = self.get_as_admin()
        self.assertEqual(response.status_code, 200)
        rows = list(response.context["rows"])
        self.assertEqual({row["target_type"] for row in rows}, {"coc", "hoa_don"})
        self.assertEqual(rows[0]["target_id"], invoice.pk)
        self.assertEqual(rows[0]["target_type"], "hoa_don")
        self.assertEqual(response.context["summary"]["can_xu_ly"], 2)
        self.assertContains(response, booking.ma_yeu_cau)
        self.assertContains(response, f"HĐ-{invoice.pk}")
        self.assertNotContains(response, deposit_evidence.anh.name)

    def test_empty_legacy_cash_and_mismatch_states_render_safely(self):
        empty = self.get_as_admin()
        self.assertContains(empty, "Không có ngoại lệ phù hợp")

        _booking, _payment, _evidence = self.pending_deposit(with_evidence=False)
        cash = self.invoice(method="tien_mat")
        mismatch = self.invoice(status="da_thanh_toan")
        mismatch_evidence = self.evidence_for_invoice(mismatch, status="cho_doi_soat")
        mismatch_evidence.anh.delete(save=False)

        response = self.get_as_admin()
        kinds = {row["kind"] for row in response.context["rows"]}
        self.assertEqual(kinds, {"thieu_chung_tu", "tien_mat_cho_doi_soat", "bat_nhat"})
        self.assertContains(response, "Thiếu chứng từ / dữ liệu cũ")
        self.assertContains(response, "Tiền mặt chờ xác nhận")
        self.assertContains(response, "Bất nhất trạng thái")
        self.assertContains(response, reverse("chi_tiet_hoa_don", args=[cash.pk]))

    def test_filters_search_age_and_invalid_values_fail_safe(self):
        self.pending_deposit()
        invoice = self.invoice()
        evidence = self.evidence_for_invoice(invoice)
        ChungTuThanhToan.objects.filter(pk=evidence.pk).update(ngay_tao=timezone.now() - timedelta(days=9))
        filtered = self.get_as_admin({
            "loai": "hoa_don",
            "phan_loai": "cho_doi_soat",
            "chung_tu": "cho_doi_soat",
            "tuoi": "8_plus",
            "co_so": str(self.facility.pk),
            "q": self.tenant.ho_ten,
        })
        self.assertEqual(len(filtered.context["rows"]), 1)
        self.assertEqual(filtered.context["rows"][0]["target_id"], invoice.pk)
        invalid = self.get_as_admin({
            "loai": "DROP TABLE",
            "phan_loai": "unknown",
            "chung_tu": "unknown",
            "tuoi": "unknown",
            "co_so": "not-an-id",
        })
        self.assertEqual(invalid.context["loai"], "")
        self.assertEqual(invalid.context["phan_loai"], "can_xu_ly")
        self.assertEqual(invalid.context["chung_tu"], "")
        self.assertEqual(invalid.context["tuoi"], "")
        self.assertEqual(invalid.context["co_so"], "")

    def test_pagination_is_twenty_and_preserves_filters(self):
        for _index in range(21):
            invoice = self.invoice()
            self.evidence_for_invoice(invoice)
        response = self.get_as_admin({"loai": "hoa_don"})
        self.assertEqual(len(response.context["rows"]), 20)
        self.assertEqual(response.context["page_obj"].paginator.count, 21)
        self.assertEqual(response.context["query_string"], "loai=hoa_don")
        page_two = self.get_as_admin({"loai": "hoa_don", "page": "2"})
        self.assertEqual(len(page_two.context["rows"]), 1)

    def test_private_evidence_link_keeps_existing_owner_authorization(self):
        invoice = self.invoice()
        evidence = self.evidence_for_invoice(invoice)
        url = reverse("anh_chung_tu_thanh_toan", args=[evidence.pk])
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        for closer in response._resource_closers:
            closer()

    def test_valid_invoice_rejection_writes_one_audit_and_one_tenant_notice(self):
        invoice = self.invoice()
        evidence = self.evidence_for_invoice(invoice)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("xu_ly_hoa_don", args=[invoice.pk]), {
            "hanh_dong": "tu_choi_thanh_toan",
            "ly_do_tu_choi": "Ảnh chứng từ không khớp giao dịch",
        })
        self.assertRedirects(response, reverse("chi_tiet_hoa_don", args=[invoice.pk]))
        invoice.refresh_from_db()
        evidence.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "chua_thanh_toan")
        self.assertEqual(invoice.phuong_thuc, "")
        self.assertEqual(evidence.trang_thai, "tu_choi")
        self.assertEqual(evidence.nguoi_xu_ly, self.admin)
        notices = ThongBao.objects.filter(
            nguoi_thue=self.tenant,
            ma_tham_chieu__startswith=f"INVOICE:{invoice.pk}:PAYMENT_REJECTED:",
        )
        self.assertEqual(notices.count(), 1)
        self.assertIn("gửi lại chứng từ hợp lệ", notices.get().noi_dung)
        self.assertNotIn("private", notices.get().noi_dung.lower())
        audits = NhatKyThaoTac.objects.filter(
            hanh_dong="tu_choi", doi_tuong="HoaDon", doi_tuong_id=invoice.pk,
        )
        self.assertEqual(audits.count(), 1)
        self.assertEqual(audits.get().du_lieu_moi["thong_bao_id"], notices.get().pk)

    def test_rejection_validation_permission_state_and_missing_object_have_no_side_effects(self):
        invoice = self.invoice()
        evidence = self.evidence_for_invoice(invoice)
        action = reverse("xu_ly_hoa_don", args=[invoice.pk])
        baseline = self.state_snapshot()
        self.client.force_login(self.user)
        self.client.post(action, {"hanh_dong": "tu_choi_thanh_toan", "ly_do_tu_choi": "No"})
        self.assertEqual(self.state_snapshot(), baseline)
        self.client.force_login(self.admin)
        self.client.post(action, {"hanh_dong": "tu_choi_thanh_toan", "ly_do_tu_choi": ""})
        self.assertEqual(self.state_snapshot(), baseline)
        invoice.trang_thai = "da_thanh_toan"
        invoice.save(update_fields=["trang_thai"])
        wrong_state = self.state_snapshot()
        self.client.post(action, {"hanh_dong": "tu_choi_thanh_toan", "ly_do_tu_choi": "No"})
        self.assertEqual(self.state_snapshot(), wrong_state)
        self.assertEqual(self.client.post(
            reverse("xu_ly_hoa_don", args=[999999999]),
            {"hanh_dong": "tu_choi_thanh_toan", "ly_do_tu_choi": "No"},
        ).status_code, 404)
        evidence.refresh_from_db()
        self.assertEqual(evidence.trang_thai, "cho_doi_soat")

    def test_rejection_duplicate_post_does_not_duplicate_side_effects(self):
        invoice = self.invoice()
        self.evidence_for_invoice(invoice)
        self.client.force_login(self.admin)
        action = reverse("xu_ly_hoa_don", args=[invoice.pk])
        payload = {"hanh_dong": "tu_choi_thanh_toan", "ly_do_tu_choi": "Sai giao dịch"}
        self.client.post(action, payload)
        counts = (ThongBao.objects.count(), NhatKyThaoTac.objects.count())
        self.client.post(action, payload)
        self.assertEqual((ThongBao.objects.count(), NhatKyThaoTac.objects.count()), counts)

    def test_rejection_csrf_contract(self):
        invoice = self.invoice()
        self.evidence_for_invoice(invoice)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        response = csrf_client.post(reverse("xu_ly_hoa_don", args=[invoice.pk]), {
            "hanh_dong": "tu_choi_thanh_toan",
            "ly_do_tu_choi": "Sai giao dịch",
        })
        self.assertEqual(response.status_code, 403)
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "cho_xac_nhan")
        self.assertFalse(ThongBao.objects.filter(ma_tham_chieu__contains="PAYMENT_REJECTED").exists())

    def test_invoice_approval_flow_remains_unchanged(self):
        invoice = self.invoice()
        evidence = self.evidence_for_invoice(invoice)
        self.client.force_login(self.admin)
        self.client.post(reverse("xu_ly_hoa_don", args=[invoice.pk]), {
            "hanh_dong": "xac_nhan_thanh_toan",
            "phuong_thuc": "chuyen_khoan",
        })
        invoice.refresh_from_db()
        evidence.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "da_thanh_toan")
        self.assertEqual(evidence.trang_thai, "da_chap_nhan")
        self.assertEqual(LichSuThanhToan.objects.filter(hoa_don=invoice).count(), 1)
        self.assertFalse(ThongBao.objects.filter(ma_tham_chieu__contains="PAYMENT_REJECTED").exists())
