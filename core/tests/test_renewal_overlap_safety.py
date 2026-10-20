"""Focused regression coverage for renewal-vs-contract date conflicts."""
from datetime import timedelta
import threading

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections, transaction
from django.test import RequestFactory, TransactionTestCase, skipUnlessDBFeature

from core.dich_vu.hop_dong import room_contract_range_conflicts
from core.du_lieu_test import tap_hop_views as views
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import (
    DatPhong, HopDong, LichSuHopDong, PhuLucHopDong, QuyenRaVao,
    ThongBao, YeuCauGiaHanHopDong,
)


class RenewalOverlapSafetyTests(BusinessFixture):
    def setUp(self):
        self.contract = self.contract(
            "sap_het_han", start=self.today - timedelta(days=60),
            end=self.today + timedelta(days=10),
        )

    def renewal(self):
        return YeuCauGiaHanHopDong.objects.create(
            hop_dong=self.contract, nguoi_yeu_cau=self.tenant,
            so_thang_gia_han=2, ngay_ket_thuc_cu=self.contract.ngay_ket_thuc,
            ngay_ket_thuc_de_xuat=self.contract.ngay_ket_thuc + timedelta(days=60),
        )

    def competing(self, start, end, status="cho_hieu_luc"):
        booking = DatPhong.objects.create(
            nguoi_thue=self.other, phong=self.room, ngay_nhan_phong=start,
            ngay_tra_du_kien=end, so_thang_thue=1, trang_thai="da_duyet",
        )
        return HopDong.objects.create(
            dat_phong=booking, so_hop_dong=f"FUTURE-{booking.pk}",
            ngay_bat_dau=start, ngay_ket_thuc=end, tien_thue_thang=1,
            trang_thai=status,
        )

    def approve(self, renewal):
        return self.post(
            views.xu_ly_yeu_cau_gia_han, renewal,
            {"hanh_dong": "duyet"}, self.admin,
        )

    def test_no_competitor_and_self_do_not_block_valid_renewal(self):
        renewal = self.renewal()
        self.approve(renewal)
        self.contract.refresh_from_db(); renewal.refresh_from_db()
        self.assertEqual(self.contract.ngay_ket_thuc, renewal.ngay_ket_thuc_de_xuat)
        self.assertEqual(renewal.trang_thai, "da_duyet")

    def test_future_contract_after_proposed_end_does_not_block(self):
        renewal = self.renewal()
        self.competing(
            renewal.ngay_ket_thuc_de_xuat + timedelta(days=1),
            renewal.ngay_ket_thuc_de_xuat + timedelta(days=30),
        )
        self.approve(renewal)
        renewal.refresh_from_db()
        self.assertEqual(renewal.trang_thai, "da_duyet")

    def test_future_contract_inside_extension_blocks_without_side_effects(self):
        renewal = self.renewal()
        self.competing(
            self.contract.ngay_ket_thuc + timedelta(days=1),
            renewal.ngay_ket_thuc_de_xuat - timedelta(days=1),
        )
        right = self.permission(ngay_ket_thuc=self.contract.ngay_ket_thuc)
        before = (
            self.contract.ngay_ket_thuc, PhuLucHopDong.objects.count(),
            LichSuHopDong.objects.count(), ThongBao.objects.count(), right.ngay_ket_thuc,
        )
        self.approve(renewal); self.approve(renewal)
        self.contract.refresh_from_db(); renewal.refresh_from_db(); right.refresh_from_db()
        self.assertEqual(renewal.trang_thai, "cho_duyet")
        self.assertEqual(
            (self.contract.ngay_ket_thuc, PhuLucHopDong.objects.count(),
             LichSuHopDong.objects.count(), ThongBao.objects.count(), right.ngay_ket_thuc),
            before,
        )

    def test_cancelled_and_expired_competitors_do_not_block(self):
        renewal = self.renewal()
        for status in ("da_huy", "da_het_han"):
            self.competing(
                self.contract.ngay_ket_thuc + timedelta(days=1),
                renewal.ngay_ket_thuc_de_xuat - timedelta(days=1), status,
            )
        self.approve(renewal)
        renewal.refresh_from_db()
        self.assertEqual(renewal.trang_thai, "da_duyet")


@skipUnlessDBFeature("has_select_for_update")
class RenewalOverlapConcurrencyTests(TransactionTestCase):
    def setUp(self):
        BusinessFixture.setUpTestData.__func__(type(self))
        booking = DatPhong.objects.create(
            nguoi_thue=self.tenant, phong=self.room,
            ngay_nhan_phong=self.today - timedelta(days=60),
            ngay_tra_du_kien=self.today + timedelta(days=10), so_thang_thue=3,
            trang_thai="da_duyet",
        )
        self.contract = HopDong.objects.create(
            dat_phong=booking, so_hop_dong="RENEW-RACE-A",
            ngay_bat_dau=booking.ngay_nhan_phong, ngay_ket_thuc=booking.ngay_tra_du_kien,
            tien_thue_thang=1, trang_thai="sap_het_han",
        )
        self.renewal = YeuCauGiaHanHopDong.objects.create(
            hop_dong=self.contract, nguoi_yeu_cau=self.tenant, so_thang_gia_han=2,
            ngay_ket_thuc_cu=self.contract.ngay_ket_thuc,
            ngay_ket_thuc_de_xuat=self.contract.ngay_ket_thuc + timedelta(days=60),
        )

    def test_renewal_and_competing_contract_creation_cannot_commit_overlap(self):
        barrier, outcomes, outcome_lock = threading.Barrier(2, timeout=10), [], threading.Lock()

        def approve():
            close_old_connections()
            try:
                barrier.wait()
                request = RequestFactory().post("/audit/", {"hanh_dong": "duyet"})
                request.user = User.objects.get(pk=self.admin.pk)
                request.session = {}; request._messages = FallbackStorage(request)
                views.xu_ly_yeu_cau_gia_han(request, self.renewal.pk)
                outcome = "approved"
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        def create_competitor():
            close_old_connections()
            try:
                barrier.wait()
                with transaction.atomic():
                    room = type(self.room).objects.select_for_update().get(pk=self.room.pk)
                    start = self.contract.ngay_ket_thuc + timedelta(days=1)
                    end = self.renewal.ngay_ket_thuc_de_xuat - timedelta(days=1)
                    if room_contract_range_conflicts(room, start, end):
                        outcome = "blocked"
                    else:
                        booking = DatPhong.objects.create(
                            nguoi_thue=type(self.other).objects.get(pk=self.other.pk), phong=room,
                            ngay_nhan_phong=start, ngay_tra_du_kien=end, so_thang_thue=1,
                            trang_thai="da_duyet",
                        )
                        HopDong.objects.create(
                            dat_phong=booking, so_hop_dong="RENEW-RACE-B",
                            ngay_bat_dau=start, ngay_ket_thuc=end, tien_thue_thang=1,
                            trang_thai="cho_hieu_luc",
                        )
                        outcome = "created"
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=approve), threading.Thread(target=create_competitor)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive(), "renewal overlap race timed out")
        connections.close_all()
        contracts = list(HopDong.objects.filter(dat_phong__phong=self.room).exclude(
            trang_thai__in=("da_huy", "da_het_han")
        ).order_by("pk"))
        self.assertFalse(
            len(contracts) == 2
            and contracts[0].ngay_bat_dau <= contracts[1].ngay_ket_thuc
            and contracts[0].ngay_ket_thuc >= contracts[1].ngay_bat_dau,
            outcomes,
        )
