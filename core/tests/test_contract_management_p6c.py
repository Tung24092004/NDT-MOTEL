from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.models import HopDong, PhienBanHopDong, YeuCauGiaHanHopDong


class ContractManagementP6CTests(Phase5BookingFixture):
    def setUp(self):
        super().setUp()
        self.contract_obj = self.contract()

    def test_six_contract_screens_opt_in_without_shared_assets(self):
        self.client.force_login(self.admin)
        admin_urls = (
            reverse("quan_ly_hop_dong"),
            reverse("chi_tiet_hop_dong", args=[self.contract_obj.pk]),
            reverse("sua_hop_dong", args=[self.contract_obj.pk]),
        )
        for url in admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "css/foundation/p5.css")
            self.assertContains(response, "css/contract_management.css")
            self.assertContains(response, "ndt-f5 ndt-contract-management")

        booking = self.booking()
        self.assertEqual(self.client.get(reverse("tao_hop_dong", args=[booking.pk])).status_code, 405)

        self.client.force_login(self.user)
        for url in (
            reverse("hop_dong_cua_toi"),
            reverse("chi_tiet_hop_dong_cua_toi", args=[self.contract_obj.pk]),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "css/foundation/p5.css")
            self.assertContains(response, "ndt-f5 ndt-contract-management")

        for base in ("templates/core/base.html", "templates/core/tenant_base.html"):
            source = Path(settings.BASE_DIR, base).read_text(encoding="utf-8")
            self.assertNotIn("contract_management.css", source)
            self.assertNotIn("foundation/p5.css", source)

    def test_admin_list_mobile_table_has_labels_for_every_cell(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("quan_ly_hop_dong")).content.decode()
        body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        self.assertEqual(body.count("<td"), body.count("data-label="))
        self.assertIn('name="q"', html)
        self.assertIn('name="trang_thai"', html)

    def test_forms_keep_post_field_names_and_p5_dialog(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("sua_hop_dong", args=[self.contract_obj.pk])).content.decode()
        for name in (
            "tien_coc", "tien_thue_thang", "ngay_thanh_toan_hang_thang",
            "phuong_thuc_thanh_toan", "so_nguoi_o", "tien_phat_tre_han",
            "cho_phep_ghep", "dieu_khoan", "ghi_chu",
        ):
            self.assertIn(f'name="{name}"', html)
        self.assertIn("data-ndt-f5-dialog", html)
        self.assertIn("js/foundation/p5-dialog.js", html)
        self.assertNotIn("window.confirm", html)
        self.assertNotIn("js/foundation/dialog.js", html)

    def test_contract_and_renewal_actions_keep_payload_names(self):
        renewal = YeuCauGiaHanHopDong.objects.create(
            hop_dong=self.contract_obj,
            nguoi_yeu_cau=self.tenant,
            so_thang_gia_han=2,
            ngay_ket_thuc_cu=self.contract_obj.ngay_ket_thuc,
            ngay_ket_thuc_de_xuat=self.contract_obj.ngay_ket_thuc,
        )
        self.client.force_login(self.admin)
        html = self.client.get(reverse("chi_tiet_hop_dong", args=[self.contract_obj.pk])).content.decode()
        for value in ('name="hanh_dong" value="huy"', 'name="hanh_dong" value="duyet"', 'name="hanh_dong" value="tu_choi"'):
            self.assertIn(value, html)
        self.assertIn('name="ly_do_huy"', html)
        self.assertIn('name="ghi_chu_admin"', html)
        self.assertIn('name="ly_do_tu_choi"', html)
        self.assertIn("data-ndt-f5-dialog", html)

        self.client.force_login(self.user)
        tenant_html = self.client.get(reverse("chi_tiet_hop_dong_cua_toi", args=[self.contract_obj.pk])).content.decode()
        self.assertIn(reverse("huy_yeu_cau_gia_han", args=[renewal.pk]), tenant_html)
        self.assertIn("data-ndt-f5-dialog", tenant_html)

    def test_get_contract_pages_are_read_only(self):
        before = list(HopDong.objects.values("id", "trang_thai", "ngay_ket_thuc"))
        self.client.force_login(self.admin)
        self.client.get(reverse("quan_ly_hop_dong"))
        self.client.get(reverse("chi_tiet_hop_dong", args=[self.contract_obj.pk]))
        self.client.force_login(self.user)
        self.client.get(reverse("hop_dong_cua_toi"))
        self.client.get(reverse("chi_tiet_hop_dong_cua_toi", args=[self.contract_obj.pk]))
        self.assertEqual(list(HopDong.objects.values("id", "trang_thai", "ngay_ket_thuc")), before)

    def test_cross_role_and_owner_access_remains_blocked(self):
        other_contract = self.contract(tenant=self.other)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("quan_ly_hop_dong")).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("quan_ly_hop_dong")).status_code, 302)
        self.assertEqual(
            self.client.get(reverse("chi_tiet_hop_dong_cua_toi", args=[other_contract.pk])).status_code,
            404,
        )
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("hop_dong_cua_toi")).status_code, 302)

    def pending_contract(self, sent_at=None):
        contract = self.contract(status="cho_nguoi_thue_xac_nhan")
        version = PhienBanHopDong.objects.create(
            hop_dong=contract,
            so_phien_ban=1,
            du_lieu={},
            ma_bam_sha256="a" * 64,
            nguoi_gui=self.admin,
            thoi_diem_gui=sent_at or timezone.now(),
        )
        contract.phien_ban_hien_tai = version
        contract.save(update_fields=["phien_ban_hien_tai"])
        return contract, version

    def test_admin_pending_filter_count_and_review_send_time(self):
        pending, version = self.pending_contract()
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("quan_ly_hop_dong"),
            {"trang_thai": "cho_nguoi_thue_xac_nhan"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["trang_thai"], "cho_nguoi_thue_xac_nhan")
        self.assertEqual(response.context["cho_nguoi_thue_xac_nhan"], 1)
        self.assertEqual(list(response.context["hop_dongs"]), [pending])
        displayed_send_time = timezone.localtime(version.thoi_diem_gui).strftime("%d/%m/%Y %H:%M")
        self.assertContains(response, displayed_send_time)

        detail = self.client.get(reverse("chi_tiet_hop_dong", args=[pending.pk]))
        self.assertContains(detail, displayed_send_time)
        self.assertContains(detail, "Tiền cọc đã xác nhận không được tự động hoàn")

    def test_pending_review_fallback_and_cancellation_copy_are_scoped(self):
        missing_version = self.contract(status="cho_nguoi_thue_xac_nhan")
        other_status = self.contract(status="cho_kich_hoat")
        self.client.force_login(self.admin)

        pending_html = self.client.get(
            reverse("chi_tiet_hop_dong", args=[missing_version.pk])
        ).content.decode()
        self.assertIn("Chưa có thời điểm gửi review để đối chiếu.", pending_html)
        self.assertIn("Tiền cọc đã xác nhận không được tự động hoàn", pending_html)

        pending_list_html = self.client.get(
            reverse("quan_ly_hop_dong"),
            {"trang_thai": "cho_nguoi_thue_xac_nhan"},
        ).content.decode()
        self.assertIn("Chưa có thời điểm gửi review", pending_list_html)

        other_html = self.client.get(
            reverse("chi_tiet_hop_dong", args=[other_status.pk])
        ).content.decode()
        self.assertNotIn("Tiền cọc đã xác nhận không được tự động hoàn", other_html)

        filtered = self.client.get(reverse("quan_ly_hop_dong"), {"trang_thai": "dang_hieu_luc"})
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.context["trang_thai"], "dang_hieu_luc")
        self.assertContains(filtered, self.contract_obj.so_hop_dong)
