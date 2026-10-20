from importlib import import_module
from datetime import timedelta

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import (
    BanChupNguoiOCungHopDong,
    DanhTinhNguoiOCung,
    FaceProfile,
    NguoiOCungPhong,
    QuyenRaVao,
)
from core.dich_vu.vong_doi_hop_dong import dong_bo_vong_doi_hop_dong


class CoTenantIdentityResidencyFoundationTests(BusinessFixture):
    def residency(self, contract, *, cccd, status="dang_o", name="Co-tenant"):
        return NguoiOCungPhong.objects.create(
            hop_dong=contract,
            ho_ten=name,
            cccd=cccd,
            ngay_vao=self.today,
            trang_thai=status,
            da_xac_minh_boi_admin=status in ("dang_o", "da_xac_minh"),
        )

    def test_normalized_cccd_reuses_one_identity_and_keeps_historical_residencies(self):
        contract = self.contract()
        first = self.residency(
            contract, cccd="000 000-000 123", status="da_roi", name="First stay"
        )
        second = self.residency(contract, cccd="000000000123", name="Return stay")

        self.assertEqual(first.identity_id, second.identity_id)
        self.assertEqual(second.identity.cccd, "000000000123")
        self.assertEqual(second.cccd, "000000000123")
        self.assertEqual(second.identity.lich_su_luu_tru.count(), 2)

    def test_db_unique_key_prevents_two_active_residencies_and_rolls_back(self):
        contract = self.contract()
        first = self.residency(contract, cccd="000000000124")
        before_identities = DanhTinhNguoiOCung.objects.count()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.residency(contract, cccd="000000000124", name="Duplicate active")

        self.assertEqual(DanhTinhNguoiOCung.objects.count(), before_identities)
        self.assertEqual(
            NguoiOCungPhong.objects.filter(identity=first.identity, trang_thai="dang_o").count(),
            1,
        )

    def test_leaving_releases_key_and_return_is_a_new_residency(self):
        contract = self.contract()
        departed = self.residency(contract, cccd="000000000125")
        departed.trang_thai = "da_roi"
        departed.ngay_ra = timezone.localdate()
        departed.save()

        returned = self.residency(contract, cccd="000000000125", name="Returned")
        self.assertNotEqual(departed.pk, returned.pk)
        self.assertEqual(departed.identity_id, returned.identity_id)
        departed.refresh_from_db()
        self.assertIsNone(departed.active_identity_key)
        self.assertEqual(returned.active_identity_key, returned.identity_id)

    def test_contract_lifecycle_releases_active_key_without_deleting_history(self):
        contract = self.contract(end=self.today - timedelta(days=1))
        resident = self.residency(contract, cccd="000000000130")
        dong_bo_vong_doi_hop_dong(contract, today=self.today)

        resident.refresh_from_db()
        self.assertEqual(resident.trang_thai, "da_roi")
        self.assertIsNone(resident.active_identity_key)
        with self.assertRaises(ValidationError):
            resident.delete()
        self.assertTrue(NguoiOCungPhong.objects.filter(pk=resident.pk).exists())

    def test_existing_face_access_and_snapshot_remain_attached_to_legacy_residency(self):
        contract = self.contract()
        resident = self.residency(contract, cccd="000000000126")
        profile = FaceProfile.objects.create(
            nguoi_o_cung=resident, loai_chu_the="nguoi_o_cung"
        )
        access = QuyenRaVao.objects.create(
            hop_dong=contract,
            phong=contract.dat_phong.phong,
            nguoi_o_cung=resident,
            loai_quyen="nguoi_o_cung",
            ngay_bat_dau=self.today,
            nguon_cap="legacy_unknown",
        )
        snapshot = BanChupNguoiOCungHopDong.objects.create(
            hop_dong=contract,
            nguoi_o_cung=resident,
            ho_ten=resident.ho_ten,
            cccd=resident.cccd,
            loai_su_kien="legacy_khong_xac_dinh",
            ngay_hieu_luc=self.today,
            nguon="legacy_migration",
            la_du_lieu_legacy=True,
        )

        resident.save()
        profile.refresh_from_db()
        access.refresh_from_db()
        snapshot.refresh_from_db()
        self.assertEqual(profile.nguoi_o_cung_id, resident.pk)
        self.assertEqual(access.nguoi_o_cung_id, resident.pk)
        self.assertEqual(snapshot.nguoi_o_cung_id, resident.pk)


class CoTenantIdentityMigrationBackfillTests(BusinessFixture):
    def residency(self, contract, *, cccd, status="da_roi", name="Legacy resident"):
        return NguoiOCungPhong.objects.create(
            hop_dong=contract, ho_ten=name, cccd=cccd,
            ngay_vao=self.today, trang_thai=status,
        )

    def test_backfill_is_deterministic_and_preserves_residency_evidence(self):
        contract = self.contract()
        resident = self.residency(contract, cccd="000 000-000 127")
        snapshot = BanChupNguoiOCungHopDong.objects.create(
            hop_dong=contract, nguoi_o_cung=resident, ho_ten=resident.ho_ten,
            cccd=resident.cccd, loai_su_kien="legacy_khong_xac_dinh",
            ngay_hieu_luc=self.today, nguon="legacy_migration", la_du_lieu_legacy=True,
        )
        other = DanhTinhNguoiOCung.objects.create(cccd="000000000128")
        NguoiOCungPhong.objects.filter(pk=resident.pk).update(identity=other)

        migration = import_module("core.migrations.0035_cotenant_identity_residency_foundation")
        migration.backfill_companion_identities(apps, None)

        resident.refresh_from_db()
        snapshot.refresh_from_db()
        self.assertEqual(resident.identity.cccd, "000000000127")
        self.assertEqual(resident.cccd, "000000000127")
        self.assertEqual(snapshot.nguoi_o_cung_id, resident.pk)

    def test_backfill_refuses_conflicting_active_legacy_rows(self):
        contract = self.contract()
        first = self.residency(contract, cccd="000000000129", status="dang_o")
        second = self.residency(contract, cccd="000000000129", status="da_roi", name="Legacy collision")
        # Emulate legacy data before the new active-key constraint without
        # asking the current model layer to accept an invalid state.
        NguoiOCungPhong.objects.filter(pk=second.pk).update(
            trang_thai="dang_o", active_identity_key=None
        )

        migration = import_module("core.migrations.0035_cotenant_identity_residency_foundation")
        with self.assertRaisesRegex(RuntimeError, "duplicate active CCCD"):
            migration.backfill_companion_identities(apps, None)
        first.refresh_from_db()
        self.assertEqual(first.trang_thai, "dang_o")
