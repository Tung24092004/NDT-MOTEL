from datetime import date, datetime
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.operations.special import RunPython
from django.test import TransactionTestCase
from django.utils import timezone


class InvoicePaymentEvidenceAttemptsMigrationTests(TransactionTestCase):
    """Exercise 0034 against historical schemas, never the runtime models."""

    migrate_from = ("core", "0033_phan_hoi_hop_dong")
    migrate_to = ("core", "0034_invoice_payment_evidence_attempts")

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.leaf_nodes = self.executor.loader.graph.leaf_nodes()
        self.addCleanup(self._restore_leaf_state)
        self._prepare_legacy_schema()

    def _prepare_legacy_schema(self):
        """Build 0033 on a blank test database without faking a data reverse.

        0034 is intentionally irreversible.  Django's test runner starts at
        the leaf migration, so executing its reverse would both be forbidden
        and could leave non-transactional MySQL DDL partially unapplied.  The
        test database contains no fixture data at this point, therefore we
        reverse only its schema operations around the irreversible data step,
        then remove its recorder row before testing the forward migration.
        """
        migration = self.executor.loader.get_migration(*self.migrate_to)
        state = self.executor.loader.project_state([self.migrate_from])
        reverse_operations = []
        for operation in migration.operations:
            previous_state = state.clone()
            state = state.clone()
            operation.state_forwards(migration.app_label, state)
            if not isinstance(operation, RunPython):
                reverse_operations.insert(0, (operation, previous_state, state))
        with connection.schema_editor() as schema_editor:
            for operation, to_state, from_state in reverse_operations:
                operation.database_backwards(
                    migration.app_label, schema_editor, from_state, to_state
                )
        MigrationRecorder(connection).migration_qs.filter(
            app=self.migrate_to[0], name=self.migrate_to[1]
        ).delete()

    def _restore_leaf_state(self):
        # DDL is not assumed transactional on MySQL/MariaDB.  Always restore
        # the test schema, even when an assertion in the historical state fails.
        MigrationExecutor(connection).migrate(self.leaf_nodes)

    @staticmethod
    def _timestamp(year, month, day):
        return timezone.make_aware(datetime(year, month, day, 10, 30))

    def _legacy_objects(self, apps):
        User = apps.get_model("auth", "User")
        CoSo = apps.get_model("core", "CoSo")
        Phong = apps.get_model("core", "Phong")
        NguoiThue = apps.get_model("core", "NguoiThue")
        DatPhong = apps.get_model("core", "DatPhong")
        HopDong = apps.get_model("core", "HopDong")
        HoaDon = apps.get_model("core", "HoaDon")

        uploader = User.objects.create(username="legacy-uploader")
        reviewer = User.objects.create(username="legacy-reviewer")
        facility = CoSo.objects.create(
            ten_co_so="Migration facility", dia_chi="1 Test Street", quan="Test district"
        )
        room = Phong.objects.create(
            co_so=facility, so_phong="M-0034", gia_thue=Decimal("2500000"), dien_tich=Decimal("20")
        )
        tenant = NguoiThue.objects.create(
            ho_ten="Legacy tenant", so_dien_thoai="0900000034", cccd="003400000001"
        )
        booking = DatPhong.objects.create(
            nguoi_thue=tenant, phong=room, ngay_nhan_phong=date(2026, 1, 1),
            trang_thai="da_duyet", ma_yeu_cau="MIGRATION-0034",
        )
        contract = HopDong.objects.create(
            dat_phong=booking, so_hop_dong="HD-MIGRATION-0034", ngay_bat_dau=date(2026, 1, 1),
            ngay_ket_thuc=date(2027, 1, 1), tien_thue_thang=Decimal("2500000"),
        )
        invoice = HoaDon.objects.create(
            hop_dong=contract, thang=1, nam=2026, tien_phong=Decimal("2500000"),
            han_thanh_toan=date(2026, 1, 5), trang_thai="chua_thanh_toan",
        )
        return uploader, reviewer, invoice

    def test_legacy_invoice_evidence_is_preserved_and_backfilled(self):
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        Evidence = old_apps.get_model("core", "ChungTuThanhToan")
        uploader, reviewer, invoice = self._legacy_objects(old_apps)
        submitted_at = self._timestamp(2026, 1, 2)
        reviewed_at = self._timestamp(2026, 1, 3)
        evidence = Evidence.objects.create(
            hoa_don=invoice, nguoi_tai_len=uploader, nguoi_xu_ly=reviewer,
            anh="payment_evidence/legacy/receipt-0034.png", mime_type="image/png",
            ma_doi_chieu="NDTMOTEL HD LEGACY", trang_thai="tu_choi",
            thoi_diem_xu_ly=reviewed_at, ghi_chu_doi_soat="Legacy rejection reason",
        )
        Evidence.objects.filter(pk=evidence.pk).update(
            ngay_tao=submitted_at, ngay_cap_nhat=reviewed_at,
        )
        expected = {
            "pk": evidence.pk, "invoice_id": invoice.pk,
            "anh": "payment_evidence/legacy/receipt-0034.png",
            "mime_type": "image/png", "reference": "NDTMOTEL HD LEGACY",
            "status": "tu_choi", "submitted_at": submitted_at, "reviewed_at": reviewed_at,
            "uploader_id": uploader.pk, "reviewer_id": reviewer.pk,
            "reason": "Legacy rejection reason",
        }

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        new_apps = self.executor.loader.project_state([self.migrate_to]).apps
        NewEvidence = new_apps.get_model("core", "ChungTuThanhToan")
        NewInvoice = new_apps.get_model("core", "HoaDon")
        preserved = NewEvidence.objects.get(pk=expected["pk"])

        self.assertEqual(preserved.hoa_don_id, expected["invoice_id"])
        self.assertEqual(preserved.anh.name, expected["anh"])
        self.assertEqual(preserved.mime_type, expected["mime_type"])
        self.assertEqual(preserved.ma_doi_chieu, expected["reference"])
        self.assertEqual(preserved.trang_thai, expected["status"])
        self.assertEqual(preserved.ngay_tao, expected["submitted_at"])
        self.assertEqual(preserved.ngay_cap_nhat, expected["reviewed_at"])
        self.assertEqual(preserved.thoi_diem_xu_ly, expected["reviewed_at"])
        self.assertEqual(preserved.nguoi_tai_len_id, expected["uploader_id"])
        self.assertEqual(preserved.nguoi_xu_ly_id, expected["reviewer_id"])
        self.assertEqual(preserved.ghi_chu_doi_soat, expected["reason"])
        self.assertEqual(preserved.so_lan, 1)

        invoice_after = NewInvoice.objects.get(pk=invoice.pk)
        second = NewEvidence.objects.create(
            hoa_don=invoice_after, so_lan=2, nguoi_tai_len_id=uploader.pk,
            anh="payment_evidence/new/receipt-0034.png", mime_type="image/png",
            ma_doi_chieu="NDTMOTEL HD RETRY",
        )
        self.assertEqual(second.so_lan, 2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NewEvidence.objects.create(
                    hoa_don=invoice_after, so_lan=2, nguoi_tai_len_id=uploader.pk,
                    anh="payment_evidence/new/duplicate-0034.png", mime_type="image/png",
                    ma_doi_chieu="NDTMOTEL HD DUPLICATE",
                )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NewEvidence.objects.create(
                    hoa_don=invoice_after, so_lan=0, nguoi_tai_len_id=uploader.pk,
                    anh="payment_evidence/new/zero-0034.png", mime_type="image/png",
                    ma_doi_chieu="NDTMOTEL HD ZERO",
                )

    def test_migration_is_irreversible(self):
        migration = self.executor.loader.get_migration(*self.migrate_to)
        self.assertTrue(any(not operation.reversible for operation in migration.operations))
