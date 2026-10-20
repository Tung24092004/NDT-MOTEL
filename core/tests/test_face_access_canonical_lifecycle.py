from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db import close_old_connections
from django.test import TransactionTestCase
from threading import Barrier, Thread
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User

from core.dich_vu.quyen_ra_vao import grant_access, revoke_access
from core.dich_vu.yeu_cau_nguoi_o_cung import direct_admit, leave_residency
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import FaceProfile, QuyenRaVao
from core.quy_tac_nghiep_vu import eligible_permissions
from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong


class CanonicalAccessLifecycleTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()

    def test_active_tenant_grant_is_idempotent_and_face_profile_alone_grants_nothing(self):
        FaceProfile.objects.create(nguoi_thue=self.tenant, loai_chu_the="nguoi_thue", trang_thai="da_xac_thuc")
        self.assertFalse(QuyenRaVao.objects.exists())
        first, created = grant_access(
            contract_id=self.contract_obj.pk, tenant_id=self.tenant.pk,
            source="thu_cong", actor=self.admin,
        )
        again, created_again = grant_access(
            contract_id=self.contract_obj.pk, tenant_id=self.tenant.pk,
            source="face_id", actor=self.admin,
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(eligible_permissions(QuyenRaVao.objects.filter(pk=first.pk)).count(), 1)

    def test_invalid_contract_and_historical_residency_fail_closed(self):
        self.contract_obj.trang_thai = "da_huy"
        self.contract_obj.save(update_fields=["trang_thai"])
        with self.assertRaises(ValidationError):
            grant_access(contract_id=self.contract_obj.pk, tenant_id=self.tenant.pk, source="thu_cong")
        self.contract_obj.trang_thai = "dang_hieu_luc"
        self.contract_obj.save(update_fields=["trang_thai"])
        resident, _ = direct_admit(
            contract_id=self.contract_obj.pk, actor=self.admin, idempotency_key="access-resident",
            ho_ten="Access resident", cccd="000000009101", ngay_vao=self.today,
        )
        leave_residency(residency_id=resident.pk, actor=self.admin, idempotency_key="access-leave")
        with self.assertRaises(ValidationError):
            grant_access(contract_id=self.contract_obj.pk, resident_id=resident.pk, source="thu_cong")

    def test_revoke_is_idempotent_and_removes_runtime_entitlement(self):
        right, _ = grant_access(
            contract_id=self.contract_obj.pk, tenant_id=self.tenant.pk,
            source="thu_cong", actor=self.admin,
        )
        closed, changed = revoke_access(permission_id=right.pk)
        retry, changed_retry = revoke_access(permission_id=right.pk)
        self.assertTrue(changed)
        self.assertFalse(changed_retry)
        self.assertEqual(closed.pk, retry.pk)
        right.refresh_from_db()
        self.assertEqual(right.trang_thai, "bi_thu_hoi")
        self.assertIsNone(right.active_access_key)
        self.assertFalse(eligible_permissions(QuyenRaVao.objects.filter(pk=right.pk)).exists())

    def test_database_constraints_reject_ambiguous_subject_and_duplicate_active_slot(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                QuyenRaVao.objects.create(
                    hop_dong=self.contract_obj, phong=self.contract_obj.dat_phong.phong,
                    nguon_cap="face_id", loai_quyen="chu_phong", trang_thai="hoat_dong",
                    ngay_bat_dau=self.today, ngay_ket_thuc=self.contract_obj.ngay_ket_thuc,
                )


class CanonicalAccessConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from django.utils import timezone
        self.today = timezone.localdate()
        self.admin = User.objects.create_user("access-race-admin", is_staff=True)
        user = User.objects.create_user("access-race-tenant")
        self.tenant = NguoiThue.objects.create(tai_khoan=user, ho_ten="Race tenant", cccd="000000007701")
        facility = CoSo.objects.create(ten_co_so="Race", dia_chi="T", quan="T")
        room = Phong.objects.create(co_so=facility, so_phong="RACE-1", gia_thue=Decimal("1"), dien_tich=Decimal("1"), so_nguoi_toi_da=2)
        booking = DatPhong.objects.create(nguoi_thue=self.tenant, phong=room, ngay_nhan_phong=self.today, ngay_tra_du_kien=self.today + timedelta(days=30), trang_thai="da_duyet")
        self.contract = HopDong.objects.create(dat_phong=booking, so_hop_dong="RACE-ACCESS", ngay_bat_dau=self.today, ngay_ket_thuc=self.today + timedelta(days=30), tien_thue_thang=Decimal("1"), trang_thai="dang_hieu_luc")

    def test_real_connections_grant_vs_revoke_serializes_without_duplicate_active_right(self):
        right, _ = grant_access(contract_id=self.contract.pk, tenant_id=self.tenant.pk, source="thu_cong", actor=self.admin)
        barrier, outcomes = Barrier(2), []
        def grant():
            close_old_connections()
            try:
                barrier.wait(5); result = grant_access(contract_id=self.contract.pk, tenant_id=self.tenant.pk, source="face_id", actor=User.objects.get(pk=self.admin.pk)); outcomes.append(("grant", result[1]))
            finally: close_old_connections()
        def revoke():
            close_old_connections()
            try:
                barrier.wait(5); result = revoke_access(permission_id=right.pk); outcomes.append(("revoke", result[1]))
            finally: close_old_connections()
        workers = [Thread(target=grant), Thread(target=revoke)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(15); self.assertFalse(worker.is_alive())
        self.assertEqual(len(outcomes), 2)
        self.assertLessEqual(QuyenRaVao.objects.filter(active_access_key__isnull=False).count(), 1)
        self.assertLessEqual(eligible_permissions(QuyenRaVao.objects.all()).count(), 1)

    def test_real_connections_grant_vs_residency_leave_leaves_no_active_access(self):
        resident, _ = direct_admit(
            contract_id=self.contract.pk, actor=self.admin, idempotency_key="race-resident",
            ho_ten="Race resident", cccd="000000007702", ngay_vao=self.today,
        )
        barrier, outcomes = Barrier(2), []
        def grant():
            close_old_connections()
            try:
                barrier.wait(5)
                grant_access(contract_id=self.contract.pk, resident_id=resident.pk, source="thu_cong", actor=User.objects.get(pk=self.admin.pk))
                outcomes.append("grant")
            except ValidationError:
                outcomes.append("grant-blocked")
            finally: close_old_connections()
        def leave():
            close_old_connections()
            try:
                barrier.wait(5)
                leave_residency(residency_id=resident.pk, actor=User.objects.get(pk=self.admin.pk), idempotency_key="race-leave")
                outcomes.append("leave")
            finally: close_old_connections()
        workers = [Thread(target=grant), Thread(target=leave)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(15); self.assertFalse(worker.is_alive())
        self.assertEqual(len(outcomes), 2)
        resident.refresh_from_db()
        self.assertEqual(resident.trang_thai, "da_roi")
        self.assertFalse(QuyenRaVao.objects.filter(nguoi_o_cung=resident, trang_thai="hoat_dong").exists())
        self.assertFalse(QuyenRaVao.objects.filter(nguoi_o_cung=resident, active_access_key__isnull=False).exists())
