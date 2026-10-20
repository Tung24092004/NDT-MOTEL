from unittest.mock import patch
from pathlib import Path

from django.db import transaction
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from core.dich_vu.chung_tu_thanh_toan import create_for_invoice
from core.models import ChungTuThanhToan
from core.private_storage import private_payment_evidence_storage
from core.tests.test_private_payment_evidence_post_p6 import PrivatePaymentEvidenceTests, image_upload


class InvoiceAttemptInsertFailureTests(PrivatePaymentEvidenceTests):
    """The service cleans only its new file if ImageField precedes a failed INSERT."""

    def _force_insert_failure(self, invoice):
        original_save = ChungTuThanhToan.save

        def save_then_fail(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)
            raise RuntimeError("forced post-file database failure")

        with patch.object(ChungTuThanhToan, "save", save_then_fail):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    locked = type(invoice).objects.select_for_update().select_related(
                        "hop_dong__dat_phong__nguoi_thue"
                    ).get(pk=invoice.pk)
                    create_for_invoice(actor=self.user, invoice=locked, uploaded=image_upload("failure.png"))

    def test_failed_first_attempt_leaves_no_database_row_or_orphan_file(self):
        invoice = self.invoice()
        self._force_insert_failure(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "chua_thanh_toan")
        self.assertFalse(ChungTuThanhToan.objects.filter(hoa_don=invoice).exists())
        self.assertEqual([path for path in Path(self.private_directory.name).rglob("*") if path.is_file()], [])

    def test_failed_retry_keeps_rejected_attempt_and_its_file(self):
        invoice = self.invoice()
        self.upload_invoice(invoice)
        first = ChungTuThanhToan.objects.get(hoa_don=invoice)
        first_name = first.anh.name
        ChungTuThanhToan.objects.filter(pk=first.pk).update(trang_thai="tu_choi", ghi_chu_doi_soat="reject")
        invoice.trang_thai = "chua_thanh_toan"; invoice.save(update_fields=["trang_thai"])
        self._force_insert_failure(invoice)
        self.assertEqual(list(ChungTuThanhToan.objects.filter(hoa_don=invoice).values_list("pk", "anh", "trang_thai")), [(first.pk, first_name, "tu_choi")])
        self.assertTrue(first.anh.storage.exists(first_name))

    def _post_insert_failure(self, invoice, upload):
        with patch("core.views_thanh_toan.notify_admin_event", side_effect=RuntimeError("forced post-insert failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("thanh_toan_hoa_don_cua_toi", args=[invoice.pk]), {
                    "buoc": "xac_thuc", "phuong_thuc": "chuyen_khoan", "xac_nhan": "dong_y",
                    "anh_chung_tu": upload,
                })

    def test_post_insert_failure_cleans_first_attempt_file_after_db_rollback(self):
        invoice = self.invoice()
        self._post_insert_failure(invoice, image_upload("post-insert.png"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "chua_thanh_toan")
        self.assertFalse(ChungTuThanhToan.objects.filter(hoa_don=invoice).exists())
        self.assertEqual([path for path in Path(self.private_directory.name).rglob("*") if path.is_file()], [])

    def test_post_insert_retry_failure_keeps_only_existing_evidence(self):
        invoice = self.invoice(); self.upload_invoice(invoice)
        first = ChungTuThanhToan.objects.get(hoa_don=invoice)
        snapshot = (first.pk, first.anh.name, first.trang_thai)
        ChungTuThanhToan.objects.filter(pk=first.pk).update(trang_thai="tu_choi", ghi_chu_doi_soat="rejected")
        invoice.trang_thai = "chua_thanh_toan"; invoice.save(update_fields=["trang_thai"])
        self._post_insert_failure(invoice, image_upload("retry-post-insert.png"))
        invoice.refresh_from_db(); first.refresh_from_db()
        self.assertEqual((first.pk, first.anh.name, first.trang_thai), (snapshot[0], snapshot[1], "tu_choi"))
        self.assertEqual(invoice.trang_thai, "chua_thanh_toan")
        self.assertEqual(ChungTuThanhToan.objects.filter(hoa_don=invoice).count(), 1)
        self.assertTrue(first.anh.storage.exists(first.anh.name))

    def test_late_exception_after_commit_never_cleans_committed_evidence(self):
        invoice = self.invoice()
        response = self.upload_invoice(invoice, anh_chung_tu=image_upload("committed.png"))
        self.assertEqual(response.status_code, 302)
        evidence = ChungTuThanhToan.objects.get(hoa_don=invoice)
        committed_name = evidence.anh.name
        self.assertTrue(evidence.anh.storage.exists(committed_name))

        # This is deliberately outside the request transaction and cleanup
        # context: a later caller failure must not own committed evidence.
        with self.assertRaises(RuntimeError):
            raise RuntimeError("forced exception after committed tenant report")

        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, "cho_xac_nhan")
        self.assertEqual(ChungTuThanhToan.objects.filter(hoa_don=invoice).count(), 1)
        evidence.refresh_from_db()
        self.assertEqual(evidence.anh.name, committed_name)
        self.assertTrue(evidence.anh.storage.exists(committed_name))

    def test_post_insert_failure_cleans_storage_returned_name_only(self):
        invoice = self.invoice()
        storage = private_payment_evidence_storage
        original_save = storage.save
        existing_name = original_save("collision/existing.png", ContentFile(b"existing"))

        def save_as_renamed_path(_name, content, max_length=None):
            return original_save("renamed/stored-name.png", content, max_length=max_length)

        with patch.object(storage, "save", side_effect=save_as_renamed_path):
            self._post_insert_failure(invoice, image_upload("client-name.png"))

        self.assertFalse(ChungTuThanhToan.objects.filter(hoa_don=invoice).exists())
        self.assertNotEqual("evidence.png", "renamed/stored-name.png")
        self.assertTrue(storage.exists(existing_name))
        self.assertFalse(storage.exists("renamed/stored-name.png"))
        self.assertEqual(
            [path.relative_to(self.private_directory.name).as_posix() for path in Path(self.private_directory.name).rglob("*") if path.is_file()],
            [existing_name],
        )
