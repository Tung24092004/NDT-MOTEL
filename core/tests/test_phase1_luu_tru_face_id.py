from datetime import timedelta
import base64
import json
from contextlib import ExitStack
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.dich_vu.luu_tru import cap_nhat_trang_thai_luu_tru
from core.models import FaceProfile, LichSuRaVao
from core.quy_tac_nghiep_vu import eligible_permissions


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "/x8AAusB9Wl2nSQAAAAASUVORK5CYII="
)


class Phase1ResidencyFaceIdTests(BusinessFixture):
    def _face_file(self, name="audit.png"):
        return SimpleUploadedFile(name, PNG_BYTES, content_type="image/png")

    def _read_streaming_response(self, response):
        return b"".join(response.streaming_content)

    def _recognize(self, room=None):
        mocks = {
            "_face_image_from_base64": object(),
            "_face_load_models": (object(), object()),
            "_face_detect": object(),
            "_face_feature": object(),
            "_face_feature_from_text": object(),
            "_face_compare": .9,
        }
        from core.du_lieu_test import tap_hop_views as views

        with ExitStack() as stack:
            for name, value in mocks.items():
                stack.enter_context(
                    patch(
                        "core.views_smart_room." + name,
                        return_value=value,
                    )
                )
            response = views.face_id_xac_thuc(
                self.request(
                    self.admin,
                    {
                        "image": "test",
                        "phong": str((room or self.room).pk),
                    },
                )
            )

        return json.loads(response.content)

    def test_tenant_cannot_view_other_face_profile(self):
        profile = FaceProfile.objects.create(
            nguoi_thue=self.other,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            anh_dai_dien=self._face_file("other.png"),
            dong_y_du_lieu_khuon_mat=True,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("chi_tiet_face_profile", args=[profile.pk])
        )

        self.assertEqual(response.status_code, 404)

        image_response = self.client.get(
            reverse("face_profile_image", args=[profile.pk])
        )
        self.assertEqual(image_response.status_code, 404)

    def test_guest_cannot_view_face_profile_or_image(self):
        profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            anh_dai_dien=self._face_file("tenant.png"),
            dong_y_du_lieu_khuon_mat=True,
        )

        detail_response = self.client.get(
            reverse("chi_tiet_face_profile", args=[profile.pk])
        )
        image_response = self.client.get(
            reverse("face_profile_image", args=[profile.pk])
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(image_response.status_code, 404)

    def test_admin_room_screen_shows_current_tenant_face_id(self):
        self.contract()
        profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            anh_dai_dien=self._face_file("tenant-admin.png"),
            dong_y_du_lieu_khuon_mat=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("sua_phong", args=[self.room.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit Tenant")
        self.assertContains(response, "Đã xác thực")
        image_url = reverse("face_profile_image", args=[profile.pk])
        self.assertContains(response, image_url)

        image_response = self.client.get(image_url)
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response["Content-Type"], "image/png")
        self.assertEqual(image_response["Cache-Control"], "private, no-store")
        self.assertEqual(image_response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self._read_streaming_response(image_response), PNG_BYTES)

        legacy_response = self.client.get(
            reverse("face_profile_media", args=[profile.anh_dai_dien.name.removeprefix("face_profiles/")])
        )
        self.assertEqual(legacy_response.status_code, 404)

    def test_owner_can_read_own_face_image(self):
        profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            anh_dai_dien=self._face_file("owner.png"),
            dong_y_du_lieu_khuon_mat=True,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("face_profile_image", args=[profile.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self._read_streaming_response(response), PNG_BYTES)

    def test_owner_can_view_own_face_profile_detail(self):
        profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="co_anh",
            anh_dai_dien=self._face_file("owner-detail.png"),
            dong_y_du_lieu_khuon_mat=True,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("chi_tiet_face_profile", args=[profile.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("face_profile_image", args=[profile.pk]))

    def test_tenant_cannot_view_face_profile_admin_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("quan_ly_face_profile"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith(reverse("tai_khoan")))

    def test_missing_face_image_returns_safe_404(self):
        profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            anh_dai_dien="face_profiles/missing.png",
            dong_y_du_lieu_khuon_mat=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("face_profile_image", args=[profile.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(str(settings.MEDIA_ROOT), response.content.decode(errors="ignore"))

    def test_legacy_face_media_and_traversal_are_blocked(self):
        self.client.force_login(self.admin)

        legacy_response = self.client.get("/media/face_profiles/owner.png")
        traversal_response = self.client.get("/media/face_profiles/../db.sqlite3")

        self.assertEqual(legacy_response.status_code, 404)
        self.assertEqual(traversal_response.status_code, 404)

    def test_face_registration_requires_backend_consent(self):
        self.contract()
        profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="chua_co_anh",
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("face_id_dang_ky", args=[profile.pk]),
            {"image": "test"},
        )

        profile.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(profile.dong_y_du_lieu_khuon_mat)
        self.assertIsNone(profile.thoi_diem_dong_y_du_lieu_khuon_mat)

    def test_admin_create_face_profile_requires_backend_consent(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("tao_face_profile"),
            {
                "nguoi_thue": str(self.tenant.pk),
                "nguoi_o_cung": "",
                "loai_chu_the": "nguoi_thue",
                "ghi_chu": "no consent",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(FaceProfile.objects.filter(nguoi_thue=self.tenant).exists())

    def test_temporary_absence_keeps_access_permission(self):
        self.contract()
        permission = self.permission()
        FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            face_encoding="audit-vector",
            dong_y_du_lieu_khuon_mat=True,
        )

        revoked = cap_nhat_trang_thai_luu_tru(
            self.tenant,
            "tam_vang",
            nguoi_thuc_hien=self.admin,
        )

        permission.refresh_from_db()
        self.assertEqual(revoked, 0)
        self.assertEqual(permission.trang_thai, "hoat_dong")
        self.assertEqual(self._recognize()["access"], "granted")

    def test_face_profile_without_consent_is_not_used_for_access(self):
        self.contract()
        self.permission()
        profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            face_encoding="audit-vector",
        )

        result = self._recognize()

        self.assertEqual(result["access"], "denied")
        self.assertTrue(FaceProfile.objects.filter(pk=profile.pk).exists())
        self.assertEqual(LichSuRaVao.objects.filter(nguoi_thue=self.tenant).count(), 0)

    def test_admin_room_get_does_not_overwrite_checked_out_status(self):
        self.contract()
        self.tenant.trang_thai_luu_tru = "da_tra_phong"
        self.tenant.save(update_fields=["trang_thai_luu_tru"])

        self.client.force_login(self.admin)
        response = self.client.get(reverse("sua_phong", args=[self.room.pk]))

        self.tenant.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.tenant.trang_thai_luu_tru, "da_tra_phong")

    def test_near_expiry_contract_does_not_mark_tenant_as_checked_out(self):
        self.contract(
            status="sap_het_han",
            start=self.today - timedelta(days=60),
            end=self.today + timedelta(days=5),
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("sua_phong", args=[self.room.pk]))

        self.tenant.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.tenant.trang_thai_luu_tru, "dang_o")

    def test_cancelled_or_expired_contract_cannot_use_access_permission(self):
        contract = self.contract()
        permission = self.permission()

        for status, start, end in (
            ("da_huy", self.today - timedelta(days=5), self.today + timedelta(days=5)),
            ("da_het_han", self.today - timedelta(days=10), self.today - timedelta(days=1)),
        ):
            with self.subTest(status=status):
                contract.trang_thai = status
                contract.ngay_bat_dau = start
                contract.ngay_ket_thuc = end
                contract.save(update_fields=[
                    "trang_thai",
                    "ngay_bat_dau",
                    "ngay_ket_thuc",
                ])

                self.assertFalse(
                    eligible_permissions(type(permission).objects.filter(pk=permission.pk)).exists()
                )

    def test_checkout_revokes_access_but_keeps_account_login(self):
        self.contract(
            start=self.today - timedelta(days=30),
            end=self.today + timedelta(days=30),
        )
        permission = self.permission()
        FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            face_encoding="audit-vector",
            dong_y_du_lieu_khuon_mat=True,
        )

        revoked = cap_nhat_trang_thai_luu_tru(
            self.tenant,
            "da_tra_phong",
            nguoi_thuc_hien=self.admin,
        )

        permission.refresh_from_db()
        self.assertEqual(revoked, 1)
        self.assertEqual(permission.trang_thai, "bi_thu_hoi")
        self.assertEqual(self._recognize()["access"], "denied")

        self.client.force_login(self.user)
        account_response = self.client.get(reverse("tai_khoan"))
        self.assertEqual(account_response.status_code, 200)

        self.assertEqual(
            LichSuRaVao.objects.filter(nguoi_thue=self.tenant).count(),
            0,
        )
