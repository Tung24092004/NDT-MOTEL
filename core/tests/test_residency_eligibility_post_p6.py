import base64
from datetime import timedelta
from io import BytesIO, StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from core.dich_vu.luu_tru import (
    danh_gia_hop_dong,
    du_dieu_kien_dang_ky_face_id,
    nguoi_o_cung_du_dieu_kien,
    quyen_ra_vao_con_hieu_luc,
)
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import FaceProfile, LichSuRaVao, NguoiOCungPhong, QuyenRaVao
from core.quy_tac_nghiep_vu import eligible_permissions


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "/x8AAusB9Wl2nSQAAAAASUVORK5CYII="
)


class ResidencyEligibilityPostP6Tests(BusinessFixture):
    def profile(self, *, tenant=None, consent=True):
        return FaceProfile.objects.create(
            nguoi_thue=tenant or self.tenant,
            loai_chu_the="nguoi_thue",
            dong_y_du_lieu_khuon_mat=consent,
            trang_thai="chua_co_anh",
        )

    def companion_profile(self, contract, status):
        resident = self.resident(contract, status)
        return resident, FaceProfile.objects.create(
            nguoi_o_cung=resident,
            loai_chu_the="nguoi_o_cung",
            trang_thai="chua_co_anh",
        )

    def test_booking_without_contract_cannot_reach_face_enrollment(self):
        self.booking(status="cho_duyet")
        self.client.force_login(self.user)
        response = self.client.get(reverse("nhan_dien_su_dung_phong"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chưa thể đăng ký Face ID")

    def test_deposit_confirmed_booking_still_needs_effective_contract(self):
        self.booking(status="da_duyet")
        self.client.force_login(self.user)
        response = self.client.get(reverse("nhan_dien_su_dung_phong"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FaceProfile.objects.filter(nguoi_thue=self.tenant).exists())

    def test_future_contract_is_ineligible(self):
        contract = self.contract(
            status="cho_hieu_luc",
            start=self.today + timedelta(days=1),
            end=self.today + timedelta(days=60),
        )
        result = du_dieu_kien_dang_ky_face_id(self.profile(), contract)
        self.assertFalse(result.du_dieu_kien)
        self.assertEqual(danh_gia_hop_dong(contract).ma_trang_thai, "chua_hieu_luc")

    def test_active_contract_residency_and_consent_are_eligible(self):
        contract = self.contract()
        result = du_dieu_kien_dang_ky_face_id(self.profile(), contract)
        self.assertTrue(result.du_dieu_kien)

    def test_expired_contract_blocks_tenant(self):
        contract = self.contract(
            status="da_het_han",
            start=self.today - timedelta(days=60),
            end=self.today - timedelta(days=1),
        )
        result = du_dieu_kien_dang_ky_face_id(self.profile(), contract)
        self.assertFalse(result.du_dieu_kien)
        self.assertIn("hết hạn", result.ly_do)

    def test_unverified_companion_is_blocked(self):
        contract = self.contract()
        resident, profile = self.companion_profile(contract, "cho_xac_minh")
        self.assertFalse(nguoi_o_cung_du_dieu_kien(resident))
        self.assertIn("chờ Admin", du_dieu_kien_dang_ky_face_id(profile, contract).ly_do)

    def test_companion_on_expired_contract_is_blocked(self):
        contract = self.contract(
            status="da_het_han",
            start=self.today - timedelta(days=60),
            end=self.today - timedelta(days=1),
        )
        resident, _ = self.companion_profile(contract, "dang_o")
        self.assertFalse(nguoi_o_cung_du_dieu_kien(resident))

    def test_legacy_active_status_is_not_treated_as_admin_verified(self):
        contract = self.contract()
        resident = NguoiOCungPhong.objects.create(
            hop_dong=contract,
            ho_ten="Legacy resident",
            ngay_vao=self.today,
            trang_thai="dang_o",
        )
        self.assertFalse(resident.da_xac_minh_boi_admin)
        self.assertFalse(nguoi_o_cung_du_dieu_kien(resident))

    def test_retired_legacy_verify_path_fails_closed(self):
        contract = self.contract()
        resident = NguoiOCungPhong.objects.create(
            hop_dong=contract,
            ho_ten="Legacy resident",
            cccd="123456789012",
            ngay_vao=self.today,
            trang_thai="dang_o",
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("xu_ly_nguoi_o_cung", args=[resident.pk]),
            {"hanh_dong": "xac_minh"},
        )
        self.assertEqual(response.status_code, 302)
        resident.refresh_from_db()
        self.assertFalse(resident.da_xac_minh_boi_admin)
        self.assertFalse(nguoi_o_cung_du_dieu_kien(resident))
        self.assertFalse(FaceProfile.objects.filter(nguoi_o_cung=resident).exists())
        self.assertFalse(QuyenRaVao.objects.filter(nguoi_o_cung=resident).exists())

    def test_tenant_contract_shows_companion_eligibility_without_face_image(self):
        contract = self.contract()
        resident = self.resident(contract, "dang_o")
        profile = FaceProfile.objects.create(
            nguoi_o_cung=resident,
            loai_chu_the="nguoi_o_cung",
            trang_thai="chua_co_anh",
            anh_dai_dien="face_profiles/companion-private.png",
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("chi_tiet_hop_dong_cua_toi", args=[contract.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Đã được Admin xác minh")
        self.assertContains(response, "Ảnh Face ID của người ở cùng không được hiển thị")
        self.assertNotContains(response, reverse("face_profile_image", args=[profile.pk]))

    def test_departed_companion_is_blocked(self):
        contract = self.contract()
        resident, _ = self.companion_profile(contract, "da_roi")
        resident.ngay_ra = self.today
        resident.save(update_fields=["ngay_ra"])
        self.assertFalse(nguoi_o_cung_du_dieu_kien(resident))

    def test_other_tenant_cannot_operate_foreign_face_profile(self):
        self.contract()
        profile = self.profile()
        self.client.force_login(self.other_user)
        response = self.client.post(reverse("face_id_dang_ky", args=[profile.pk]), {"image": "x"})
        self.assertEqual(response.status_code, 403)

    def test_admin_keeps_existing_face_management_access(self):
        self.contract()
        profile = self.profile()
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(reverse("chi_tiet_face_profile", args=[profile.pk])).status_code,
            200,
        )

    def test_expired_access_right_cannot_open_door(self):
        contract = self.contract()
        right = self.permission(
            hop_dong=contract,
            ngay_ket_thuc=self.today - timedelta(days=1),
        )
        self.assertFalse(quyen_ra_vao_con_hieu_luc(right))
        self.assertFalse(eligible_permissions(QuyenRaVao.objects.filter(pk=right.pk)).exists())

    def test_command_dry_run_does_not_write_or_delete_history(self):
        contract = self.contract(
            status="da_het_han",
            start=self.today - timedelta(days=60),
            end=self.today - timedelta(days=1),
        )
        right = self.permission(hop_dong=contract)
        history = LichSuRaVao.objects.create(
            quyen_ra_vao=right,
            phong=self.room,
            nguoi_thue=self.tenant,
            ten_nguoi=self.tenant.ho_ten,
            loai_su_kien="vao",
            nguon="camera",
            thoi_diem=timezone.now(),
        )
        output = StringIO()
        call_command("revoke_expired_access", "--dry-run", stdout=output)
        right.refresh_from_db()
        self.assertEqual(right.trang_thai, "hoat_dong")
        self.assertTrue(LichSuRaVao.objects.filter(pk=history.pk).exists())
        self.assertIn("no writes", output.getvalue())

    def test_command_is_idempotent(self):
        contract = self.contract(
            status="da_het_han",
            start=self.today - timedelta(days=60),
            end=self.today - timedelta(days=1),
        )
        right = self.permission(hop_dong=contract)
        call_command("revoke_expired_access", stdout=StringIO())
        right.refresh_from_db()
        first_note = right.ghi_chu
        self.assertEqual(right.trang_thai, "het_han")
        call_command("revoke_expired_access", stdout=StringIO())
        right.refresh_from_db()
        self.assertEqual(right.ghi_chu, first_note)
        self.assertEqual(right.ghi_chu.count("RESIDENCY_ELIGIBILITY"), 1)

    def test_contract_warning_boundaries_five_and_two_days(self):
        contract = self.contract(
            status="sap_het_han",
            start=self.today - timedelta(days=30),
            end=self.today + timedelta(days=5),
        )
        warning = danh_gia_hop_dong(contract)
        self.assertEqual((warning.so_ngay_con_lai, warning.muc_canh_bao), (5, "canh_bao"))
        contract.ngay_ket_thuc = self.today + timedelta(days=2)
        high = danh_gia_hop_dong(contract)
        self.assertEqual((high.so_ngay_con_lai, high.muc_canh_bao), (2, "cao"))

    def test_face_image_remains_private_and_object_scoped(self):
        profile = self.profile()
        profile.anh_dai_dien = "face_profiles/private.png"
        profile.save(update_fields=["anh_dai_dien"])
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(reverse("face_profile_image", args=[profile.pk])).status_code,
            404,
        )
        self.client.logout()
        self.client.force_login(self.user)
        with patch("django.db.models.fields.files.FieldFile.open", return_value=BytesIO(PNG_BYTES)):
            own = self.client.get(reverse("face_profile_image", args=[profile.pk]))
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own["Cache-Control"], "private, no-store")
