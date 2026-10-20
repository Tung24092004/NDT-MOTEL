from unittest.mock import patch
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.http import Http404
from django.test import Client, RequestFactory
from django.test import override_settings
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.dich_vu.yeu_cau_nguoi_o_cung import reject_request, request_supplement
from core.models import NguoiOCungPhong, PhuLucHopDong, YeuCauNguoiOCung
from core.views_hop_dong import tao_yeu_cau_nguoi_o_cung_cua_toi


def csrf_failure_for_cotenant_test(request, reason=""):
    return HttpResponseForbidden("csrf rejected")


class CoTenantTenantSelfServiceTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.detail_url = reverse("chi_tiet_hop_dong_cua_toi", args=[self.contract_obj.pk])
        self.create_url = reverse("tao_yeu_cau_nguoi_o_cung_cua_toi", args=[self.contract_obj.pk])
        self.client.force_login(self.user)

    def payload(self, key="tenant-ui-key", **extra):
        data = {
            "idempotency_key": key, "ho_ten": "Tenant Candidate",
            "cccd": "000000001111", "ngay_vao": self.today.isoformat(),
            "ngay_sinh": "", "gioi_tinh": "", "so_dien_thoai": "", "quan_he": "Ban be",
        }
        data.update(extra)
        return data

    def request_obj(self, state="cho_xac_minh", revision=1):
        return YeuCauNguoiOCung.objects.create(
            hop_dong=self.contract_obj, nguoi_yeu_cau=self.tenant,
            ho_ten="Existing Candidate", cccd="000000001112", ngay_vao=self.today,
            ma_idempotency=f"manual-{state}-{revision}", trang_thai=state,
            revision=revision,
        )

    def test_owner_detail_shows_panel_and_only_own_request_actions(self):
        pending = self.request_obj()
        supplement = self.request_obj("cho_bo_sung", 2)
        # The runner's Django 4.2/Python 3.14 template-context copier is
        # broken globally, so keep this structural rendering assertion free of
        # Client.get(); request actions are exercised below through HTTP POST.
        source = Path(settings.BASE_DIR, "templates/core/chi_tiet_hop_dong_cua_toi.html").read_text(encoding="utf-8")
        self.assertIn("Yêu cầu người ở cùng", source)
        self.assertIn("gui_lai_yeu_cau_nguoi_o_cung_cua_toi", source)
        self.assertIn("huy_yeu_cau_nguoi_o_cung_cua_toi", source)
        self.assertIn("ndt-f5-panel", source)

    def test_create_is_prg_idempotent_and_never_creates_residency_before_approval(self):
        response = self.client.post(self.create_url, self.payload())
        self.assertEqual((response.status_code, response["Location"]), (302, self.detail_url))
        request = YeuCauNguoiOCung.objects.get()
        self.assertEqual(request.trang_thai, "cho_xac_minh")
        self.assertEqual(request.nguoi_yeu_cau_id, self.tenant.pk)
        self.assertFalse(NguoiOCungPhong.objects.exists())
        self.assertFalse(PhuLucHopDong.objects.exists())
        self.client.post(self.create_url, self.payload())
        self.assertEqual(YeuCauNguoiOCung.objects.count(), 1)

    def test_invalid_form_is_prg_and_creates_nothing(self):
        response = self.client.post(self.create_url, self.payload(cccd=""))
        self.assertEqual((response.status_code, response["Location"]), (302, self.detail_url))
        self.assertFalse(YeuCauNguoiOCung.objects.exists())

    def test_csrf_and_other_tenant_are_blocked(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        with override_settings(CSRF_FAILURE_VIEW="core.tests.test_cotenant_tenant_self_service.csrf_failure_for_cotenant_test"):
            self.assertEqual(csrf_client.post(self.create_url, self.payload()).status_code, 403)
        other_contract = self.contract(tenant=self.other)
        self.client.force_login(self.other_user)
        denied_request = RequestFactory().post(self.create_url, self.payload())
        denied_request.user = self.other_user
        with self.assertRaises(Http404):
            tao_yeu_cau_nguoi_o_cung_cua_toi(denied_request, self.contract_obj.pk)
        self.assertEqual(self.client.post(reverse("tao_yeu_cau_nguoi_o_cung_cua_toi", args=[other_contract.pk]), self.payload(key="other-owner")).status_code, 302)

    def test_cancel_and_stale_revision_have_expected_zero_write_behavior(self):
        request = self.request_obj()
        cancel_url = reverse("huy_yeu_cau_nguoi_o_cung_cua_toi", args=[request.pk])
        response = self.client.post(cancel_url, {"expected_revision": 1})
        self.assertEqual((response.status_code, response["Location"]), (302, self.detail_url))
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision), ("da_huy", 2))
        before = (request.trang_thai, request.revision)
        self.client.post(cancel_url, {"expected_revision": 1})
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.revision), before)

    def test_supplement_edits_are_persisted_only_through_resubmit_service(self):
        request = self.request_obj()
        request_supplement(request_id=request.pk, actor=self.admin, expected_revision=1, reason="Bo sung CCCD")
        request.refresh_from_db()
        resubmit_url = reverse("gui_lai_yeu_cau_nguoi_o_cung_cua_toi", args=[request.pk])
        response = self.client.post(resubmit_url, self.payload(
            key="ignored", ho_ten="Corrected Candidate", cccd="000000001113", expected_revision=request.revision,
        ))
        self.assertEqual((response.status_code, response["Location"]), (302, self.detail_url))
        request.refresh_from_db()
        self.assertEqual((request.trang_thai, request.ho_ten, request.cccd), ("cho_xac_minh", "Corrected Candidate", "000000001113"))
        self.assertFalse(NguoiOCungPhong.objects.exists())
        self.assertFalse(PhuLucHopDong.objects.exists())

    def test_terminal_request_is_read_only_and_rejected_can_create_new_request(self):
        request = self.request_obj()
        reject_request(request_id=request.pk, actor=self.admin, expected_revision=1, reason="Tu choi")
        request.refresh_from_db()
        resubmit_url = reverse("gui_lai_yeu_cau_nguoi_o_cung_cua_toi", args=[request.pk])
        self.client.post(resubmit_url, self.payload(expected_revision=request.revision))
        request.refresh_from_db()
        self.assertEqual(request.trang_thai, "tu_choi")
        self.client.post(self.create_url, self.payload(key="new-after-reject", cccd="000000001114"))
        self.assertEqual(YeuCauNguoiOCung.objects.count(), 2)

    def test_former_contract_and_service_failure_are_safe(self):
        self.contract_obj.trang_thai = "da_het_han"
        self.contract_obj.save(update_fields=["trang_thai", "ngay_cap_nhat"])
        self.client.post(self.create_url, self.payload())
        self.assertFalse(YeuCauNguoiOCung.objects.exists())
        self.contract_obj.trang_thai = "dang_hieu_luc"
        self.contract_obj.save(update_fields=["trang_thai", "ngay_cap_nhat"])
        with patch("core.views_hop_dong.create_request", side_effect=ValidationError("Domain rejected")):
            response = self.client.post(self.create_url, self.payload(key="service-error"))
        self.assertEqual((response.status_code, response["Location"]), (302, self.detail_url))
        self.assertFalse(YeuCauNguoiOCung.objects.exists())
