from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.urls import resolve, reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import (
    CoSo,
    DatPhong,
    HopDong,
    LichSuRaVao,
    NguoiOCungPhong,
    Phong,
    QuyenRaVao,
)
from core.views_smart_room import quyen_va_lich_su_ra_vao_cua_toi


class TenantAccessStatusHistoryContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(settings.BASE_DIR)
        cls.template = (
            root / "templates/core/quyen_va_lich_su_ra_vao_cua_toi.html"
        ).read_text(encoding="utf-8")
        cls.css = (
            root / "static/css/tenant_access_history_post_p6.css"
        ).read_text(encoding="utf-8")
        cls.base = (root / "templates/core/base.html").read_text(encoding="utf-8")
        cls.tenant_base = (
            root / "templates/core/tenant_base.html"
        ).read_text(encoding="utf-8")

    def test_route_resolves_to_owner_scoped_read_model(self):
        match = resolve(reverse("quyen_va_lich_su_ra_vao_cua_toi"))
        self.assertEqual(match.func, quyen_va_lich_su_ra_vao_cua_toi)
        self.assertEqual(
            reverse("quyen_va_lich_su_ra_vao_cua_toi"),
            "/tai-khoan/quyen-va-lich-su-ra-vao/",
        )

    def test_template_is_read_only_private_and_p5_scoped(self):
        self.assertIn("css/foundation/p5.css", self.template)
        self.assertIn("css/tenant_access_history_post_p6.css", self.template)
        self.assertIn("ndt-tenant-access-read-model", self.template)
        self.assertNotIn('method="post"', self.template.lower())
        self.assertNotIn("face_profile_image", self.template)
        self.assertNotIn("face_profile_media", self.template)
        self.assertNotIn("ma_the", self.template)
        self.assertNotIn("nguoi_o_cung.", self.template)
        self.assertNotIn("chi_tiet_quyen_ra_vao", self.template)
        self.assertNotIn("chi_tiet_lich_su_ra_vao", self.template)

    def test_assets_and_navigation_are_isolated(self):
        self.assertIn(".ndt-f5.ndt-tenant-access-read-model", self.css)
        self.assertNotIn("!important", self.css)
        self.assertNotIn("url(", self.css)
        route_token = "{% url 'quyen_va_lich_su_ra_vao_cua_toi' %}"
        self.assertIn(route_token, self.base)
        self.assertIn(route_token, self.tenant_base)


