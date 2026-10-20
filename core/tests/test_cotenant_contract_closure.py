from datetime import timedelta

from django.core.exceptions import ValidationError

from core.dich_vu.luu_tru import cap_nhat_trang_thai_luu_tru
from core.dich_vu.vong_doi_hop_dong import dong_bo_vong_doi_hop_dong
from core.dich_vu.yeu_cau_nguoi_o_cung import (
    approve_request, create_request, direct_admit, leave_residency,
    request_supplement, resubmit_request, return_as_new_residency,
)
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import FaceProfile, NguoiOCungPhong, PhuLucHopDong, QuyenRaVao
from core.views_hop_dong import xu_ly_hop_dong


class CoTenantContractClosureTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()

    def admit(self, cccd, key):
        return direct_admit(
            contract_id=self.contract_obj.pk, actor=self.admin, idempotency_key=key,
            ho_ten=f"Resident {cccd[-2:]}", cccd=cccd, ngay_vao=self.today,
        )[0]

    def access(self, resident):
        return self.permission(
            hop_dong=self.contract_obj, nguoi_thue=None, nguoi_o_cung=resident,
            loai_quyen="nguoi_o_cung", nguon_cap="thu_cong", ngay_ket_thuc=None,
        )

    def test_expiry_closes_every_active_residency_without_per_person_appendices(self):
        first = self.admit("000000006101", "expiry-1")
        second = self.admit("000000006102", "expiry-2")
        profile = FaceProfile.objects.create(
            danh_tinh_nguoi_o_cung=first.identity,
            nguoi_o_cung=first,
            loai_chu_the="nguoi_o_cung",
        )
        first_access, second_access = self.access(first), self.access(second)
        appendix_count = PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count()
        self.contract_obj.ngay_ket_thuc = self.today - timedelta(days=1)
        self.contract_obj.save(update_fields=["ngay_ket_thuc"])
        dong_bo_vong_doi_hop_dong(self.contract_obj, today=self.today)
        for resident, access in ((first, first_access), (second, second_access)):
            resident.refresh_from_db(); access.refresh_from_db()
            self.assertEqual(resident.trang_thai, "da_roi")
            self.assertIsNone(resident.active_identity_key)
            self.assertEqual(access.trang_thai, "het_han")
        self.assertTrue(FaceProfile.objects.filter(pk=profile.pk, nguoi_o_cung=first).exists())
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), appendix_count)
        snapshot = list(NguoiOCungPhong.objects.order_by("pk").values("pk", "trang_thai", "ngay_ra", "active_identity_key"))
        dong_bo_vong_doi_hop_dong(self.contract_obj, today=self.today)
        self.assertEqual(list(NguoiOCungPhong.objects.order_by("pk").values("pk", "trang_thai", "ngay_ra", "active_identity_key")), snapshot)

    def test_cancellation_and_checkout_use_same_closure_and_preserve_history(self):
        resident = self.admit("000000006103", "cancel-1")
        access = self.access(resident)
        response = xu_ly_hop_dong(self.request(self.admin, {"hanh_dong": "huy"}), self.contract_obj.pk)
        self.assertEqual(response.status_code, 302)
        resident.refresh_from_db(); access.refresh_from_db()
        self.assertEqual((resident.trang_thai, access.trang_thai), ("da_roi", "bi_thu_hoi"))

        contract = self.contract()
        resident, _ = direct_admit(
            contract_id=contract.pk, actor=self.admin, idempotency_key="checkout-1",
            ho_ten="Checkout resident", cccd="000000006104", ngay_vao=self.today,
        )
        access = self.permission(hop_dong=contract, nguoi_thue=None, nguoi_o_cung=resident,
            loai_quyen="nguoi_o_cung", nguon_cap="thu_cong", ngay_ket_thuc=None)
        cap_nhat_trang_thai_luu_tru(self.tenant, "da_tra_phong", nguoi_thuc_hien=self.admin, hop_dong=contract)
        resident.refresh_from_db(); access.refresh_from_db()
        self.assertEqual((resident.trang_thai, access.trang_thai), ("da_roi", "bi_thu_hoi"))

    def test_termination_wins_over_leave_return_and_pending_requests_are_not_actionable(self):
        resident = self.admit("000000006105", "race-1")
        leave_residency(residency_id=resident.pk, actor=self.admin, idempotency_key="leave-before-term")
        self.contract_obj.trang_thai = "da_huy"
        self.contract_obj.save(update_fields=["trang_thai"])
        dong_bo_vong_doi_hop_dong(self.contract_obj, today=self.today)
        with self.assertRaisesRegex(ValidationError, "Hop dong|Nguoi thue"):
            return_as_new_residency(residency_id=resident.pk, actor=self.admin, idempotency_key="return-after-term")

        # A separate active contract holds a pending request before expiry.
        contract = self.contract()
        request, _ = create_request(
            contract_id=contract.pk, actor=self.user, idempotency_key="pending-close",
            ho_ten="Pending", cccd="000000006106", ngay_vao=self.today,
        )
        contract.trang_thai = "da_huy"; contract.save(update_fields=["trang_thai"])
        dong_bo_vong_doi_hop_dong(contract, today=self.today)
        with self.assertRaises(ValidationError):
            approve_request(request_id=request.pk, actor=self.admin, expected_revision=1)
        with self.assertRaises(ValidationError):
            request_supplement(request_id=request.pk, actor=self.admin, expected_revision=1, reason="Need document")
        with self.assertRaises(ValidationError):
            resubmit_request(request_id=request.pk, actor=self.user, expected_revision=1, ho_ten="Changed")
        request.refresh_from_db()
        self.assertEqual(request.trang_thai, "cho_xac_minh")
