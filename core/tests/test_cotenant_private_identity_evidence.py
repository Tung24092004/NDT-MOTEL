from io import BytesIO
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from core.dich_vu.chung_tu_danh_tinh_nguoi_o_cung import upload_identity_evidence
from core.dich_vu.vong_doi_hop_dong import dong_bo_vong_doi_hop_dong
from core.dich_vu.yeu_cau_nguoi_o_cung import (
    approve_request, cancel_request, create_request, leave_residency, reject_request,
)
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import ChungTuDanhTinhNguoiOCung, FaceProfile, NguoiOCungPhong
from core.private_storage import private_cotenant_identity_evidence_storage


def image_upload(name="identity.png", image_format="PNG"):
    payload = BytesIO()
    Image.new("RGB", (8, 8), "white").save(payload, format=image_format)
    return SimpleUploadedFile(name, payload.getvalue(), content_type="image/png")


class CoTenantPrivateIdentityEvidenceTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        directory = settings.BASE_DIR / ".test-media" / f"cotenant-evidence-{uuid4().hex}"
        directory.mkdir()
        self.private_directory = SimpleNamespace(name=str(directory))
        self.storage_state = dict(private_cotenant_identity_evidence_storage.__dict__)
        private_cotenant_identity_evidence_storage._location = self.private_directory.name
        private_cotenant_identity_evidence_storage.__dict__.pop("base_location", None)
        private_cotenant_identity_evidence_storage.__dict__.pop("location", None)
        self.request_obj, _ = create_request(
            contract_id=self.contract_obj.pk, actor=self.user, idempotency_key="identity-request",
            ho_ten="Evidence candidate", cccd="000000007101", ngay_vao=self.today,
        )

    def tearDown(self):
        private_cotenant_identity_evidence_storage.__dict__.clear()
        private_cotenant_identity_evidence_storage.__dict__.update(self.storage_state)
        shutil.rmtree(self.private_directory.name)
        super().tearDown()

    def upload(self, key="evidence-key", uploaded=None, actor=None):
        return upload_identity_evidence(
            request_id=self.request_obj.pk, actor=actor or self.user,
            idempotency_key=key, uploaded=uploaded or image_upload(),
        )

    def test_private_upload_resolves_identity_and_safe_random_storage_name(self):
        evidence, created = self.upload(uploaded=image_upload(r"..\\evil\\identity.png"))
        self.assertTrue(created)
        self.assertEqual(evidence.yeu_cau_nguon_id, self.request_obj.pk)
        self.assertEqual(evidence.danh_tinh.cccd, self.request_obj.cccd)
        self.assertFalse(str(evidence.tep.name).startswith("/"))
        self.assertRegex(Path(evidence.tep.name).name, r"^[0-9a-f]{32}\.png$")
        self.assertTrue(evidence.tep.storage.exists(evidence.tep.name))
        self.assertNotIn(str(settings.MEDIA_ROOT), str(evidence.tep.storage.location))

    def test_validation_rejects_spoofed_invalid_unsupported_and_oversize_files(self):
        fake = SimpleUploadedFile("identity.png", b"not image", content_type="image/png")
        with self.assertRaises(ValidationError): self.upload("fake", fake)
        with self.assertRaises(ValidationError): self.upload("mismatch", image_upload("identity.jpg", "PNG"))
        with self.assertRaises(ValidationError): self.upload("unsupported", image_upload("identity.gif", "PNG"))
        large = SimpleUploadedFile("large.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
        with self.assertRaises(ValidationError): self.upload("large", large)
        self.assertFalse(ChungTuDanhTinhNguoiOCung.objects.exists())

    def test_versions_are_immutable_and_retry_creates_no_duplicate(self):
        first, created = self.upload("retry-key")
        retry, created_retry = self.upload("retry-key", image_upload("ignored.png"))
        self.assertTrue(created); self.assertFalse(created_retry); self.assertEqual(first.pk, retry.pk)
        second, created_second = self.upload("replacement-key", image_upload("replacement.png"))
        self.assertTrue(created_second)
        self.assertEqual((first.so_phien_ban, second.so_phien_ban), (1, 2))
        self.assertTrue(first.tep.storage.exists(first.tep.name))
        second.tep = image_upload("overwrite.png")
        with self.assertRaises(ValidationError): second.save()

    def test_permissions_and_failure_cleanup_are_safe(self):
        with self.assertRaises(PermissionDenied): self.upload(actor=self.other_user)
        original_save = ChungTuDanhTinhNguoiOCung.save
        def save_then_fail(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)
            raise RuntimeError("db failed")
        with patch.object(ChungTuDanhTinhNguoiOCung, "save", autospec=True, side_effect=save_then_fail):
            with self.assertRaisesRegex(RuntimeError, "db failed"):
                self.upload("db-fail")
        self.assertFalse(ChungTuDanhTinhNguoiOCung.objects.exists())
        self.assertEqual([p for p in Path(self.private_directory.name).rglob("*") if p.is_file()], [])
        with patch.object(private_cotenant_identity_evidence_storage, "save", side_effect=OSError("storage failed")):
            with self.assertRaisesRegex(OSError, "storage failed"):
                self.upload("file-fail")
        self.assertFalse(ChungTuDanhTinhNguoiOCung.objects.exists())

    def test_lifecycle_does_not_delete_historical_identity_evidence_or_touch_face(self):
        evidence, _ = self.upload()
        stored_name = evidence.tep.name
        cancel_request(request_id=self.request_obj.pk, actor=self.user, expected_revision=1)
        rejected_request, _ = create_request(
            contract_id=self.contract_obj.pk, actor=self.user, idempotency_key="rejected-evidence-request",
            ho_ten="Rejected evidence", cccd=self.request_obj.cccd, ngay_vao=self.today,
        )
        rejected_evidence, _ = upload_identity_evidence(
            request_id=rejected_request.pk, actor=self.user, idempotency_key="rejected-evidence", uploaded=image_upload(),
        )
        reject_request(request_id=rejected_request.pk, actor=self.admin, expected_revision=1, reason="Not enough")
        request2, _ = create_request(
            contract_id=self.contract_obj.pk, actor=self.user, idempotency_key="approved-evidence-request",
            ho_ten="Approved evidence", cccd=self.request_obj.cccd, ngay_vao=self.today,
        )
        approved, changed = approve_request(request_id=request2.pk, actor=self.admin, expected_revision=1)
        self.assertTrue(changed)
        leave_residency(residency_id=approved.residency_id, actor=self.admin, idempotency_key="evidence-leave")
        self.contract_obj.trang_thai = "da_huy"
        self.contract_obj.save(update_fields=["trang_thai"])
        dong_bo_vong_doi_hop_dong(self.contract_obj, today=self.today)
        evidence.refresh_from_db()
        self.assertTrue(evidence.tep.storage.exists(stored_name))
        self.assertEqual(ChungTuDanhTinhNguoiOCung.objects.count(), 2)
        self.assertTrue(rejected_evidence.tep.storage.exists(rejected_evidence.tep.name))
        self.assertFalse(FaceProfile.objects.exists())
        self.assertEqual(NguoiOCungPhong.objects.get().trang_thai, "da_roi")
        self.assertNotIn("payment", evidence._meta.db_table)
