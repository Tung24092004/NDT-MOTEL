from io import StringIO

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import LichSuRaVao, NguoiOCungPhong, NhatKyThaoTac, QuyenRaVao


class AdminLegacyCompanionFlowTests(BusinessFixture):
    def legacy_resident(self, contract, *, cccd="123456789012", status="dang_o"):
        return NguoiOCungPhong.objects.create(
            hop_dong=contract,
            ho_ten="Legacy companion",
            cccd=cccd,
            ngay_vao=self.today,
            trang_thai=status,
        )

    def test_only_admin_can_view_and_operate_legacy_profile(self):
        resident = self.legacy_resident(self.contract())
        detail = reverse("chi_tiet_nguoi_o_cung", args=[resident.pk])
        action = reverse("xu_ly_nguoi_o_cung", args=[resident.pk])

        self.client.force_login(self.user)
        self.assertEqual(self.client.get(detail).status_code, 302)
        self.client.post(action, {"hanh_dong": "xac_minh"})
        resident.refresh_from_db()
        self.assertFalse(resident.da_xac_minh_boi_admin)

        self.client.force_login(self.admin)
        response = self.client.get(detail)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin xác minh")
        self.assertContains(response, "Yêu cầu bổ sung")
        self.assertContains(response, "Từ chối hồ sơ")
        self.assertContains(response, "không đối chiếu CCCD với cơ sở dữ liệu nhà nước")

    def test_invalid_or_duplicate_cccd_cannot_be_verified(self):
        contract = self.contract()
        invalid = self.legacy_resident(contract, cccd="LEGACY-12345")
        duplicate = self.legacy_resident(contract, cccd=self.other.cccd)
        self.client.force_login(self.admin)

        invalid_page = self.client.get(reverse("chi_tiet_nguoi_o_cung", args=[invalid.pk]))
        self.assertContains(invalid_page, "CCCD phải gồm đúng 9 hoặc 12 chữ số")
        self.client.post(
            reverse("xu_ly_nguoi_o_cung", args=[invalid.pk]),
            {"hanh_dong": "xac_minh"},
        )
        self.client.post(
            reverse("xu_ly_nguoi_o_cung", args=[duplicate.pk]),
            {"hanh_dong": "xac_minh"},
        )
        invalid.refresh_from_db()
        duplicate.refresh_from_db()
        self.assertFalse(invalid.da_xac_minh_boi_admin)
        self.assertFalse(duplicate.da_xac_minh_boi_admin)

    def test_admin_verification_is_explicit_and_audited(self):
        resident = self.legacy_resident(self.contract())
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("xu_ly_nguoi_o_cung", args=[resident.pk]),
            {"hanh_dong": "xac_minh"},
        )
        self.assertEqual(response.status_code, 302)
        resident.refresh_from_db()
        self.assertTrue(resident.da_xac_minh_boi_admin)
        self.assertEqual(resident.trang_thai, "dang_o")
        audit = NhatKyThaoTac.objects.get(
            doi_tuong="NguoiOCungPhong", doi_tuong_id=resident.pk
        )
        self.assertEqual(audit.nguoi_thuc_hien, self.admin)
        self.assertEqual(audit.hanh_dong, "duyet")

    def test_supplement_and_reject_revoke_rights_but_preserve_history(self):
        contract = self.contract()
        self.client.force_login(self.admin)
        for index, action in enumerate(("cho_bo_sung", "tu_choi"), start=1):
            resident = NguoiOCungPhong.objects.create(
                hop_dong=contract,
                ho_ten=f"Resident {index}",
                cccd=f"12345678901{index}",
                ngay_vao=self.today,
                trang_thai="dang_o",
                da_xac_minh_boi_admin=True,
            )
            right = QuyenRaVao.objects.create(
                hop_dong=contract,
                nguon_cap="duyet_ghep",
                phong=self.room,
                nguoi_o_cung=resident,
                loai_quyen="nguoi_o_cung",
                trang_thai="hoat_dong",
                ngay_bat_dau=self.today,
                ngay_ket_thuc=contract.ngay_ket_thuc,
            )
            history = LichSuRaVao.objects.create(
                quyen_ra_vao=right,
                phong=self.room,
                nguoi_o_cung=resident,
                ten_nguoi=resident.ho_ten,
                loai_su_kien="vao",
                nguon="camera",
                thoi_diem=timezone.now(),
            )
            self.client.post(
                reverse("xu_ly_nguoi_o_cung", args=[resident.pk]),
                {"hanh_dong": action},
            )
            resident.refresh_from_db()
            right.refresh_from_db()
            self.assertFalse(resident.da_xac_minh_boi_admin)
            self.assertEqual(
                resident.trang_thai,
                "cho_bo_sung" if action == "cho_bo_sung" else "tu_choi",
            )
            self.assertEqual(right.trang_thai, "bi_thu_hoi")
            self.assertTrue(LichSuRaVao.objects.filter(pk=history.pk).exists())


class RevokeExpiredAccessFollowupTests(BusinessFixture):
    def test_dry_run_reports_each_reason_without_writes(self):
        contract = self.contract()
        invalid = QuyenRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.tenant,
            loai_quyen="chu_phong",
            trang_thai="hoat_dong",
            ngay_bat_dau=self.today,
            nguon_cap="legacy_unknown",
        )
        valid = self.permission(hop_dong=contract)
        output = StringIO()
        call_command("revoke_expired_access", "--dry-run", stdout=output)
        invalid.refresh_from_db()
        valid.refresh_from_db()
        self.assertEqual(invalid.trang_thai, "hoat_dong")
        self.assertEqual(valid.trang_thai, "hoat_dong")
        self.assertIn(f"permission#{invalid.pk}", output.getvalue())
        self.assertIn("nguon_khong_hop_le", output.getvalue())
        self.assertIn("thieu_hop_dong", output.getvalue())

    def test_write_is_idempotent_and_preserves_access_history(self):
        contract = self.contract()
        invalid = QuyenRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.tenant,
            loai_quyen="chu_phong",
            trang_thai="hoat_dong",
            ngay_bat_dau=self.today,
            nguon_cap="legacy_unknown",
        )
        valid = self.permission(hop_dong=contract)
        history = LichSuRaVao.objects.create(
            quyen_ra_vao=invalid,
            phong=self.room,
            nguoi_thue=self.tenant,
            ten_nguoi=self.tenant.ho_ten,
            loai_su_kien="vao",
            nguon="camera",
            thoi_diem=timezone.now(),
        )

        first = StringIO()
        call_command("revoke_expired_access", stdout=first)
        invalid.refresh_from_db()
        valid.refresh_from_db()
        first_note = invalid.ghi_chu
        self.assertEqual(invalid.trang_thai, "bi_thu_hoi")
        self.assertEqual(invalid.ngay_ket_thuc, self.today)
        self.assertEqual(valid.trang_thai, "hoat_dong")
        self.assertTrue(LichSuRaVao.objects.filter(pk=history.pk).exists())
        self.assertEqual(first_note.count("RESIDENCY_ELIGIBILITY"), 1)

        second = StringIO()
        call_command("revoke_expired_access", stdout=second)
        invalid.refresh_from_db()
        self.assertEqual(invalid.ghi_chu, first_note)
        self.assertIn("Revoked 0 access rights", second.getvalue())
