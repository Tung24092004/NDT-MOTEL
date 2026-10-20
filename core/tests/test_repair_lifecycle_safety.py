"""Focused regressions for the repair-request lifecycle boundary."""
import threading
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from core.admin import YeuCauSuaChuaAdmin
from core.dich_vu.sua_chua import create_repair_request, transition_repair_request
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import LichSuSuaChua, YeuCauSuaChua


class RepairLifecycleSafetyTests(BusinessFixture):
    def create_repair(self):
        return create_repair_request(
            actor=self.user, tenant_id=self.tenant.pk, room_id=self.room.pk,
            title="Leaking tap", content="Bathroom tap leaks.", issue_type="nuoc",
            priority="cao",
        )

    def test_current_tenant_can_create_repair_without_changing_room_state(self):
        self.contract()
        before = self.room.trang_thai
        repair = self.create_repair()
        self.room.refresh_from_db()
        self.assertEqual(self.room.trang_thai, before)
        self.assertEqual(repair.trang_thai, "moi")
        self.assertEqual(LichSuSuaChua.objects.filter(yeu_cau=repair).count(), 1)

    def test_stale_active_status_after_end_date_cannot_create_repair(self):
        contract = self.contract()
        contract.ngay_ket_thuc = self.today - timedelta(days=1)
        contract.save(update_fields=["ngay_ket_thuc"])
        with self.assertRaises(ValidationError):
            self.create_repair()

    def test_other_tenant_cannot_create_for_another_room(self):
        self.contract()
        with self.assertRaises(ValidationError):
            create_repair_request(
                actor=self.other_user, tenant_id=self.other.pk, room_id=self.room.pk,
                title="Foreign", content="Not my room.", issue_type="dien", priority="cao",
            )

    def test_forward_transitions_append_one_history_each(self):
        repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant, phong=self.room, tieu_de="Repair", noi_dung="Detail",
            loai_su_co="dien", muc_do="cao",
        )
        for target, handler in (("dang_xu_ly", "Technician"), ("cho_thay_the", "Technician"),
                                ("hoan_thanh", "Technician")):
            transition_repair_request(
                actor=self.admin, repair_id=repair.pk, target_status=target, handler=handler,
                cost=0, cost_detail="", admin_note="",
            )
        repair.refresh_from_db()
        self.assertEqual(repair.trang_thai, "hoan_thanh")
        self.assertIsNotNone(repair.ngay_bat_dau_xu_ly)
        self.assertIsNotNone(repair.ngay_hoan_thanh)
        self.assertEqual(LichSuSuaChua.objects.filter(yeu_cau=repair).count(), 3)

    def test_invalid_backward_and_terminal_transitions_preserve_request_and_history(self):
        repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant, phong=self.room, tieu_de="Repair", noi_dung="Detail",
            loai_su_co="dien", muc_do="cao",
        )
        with self.assertRaises(ValidationError):
            transition_repair_request(actor=self.admin, repair_id=repair.pk, target_status="hoan_thanh",
                                      handler="", cost=0, cost_detail="", admin_note="")
        self.assertEqual(LichSuSuaChua.objects.filter(yeu_cau=repair).count(), 0)
        transition_repair_request(actor=self.admin, repair_id=repair.pk, target_status="dang_xu_ly",
                                  handler="Technician", cost=0, cost_detail="", admin_note="")
        repair.refresh_from_db()
        before = (repair.trang_thai, repair.ngay_bat_dau_xu_ly, repair.ngay_hoan_thanh,
                  LichSuSuaChua.objects.filter(yeu_cau=repair).count())
        with self.assertRaises(ValidationError):
            transition_repair_request(actor=self.admin, repair_id=repair.pk, target_status="moi",
                                      handler="", cost=0, cost_detail="", admin_note="")
        repair.refresh_from_db()
        after = (repair.trang_thai, repair.ngay_bat_dau_xu_ly, repair.ngay_hoan_thanh,
                 LichSuSuaChua.objects.filter(yeu_cau=repair).count())
        self.assertEqual(after, before)
        transition_repair_request(actor=self.admin, repair_id=repair.pk, target_status="hoan_thanh",
                                  handler="Technician", cost=0, cost_detail="", admin_note="")
        with self.assertRaises(ValidationError):
            transition_repair_request(actor=self.admin, repair_id=repair.pk, target_status="dang_xu_ly",
                                      handler="Technician", cost=0, cost_detail="", admin_note="")

    def test_non_admin_cannot_transition_directly(self):
        repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant, phong=self.room, tieu_de="Repair", noi_dung="Detail",
            loai_su_co="dien", muc_do="cao",
        )
        with self.assertRaises(PermissionDenied):
            transition_repair_request(actor=self.user, repair_id=repair.pk, target_status="dang_xu_ly",
                                      handler="Technician", cost=0, cost_detail="", admin_note="")

    def test_django_admin_cannot_bypass_lifecycle_fields_or_create_delete(self):
        repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant, phong=self.room, tieu_de="Repair", noi_dung="Detail",
            loai_su_co="dien", muc_do="cao",
        )
        admin = YeuCauSuaChuaAdmin(YeuCauSuaChua, AdminSite())
        readonly = admin.get_readonly_fields(None, repair)
        self.assertFalse(admin.has_add_permission(None))
        self.assertFalse(admin.has_delete_permission(None, repair))
        self.assertTrue({"trang_thai", "ngay_bat_dau_xu_ly", "ngay_hoan_thanh"}.issubset(readonly))


@skipUnlessDBFeature("has_select_for_update")
class RepairLifecycleConcurrencyTests(TransactionTestCase):
    def setUp(self):
        BusinessFixture.setUpTestData.__func__(type(self))
        self.repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant, phong=self.room, tieu_de="Repair", noi_dung="Detail",
            loai_su_co="dien", muc_do="cao",
        )

    def test_concurrent_admin_transitions_leave_one_state_and_one_history(self):
        barrier = threading.Barrier(2, timeout=10)
        outcomes, outcome_lock = [], threading.Lock()

        def worker(target, handler):
            close_old_connections()
            try:
                barrier.wait()
                transition_repair_request(
                    actor=type(self.admin).objects.get(pk=self.admin.pk), repair_id=self.repair.pk,
                    target_status=target, handler=handler, cost=0, cost_detail="", admin_note="",
                )
                outcome = "ok"
            except ValidationError:
                outcome = "blocked"
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=worker, args=("dang_xu_ly", "A")),
                   threading.Thread(target=worker, args=("tu_choi", ""))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive(), "repair transition race timed out")
        connections.close_all()
        self.repair.refresh_from_db()
        self.assertEqual(sorted(outcomes), ["blocked", "ok"])
        self.assertIn(self.repair.trang_thai, ("dang_xu_ly", "tu_choi"))
        self.assertEqual(LichSuSuaChua.objects.filter(yeu_cau=self.repair).count(), 1)
