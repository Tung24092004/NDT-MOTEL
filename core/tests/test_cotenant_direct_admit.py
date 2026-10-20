from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Thread
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import RequestFactory, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from core.dich_vu.yeu_cau_nguoi_o_cung import direct_admit
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import (
    DanhTinhNguoiOCung,
    FaceProfile,
    NguoiOCungPhong,
    PhuLucHopDong,
    QuyenRaVao,
    ThongBao,
    YeuCauGhepNguoi,
    YeuCauNguoiOCung,
    CoSo,
    DatPhong,
    HopDong,
    NguoiThue,
    Phong,
)
from core.views_smart_room import tao_nguoi_o_cung


class CoTenantDirectAdmitTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()

    def payload(self, cccd="000000004101"):
        return {
            "ho_ten": "Verified direct admit", "cccd": cccd,
            "ngay_vao": self.today, "ngay_sinh": None,
            "gioi_tinh": "", "so_dien_thoai": "0900004101", "quan_he": "Ban",
        }

    def admit(self, *, key="direct-admit-key", actor=None, contract_id=None, **overrides):
        payload = self.payload()
        payload.update(overrides)
        return direct_admit(
            contract_id=contract_id or self.contract_obj.pk, actor=actor or self.admin,
            idempotency_key=key, **payload,
        )

    def test_valid_direct_admit_creates_only_canonical_domain_records(self):
        before = (
            YeuCauNguoiOCung.objects.count(), FaceProfile.objects.count(),
            QuyenRaVao.objects.count(),
        )
        resident, created = self.admit()
        self.assertTrue(created)
        self.assertEqual(resident.trang_thai, "dang_o")
        self.assertTrue(resident.da_xac_minh_boi_admin)
        self.assertEqual(DanhTinhNguoiOCung.objects.filter(cccd="000000004101").count(), 1)
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 1)
        self.assertEqual(
            (YeuCauNguoiOCung.objects.count(), FaceProfile.objects.count(), QuyenRaVao.objects.count()),
            before,
        )

    def test_retry_is_idempotent_and_different_key_hits_active_identity_protection(self):
        resident, created = self.admit(key="same-key")
        retry, retried = self.admit(key="same-key")
        self.assertTrue(created)
        self.assertFalse(retried)
        self.assertEqual(retry.pk, resident.pk)
        self.assertEqual(NguoiOCungPhong.objects.count(), 1)
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 1)
        self.assertEqual(
            ThongBao.objects.filter(
                ma_tham_chieu=f"COTENANT_DIRECT_ADMIT:{self.contract_obj.pk}:same-key"
            ).count(),
            1,
        )
        with self.assertRaisesRegex(ValidationError, "dang luu tru"):
            self.admit(key="other-key")
        self.assertEqual(NguoiOCungPhong.objects.count(), 1)

    def test_permissions_contract_tenant_cccd_and_capacity_are_enforced(self):
        with self.assertRaisesRegex(ValidationError, "Khong co quyen"):
            self.admit(actor=self.user)
        self.contract_obj.trang_thai = "da_het_han"
        self.contract_obj.save(update_fields=["trang_thai", "ngay_cap_nhat"])
        with self.assertRaisesRegex(ValidationError, "khong con hieu luc"):
            self.admit(key="inactive")
        self.contract_obj.trang_thai = "dang_hieu_luc"
        self.contract_obj.save(update_fields=["trang_thai", "ngay_cap_nhat"])
        with self.assertRaisesRegex(ValidationError, "nguoi thue chinh"):
            self.admit(key="tenant-cccd", cccd=self.tenant.cccd)
        self.room.so_nguoi_toi_da = 1
        self.room.save(update_fields=["so_nguoi_toi_da", "ngay_cap_nhat"])
        with self.assertRaisesRegex(ValidationError, "suc chua"):
            self.admit(key="full-room")

    def test_critical_failures_rollback_and_audit_is_best_effort(self):
        with patch(
            "core.dich_vu.yeu_cau_nguoi_o_cung.ghi_nhan_thay_doi_cu_tru",
            side_effect=RuntimeError("appendix failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "appendix failed"):
                self.admit(key="appendix-fail")
        self.assertEqual(NguoiOCungPhong.objects.count(), 0)
        self.assertEqual(DanhTinhNguoiOCung.objects.count(), 0)

        with patch("core.dich_vu.yeu_cau_nguoi_o_cung.ghi_nhat_ky", side_effect=RuntimeError("audit failed")):
            resident, created = self.admit(key="audit-fail")
        self.assertTrue(created)
        self.assertEqual(NguoiOCungPhong.objects.get().pk, resident.pk)

    def test_notification_failure_rolls_back_under_existing_transactional_policy(self):
        with patch.object(ThongBao.objects, "get_or_create", side_effect=RuntimeError("notification failed")):
            with self.assertRaisesRegex(RuntimeError, "notification failed"):
                self.admit(key="notification-fail")
        self.assertEqual(NguoiOCungPhong.objects.count(), 0)
        self.assertEqual(PhuLucHopDong.objects.count(), 0)

    def test_admin_form_calls_service_without_direct_orm_write(self):
        request = RequestFactory().post(reverse("tao_nguoi_o_cung"), {
            "hop_dong": self.contract_obj.pk, "ho_ten": "Form candidate",
            "cccd": "000000004106", "ngay_vao": self.today.isoformat(),
            "idempotency_key": "form-key",
        })
        request.user = self.admin
        request.session = {}
        request._messages = FallbackStorage(request)
        with patch("core.views_smart_room.direct_admit", return_value=(type("R", (), {"pk": 77})(), True)) as service:
            response = tao_nguoi_o_cung(request)
        service.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(NguoiOCungPhong.objects.exists())

    def test_non_admin_form_denied_and_legacy_approval_is_fail_closed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("tao_nguoi_o_cung"), {}).status_code, 302)
        legacy = YeuCauGhepNguoi.objects.create(
            hop_dong=self.contract_obj, nguoi_dang_ky=self.other,
            ho_ten="Legacy preserved", cccd="000000004107", ngay_du_kien_vao=self.today,
        )
        before = (NguoiOCungPhong.objects.count(), FaceProfile.objects.count(), QuyenRaVao.objects.count())
        self.client.force_login(self.admin)
        response = self.client.post(reverse("xu_ly_yeu_cau_ghep", args=[legacy.pk]), {"hanh_dong": "duyet"})
        self.assertEqual(response.status_code, 302)
        legacy.refresh_from_db()
        self.assertEqual(legacy.trang_thai, "cho_duyet")
        self.assertEqual((NguoiOCungPhong.objects.count(), FaceProfile.objects.count(), QuyenRaVao.objects.count()), before)
        terminal = YeuCauGhepNguoi.objects.create(
            hop_dong=self.contract_obj, nguoi_dang_ky=self.other,
            ho_ten="Terminal legacy", cccd="000000004108", ngay_du_kien_vao=self.today,
            trang_thai="da_huy",
        )
        self.client.post(reverse("xu_ly_yeu_cau_ghep", args=[terminal.pk]), {"hanh_dong": "duyet"})
        terminal.refresh_from_db()
        self.assertEqual(terminal.trang_thai, "da_huy")


class CoTenantDirectAdmitConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user("direct-admin", is_staff=True)
        tenant_user = User.objects.create_user("direct-tenant")
        tenant = NguoiThue.objects.create(
            tai_khoan=tenant_user, ho_ten="Direct tenant", cccd="000000004201",
            so_dien_thoai="0900004201",
        )
        facility = CoSo.objects.create(ten_co_so="Direct facility", dia_chi="Test", quan="Test")
        room = Phong.objects.create(
            co_so=facility, so_phong="DA-1", gia_thue=Decimal("2500000"),
            dien_tich=Decimal("20"), so_nguoi_toi_da=3,
        )
        booking = DatPhong.objects.create(
            nguoi_thue=tenant, phong=room, ngay_nhan_phong=self.today,
            ngay_tra_du_kien=self.today + timedelta(days=90), trang_thai="da_duyet",
        )
        self.contract_obj = HopDong.objects.create(
            dat_phong=booking, so_hop_dong="DIRECT-CONCURRENT", ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today + timedelta(days=90),
            tien_thue_thang=Decimal("2500000"), trang_thai="dang_hieu_luc",
        )

    def test_concurrent_direct_admits_for_one_identity_have_one_winner(self):
        barrier = Barrier(2)
        outcomes = []

        def admit(key):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                resident, created = direct_admit(
                    contract_id=self.contract_obj.pk, actor=User.objects.get(pk=self.admin.pk),
                    idempotency_key=key, ho_ten="Concurrent candidate",
                    cccd="000000004299", ngay_vao=self.today,
                )
                outcomes.append(("created" if created else "retried", resident.pk))
            except ValidationError:
                outcomes.append(("blocked", None))
            finally:
                close_old_connections()

        threads = [Thread(target=admit, args=(key,)) for key in ("concurrent-a", "concurrent-b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive())

        self.assertEqual(sorted(kind for kind, _ in outcomes), ["blocked", "created"])
        self.assertEqual(NguoiOCungPhong.objects.filter(trang_thai="dang_o").count(), 1)
        self.assertEqual(PhuLucHopDong.objects.filter(loai="thay_doi_cu_tru").count(), 1)
