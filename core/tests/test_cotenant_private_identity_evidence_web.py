from io import BytesIO
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponseForbidden
from django.http import Http404
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse

from core.dich_vu.yeu_cau_nguoi_o_cung import approve_request, reject_request
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import ChungTuDanhTinhNguoiOCung, NguoiOCungPhong, PhuLucHopDong
from core.private_storage import private_cotenant_identity_evidence_storage
from core.views_chung_tu_danh_tinh_nguoi_o_cung import xem_chung_tu_danh_tinh_nguoi_o_cung


def image_upload(name="identity.png"):
    payload = BytesIO()
    Image.new("RGB", (8, 8), "white").save(payload, format="PNG")
    return SimpleUploadedFile(name, payload.getvalue(), content_type="image/png")


def csrf_failure(request, reason=""):
    return HttpResponseForbidden("csrf rejected")


class CoTenantPrivateIdentityEvidenceWebTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.private_directory = settings.BASE_DIR / ".test-media" / f"cotenant-web-evidence-{uuid4().hex}"
        self.private_directory.mkdir()
        self.storage_state = dict(private_cotenant_identity_evidence_storage.__dict__)
        private_cotenant_identity_evidence_storage._location = str(self.private_directory)
        private_cotenant_identity_evidence_storage.__dict__.pop("base_location", None)
        private_cotenant_identity_evidence_storage.__dict__.pop("location", None)
        self.request_obj = self.create_request(
            contract=self.contract_obj, tenant=self.tenant, cccd="000000008881",
        )
        self.detail_url = reverse("chi_tiet_hop_dong_cua_toi", args=[self.contract_obj.pk])
        self.upload_url = reverse("tai_chung_tu_danh_tinh_nguoi_o_cung_cua_toi", args=[self.request_obj.pk])
        self.client.force_login(self.user)

    def tearDown(self):
        private_cotenant_identity_evidence_storage.__dict__.clear()
        private_cotenant_identity_evidence_storage.__dict__.update(self.storage_state)
        shutil.rmtree(self.private_directory, ignore_errors=True)
        super().tearDown()

    def create_request(self, *, contract, tenant, cccd):
        from core.dich_vu.yeu_cau_nguoi_o_cung import create_request
        request_obj, _ = create_request(
            contract_id=contract.pk, actor=tenant.tai_khoan,
            idempotency_key=f"web-request-{cccd}", ho_ten="Evidence Candidate",
            cccd=cccd, ngay_vao=self.today,
        )
        return request_obj

    def upload(self, key="web-upload", uploaded=None):
        return self.client.post(self.upload_url, {
            "idempotency_key": key, "evidence": uploaded or image_upload(),
        })

    def test_tenant_uploads_through_service_prg_and_retry_is_idempotent(self):
        with patch("core.views_hop_dong.upload_identity_evidence", wraps=__import__(
            "core.dich_vu.chung_tu_danh_tinh_nguoi_o_cung", fromlist=["upload_identity_evidence"]
        ).upload_identity_evidence) as service:
            response = self.upload()
        self.assertEqual((response.status_code, response["Location"]), (302, self.detail_url))
        service.assert_called_once()
        evidence = ChungTuDanhTinhNguoiOCung.objects.get()
        self.assertEqual((evidence.yeu_cau_nguon_id, evidence.so_phien_ban), (self.request_obj.pk, 1))
        self.upload("web-upload", image_upload("retry.png"))
        self.assertEqual(ChungTuDanhTinhNguoiOCung.objects.count(), 1)
        self.upload("new-version", image_upload("new.png"))
        self.assertEqual(list(ChungTuDanhTinhNguoiOCung.objects.values_list("so_phien_ban", flat=True)), [1, 2])

    def test_download_authorization_headers_and_post_approval_lock(self):
        self.upload()
        evidence = ChungTuDanhTinhNguoiOCung.objects.get()
        url = reverse("xem_chung_tu_danh_tinh_nguoi_o_cung", args=[evidence.pk])
        owner_request = RequestFactory().get(url); owner_request.user = self.user
        response = xem_chung_tu_danh_tinh_nguoi_o_cung(owner_request, evidence.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertNotIn(evidence.tep.name, response.get("Content-Disposition", ""))
        denied = RequestFactory().get(url); denied.user = self.other_user
        anonymous = RequestFactory().get(url); anonymous.user = __import__("django.contrib.auth.models", fromlist=["AnonymousUser"]).AnonymousUser()
        with self.assertRaises(Http404): xem_chung_tu_danh_tinh_nguoi_o_cung(denied, evidence.pk)
        with self.assertRaises(Http404): xem_chung_tu_danh_tinh_nguoi_o_cung(anonymous, evidence.pk)
        approve_request(request_id=self.request_obj.pk, actor=self.admin, expected_revision=1)
        denied_after = RequestFactory().get(url); denied_after.user = self.user
        with self.assertRaises(Http404): xem_chung_tu_danh_tinh_nguoi_o_cung(denied_after, evidence.pk)
        admin_request = RequestFactory().get(url); admin_request.user = self.admin
        admin_response = xem_chung_tu_danh_tinh_nguoi_o_cung(admin_request, evidence.pk)
        self.assertEqual(admin_response.status_code, 200)

    def test_retained_rejected_evidence_missing_file_and_csrf_fail_closed(self):
        csrf_client = Client(enforce_csrf_checks=True); csrf_client.force_login(self.user)
        with override_settings(CSRF_FAILURE_VIEW="core.tests.test_cotenant_private_identity_evidence_web.csrf_failure"):
            self.assertEqual(csrf_client.post(self.upload_url, {"idempotency_key": "csrf", "evidence": image_upload()}).status_code, 403)
        self.upload()
        evidence = ChungTuDanhTinhNguoiOCung.objects.get()
        reject_request(request_id=self.request_obj.pk, actor=self.admin, expected_revision=1, reason="Rejected")
        evidence.refresh_from_db()
        self.assertTrue(evidence.tep.storage.exists(evidence.tep.name))
        url = reverse("xem_chung_tu_danh_tinh_nguoi_o_cung", args=[evidence.pk])
        admin_request = RequestFactory().get(url); admin_request.user = self.admin
        retained_response = xem_chung_tu_danh_tinh_nguoi_o_cung(admin_request, evidence.pk)
        self.assertEqual(retained_response.status_code, 200)
        from unittest.mock import patch
        missing = RequestFactory().get(url); missing.user = self.admin
        with patch.object(evidence.tep.storage, "open", side_effect=FileNotFoundError):
            with self.assertRaises(Http404): xem_chung_tu_danh_tinh_nguoi_o_cung(missing, evidence.pk)

    def test_invalid_upload_and_unrelated_lifecycle_do_not_create_or_bypass_domain_records(self):
        response = self.client.post(self.upload_url, {"idempotency_key": "invalid"})
        self.assertEqual((response.status_code, response["Location"]), (302, self.detail_url))
        self.assertFalse(ChungTuDanhTinhNguoiOCung.objects.exists())
        self.upload()
        self.assertFalse(NguoiOCungPhong.objects.exists())
        self.assertFalse(PhuLucHopDong.objects.exists())
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.trang_thai, "cho_xac_minh")

    def test_terminal_request_does_not_allow_tenant_replacement_upload(self):
        self.upload()
        reject_request(request_id=self.request_obj.pk, actor=self.admin, expected_revision=1, reason="Rejected")
        self.upload("after-terminal")
        self.assertEqual(ChungTuDanhTinhNguoiOCung.objects.count(), 1)
