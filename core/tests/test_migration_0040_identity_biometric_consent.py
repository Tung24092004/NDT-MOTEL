from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class IdentityBiometricConsentMigrationTests(TransactionTestCase):
    databases = "__all__"

    def setUp(self):
        self.name = "test_ndt_motel_m0040_" + uuid4().hex[:10]
        self.alias = "m0040_" + uuid4().hex[:10]
        self.assertTrue(self.name.startswith("test_"))
        with connections["default"].cursor() as cursor:
            cursor.execute("CREATE DATABASE `%s` CHARACTER SET utf8mb4" % self.name)
        config = connections.databases["default"].copy()
        config["NAME"] = self.name
        connections.databases[self.alias] = config
        self.conn = connections[self.alias]
        self.executor = MigrationExecutor(self.conn)
        self.executor.migrate([("core", "0039_canonical_access_active_key")])

    def tearDown(self):
        self.conn.close()
        connections.databases.pop(self.alias, None)
        with connections["default"].cursor() as cursor:
            cursor.execute("DROP DATABASE IF EXISTS `%s`" % self.name)

    def _historical_objects(self):
        apps = self.executor.loader.project_state(
            [("core", "0039_canonical_access_active_key")]
        ).apps
        return (
            apps,
            apps.get_model("core", "DanhTinhNguoiOCung"),
            apps.get_model("core", "NguoiOCungPhong"),
            apps.get_model("core", "FaceProfile"),
        )

    def _contract(self, apps, suffix):
        User = apps.get_model("auth", "User")
        Tenant = apps.get_model("core", "NguoiThue")
        Facility = apps.get_model("core", "CoSo")
        Room = apps.get_model("core", "Phong")
        Booking = apps.get_model("core", "DatPhong")
        Contract = apps.get_model("core", "HopDong")
        today = date.today()
        user = User.objects.using(self.alias).create(username="historic0040" + suffix)
        tenant = Tenant.objects.using(self.alias).create(tai_khoan_id=user.pk, ho_ten="Historic", cccd="0000000096" + suffix, trang_thai_luu_tru="dang_o")
        facility = Facility.objects.using(self.alias).create(ten_co_so="H" + suffix, dia_chi="T", quan="T")
        room = Room.objects.using(self.alias).create(co_so_id=facility.pk, so_phong="H-" + suffix, gia_thue=Decimal("1"), dien_tich=Decimal("1"), so_nguoi_toi_da=2)
        booking = Booking.objects.using(self.alias).create(nguoi_thue_id=tenant.pk, phong_id=room.pk, ngay_nhan_phong=today, ngay_tra_du_kien=today + timedelta(days=2), trang_thai="da_duyet")
        return Contract.objects.using(self.alias).create(dat_phong_id=booking.pk, so_hop_dong="H0040" + suffix, ngay_bat_dau=today, ngay_ket_thuc=today + timedelta(days=2), tien_thue_thang=Decimal("1"), trang_thai="dang_hieu_luc")

    def test_valid_residency_profile_is_preserved_and_bound_to_identity(self):
        apps, Identity, Resident, Profile = self._historical_objects()
        contract = self._contract(apps, "1")
        Booking = apps.get_model("core", "DatPhong")
        tenant_id = Booking.objects.using(self.alias).get(pk=contract.dat_phong_id).nguoi_thue_id
        identity = Identity.objects.using(self.alias).create(cccd="000000009601")
        resident = Resident.objects.using(self.alias).create(
            identity_id=identity.pk, ho_ten="Historical face", cccd=identity.cccd,
            hop_dong_id=contract.pk, trang_thai="da_roi", ngay_vao=date.today(), ngay_ra=date.today(),
        )
        profile = Profile.objects.using(self.alias).create(
            nguoi_o_cung_id=resident.pk, loai_chu_the="nguoi_o_cung",
            trang_thai="da_xac_thuc", face_encoding="preserved-vector",
            dong_y_du_lieu_khuon_mat=True,
        )
        tenant_profile = Profile.objects.using(self.alias).create(
            nguoi_thue_id=tenant_id, loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc", face_encoding="tenant-vector",
        )
        MigrationExecutor(self.conn).migrate([("core", "0040_identity_biometric_consent_foundation")])
        apps = MigrationExecutor(self.conn).loader.project_state(
            [("core", "0040_identity_biometric_consent_foundation")]
        ).apps
        NewProfile = apps.get_model("core", "FaceProfile")
        after = NewProfile.objects.using(self.alias).get(pk=profile.pk)
        tenant_after = NewProfile.objects.using(self.alias).get(pk=tenant_profile.pk)
        self.assertEqual(after.nguoi_o_cung_id, resident.pk)
        self.assertEqual(after.danh_tinh_nguoi_o_cung_id, identity.pk)
        self.assertEqual(after.face_encoding, "preserved-vector")
        self.assertEqual(tenant_after.nguoi_thue_id, tenant_id)
        self.assertIsNone(tenant_after.danh_tinh_nguoi_o_cung_id)
        self.assertEqual(tenant_after.face_encoding, "tenant-vector")

    def test_two_historical_profiles_for_one_identity_fail_closed(self):
        apps, Identity, Resident, Profile = self._historical_objects()
        contract = self._contract(apps, "2")
        identity = Identity.objects.using(self.alias).create(cccd="000000009602")
        first = Resident.objects.using(self.alias).create(hop_dong_id=contract.pk, identity_id=identity.pk, ho_ten="Old A", cccd=identity.cccd, trang_thai="da_roi", ngay_vao=date.today())
        second = Resident.objects.using(self.alias).create(hop_dong_id=contract.pk, identity_id=identity.pk, ho_ten="Old B", cccd=identity.cccd, trang_thai="da_roi", ngay_vao=date.today())
        one = Profile.objects.using(self.alias).create(nguoi_o_cung_id=first.pk, loai_chu_the="nguoi_o_cung")
        two = Profile.objects.using(self.alias).create(nguoi_o_cung_id=second.pk, loai_chu_the="nguoi_o_cung")
        with self.assertRaisesRegex(RuntimeError, "map to identity"):
            MigrationExecutor(self.conn).migrate([("core", "0040_identity_biometric_consent_foundation")])
        self.assertEqual(Profile.objects.using(self.alias).filter(pk__in=[one.pk, two.pk]).count(), 2)
