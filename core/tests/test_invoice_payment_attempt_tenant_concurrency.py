import threading
import shutil
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction, close_old_connections
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from core.dich_vu.chung_tu_thanh_toan import active_invoice_attempt, create_for_invoice
from core.models import ChungTuThanhToan, CoSo, DatPhong, HoaDon, HopDong, NguoiThue, Phong
from core.private_storage import private_payment_evidence_storage


def receipt(name, color):
    payload = BytesIO()
    Image.new("RGB", (8, 8), color).save(payload, format="PNG")
    return SimpleUploadedFile(name, payload.getvalue(), content_type="image/png")


@skipUnlessDBFeature("has_select_for_update")
class TenantInvoiceAttemptConcurrencyTests(TransactionTestCase):
    """Real MySQL connections exercise the invoice-first locking contract."""

    reset_sequences = True

    def setUp(self):
        super().setUp()
        self.assertEqual(connection.vendor, "mysql", "These races require MySQL/MariaDB.")
        self.private_directory = settings.BASE_DIR / ".test-media" / f"invoice-attempt-{uuid4().hex}"
        self.private_directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.private_directory, ignore_errors=True)
        self.storage_state = dict(private_payment_evidence_storage.__dict__)
        private_payment_evidence_storage._location = str(self.private_directory)
        private_payment_evidence_storage.__dict__.pop("base_location", None)
        private_payment_evidence_storage.__dict__.pop("location", None)
        self.user = User.objects.create_user("invoice-race-owner")
        facility = CoSo.objects.create(ten_co_so="Invoice race", dia_chi="Test", quan="Hai Chau")
        room = Phong.objects.create(
            co_so=facility, so_phong="INVOICE-RACE", gia_thue=Decimal("2500000"), dien_tich=Decimal("24")
        )
        tenant = NguoiThue.objects.create(
            tai_khoan=self.user, ho_ten="Invoice race owner", cccd="012345670034", so_dien_thoai="0900000034"
        )
        booking = DatPhong.objects.create(
            nguoi_thue=tenant, phong=room, ngay_nhan_phong=date(2026, 1, 1),
            trang_thai="da_duyet", ma_yeu_cau="INVOICE-RACE-0034",
        )
        contract = HopDong.objects.create(
            dat_phong=booking, so_hop_dong="HD-INVOICE-RACE", ngay_bat_dau=date(2026, 1, 1),
            ngay_ket_thuc=date(2027, 1, 1), tien_thue_thang=Decimal("2500000"),
        )
        self.invoice = HoaDon.objects.create(
            hop_dong=contract, thang=1, nam=2026, tien_phong=Decimal("2500000"),
            han_thanh_toan=date(2026, 1, 5), trang_thai="chua_thanh_toan",
        )

    def tearDown(self):
        private_payment_evidence_storage.__dict__.clear()
        private_payment_evidence_storage.__dict__.update(self.storage_state)
        shutil.rmtree(self.private_directory, ignore_errors=True)
        super().tearDown()

    def _files(self):
        return sorted(
            path.relative_to(self.private_directory).as_posix()
            for path in self.private_directory.rglob("*") if path.is_file()
        )

    def _concurrent_report(self, first, second):
        barrier = threading.Barrier(2, timeout=10)
        results, result_lock = [], threading.Lock()

        def worker(upload):
            close_old_connections()
            try:
                client = Client()
                client.force_login(User.objects.get(pk=self.user.pk))
                barrier.wait()
                response = client.post(reverse("thanh_toan_hoa_don_cua_toi", args=[self.invoice.pk]), {
                    "buoc": "xac_thuc", "phuong_thuc": "chuyen_khoan", "xac_nhan": "dong_y",
                    "anh_chung_tu": upload,
                })
                outcome = ("response", response.status_code)
            except Exception as exc:  # Assert worker failures rather than losing them in a thread.
                outcome = ("error", repr(exc))
            finally:
                with result_lock:
                    results.append(outcome)
                close_old_connections()

        threads = [threading.Thread(target=worker, args=(upload,)) for upload in (first, second)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads), "A tenant race worker hung.")
        self.assertEqual(sorted(results), [("response", 302), ("response", 302)])

    def test_concurrent_first_submission_creates_one_attempt_and_one_file(self):
        self._concurrent_report(receipt("first-a.png", "red"), receipt("first-b.png", "blue"))
        self.invoice.refresh_from_db()
        attempts = list(ChungTuThanhToan.objects.filter(hoa_don=self.invoice))
        self.assertEqual(len(attempts), 1)
        attempt = attempts[0]
        self.assertEqual((attempt.so_lan, attempt.trang_thai), (1, "cho_doi_soat"))
        self.assertEqual(self.invoice.trang_thai, "cho_xac_nhan")
        self.assertEqual(active_invoice_attempt(self.invoice).pk, attempt.pk)
        self.assertEqual(self._files(), [attempt.anh.name])

    def test_concurrent_retry_creates_only_attempt_two_and_keeps_attempt_one(self):
        self._concurrent_report(receipt("initial.png", "red"), receipt("ignored.png", "blue"))
        first = ChungTuThanhToan.objects.get(hoa_don=self.invoice)
        first_snapshot = (first.pk, first.anh.name, first.nguoi_tai_len_id)
        ChungTuThanhToan.objects.filter(pk=first.pk).update(
            trang_thai="tu_choi", ghi_chu_doi_soat="Rejected receipt", nguoi_xu_ly_id=self.user.pk
        )
        HoaDon.objects.filter(pk=self.invoice.pk).update(trang_thai="chua_thanh_toan", phuong_thuc="")

        self._concurrent_report(receipt("retry-a.png", "green"), receipt("retry-b.png", "yellow"))
        attempts = list(ChungTuThanhToan.objects.filter(hoa_don=self.invoice).order_by("so_lan"))
        self.assertEqual([(item.so_lan, item.trang_thai) for item in attempts], [(1, "tu_choi"), (2, "cho_doi_soat")])
        self.assertEqual((attempts[0].pk, attempts[0].anh.name, attempts[0].nguoi_tai_len_id), first_snapshot)
        self.assertNotEqual(attempts[1].anh.name, attempts[0].anh.name)
        self.assertEqual(active_invoice_attempt(self.invoice).pk, attempts[1].pk)
        self.assertEqual(self._files(), sorted([item.anh.name for item in attempts]))

    def test_delayed_tenant_report_after_paid_does_not_regress_invoice(self):
        self._concurrent_report(receipt("initial.png", "red"), receipt("ignored.png", "blue"))
        original = ChungTuThanhToan.objects.get(hoa_don=self.invoice)
        HoaDon.objects.filter(pk=self.invoice.pk).update(trang_thai="da_thanh_toan")
        client = Client()
        client.force_login(self.user)
        response = client.post(reverse("thanh_toan_hoa_don_cua_toi", args=[self.invoice.pk]), {
            "buoc": "xac_thuc", "phuong_thuc": "chuyen_khoan", "xac_nhan": "dong_y",
            "anh_chung_tu": receipt("late.png", "green"),
        })
        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.trang_thai, "da_thanh_toan")
        self.assertEqual(list(ChungTuThanhToan.objects.filter(hoa_don=self.invoice).values_list("pk", "anh")), [(original.pk, original.anh.name)])
        self.assertEqual(self._files(), [original.anh.name])

    def test_corrupt_multiple_pending_attempts_fail_closed_without_mutation(self):
        first = ChungTuThanhToan.objects.create(
            hoa_don=self.invoice, so_lan=1, nguoi_tai_len=self.user,
            anh=receipt("corrupt-a.png", "red"), mime_type="image/png", ma_doi_chieu="CORRUPT-A",
        )
        second = ChungTuThanhToan.objects.create(
            hoa_don=self.invoice, so_lan=2, nguoi_tai_len=self.user,
            anh=receipt("corrupt-b.png", "blue"), mime_type="image/png", ma_doi_chieu="CORRUPT-B",
        )
        before = list(ChungTuThanhToan.objects.filter(hoa_don=self.invoice).values_list("pk", "so_lan", "anh", "trang_thai"))
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                locked = HoaDon.objects.select_for_update().select_related(
                    "hop_dong__dat_phong__nguoi_thue"
                ).get(pk=self.invoice.pk)
                create_for_invoice(actor=self.user, invoice=locked, uploaded=receipt("blocked.png", "green"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.trang_thai, "chua_thanh_toan")
        self.assertEqual(list(ChungTuThanhToan.objects.filter(hoa_don=self.invoice).values_list("pk", "so_lan", "anh", "trang_thai")), before)
        self.assertEqual({first.pk, second.pk}, set(ChungTuThanhToan.objects.filter(hoa_don=self.invoice).values_list("pk", flat=True)))
