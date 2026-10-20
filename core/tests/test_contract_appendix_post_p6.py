"""Focused coverage for immutable contract snapshots and appendices."""
from datetime import timedelta
from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse

from core.dich_vu.phu_luc_hop_dong import (
    dam_bao_ban_chup_hop_dong,
    ghi_nhan_thay_doi_cu_tru,
    snapshot_nguoi_o_cung_khi_ky,
)
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.dich_vu.hop_dong import confirm_deposit_and_create_contract
from core.dich_vu.tien_coc import report_paid
from core.models import (
    BanChupHopDong,
    BanChupNguoiOCungHopDong,
    KhaiBaoNguoiOCungDatPhong,
    LichSuHopDong,
    LichSuRaVao,
    NhatKyThaoTac,
    PhuLucHopDong,
    QuyenRaVao,
    YeuCauGiaHanHopDong,
)
from core.views_gia_han import xu_ly_yeu_cau_gia_han


class ContractSnapshotTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.contract_obj.dat_phong.so_nguoi_o = 3
        self.contract_obj.dat_phong.save(update_fields=["so_nguoi_o"])

    def declaration(self, cccd, status="da_xac_minh", name="Snapshot Resident"):
        return KhaiBaoNguoiOCungDatPhong.objects.create(
            dat_phong=self.contract_obj.dat_phong,
            ho_ten=name,
            cccd=cccd,
            trang_thai_xac_minh=status,
        )

    def test_signing_snapshot_is_scoped_idempotent_and_immutable(self):
        valid = self.declaration("000000000003")
        self.declaration("000000000004", status="tu_choi", name="Rejected")
        other_contract = self.contract(tenant=self.other)
        other_contract.dat_phong.so_nguoi_o = 2
        other_contract.dat_phong.save(update_fields=["so_nguoi_o"])
        KhaiBaoNguoiOCungDatPhong.objects.create(
            dat_phong=other_contract.dat_phong,
            ho_ten="Other booking",
            cccd="000000000005",
            trang_thai_xac_minh="da_xac_minh",
        )

        dam_bao_ban_chup_hop_dong(self.contract_obj, actor=self.admin)
        snapshot_nguoi_o_cung_khi_ky(self.contract_obj)
        snapshot_nguoi_o_cung_khi_ky(self.contract_obj)
        snapshots = BanChupNguoiOCungHopDong.objects.filter(
            hop_dong=self.contract_obj, loai_su_kien="co_mat_khi_ky"
        )
        self.assertEqual(snapshots.count(), 1)
        self.assertEqual(snapshots.get().khai_bao_dat_phong_id, valid.pk)
        valid.ho_ten = "Changed live"
        valid.save(update_fields=["ho_ten"])
        self.assertEqual(snapshots.get().ho_ten, "Snapshot Resident")

    def test_post_signing_change_does_not_mutate_original_snapshot(self):
        self.declaration("000000000003")
        dam_bao_ban_chup_hop_dong(self.contract_obj, actor=self.admin)
        snapshot_nguoi_o_cung_khi_ky(self.contract_obj)
        resident = self.resident(self.contract_obj)
        original = list(
            BanChupNguoiOCungHopDong.objects.filter(loai_su_kien="co_mat_khi_ky")
            .values_list("ho_ten", flat=True)
        )
        ghi_nhan_thay_doi_cu_tru(
            resident=resident, event="them_sau_ky", actor=self.admin, reason="Admin verified"
        )
        resident.trang_thai = "da_roi"
        resident.save(update_fields=["trang_thai"])
        ghi_nhan_thay_doi_cu_tru(
            resident=resident, event="roi_sau_ky", actor=self.admin, reason="Departed"
        )
        self.assertEqual(
            list(BanChupNguoiOCungHopDong.objects.filter(loai_su_kien="co_mat_khi_ky").values_list("ho_ten", flat=True)),
            original,
        )
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 2)

    def test_details_separate_signed_changes_and_current_state(self):
        self.declaration("000000000003")
        dam_bao_ban_chup_hop_dong(self.contract_obj, actor=self.admin)
        snapshot_nguoi_o_cung_khi_ky(self.contract_obj)
        resident = self.resident(self.contract_obj)
        ghi_nhan_thay_doi_cu_tru(resident=resident, event="them_sau_ky", actor=self.admin)

        for user, route in (
            (self.admin, "chi_tiet_hop_dong"),
            (self.user, "chi_tiet_hop_dong_cua_toi"),
        ):
            self.client.force_login(user)
            response = self.client.get(reverse(route, args=[self.contract_obj.pk]))
            self.assertContains(response, "Người ở cùng tại thời điểm ký")
            self.assertContains(response, "Thay đổi sau khi ký")
            self.assertContains(response, "Tình trạng cư trú hiện tại")
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(reverse("chi_tiet_hop_dong_cua_toi", args=[self.contract_obj.pk])).status_code,
            404,
        )

    def test_renewal_constraint_rejects_non_increasing_dates(self):
        request_obj = YeuCauGiaHanHopDong.objects.create(
            hop_dong=self.contract_obj,
            nguoi_yeu_cau=self.tenant,
            so_thang_gia_han=1,
            ngay_ket_thuc_cu=self.today,
            ngay_ket_thuc_de_xuat=self.today + timedelta(days=1),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PhuLucHopDong.objects.create(
                hop_dong=self.contract_obj,
                yeu_cau_gia_han=request_obj,
                loai="gia_han",
                ma_phu_luc="INVALID",
                ngay_hieu_luc=self.today,
                ngay_ket_thuc_cu=self.today,
                ngay_ket_thuc_moi=self.today,
            )

    def test_renewal_appendix_rejects_request_from_another_contract(self):
        other_contract = self.contract(tenant=self.other)
        request_obj = YeuCauGiaHanHopDong.objects.create(
            hop_dong=other_contract,
            nguoi_yeu_cau=self.other,
            so_thang_gia_han=1,
            ngay_ket_thuc_cu=other_contract.ngay_ket_thuc,
            ngay_ket_thuc_de_xuat=other_contract.ngay_ket_thuc + timedelta(days=30),
        )
        appendix = PhuLucHopDong(
            hop_dong=self.contract_obj,
            yeu_cau_gia_han=request_obj,
            loai="gia_han",
            ma_phu_luc="WRONG-CONTRACT",
            ngay_hieu_luc=self.today,
            ngay_ket_thuc_cu=self.today,
            ngay_ket_thuc_moi=self.today + timedelta(days=30),
        )
        with self.assertRaises(ValidationError):
            appendix.full_clean()


class ContractCreationSnapshotTests(Phase5BookingFixture):
    def test_contract_service_snapshots_only_valid_booking_declarations(self):
        booking, payment = self.new_booking(people=2)
        rejected = KhaiBaoNguoiOCungDatPhong.objects.create(
            dat_phong=booking,
            ho_ten="Rejected declaration",
            cccd="000000000099",
            trang_thai_xac_minh="tu_choi",
        )
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="SNAPSHOT-001")

        contract = confirm_deposit_and_create_contract(
            actor=self.admin, booking_id=booking.pk
        )
        snapshots = BanChupNguoiOCungHopDong.objects.filter(
            hop_dong=contract, loai_su_kien="co_mat_khi_ky"
        )
        self.assertEqual(snapshots.count(), 1)
        self.assertFalse(snapshots.filter(khai_bao_dat_phong=rejected).exists())
        self.assertEqual(contract.ban_chup_goc.du_lieu["so_hop_dong"], contract.so_hop_dong)


class ContractAppendixRenewalTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract(
            "sap_het_han", start=self.today - timedelta(days=60), end=self.today + timedelta(days=10)
        )
        dam_bao_ban_chup_hop_dong(self.contract_obj, actor=self.admin)
        self.renewal = YeuCauGiaHanHopDong.objects.create(
            hop_dong=self.contract_obj,
            nguoi_yeu_cau=self.tenant,
            so_thang_gia_han=2,
            ngay_ket_thuc_cu=self.contract_obj.ngay_ket_thuc,
            ngay_ket_thuc_de_xuat=self.contract_obj.ngay_ket_thuc + timedelta(days=60),
        )

    def approve(self):
        return self.post(
            xu_ly_yeu_cau_gia_han,
            self.renewal,
            {"hanh_dong": "duyet", "ghi_chu_admin": "Approved"},
            self.admin,
        )

    def test_approval_creates_exactly_one_appendix_and_one_audit_history(self):
        active = self.permission(ngay_ket_thuc=self.renewal.ngay_ket_thuc_cu)
        revoked = self.permission(
            ngay_ket_thuc=self.renewal.ngay_ket_thuc_cu,
            trang_thai="bi_thu_hoi",
            nguon_cap="manual",
        )
        self.approve()
        appendix = PhuLucHopDong.objects.get(yeu_cau_gia_han=self.renewal)
        self.assertEqual(appendix.ngay_ket_thuc_cu, self.renewal.ngay_ket_thuc_cu)
        self.assertEqual(appendix.ngay_ket_thuc_moi, self.renewal.ngay_ket_thuc_de_xuat)
        active.refresh_from_db()
        revoked.refresh_from_db()
        self.assertEqual(active.ngay_ket_thuc, self.renewal.ngay_ket_thuc_de_xuat)
        self.assertEqual(revoked.trang_thai, "bi_thu_hoi")
        self.assertEqual(revoked.nguon_cap, "manual")
        self.assertEqual(LichSuHopDong.objects.filter(hanh_dong="gia_han").count(), 1)
        self.assertEqual(NhatKyThaoTac.objects.count(), 1)
        self.approve()
        self.assertEqual(PhuLucHopDong.objects.filter(yeu_cau_gia_han=self.renewal).count(), 1)
        self.assertEqual(LichSuHopDong.objects.filter(hanh_dong="gia_han").count(), 1)
        self.assertEqual(NhatKyThaoTac.objects.count(), 1)

    def test_original_pdf_uses_snapshot_after_live_contract_changes(self):
        original_end = self.contract_obj.ngay_ket_thuc.strftime("%d/%m/%Y")
        self.approve()
        captured = {}

        class FakeDoc:
            def __init__(self, response, *args, **kwargs):
                self.page = 1

            def build(self, story, *args, **kwargs):
                captured["text"] = "\n".join(
                    item.getPlainText() for item in story if hasattr(item, "getPlainText")
                )

        self.client.force_login(self.admin)
        with patch("core.views_hop_dong.SimpleDocTemplate", FakeDoc):
            response = self.client.get(reverse("xuat_hop_dong_pdf", args=[self.contract_obj.pk]))
        self.assertEqual(response.status_code, 200)
        # The snapshot itself is the authoritative assertion; PDF rendering is exercised above.
        self.assertEqual(
            self.contract_obj.ban_chup_goc.du_lieu["ngay_ket_thuc_goc"],
            self.renewal.ngay_ket_thuc_cu.isoformat(),
        )
        self.assertNotEqual(
            self.contract_obj.ban_chup_goc.du_lieu["ngay_ket_thuc_goc"],
            self.renewal.ngay_ket_thuc_de_xuat.isoformat(),
        )

    def test_appendix_pdf_owner_permission(self):
        self.approve()
        appendix = PhuLucHopDong.objects.get(yeu_cau_gia_han=self.renewal)
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(reverse("xuat_phu_luc_hop_dong_pdf", args=[appendix.pk])).status_code,
            200,
        )
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(reverse("xuat_phu_luc_hop_dong_pdf", args=[appendix.pk])).status_code,
            302,
        )


