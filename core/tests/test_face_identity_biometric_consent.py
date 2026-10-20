from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test import RequestFactory
from unittest.mock import patch
import numpy as np

from core.dich_vu.dong_y_sinh_trac_hoc import (
    has_effective_consent,
    record_consent,
    withdraw_consent,
)
from core.dich_vu.luu_tru import du_dieu_kien_dang_ky_face_id
from core.dich_vu.yeu_cau_nguoi_o_cung import direct_admit, leave_residency, return_as_new_residency
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import FaceProfile, QuyenRaVao, SuKienDongYSinhTracHoc
from core.dich_vu.quyen_ra_vao import grant_access
from core.views_smart_room import face_id_xac_thuc


class IdentityBiometricConsentTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.resident, _ = direct_admit(
            contract_id=self.contract_obj.pk,
            actor=self.admin,
            idempotency_key="biometric-foundation-resident",
            ho_ten="Biometric companion",
            cccd="000000009501",
            ngay_vao=self.today,
        )

    def _profile(self):
        return FaceProfile.objects.create(
            danh_tinh_nguoi_o_cung=self.resident.identity,
            nguoi_o_cung=self.resident,  # historical provenance only
            loai_chu_the="nguoi_o_cung",
            trang_thai="da_xac_thuc",
            dong_y_du_lieu_khuon_mat=True,
        )

    def test_admin_consent_is_append_only_and_idempotent(self):
        event, created = record_consent(identity_id=self.resident.identity_id, actor=self.admin)
        retry, repeated = record_consent(identity_id=self.resident.identity_id, actor=self.admin)
        self.assertTrue(created)
        self.assertFalse(repeated)
        self.assertEqual(event.pk, retry.pk)
        self.assertTrue(has_effective_consent(self.resident.identity))
        withdrawn, changed = withdraw_consent(identity_id=self.resident.identity_id, actor=self.admin)
        self.assertTrue(changed)
        self.assertEqual(withdrawn.su_kien, "rut_lai")
        self.assertFalse(has_effective_consent(self.resident.identity))
        self.assertEqual(SuKienDongYSinhTracHoc.objects.count(), 2)

    def test_tenant_cannot_proxy_consent(self):
        with self.assertRaises(PermissionDenied):
            record_consent(identity_id=self.resident.identity_id, actor=self.tenant.tai_khoan)
        self.assertFalse(SuKienDongYSinhTracHoc.objects.exists())

    def test_identity_profile_requires_consent_but_never_grants_access(self):
        profile = self._profile()
        self.assertFalse(du_dieu_kien_dang_ky_face_id(profile).du_dieu_kien)
        self.assertFalse(QuyenRaVao.objects.exists())
        record_consent(identity_id=self.resident.identity_id, actor=self.admin)
        self.assertTrue(du_dieu_kien_dang_ky_face_id(profile).du_dieu_kien)
        self.assertFalse(QuyenRaVao.objects.exists())
        right, _ = grant_access(
            contract_id=self.contract_obj.pk, resident_id=self.resident.pk,
            source="thu_cong", actor=self.admin,
        )
        withdraw_consent(identity_id=self.resident.identity_id, actor=self.admin)
        right.refresh_from_db()
        self.assertEqual(right.trang_thai, "hoat_dong")
        self.assertEqual(QuyenRaVao.objects.count(), 1)

    def test_identity_profile_survives_leave_and_return_without_reassignment(self):
        profile = self._profile()
        record_consent(identity_id=self.resident.identity_id, actor=self.admin)
        leave_residency(residency_id=self.resident.pk, actor=self.admin, idempotency_key="bio-leave")
        new_resident, _ = return_as_new_residency(
            residency_id=self.resident.pk, actor=self.admin,
            idempotency_key="bio-return", entry_date=self.today,
        )
        profile.refresh_from_db()
        self.resident.refresh_from_db()
        self.assertNotEqual(new_resident.pk, self.resident.pk)
        self.assertEqual(profile.danh_tinh_nguoi_o_cung_id, new_resident.identity_id)
        self.assertEqual(profile.nguoi_o_cung_id, self.resident.pk)

    def test_database_prevents_duplicate_identity_profile_and_invalid_subject(self):
        self._profile()
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                FaceProfile.objects.create(
                    danh_tinh_nguoi_o_cung=self.resident.identity,
                    loai_chu_the="nguoi_o_cung",
                )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                FaceProfile.objects.create(loai_chu_the="nguoi_o_cung")

    def test_withdrawal_excludes_identity_profile_from_recognition_without_revoking_access(self):
        profile = self._profile()
        profile.face_encoding = "stored"
        profile.save(update_fields=["face_encoding"])
        record_consent(identity_id=self.resident.identity_id, actor=self.admin)
        right, _ = grant_access(
            contract_id=self.contract_obj.pk, resident_id=self.resident.pk,
            source="thu_cong", actor=self.admin,
        )
        withdraw_consent(identity_id=self.resident.identity_id, actor=self.admin)
        request = RequestFactory().post("/face/verify/", {
            "image": "frame", "phong": self.contract_obj.dat_phong.phong_id,
            "loai_su_kien": "vao",
        })
        request.user = self.admin
        with patch("core.views_smart_room._face_image_from_base64", return_value=np.full((480, 640, 3), 128, dtype=np.uint8)), patch(
            "core.views_smart_room._face_load_models", return_value=(object(), object())
        ), patch("core.views_smart_room._face_detect", return_value=object()), patch(
            "core.views_smart_room._face_feature", return_value=object()
        ):
            response = face_id_xac_thuc(request)
        self.assertEqual(response.status_code, 403)
        right.refresh_from_db()
        self.assertEqual(right.trang_thai, "hoat_dong")