class TenantAccessStatusHistoryIntegrationTests(BusinessFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        booking = DatPhong.objects.create(
            nguoi_thue=cls.tenant,
            phong=cls.room,
            ngay_nhan_phong=cls.today,
            ngay_tra_du_kien=cls.today + timedelta(days=90),
            so_thang_thue=3,
            trang_thai="da_duyet",
        )
        cls.own_contract = HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong="ACCESS-OWNER",
            ngay_bat_dau=cls.today,
            ngay_ket_thuc=cls.today + timedelta(days=90),
            tien_thue_thang=Decimal("2500000"),
            trang_thai="dang_hieu_luc",
            cho_phep_ghep=True,
        )
        cls.room.dong_bo_trang_thai()
        cls.own_right = QuyenRaVao.objects.create(
            phong=cls.room,
            nguoi_thue=cls.tenant,
            hop_dong=cls.own_contract,
            nguon_cap="face_id",
            loai_quyen="chu_phong",
            trang_thai="hoat_dong",
            ngay_bat_dau=cls.today,
            ngay_ket_thuc=cls.today + timedelta(days=90),
            ma_the="PRIVATE-PIN-1234",
        )
        cls.own_history = LichSuRaVao.objects.create(
            quyen_ra_vao=cls.own_right,
            phong=cls.room,
            nguoi_thue=cls.tenant,
            loai_su_kien="vao",
            nguon="camera",
            ket_qua="cho_phep",
            thoi_diem=timezone.now(),
            ghi_chu="[CHO PHÉP] OWN-EVENT",
        )
        cls.companion = NguoiOCungPhong.objects.create(
            hop_dong=cls.own_contract,
            ho_ten="PRIVATE COMPANION",
            ngay_vao=cls.today,
            trang_thai="dang_o",
            da_xac_minh_boi_admin=True,
        )
        LichSuRaVao.objects.create(
            phong=cls.room,
            nguoi_o_cung=cls.companion,
            loai_su_kien="vao",
            nguon="camera",
            ket_qua="cho_phep",
            thoi_diem=timezone.now(),
            ghi_chu="[CHO PHÉP] COMPANION-EVENT",
        )
        cls.foreign_facility = CoSo.objects.create(
            ten_co_so="Foreign Facility", dia_chi="Private", quan="Private"
        )
        cls.foreign_room = Phong.objects.create(
            co_so=cls.foreign_facility,
            so_phong="PRIVATE-OTHER",
            gia_thue=Decimal("2600000"),
            dien_tich=24,
            so_nguoi_toi_da=2,
            tien_coc_mac_dinh=Decimal("500000"),
        )
        cls.foreign_history = LichSuRaVao.objects.create(
            phong=cls.foreign_room,
            nguoi_thue=cls.other,
            loai_su_kien="ra",
            nguon="thu_cong",
            ket_qua="khong_xac_dinh",
            thoi_diem=timezone.now(),
            ghi_chu="FOREIGN-EVENT-SECRET",
        )

    @property
    def url(self):
        return reverse("quyen_va_lich_su_ra_vao_cua_toi")

    def test_guest_redirects_and_admin_returns_to_admin_dashboard(self):
        guest = self.client.get(self.url)
        self.assertRedirects(guest, reverse("dang_nhap"), fetch_redirect_response=False)
        self.client.force_login(self.admin)
        admin = self.client.get(self.url)
        self.assertRedirects(admin, reverse("dashboard_admin"), fetch_redirect_response=False)

    def test_endpoint_is_get_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)

    def test_tenant_sees_only_own_right_and_own_history(self):
        self.client.force_login(self.user)
        before = (
            QuyenRaVao.objects.count(),
            LichSuRaVao.objects.count(),
            self.effects(),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tong_quyen"], 1)
        self.assertEqual(response.context["quyen_hieu_luc"], 1)
        self.assertEqual(response.context["tong_lich_su"], 1)
        self.assertContains(response, "OWN-EVENT")
        self.assertNotContains(response, "COMPANION-EVENT")
        self.assertNotContains(response, "PRIVATE COMPANION")
        self.assertNotContains(response, "FOREIGN-EVENT-SECRET")
        self.assertNotContains(response, "PRIVATE-PIN-1234")
        after = (
            QuyenRaVao.objects.count(),
            LichSuRaVao.objects.count(),
            self.effects(),
        )
        self.assertEqual(before, after)

    def test_foreign_room_filter_discloses_no_foreign_row_or_label(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, {"phong": self.foreign_room.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["danh_sach_quyen"], [])
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertNotContains(response, "Foreign Facility")
        self.assertNotContains(response, "PRIVATE-OTHER")
        self.assertNotContains(response, "FOREIGN-EVENT-SECRET")

    def test_history_filters_preserve_owner_scope_and_query_string(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, {
            "loai": "vao",
            "nguon": "camera",
            "tu_ngay": self.today.isoformat(),
            "den_ngay": self.today.isoformat(),
            "trang_thai": "hoat_dong",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertContains(response, "OWN-EVENT")
        self.assertNotIn("page=", response.context["query_string"])
        self.assertIn("nguon=camera", response.context["query_string"])

    def test_revoked_right_remains_visible_but_is_not_reported_as_effective(self):
        revoked = QuyenRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.tenant,
            hop_dong=self.own_contract,
            nguon_cap="thu_cong",
            loai_quyen="chu_phong",
            trang_thai="bi_thu_hoi",
            ngay_bat_dau=self.today - timedelta(days=30),
            ngay_ket_thuc=self.today - timedelta(days=1),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.url, {"trang_thai": "bi_thu_hoi"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item.pk for item in response.context["danh_sach_quyen"]], [revoked.pk])
        self.assertFalse(
            response.context["danh_sach_quyen"][0].danh_gia_hieu_luc.du_dieu_kien
        )
        self.assertContains(response, "Bị thu hồi")
        self.assertContains(response, "Không còn hiệu lực")
        self.assertEqual(response.context["tong_lich_su"], 1)

    def test_history_is_paginated_twenty_per_page(self):
        for index in range(21):
            LichSuRaVao.objects.create(
                quyen_ra_vao=self.own_right,
                phong=self.room,
                nguoi_thue=self.tenant,
                loai_su_kien="ra",
                nguon="thu_cong",
                ket_qua="cho_phep",
                thoi_diem=timezone.now() - timedelta(minutes=index + 1),
                ghi_chu=f"PAGE-EVENT-{index:02d}",
            )
        self.client.force_login(self.user)
        first = self.client.get(self.url)
        second = self.client.get(self.url, {"page": 2})
        self.assertEqual(first.context["page_obj"].paginator.per_page, 20)
        self.assertEqual(first.context["page_obj"].paginator.count, 22)
        self.assertEqual(len(first.context["lich_su"]), 20)
        self.assertEqual(second.context["page_obj"].number, 2)
        self.assertEqual(len(second.context["lich_su"]), 2)

    def test_invalid_filter_values_are_normalized_without_broadening_scope(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, {
            "phong": "not-an-id",
            "loai": "unknown",
            "nguon": "unknown",
            "trang_thai": "unknown",
            "tu_ngay": "not-a-date",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["phong_filter"], "")
        self.assertEqual(response.context["loai_filter"], "")
        self.assertEqual(response.context["nguon_filter"], "")
        self.assertEqual(response.context["trang_thai_filter"], "")
        self.assertEqual(response.context["tu_ngay_filter"], "")
        self.assertNotContains(response, "FOREIGN-EVENT-SECRET")

    def test_authenticated_account_without_tenant_record_gets_404(self):
        account = User.objects.create_user("tenant-without-profile")
        self.client.force_login(account)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_existing_admin_access_routes_still_render_for_admin(self):
        self.client.force_login(self.admin)
        for route_name in ("quan_ly_quyen_ra_vao", "quan_ly_lich_su_ra_vao"):
            with self.subTest(route=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)
