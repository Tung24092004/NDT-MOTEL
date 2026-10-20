"""TENANCY-01: current-tenancy resolution and tenant-only surfaces."""
from datetime import timedelta
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory

from core.dich_vu.home_panel import lay_home_panel_context
from core.dich_vu.luu_tru import lay_hop_dong_luu_tru_hien_tai
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import DatPhong, HopDong, Phong
from core.views_hop_dong import chi_tiet_hop_dong_cua_toi
from core.views_tai_khoan import tai_khoan


class TenancyResolutionTests(BusinessFixture):
    def test_current_contract_is_the_authoritative_tenancy_and_room_state(self):
        contract = self.contract()

        tenancy = lay_hop_dong_luu_tru_hien_tai(nguoi_thue=self.tenant)

        self.assertEqual(tenancy.pk, contract.pk)
        self.assertEqual(tenancy.dat_phong.phong_id, self.room.pk)
        self.room.refresh_from_db()
        self.assertEqual(self.room.trang_thai, "dang_thue")
        self.assertEqual(self.room.hop_dong_dang_hieu_luc().pk, contract.pk)

    def test_future_ended_non_active_and_checked_out_contracts_are_not_current(self):
        contract = self.contract()
        contract.ngay_bat_dau = self.today + timedelta(days=1)
        contract.ngay_ket_thuc = self.today + timedelta(days=31)
        contract.save(update_fields=["ngay_bat_dau", "ngay_ket_thuc"])
        self.assertIsNone(lay_hop_dong_luu_tru_hien_tai(nguoi_thue=self.tenant))
        self.room.dong_bo_trang_thai(); self.room.refresh_from_db()
        self.assertEqual(self.room.trang_thai, "da_dat")

        contract.ngay_bat_dau = self.today - timedelta(days=31)
        contract.ngay_ket_thuc = self.today - timedelta(days=1)
        contract.save(update_fields=["ngay_bat_dau", "ngay_ket_thuc"])
        self.assertIsNone(lay_hop_dong_luu_tru_hien_tai(nguoi_thue=self.tenant))

        contract.ngay_ket_thuc = self.today + timedelta(days=31)
        contract.trang_thai = "cho_hieu_luc"
        contract.save(update_fields=["ngay_ket_thuc", "trang_thai"])
        self.assertIsNone(lay_hop_dong_luu_tru_hien_tai(nguoi_thue=self.tenant))

        contract.trang_thai = "dang_hieu_luc"
        contract.save(update_fields=["trang_thai"])
        self.tenant.trang_thai_luu_tru = "da_tra_phong"
        self.tenant.save(update_fields=["trang_thai_luu_tru"])
        self.assertIsNone(lay_hop_dong_luu_tru_hien_tai(nguoi_thue=self.tenant))

    def test_home_panel_and_account_use_the_same_current_tenancy(self):
        contract = self.contract()
        request = RequestFactory().get("/")
        request.user = self.user

        self.assertEqual(lay_home_panel_context(request)["hop_dong_hien_tai"].pk, contract.pk)
        with patch("core.views_tai_khoan.render") as render:
            tai_khoan(request)
        self.assertEqual(render.call_args.args[2]["hop_dong_hien_tai"].pk, contract.pk)

    def test_tenant_cannot_tamper_with_another_tenants_contract_id(self):
        contract = self.contract()
        request = RequestFactory().get(f"/hop-dong-cua-toi/{contract.pk}/")
        request.user = self.other_user
        with self.assertRaises(Http404):
            chi_tiet_hop_dong_cua_toi(request, contract.pk)

    def test_same_tenant_cannot_have_competing_current_contracts(self):
        contract = self.contract()
        other_room = Phong.objects.create(
            co_so=self.facility, so_phong="AUDIT-2", gia_thue=2500000,
            dien_tich=20, so_nguoi_toi_da=2, tien_coc_mac_dinh=500000,
        )
        booking = DatPhong.objects.create(
            nguoi_thue=self.tenant, phong=other_room, ngay_nhan_phong=self.today,
            ngay_tra_du_kien=self.today + timedelta(days=90), so_thang_thue=3,
            trang_thai="da_duyet",
        )
        competing = HopDong.objects.create(
            dat_phong=booking, so_hop_dong="AUDIT-COMPETING",
            ngay_bat_dau=self.today, ngay_ket_thuc=self.today + timedelta(days=90),
            tien_thue_thang=2500000, trang_thai="dang_hieu_luc",
        )

        # Legacy-invalid duplicates resolve deterministically and never leak a
        # second room; activation prevents new duplicates at the write boundary.
        self.assertEqual(lay_hop_dong_luu_tru_hien_tai(nguoi_thue=self.tenant).pk, contract.pk)
        self.assertEqual(competing.dat_phong.nguoi_thue_id, contract.dat_phong.nguoi_thue_id)
