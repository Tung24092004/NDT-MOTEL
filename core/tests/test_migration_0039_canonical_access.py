from uuid import uuid4
from datetime import date, timedelta
from decimal import Decimal
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CanonicalAccessMigrationTests(TransactionTestCase):
    """A fresh MySQL schema is required: MySQL DDL cannot be rolled back."""
    databases = "__all__"

    def setUp(self):
        self.name = "test_ndt_motel_m0039_" + uuid4().hex[:10]
        self.alias = "m0039_" + uuid4().hex[:10]
        self.assertTrue(self.name.startswith("test_")); self.assertNotEqual(self.name, "ndt_motel")
        with connections["default"].cursor() as c:
            c.execute("CREATE DATABASE `%s` CHARACTER SET utf8mb4" % self.name)
        cfg = connections.databases["default"].copy()
        cfg["NAME"] = self.name
        connections.databases[self.alias] = cfg
        self.conn = connections[self.alias]
        self.executor = MigrationExecutor(self.conn)
        self.executor.migrate([("core", "0038_cotenant_private_identity_evidence")])
        cols = self.conn.introspection.get_table_description(self.conn.cursor(), "core_quyenravao")
        self.assertNotIn("active_access_key", [x.name for x in cols])

    def tearDown(self):
        self.conn.close()
        del connections[self.alias]
        with connections["default"].cursor() as c:
            c.execute("DROP DATABASE IF EXISTS `%s`" % self.name)
        connections.databases.pop(self.alias, None)

    def test_clean_schema_reaches_0039(self):
        MigrationExecutor(self.conn).migrate([("core", "0039_canonical_access_active_key")])
        cols = self.conn.introspection.get_table_description(self.conn.cursor(), "core_quyenravao")
        self.assertIn("active_access_key", [x.name for x in cols])

    def test_valid_tenant_history_is_preserved_and_backfilled(self):
        apps = self.executor.loader.project_state([("core", "0038_cotenant_private_identity_evidence")]).apps
        User=apps.get_model("auth","User"); Tenant=apps.get_model("core","NguoiThue"); Facility=apps.get_model("core","CoSo"); Room=apps.get_model("core","Phong"); Booking=apps.get_model("core","DatPhong"); Contract=apps.get_model("core","HopDong"); Right=apps.get_model("core","QuyenRaVao")
        today=date.today(); user=User.objects.using(self.alias).create(username="historic0039"); tenant=Tenant.objects.using(self.alias).create(tai_khoan_id=user.pk,ho_ten="Historic",cccd="000000008901",trang_thai_luu_tru="dang_o")
        facility=Facility.objects.using(self.alias).create(ten_co_so="H",dia_chi="T",quan="T"); room=Room.objects.using(self.alias).create(co_so_id=facility.pk,so_phong="H-1",gia_thue=Decimal("1"),dien_tich=Decimal("1"),so_nguoi_toi_da=2)
        booking=Booking.objects.using(self.alias).create(nguoi_thue_id=tenant.pk,phong_id=room.pk,ngay_nhan_phong=today,ngay_tra_du_kien=today+timedelta(days=9),trang_thai="da_duyet")
        contract=Contract.objects.using(self.alias).create(dat_phong_id=booking.pk,so_hop_dong="H0039",ngay_bat_dau=today,ngay_ket_thuc=today+timedelta(days=9),tien_thue_thang=Decimal("1"),trang_thai="dang_hieu_luc")
        Identity=apps.get_model("core", "DanhTinhNguoiOCung"); Resident=apps.get_model("core", "NguoiOCungPhong")
        identity=Identity.objects.using(self.alias).create(cccd="000000008902")
        resident=Resident.objects.using(self.alias).create(hop_dong_id=contract.pk, identity_id=identity.pk, ho_ten="Co tenant", cccd=identity.cccd, trang_thai="dang_o", ngay_vao=today, active_identity_key=identity.pk)
        active=Right.objects.using(self.alias).create(hop_dong_id=contract.pk,phong_id=room.pk,nguoi_thue_id=tenant.pk,loai_quyen="chu_phong",nguon_cap="face_id",trang_thai="hoat_dong",ngay_bat_dau=today,ngay_ket_thuc=contract.ngay_ket_thuc,ma_the="preserve")
        cotenant_active=Right.objects.using(self.alias).create(hop_dong_id=contract.pk,phong_id=room.pk,nguoi_o_cung_id=resident.pk,loai_quyen="nguoi_o_cung",nguon_cap="duyet_ghep",trang_thai="hoat_dong",ngay_bat_dau=today,ngay_ket_thuc=contract.ngay_ket_thuc)
        old=Right.objects.using(self.alias).create(hop_dong_id=contract.pk,phong_id=room.pk,nguoi_thue_id=tenant.pk,loai_quyen="chu_phong",nguon_cap="thu_cong",trang_thai="bi_thu_hoi",ngay_bat_dau=today,ngay_ket_thuc=today)
        MigrationExecutor(self.conn).migrate([("core","0039_canonical_access_active_key")])
        New=MigrationExecutor(self.conn).loader.project_state([("core","0039_canonical_access_active_key")]).apps.get_model("core","QuyenRaVao")
        tenant_after=New.objects.using(self.alias).get(pk=active.pk); resident_after=New.objects.using(self.alias).get(pk=cotenant_active.pk); old_after=New.objects.using(self.alias).get(pk=old.pk)
        self.assertEqual(tenant_after.ma_the,"preserve")
        self.assertEqual(tenant_after.active_access_key, f"contract:{contract.pk}:room:{room.pk}:tenant:{tenant.pk}")
        self.assertEqual(resident_after.active_access_key, f"contract:{contract.pk}:room:{room.pk}:resident:{resident.pk}")
        self.assertEqual(resident_after.nguoi_o_cung_id, resident.pk)
        self.assertEqual(old_after.trang_thai, "bi_thu_hoi")
        self.assertIsNone(old_after.active_access_key)

    def test_duplicate_active_historical_grants_fail_closed(self):
        apps = self.executor.loader.project_state([("core", "0038_cotenant_private_identity_evidence")]).apps
        User=apps.get_model("auth", "User"); Tenant=apps.get_model("core", "NguoiThue"); Facility=apps.get_model("core", "CoSo"); Room=apps.get_model("core", "Phong"); Booking=apps.get_model("core", "DatPhong"); Contract=apps.get_model("core", "HopDong"); Right=apps.get_model("core", "QuyenRaVao")
        today=date.today(); user=User.objects.using(self.alias).create(username="duplicate0039"); tenant=Tenant.objects.using(self.alias).create(tai_khoan_id=user.pk, ho_ten="Duplicate", cccd="000000008903", trang_thai_luu_tru="dang_o")
        facility=Facility.objects.using(self.alias).create(ten_co_so="D", dia_chi="T", quan="T"); room=Room.objects.using(self.alias).create(co_so_id=facility.pk, so_phong="D-1", gia_thue=Decimal("1"), dien_tich=Decimal("1"), so_nguoi_toi_da=2)
        booking=Booking.objects.using(self.alias).create(nguoi_thue_id=tenant.pk, phong_id=room.pk, ngay_nhan_phong=today, ngay_tra_du_kien=today + timedelta(days=9), trang_thai="da_duyet")
        contract=Contract.objects.using(self.alias).create(dat_phong_id=booking.pk, so_hop_dong="D0039", ngay_bat_dau=today, ngay_ket_thuc=today + timedelta(days=9), tien_thue_thang=Decimal("1"), trang_thai="dang_hieu_luc")
        first=Right.objects.using(self.alias).create(hop_dong_id=contract.pk, phong_id=room.pk, nguoi_thue_id=tenant.pk, loai_quyen="chu_phong", nguon_cap="face_id", trang_thai="hoat_dong", ngay_bat_dau=today)
        second=Right.objects.using(self.alias).create(hop_dong_id=contract.pk, phong_id=room.pk, nguoi_thue_id=tenant.pk, loai_quyen="chu_phong", nguon_cap="thu_cong", trang_thai="hoat_dong", ngay_bat_dau=today)
        with self.assertRaisesRegex(RuntimeError, "duplicate active entitlement"):
            MigrationExecutor(self.conn).migrate([("core", "0039_canonical_access_active_key")])
        self.assertEqual(Right.objects.using(self.alias).filter(pk__in=[first.pk, second.pk]).count(), 2)

    def test_ambiguous_historical_subject_fails_closed(self):
        apps = self.executor.loader.project_state([("core", "0038_cotenant_private_identity_evidence")]).apps
        Facility=apps.get_model("core", "CoSo"); Room=apps.get_model("core", "Phong"); Right=apps.get_model("core", "QuyenRaVao")
        facility=Facility.objects.using(self.alias).create(ten_co_so="A", dia_chi="T", quan="T"); room=Room.objects.using(self.alias).create(co_so_id=facility.pk, so_phong="A-1", gia_thue=Decimal("1"), dien_tich=Decimal("1"), so_nguoi_toi_da=2)
        invalid=Right.objects.using(self.alias).create(phong_id=room.pk, loai_quyen="chu_phong", nguon_cap="face_id", trang_thai="hoat_dong", ngay_bat_dau=date.today())
        with self.assertRaisesRegex(RuntimeError, "invalid known-source subject rows"):
            MigrationExecutor(self.conn).migrate([("core", "0039_canonical_access_active_key")])
        self.assertTrue(Right.objects.using(self.alias).filter(pk=invalid.pk).exists())