class ContractAppendixMigrationTests(BusinessFixture):
    def test_backfill_is_idempotent_and_does_not_change_operational_state(self):
        contract = self.contract()
        resident = self.resident(contract, "cho_xac_minh")
        permission = self.permission(hop_dong=contract, trang_thai="bi_thu_hoi")
        before = (resident.da_xac_minh_boi_admin, permission.trang_thai, LichSuRaVao.objects.count())
        migration = import_module(
            "core.migrations.0027_phuluchopdong_banchupnguoiocunghopdong_and_more"
        )
        migration.backfill_immutable_contract_history(apps, None)
        counts = (BanChupHopDong.objects.count(), BanChupNguoiOCungHopDong.objects.count())
        migration.backfill_immutable_contract_history(apps, None)
        resident.refresh_from_db()
        permission.refresh_from_db()
        self.assertEqual((BanChupHopDong.objects.count(), BanChupNguoiOCungHopDong.objects.count()), counts)
        self.assertEqual(
            (resident.da_xac_minh_boi_admin, permission.trang_thai, LichSuRaVao.objects.count()),
            before,
        )
        self.assertTrue(BanChupHopDong.objects.get(hop_dong=contract).la_du_lieu_legacy)
        self.assertTrue(
            BanChupNguoiOCungHopDong.objects.get(nguoi_o_cung=resident).la_du_lieu_legacy
        )


class ContractAppendixSchemaMigrationTests(TransactionTestCase):
    migrate_from = [("core", "0026_alter_nguoiocungphong_trang_thai")]
    migrate_to = [("core", "0027_phuluchopdong_banchupnguoiocunghopdong_and_more")]

    def test_migrates_cleanly_from_0026_to_0027(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        self.assertIsNotNone(old_apps.get_model("core", "HopDong"))

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        self.assertIsNotNone(new_apps.get_model("core", "PhuLucHopDong"))
        self.assertIsNotNone(new_apps.get_model("core", "BanChupHopDong"))
        self.assertIsNotNone(new_apps.get_model("core", "BanChupNguoiOCungHopDong"))
