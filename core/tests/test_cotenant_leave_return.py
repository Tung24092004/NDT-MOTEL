from threading import Barrier, Thread
from unittest.mock import patch
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase

from core.dich_vu.yeu_cau_nguoi_o_cung import (
    direct_admit, leave_residency, return_as_new_residency,
)
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import CoSo, DatPhong, FaceProfile, HopDong, NguoiOCungPhong, NguoiThue, Phong, PhuLucHopDong, QuyenRaVao, ThongBao
from core.views_smart_room import xu_ly_nguoi_o_cung


class CoTenantLeaveReturnTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.resident, _ = direct_admit(
            contract_id=self.contract_obj.pk, actor=self.admin, idempotency_key="leave-seed",
            ho_ten="Lifecycle resident", cccd="000000005101", ngay_vao=self.today,
        )
        self.face = FaceProfile.objects.create(
            danh_tinh_nguoi_o_cung=self.resident.identity,
            nguoi_o_cung=self.resident,
            loai_chu_the="nguoi_o_cung",
        )
        self.access = self.permission(
            hop_dong=self.contract_obj, nguoi_thue=None, nguoi_o_cung=self.resident,
            loai_quyen="nguoi_o_cung", nguon_cap="thu_cong", ngay_ket_thuc=None,
        )

    def leave(self, key="leave-key"):
        return leave_residency(residency_id=self.resident.pk, actor=self.admin, idempotency_key=key)

    def test_leave_preserves_history_face_and_revokes_active_access_once(self):
        resident, changed = self.leave()
        self.assertTrue(changed)
        resident.refresh_from_db(); self.access.refresh_from_db()
        self.assertEqual(resident.trang_thai, "da_roi")
        self.assertIsNone(resident.active_identity_key)
        self.assertTrue(FaceProfile.objects.filter(pk=self.face.pk, nguoi_o_cung=resident).exists())
        self.assertEqual(self.access.trang_thai, "bi_thu_hoi")
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 2)
        retry, changed = self.leave()
        self.assertFalse(changed); self.assertEqual(retry.pk, resident.pk)
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 2)

    def test_return_creates_new_row_reuses_identity_and_does_not_move_face_or_access(self):
        old, _ = self.leave()
        resident, created = return_as_new_residency(
            residency_id=old.pk, actor=self.admin, idempotency_key="return-key"
        )
        self.assertTrue(created); self.assertNotEqual(resident.pk, old.pk)
        old.refresh_from_db(); self.face.refresh_from_db(); self.access.refresh_from_db()
        self.assertEqual(old.trang_thai, "da_roi")
        self.assertEqual(resident.trang_thai, "dang_o")
        self.assertEqual(resident.identity_id, old.identity_id)
        self.assertEqual(self.face.nguoi_o_cung_id, old.pk)
        self.assertEqual(self.access.nguoi_o_cung_id, old.pk)
        self.assertEqual(QuyenRaVao.objects.filter(nguoi_o_cung=resident).count(), 0)
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 3)
        retry, created = return_as_new_residency(residency_id=old.pk, actor=self.admin, idempotency_key="return-key")
        self.assertFalse(created); self.assertEqual(retry.pk, resident.pk)

    def test_core_and_access_failures_rollback_and_audit_is_best_effort(self):
        with patch("core.dich_vu.yeu_cau_nguoi_o_cung.ghi_nhan_thay_doi_cu_tru", side_effect=RuntimeError("appendix")):
            with self.assertRaisesRegex(RuntimeError, "appendix"):
                self.leave("fail-appendix")
        self.resident.refresh_from_db(); self.assertEqual(self.resident.trang_thai, "dang_o")
        with patch("core.dich_vu.yeu_cau_nguoi_o_cung.thu_hoi_quyen_nguoi_o_cung", side_effect=RuntimeError("access")):
            with self.assertRaisesRegex(RuntimeError, "access"):
                self.leave("fail-access")
        self.resident.refresh_from_db(); self.assertEqual(self.resident.trang_thai, "dang_o")
        with patch("core.dich_vu.yeu_cau_nguoi_o_cung.ghi_nhat_ky", side_effect=RuntimeError("audit")):
            _, changed = self.leave("audit-failure")
        self.assertTrue(changed)

    def test_return_conflicts_and_generic_edit_cannot_change_lifecycle(self):
        old, _ = self.leave()
        active = NguoiOCungPhong.objects.create(
            hop_dong=self.contract_obj, identity=old.identity, ho_ten="Conflicting active",
            cccd=old.cccd, ngay_vao=self.today, trang_thai="dang_o", da_xac_minh_boi_admin=True,
        )
        with self.assertRaisesRegex(ValidationError, "dang luu tru"):
            return_as_new_residency(residency_id=old.pk, actor=self.admin, idempotency_key="conflict")
        active.trang_thai = "da_roi"; active.ngay_ra = self.today
        active.save(update_fields=["trang_thai", "ngay_ra", "active_identity_key", "ngay_cap_nhat"])
        request = self.request(self.admin, {"hanh_dong": "cap_nhat", "ho_ten": old.ho_ten, "cccd": old.cccd, "trang_thai": "dang_o"})
        response = xu_ly_nguoi_o_cung(request, old.pk)
        self.assertEqual(response.status_code, 302); old.refresh_from_db()
        self.assertEqual(old.trang_thai, "da_roi")

    def test_legacy_status_actions_are_fail_closed_and_return_failure_rolls_back(self):
        response = xu_ly_nguoi_o_cung(self.request(self.admin, {"hanh_dong": "cho_bo_sung"}), self.resident.pk)
        self.assertEqual(response.status_code, 302)
        self.resident.refresh_from_db(); self.assertEqual(self.resident.trang_thai, "dang_o")
        old, _ = self.leave()
        before = NguoiOCungPhong.objects.count()
        with patch("core.dich_vu.yeu_cau_nguoi_o_cung.ghi_nhan_thay_doi_cu_tru", side_effect=RuntimeError("appendix")):
            with self.assertRaisesRegex(RuntimeError, "appendix"):
                return_as_new_residency(residency_id=old.pk, actor=self.admin, idempotency_key="return-fail")
        old.refresh_from_db()
        self.assertEqual(old.trang_thai, "da_roi")
        self.assertEqual(NguoiOCungPhong.objects.count(), before)

    def test_legacy_return_post_creates_new_residency_and_no_notification_is_introduced(self):
        old, _ = self.leave()
        before_notifications = ThongBao.objects.count()
        response = xu_ly_nguoi_o_cung(self.request(self.admin, {"hanh_dong": "quay_lai"}), old.pk)
        self.assertEqual(response.status_code, 302)
        old.refresh_from_db()
        self.assertEqual(old.trang_thai, "da_roi")
        self.assertEqual(NguoiOCungPhong.objects.filter(identity=old.identity, trang_thai="dang_o").count(), 1)
        self.assertEqual(ThongBao.objects.count(), before_notifications)


class CoTenantReturnConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from django.utils import timezone
        self.today = timezone.localdate()
        self.admin = User.objects.create_user("return-admin", is_staff=True)
        tenant_user = User.objects.create_user("return-tenant")
        tenant = NguoiThue.objects.create(tai_khoan=tenant_user, ho_ten="Return tenant", cccd="000000005200", so_dien_thoai="0900005200")
        facility = CoSo.objects.create(ten_co_so="Return facility", dia_chi="Test", quan="Test")
        room = Phong.objects.create(co_so=facility, so_phong="RT-1", gia_thue=Decimal("2500000"), dien_tich=Decimal("20"), so_nguoi_toi_da=3)
        booking = DatPhong.objects.create(nguoi_thue=tenant, phong=room, ngay_nhan_phong=self.today, ngay_tra_du_kien=self.today + timedelta(days=90), trang_thai="da_duyet")
        self.contract_obj = HopDong.objects.create(dat_phong=booking, so_hop_dong="RETURN-CONCURRENT", ngay_bat_dau=self.today, ngay_ket_thuc=self.today + timedelta(days=90), tien_thue_thang=Decimal("2500000"), trang_thai="dang_hieu_luc")
        self.resident, _ = direct_admit(
            contract_id=self.contract_obj.pk, actor=self.admin, idempotency_key="concurrent-seed",
            ho_ten="Concurrent return", cccd="000000005201", ngay_vao=self.today,
        )
        leave_residency(residency_id=self.resident.pk, actor=self.admin, idempotency_key="concurrent-leave")

    def test_two_returns_have_one_winner(self):
        barrier, outcomes = Barrier(2), []
        def worker(key):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                resident, created = return_as_new_residency(
                    residency_id=self.resident.pk, actor=type(self.admin).objects.get(pk=self.admin.pk),
                    idempotency_key=key,
                )
                outcomes.append(("created" if created else "retry", resident.pk))
            except ValidationError:
                outcomes.append(("blocked", None))
            finally:
                close_old_connections()
        threads = [Thread(target=worker, args=(key,)) for key in ("return-a", "return-b")]
        for thread in threads: thread.start()
        for thread in threads:
            thread.join(timeout=15); self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(x[0] for x in outcomes), ["blocked", "created"])
        self.assertEqual(NguoiOCungPhong.objects.filter(identity=self.resident.identity, trang_thai="dang_o").count(), 1)
