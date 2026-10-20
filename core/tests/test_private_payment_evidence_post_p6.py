from io import BytesIO
from pathlib import Path
import shutil
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.http import Http404
from django.test import Client, RequestFactory
from django.urls import reverse

from core.dich_vu.hop_dong import confirm_deposit_and_create_contract, reject_deposit
from core.dich_vu.chung_tu_thanh_toan import active_invoice_attempt
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import ChungTuThanhToan, HoaDon, LichSuThanhToan
from core.private_storage import private_payment_evidence_storage
from core.views_chung_tu_thanh_toan import xem_anh_chung_tu_thanh_toan


def image_upload(name="receipt.png", *, size=(8, 8), image_format="PNG"):
    payload = BytesIO()
    Image.new("RGB", size, "white").save(payload, format=image_format)
    mime = "image/jpeg" if image_format == "JPEG" else f"image/{image_format.lower()}"
    return SimpleUploadedFile(name, payload.getvalue(), content_type=mime)


class PrivatePaymentEvidenceTests(Phase5BookingFixture):
    def setUp(self):
        super().setUp()
        # tempfile.TemporaryDirectory applies a restrictive Windows ACL here;
        # a normal child of the runner-owned parent stays isolated and writable.
        private_directory = settings.BASE_DIR / ".test-media" / f"evidence-{uuid4().hex}"
        private_directory.mkdir()
        # Retain TemporaryDirectory's `.name` test-fixture contract for the
        # failure suite that subclasses this fixture.
        self.private_directory = SimpleNamespace(name=str(private_directory))
        self.storage_state = dict(private_payment_evidence_storage.__dict__)
        private_payment_evidence_storage._location = self.private_directory.name
        private_payment_evidence_storage.__dict__.pop("base_location", None)
        private_payment_evidence_storage.__dict__.pop("location", None)

    def tearDown(self):
        private_payment_evidence_storage.__dict__.clear()
        private_payment_evidence_storage.__dict__.update(self.storage_state)
        shutil.rmtree(self.private_directory.name)
        super().tearDown()

    def invoice(self):
        return HoaDon.objects.create(
            hop_dong=self.contract(),
            thang=10,
            nam=2026,
            tien_phong=2500000,
            han_thanh_toan=self.today,
        )

    def upload_deposit(self, booking, **changes):
        data = {
            "action": "report",
            "ma_giao_dich": "BANK-DEPOSIT-01",
            "anh_chung_tu": image_upload(),
        }
        data.update(changes)
        return self.client.post(reverse("thanh_toan_coc_cua_toi", args=[booking.pk]), data)

    def upload_invoice(self, invoice, **changes):
        data = {
            "buoc": "xac_thuc",
            "phuong_thuc": "chuyen_khoan",
            "xac_nhan": "dong_y",
            "anh_chung_tu": image_upload(),
        }
        data.update(changes)
        return self.client.post(reverse("thanh_toan_hoa_don_cua_toi", args=[invoice.pk]), data)

    def test_tenant_uploads_own_deposit_without_auto_confirmation(self):
        booking, payment = self.new_booking()
        response = self.upload_deposit(booking)
        self.assertRedirects(response, reverse("chi_tiet_dat_phong_cua_toi", args=[booking.pk]))
        payment.refresh_from_db()
        evidence = ChungTuThanhToan.objects.get(giao_dich_coc=payment)
        self.assertEqual(payment.trang_thai, "cho_xac_nhan")
        self.assertEqual(evidence.trang_thai, "cho_doi_soat")
        self.assertEqual(evidence.nguoi_tai_len, self.user)
        self.assertEqual(evidence.ma_doi_chieu, payment.ma_tham_chieu)
        self.assertRegex(Path(evidence.anh.name).name, r"^[0-9a-f]{32}\.png$")

    def test_tenant_uploads_own_invoice_without_auto_settlement(self):
        invoice = self.invoice()
        response = self.upload_invoice(invoice)
        self.assertRedirects(response, reverse("chi_tiet_hoa_don_cua_toi", args=[invoice.pk]))
        invoice.refresh_from_db()
        evidence = ChungTuThanhToan.objects.get(hoa_don=invoice)
        self.assertEqual(invoice.trang_thai, "cho_xac_nhan")
        self.assertIsNone(invoice.ngay_thanh_toan)
        self.assertIsNone(invoice.nguoi_xac_nhan)
        self.assertFalse(LichSuThanhToan.objects.filter(hoa_don=invoice).exists())
        self.assertEqual(evidence.ma_doi_chieu, f"NDTMOTEL HD{invoice.pk}")
        self.assertEqual(evidence.so_lan, 1)

    def test_guest_and_other_tenant_cannot_upload(self):
        booking, payment = self.new_booking()
        invoice = self.invoice()
        guest = Client()
        self.assertEqual(
            guest.post(reverse("thanh_toan_coc_cua_toi", args=[booking.pk]), {"action": "report"}).status_code,
            302,
        )
        self.client.force_login(self.other_user)
        self.assertEqual(self.upload_deposit(booking).status_code, 404)
        self.assertEqual(self.upload_invoice(invoice).status_code, 404)
        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.trang_thai, "chua_thanh_toan")
        self.assertEqual(invoice.trang_thai, "chua_thanh_toan")
        self.assertFalse(ChungTuThanhToan.objects.exists())

    def test_private_image_owner_admin_and_non_disclosure(self):
        booking, _payment = self.new_booking()
        self.upload_deposit(booking)
        evidence = ChungTuThanhToan.objects.get()
        url = reverse("anh_chung_tu_thanh_toan", args=[evidence.pk])
        self.assertEqual(Client().get(f"/media/{evidence.anh.name}").status_code, 404)
        factory = RequestFactory()

        owner_request = factory.get(url)
        owner_request.user = self.user
        owner_response = xem_anh_chung_tu_thanh_toan(owner_request, evidence.pk)
        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(owner_response["Content-Type"], "image/png")
        self.assertEqual(owner_response["Cache-Control"], "private, no-store")
        self.assertEqual(owner_response["X-Content-Type-Options"], "nosniff")

        admin_request = factory.get(url)
        admin_request.user = self.admin
        admin_response = xem_anh_chung_tu_thanh_toan(admin_request, evidence.pk)
        self.assertEqual(admin_response.status_code, 200)

        for user in (self.other_user, AnonymousUser()):
            denied_request = factory.get(url)
            denied_request.user = user
            with self.assertRaises(Http404):
                xem_anh_chung_tu_thanh_toan(denied_request, evidence.pk)
        admin_response.file_to_stream.close()
        owner_response.file_to_stream.close()

    def test_fake_and_oversize_files_are_rejected(self):
        booking, payment = self.new_booking()
        fake = SimpleUploadedFile("receipt.png", b"<html>not an image</html>", content_type="image/png")
        response = self.upload_deposit(booking, anh_chung_tu=fake)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "JPEG, PNG")
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "chua_thanh_toan")

        too_large = SimpleUploadedFile("large.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
        response = self.upload_deposit(booking, anh_chung_tu=too_large)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "5 MB")
        self.assertFalse(ChungTuThanhToan.objects.exists())

    def test_pending_and_confirmed_deposit_cannot_submit_again(self):
        booking, payment = self.new_booking()
        self.upload_deposit(booking)
        self.upload_deposit(booking, anh_chung_tu=image_upload("second.png"))
        self.assertEqual(ChungTuThanhToan.objects.filter(giao_dich_coc=payment).count(), 1)
        contract = confirm_deposit_and_create_contract(actor=self.admin, booking_id=booking.pk)
        self.assertIsNotNone(contract.pk)
        self.upload_deposit(booking, anh_chung_tu=image_upload("third.png"))
        self.assertEqual(ChungTuThanhToan.objects.filter(giao_dich_coc=payment).count(), 1)
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "da_xac_nhan")
        self.assertEqual(payment.chung_tu.trang_thai, "da_chap_nhan")

    def test_rejected_deposit_uses_new_payment_attempt(self):
        booking, first = self.new_booking()
        self.upload_deposit(booking)
        reject_deposit(actor=self.admin, booking_id=booking.pk, reason="Ảnh không khớp")
        first.refresh_from_db()
        self.assertEqual(first.chung_tu.trang_thai, "tu_choi")
        self.client.post(reverse("thanh_toan_coc_cua_toi", args=[booking.pk]), {"action": "retry"})
        second = booking.giao_dich_coc.get(active_slot=1)
        self.assertNotEqual(first.pk, second.pk)
        self.upload_deposit(booking, anh_chung_tu=image_upload("replacement.png"))
        self.assertEqual(ChungTuThanhToan.objects.filter(giao_dich_coc__dat_phong=booking).count(), 2)

    def test_invoice_pending_and_paid_cannot_submit_again(self):
        invoice = self.invoice()
        self.upload_invoice(invoice)
        self.upload_invoice(invoice, anh_chung_tu=image_upload("second.png"))
        self.assertEqual(ChungTuThanhToan.objects.filter(hoa_don=invoice).count(), 1)
        self.client.force_login(self.admin)
        self.client.post(
            reverse("xu_ly_hoa_don", args=[invoice.pk]),
            {"hanh_dong": "xac_nhan_thanh_toan", "phuong_thuc": "chuyen_khoan"},
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "da_thanh_toan")
        self.client.force_login(self.user)
        self.upload_invoice(invoice, anh_chung_tu=image_upload("third.png"))
        self.assertEqual(ChungTuThanhToan.objects.filter(hoa_don=invoice).count(), 1)

    def test_rejected_invoice_evidence_is_retained_and_retry_is_new_attempt(self):
        invoice = self.invoice()
        self.upload_invoice(invoice, anh_chung_tu=image_upload("first.png"))
        first = ChungTuThanhToan.objects.get(hoa_don=invoice)
        first_path = first.anh.name

        self.client.force_login(self.admin)
        self.client.post(reverse("xu_ly_hoa_don", args=[invoice.pk]), {
            "hanh_dong": "tu_choi_thanh_toan", "ly_do_tu_choi": "Ảnh không khớp",
        })
        first.refresh_from_db()
        self.assertEqual(first.trang_thai, "tu_choi")
        self.assertTrue(private_payment_evidence_storage.exists(first_path))

        self.client.force_login(self.user)
        response = self.upload_invoice(invoice, anh_chung_tu=image_upload("second.png"))
        self.assertRedirects(response, reverse("chi_tiet_hoa_don_cua_toi", args=[invoice.pk]))
        attempts = list(ChungTuThanhToan.objects.filter(hoa_don=invoice).order_by("so_lan"))
        self.assertEqual([(attempt.so_lan, attempt.trang_thai) for attempt in attempts], [(1, "tu_choi"), (2, "cho_doi_soat")])
        self.assertEqual(attempts[0].anh.name, first_path)
        self.assertNotEqual(attempts[1].anh.name, first_path)

    def test_invoice_attempt_identity_and_file_cannot_be_overwritten(self):
        invoice = self.invoice()
        self.upload_invoice(invoice)
        evidence = ChungTuThanhToan.objects.get(hoa_don=invoice)
        evidence.anh = image_upload("replacement.png")
        with self.assertRaises(ValidationError):
            evidence.save()

    def test_invoice_attempt_number_is_unique_per_invoice(self):
        invoice = self.invoice()
        self.upload_invoice(invoice)
        evidence = ChungTuThanhToan.objects.get(hoa_don=invoice)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChungTuThanhToan.objects.create(
                    hoa_don=invoice, so_lan=evidence.so_lan, nguoi_tai_len=self.user,
                    anh=image_upload("duplicate.png"), mime_type="image/png",
                    ma_doi_chieu=f"NDTMOTEL HD{invoice.pk}",
                )

    def test_multiple_pending_invoice_attempts_fail_closed(self):
        invoice = self.invoice()
        self.upload_invoice(invoice)
        ChungTuThanhToan.objects.create(
            hoa_don=invoice, so_lan=2, nguoi_tai_len=self.user,
            anh=image_upload("corrupt-second.png"), mime_type="image/png",
            ma_doi_chieu=f"NDTMOTEL HD{invoice.pk}",
        )
        with self.assertRaises(ValidationError):
            active_invoice_attempt(invoice, for_update=False)

    def test_exactly_one_target_constraint(self):
        booking, payment = self.new_booking()
        invoice = self.invoice()
        target_constraint = next(
            constraint
            for constraint in ChungTuThanhToan._meta.constraints
            if constraint.name == "payment_evidence_exactly_one_target"
        )
        self.assertIsNotNone(target_constraint)
        for invalid in (
            ChungTuThanhToan(
                nguoi_tai_len=self.user,
                anh=image_upload(),
                mime_type="image/png",
                ma_doi_chieu="INVALID-NONE",
            ),
            ChungTuThanhToan(
                giao_dich_coc=payment,
                hoa_don=invoice,
                nguoi_tai_len=self.user,
                anh=image_upload(),
                mime_type="image/png",
                ma_doi_chieu="INVALID-BOTH",
            ),
        ):
            with self.assertRaises(ValidationError):
                invalid.full_clean()

    def test_csrf_and_multipart_contract(self):
        booking, _payment = self.new_booking()
        response = self.client.get(reverse("thanh_toan_coc_cua_toi", args=[booking.pk]))
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="anh_chung_tu"')
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(
            csrf_client.post(
                reverse("thanh_toan_coc_cua_toi", args=[booking.pk]),
                {"action": "report", "anh_chung_tu": image_upload()},
            ).status_code,
            403,
        )


class PrivatePaymentEvidenceMigrationContractTests(Phase5BookingFixture):
    def test_migration_is_additive_for_existing_financial_rows(self):
        booking, payment = self.new_booking()
        invoice = HoaDon.objects.create(
            hop_dong=self.contract(), thang=11, nam=2026, tien_phong=2500000,
            han_thanh_toan=self.today,
        )
        before = {
            "payment": (payment.pk, payment.so_tien, payment.trang_thai),
            "invoice": (invoice.pk, invoice.tien_phong, invoice.trang_thai),
        }
        table_names = set(connection.introspection.table_names())
        self.assertIn(ChungTuThanhToan._meta.db_table, table_names)
        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual((payment.pk, payment.so_tien, payment.trang_thai), before["payment"])
        self.assertEqual((invoice.pk, invoice.tien_phong, invoice.trang_thai), before["invoice"])
