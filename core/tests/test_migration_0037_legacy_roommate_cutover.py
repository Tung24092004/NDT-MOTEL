from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import (
    DanhTinhNguoiOCung,
    FaceProfile,
    NguoiOCungPhong,
    PhuLucHopDong,
    QuyenRaVao,
    YeuCauGhepNguoi,
    YeuCauNguoiOCung,
)


class LegacyRoommateCutoverMigrationTests(BusinessFixture):
    migrate_from = ("core", "0036_cotenant_request_foundation")

    def historical_apps(self):
        return MigrationExecutor(connection).loader.project_state(
            [self.migrate_from]
        ).apps

    def legacy_request(self, *, state, name, cccd):
        request = self.sharing_request(self.contract())
        request.ho_ten = name
        request.cccd = cccd
        request.trang_thai = state
        request.ly_do = "Preserved legacy detail"
        request.ly_do_tu_choi = "Preserved prior rejection"
        request.ghi_chu_admin = "Preserved admin note"
        request.save()
        return request

    def test_forward_retires_only_pending_and_preserves_history_without_side_effects(self):
        pending = self.legacy_request(
            state="cho_duyet", name="Pending legacy", cccd="000000003701"
        )
        approved = self.legacy_request(
            state="da_duyet", name="Approved legacy", cccd="000000003702"
        )
        rejected = self.legacy_request(
            state="tu_choi", name="Rejected legacy", cccd="000000003703"
        )
        cancelled = self.legacy_request(
            state="da_huy", name="Cancelled legacy", cccd="000000003704"
        )
        preserved = (
            pending.ho_ten, pending.cccd, pending.ly_do, pending.ly_do_tu_choi,
            pending.ghi_chu_admin, pending.hop_dong_id, pending.nguoi_dang_ky_id,
        )
        effects_before = (
            YeuCauNguoiOCung.objects.count(), DanhTinhNguoiOCung.objects.count(),
            NguoiOCungPhong.objects.count(), PhuLucHopDong.objects.count(),
            FaceProfile.objects.count(), QuyenRaVao.objects.count(),
        )

        migration = import_module(
            "core.migrations.0037_retire_legacy_pending_roommate_requests"
        )
        migration.retire_pending_legacy_roommate_requests(
            self.historical_apps(), None
        )

        pending.refresh_from_db()
        self.assertEqual(pending.trang_thai, "da_huy")
        self.assertEqual(
            (
                pending.ho_ten, pending.cccd, pending.ly_do,
                pending.ly_do_tu_choi, pending.ghi_chu_admin,
                pending.hop_dong_id, pending.nguoi_dang_ky_id,
            ),
            preserved,
        )
        for request, state in (
            (approved, "da_duyet"), (rejected, "tu_choi"), (cancelled, "da_huy"),
        ):
            request.refresh_from_db()
            self.assertEqual(request.trang_thai, state)
        self.assertEqual(
            (
                YeuCauNguoiOCung.objects.count(), DanhTinhNguoiOCung.objects.count(),
                NguoiOCungPhong.objects.count(), PhuLucHopDong.objects.count(),
                FaceProfile.objects.count(), QuyenRaVao.objects.count(),
            ),
            effects_before,
        )

        migration.retire_pending_legacy_roommate_requests(
            self.historical_apps(), None
        )
        self.assertEqual(
            YeuCauGhepNguoi.objects.filter(trang_thai="cho_duyet").count(), 0
        )

    def test_zero_pending_is_safe_and_migration_has_no_reverse(self):
        self.legacy_request(
            state="da_huy", name="Already terminal", cccd="000000003705"
        )
        migration = import_module(
            "core.migrations.0037_retire_legacy_pending_roommate_requests"
        )
        migration.retire_pending_legacy_roommate_requests(
            self.historical_apps(), None
        )
        self.assertEqual(
            YeuCauGhepNguoi.objects.filter(trang_thai="cho_duyet").count(), 0
        )
        self.assertFalse(migration.Migration.operations[0].reversible)
