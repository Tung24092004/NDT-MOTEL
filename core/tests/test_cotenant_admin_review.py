import threading
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.db import close_old_connections
from django.test import Client, RequestFactory, TransactionTestCase, override_settings
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.dich_vu.yeu_cau_nguoi_o_cung import approve_request
from core.models import (
    CoSo, DanhTinhNguoiOCung, DatPhong, HopDong, NguoiOCungPhong,
    NguoiThue, NhatKyThaoTac, Phong,
    PhuLucHopDong, QuyenRaVao, ThongBao, YeuCauNguoiOCung,
)
from core.views_yeu_cau_nguoi_o_cung import (
    chi_tiet_yeu_cau_nguoi_o_cung,
    quan_ly_yeu_cau_nguoi_o_cung,
)


def csrf_failure_for_admin_cotenant_test(request, reason=""):
    return HttpResponseForbidden("csrf rejected")


class CoTenantAdminReviewTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.queue_url = reverse("quan_ly_yeu_cau_nguoi_o_cung")
        self.client.force_login(self.admin)

    def request_obj(self, key="admin-review", state="cho_xac_minh", revision=1, cccd="000000002221"):
        return YeuCauNguoiOCung.objects.create(
            hop_dong=self.contract_obj, nguoi_yeu_cau=self.tenant,
            ho_ten="Admin Review Candidate", cccd=cccd, ngay_vao=self.today,
            ma_idempotency=key, trang_thai=state, revision=revision,
        )

    def post_url(self, name, request):
        return reverse(name, args=[request.pk])

    def test_non_admin_is_denied_and_queue_render_is_p5_structured(self):
        self.client.force_login(self.user)
        response = self.client.post(self.queue_url, {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tai_khoan"))
        request_obj = self.request_obj()
        response = self.client.post(
            self.post_url("duyet_yeu_cau_nguoi_o_cung", request_obj),
            {"expected_revision": request_obj.revision},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tai_khoan"))
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.trang_thai, "cho_xac_minh")
        request = RequestFactory().get(self.queue_url, {"trang_thai": "cho_xac_minh"})
        request.user = self.admin
        response = quan_ly_yeu_cau_nguoi_o_cung(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"cotenant-request-queue", response.content)

    def test_detail_render_and_service_navigation_link(self):
        request_obj = self.request_obj()
        view_request = RequestFactory().get(
            self.post_url("chi_tiet_yeu_cau_nguoi_o_cung", request_obj)
        )
        view_request.user = self.admin
        response = chi_tiet_yeu_cau_nguoi_o_cung(view_request, request_obj.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"cotenant-request-detail", response.content)
        with open("templates/core/base.html", encoding="utf-8") as template_file:
            base_template = template_file.read()
        self.assertEqual(base_template.count("quan_ly_yeu_cau_nguoi_o_cung"), 3)

    def test_csrf_is_enforced(self):
        request = self.request_obj()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        with override_settings(CSRF_FAILURE_VIEW="core.tests.test_cotenant_admin_review.csrf_failure_for_admin_cotenant_test"):
            self.assertEqual(csrf_client.post(self.post_url("duyet_yeu_cau_nguoi_o_cung", request), {"expected_revision": 1}).status_code, 403)

    def test_supplement_and_blank_reason(self):
        request = self.request_obj()
        url = self.post_url("yeu_cau_nguoi_o_cung_bo_sung", request)
        self.client.post(url, {"expected_revision": 1, "reason": ""})
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision), ("cho_xac_minh", 1))
        response = self.client.post(url, {"expected_revision": 1, "reason": "Cần bản CCCD rõ hơn"})
        self.assertEqual(response.status_code, 302)
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision, request.ly_do), ("cho_bo_sung", 2, "Cần bản CCCD rõ hơn"))

    def test_approve_creates_one_residency_appendix_and_notification(self):
        request = self.request_obj()
        response = self.client.post(self.post_url("duyet_yeu_cau_nguoi_o_cung", request), {"expected_revision": 1})
        self.assertEqual(response.status_code, 302)
        request.refresh_from_db()
        self.assertEqual(request.trang_thai, "da_duyet")
        self.assertIsNotNone(request.residency_id)
        self.assertEqual(NguoiOCungPhong.objects.filter(pk=request.residency_id).count(), 1)
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 1)
        self.assertEqual(ThongBao.objects.filter(ma_tham_chieu=f"COTENANT_REQUEST:{request.pk}:APPROVED").count(), 1)
        self.client.post(self.post_url("duyet_yeu_cau_nguoi_o_cung", request), {"expected_revision": 1})
        self.assertEqual(NguoiOCungPhong.objects.count(), 1)
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 1)
        self.assertEqual(ThongBao.objects.filter(ma_tham_chieu=f"COTENANT_REQUEST:{request.pk}:APPROVED").count(), 1)

    def test_approval_service_requires_admin_and_preserves_pending_request(self):
        request = self.request_obj()
        before = (
            NguoiOCungPhong.objects.count(), DanhTinhNguoiOCung.objects.count(),
            PhuLucHopDong.objects.count(), QuyenRaVao.objects.count(), NhatKyThaoTac.objects.count(),
        )
        with self.assertRaisesRegex(ValidationError, "Khong co quyen"):
            approve_request(request_id=request.pk, actor=self.user, expected_revision=request.revision)
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision, request.residency_id), ("cho_xac_minh", 1, None))
        self.assertEqual(
            (NguoiOCungPhong.objects.count(), DanhTinhNguoiOCung.objects.count(),
             PhuLucHopDong.objects.count(), QuyenRaVao.objects.count(), NhatKyThaoTac.objects.count()),
            before,
        )

    def test_full_room_rejects_approval_without_partial_records(self):
        request = self.request_obj()
        self.room.so_nguoi_toi_da = 1
        self.room.save(update_fields=["so_nguoi_toi_da", "ngay_cap_nhat"])
        before = (
            NguoiOCungPhong.objects.count(), DanhTinhNguoiOCung.objects.count(),
            PhuLucHopDong.objects.count(), QuyenRaVao.objects.count(), NhatKyThaoTac.objects.count(),
        )
        with self.assertRaisesRegex(ValidationError, "suc chua"):
            approve_request(request_id=request.pk, actor=self.admin, expected_revision=request.revision)
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision, request.residency_id), ("cho_xac_minh", 1, None))
        self.assertEqual(
            (NguoiOCungPhong.objects.count(), DanhTinhNguoiOCung.objects.count(),
             PhuLucHopDong.objects.count(), QuyenRaVao.objects.count(), NhatKyThaoTac.objects.count()),
            before,
        )

    def test_duplicate_active_identity_rejects_approval_without_changing_request(self):
        request = self.request_obj(cccd="000000002241")
        NguoiOCungPhong.objects.create(
            hop_dong=self.contract_obj, ho_ten="Existing resident", cccd=request.cccd,
            ngay_vao=self.today, trang_thai="dang_o", da_xac_minh_boi_admin=True,
        )
        with self.assertRaisesRegex(ValidationError, "dang luu tru"):
            approve_request(request_id=request.pk, actor=self.admin, expected_revision=request.revision)
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision, request.residency_id), ("cho_xac_minh", 1, None))

    def test_reject_blank_reason_terminal_and_stale_zero_write(self):
        request = self.request_obj()
        url = self.post_url("tu_choi_yeu_cau_nguoi_o_cung", request)
        self.client.post(url, {"expected_revision": 1, "reason": ""})
        request.refresh_from_db()
        self.assertEqual(request.trang_thai, "cho_xac_minh")
        self.client.post(url, {"expected_revision": 1, "reason": "Không phù hợp"})
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision), ("tu_choi", 2))
        self.client.post(url, {"expected_revision": 1, "reason": "stale"})
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision), ("tu_choi", 2))

    def test_waiting_for_supplement_cannot_be_approved_or_supplemented_again(self):
        request = self.request_obj(state="cho_bo_sung", revision=2)
        self.client.post(self.post_url("duyet_yeu_cau_nguoi_o_cung", request), {"expected_revision": 2})
        self.client.post(self.post_url("yeu_cau_nguoi_o_cung_bo_sung", request), {"expected_revision": 2, "reason": "Again"})
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision), ("cho_bo_sung", 2))
        self.assertFalse(NguoiOCungPhong.objects.exists())

    def test_competing_admin_and_contract_conflict_have_one_safe_outcome(self):
        request = self.request_obj()
        admin_two = User.objects.create_user("admin-two", is_staff=True)
        self.client.post(self.post_url("duyet_yeu_cau_nguoi_o_cung", request), {"expected_revision": 1})
        self.client.force_login(admin_two)
        self.client.post(self.post_url("tu_choi_yeu_cau_nguoi_o_cung", request), {"expected_revision": 1, "reason": "late"})
        request.refresh_from_db()
        self.assertEqual(request.trang_thai, "da_duyet")
        self.assertEqual(NguoiOCungPhong.objects.count(), 1)

        conflict = self.request_obj("expired-contract", cccd="000000002222")
        self.contract_obj.trang_thai = "da_het_han"
        self.contract_obj.save(update_fields=["trang_thai", "ngay_cap_nhat"])
        self.client.post(self.post_url("duyet_yeu_cau_nguoi_o_cung", conflict), {"expected_revision": 1})
        conflict.refresh_from_db()
        self.assertEqual((conflict.trang_thai, conflict.residency_id), ("cho_xac_minh", None))

    def test_queue_filters_and_view_uses_shared_approval_service(self):
        request = self.request_obj()
        view_request = RequestFactory().get(self.queue_url, {"trang_thai": "cho_xac_minh", "phong": self.contract_obj.dat_phong.phong_id})
        view_request.user = self.admin
        response = quan_ly_yeu_cau_nguoi_o_cung(view_request)
        self.assertEqual(response.status_code, 200)
        with patch("core.views_yeu_cau_nguoi_o_cung.approve_request", return_value=(request, False)) as service:
            self.client.post(self.post_url("duyet_yeu_cau_nguoi_o_cung", request), {"expected_revision": 1})
        service.assert_called_once_with(request_id=request.pk, actor=self.admin, expected_revision=1)
        self.assertFalse(NguoiOCungPhong.objects.exists())


class CoTenantApprovalCapacityConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from django.utils import timezone

        self.today = timezone.localdate()
        self.admin = User.objects.create_user("approval-race-admin", is_staff=True)
        tenant_user = User.objects.create_user("approval-race-tenant")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=tenant_user, ho_ten="Approval tenant", cccd="000000002301",
            so_dien_thoai="0900002301",
        )
        facility = CoSo.objects.create(ten_co_so="Approval race", dia_chi="Test", quan="Test")
        self.room = Phong.objects.create(
            co_so=facility, so_phong="APPROVAL-1", gia_thue=Decimal("2500000"),
            dien_tich=Decimal("20"), so_nguoi_toi_da=2,
        )
        booking = DatPhong.objects.create(
            nguoi_thue=self.tenant, phong=self.room, ngay_nhan_phong=self.today,
            ngay_tra_du_kien=self.today + timedelta(days=90), trang_thai="da_duyet",
        )
        self.contract = HopDong.objects.create(
            dat_phong=booking, so_hop_dong="APPROVAL-RACE", ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today + timedelta(days=90),
            tien_thue_thang=Decimal("2500000"), trang_thai="dang_hieu_luc",
        )
        self.requests = [
            YeuCauNguoiOCung.objects.create(
                hop_dong=self.contract, nguoi_yeu_cau=self.tenant,
                ho_ten=f"Candidate {index}", cccd=f"00000000230{index + 2}",
                ngay_vao=self.today, ma_idempotency=f"approval-race-{index}",
                trang_thai="cho_xac_minh", revision=1,
            )
            for index in range(2)
        ]

    def test_competing_approvals_for_last_slot_have_one_winner(self):
        barrier = threading.Barrier(2, timeout=10)
        outcomes = []
        outcome_lock = threading.Lock()

        def approve(request_id):
            close_old_connections()
            try:
                barrier.wait()
                _request, changed = approve_request(
                    request_id=request_id, actor=User.objects.get(pk=self.admin.pk), expected_revision=1,
                )
                outcome = "approved" if changed else "unchanged"
            except ValidationError:
                outcome = "blocked"
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        workers = [threading.Thread(target=approve, args=(request.pk,)) for request in self.requests]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=15)
            self.assertFalse(worker.is_alive(), "approval race timed out")

        self.assertEqual(sorted(outcomes), ["approved", "blocked"])
        self.assertEqual(NguoiOCungPhong.objects.filter(hop_dong=self.contract, trang_thai="dang_o").count(), 1)
        self.assertEqual(YeuCauNguoiOCung.objects.filter(trang_thai="da_duyet").count(), 1)
        self.assertEqual(YeuCauNguoiOCung.objects.filter(trang_thai="cho_xac_minh").count(), 1)
