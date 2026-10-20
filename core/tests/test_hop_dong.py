from core.tests import test_phong_thong_minh as access_tests
"""Business regression tests. ORM mutations run only in Django's test database."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, IntegrityError, transaction
from django.test import Client, TestCase, RequestFactory
from django.urls import reverse, resolve, NoReverseMatch
from django.utils import timezone

from core.du_lieu_test import tap_hop_views as views
from core.models import (
    CoSo, Phong, NguoiThue, DatPhong, HopDong, NguoiOCungPhong,
    YeuCauGhepNguoi, HoaDon, LichSuThanhToan, QuyenRaVao, FaceProfile,
    LichSuRaVao, ThongBao, NhatKyThaoTac, LichSuHopDong, ChinhSachHoTro,
)


from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture

class ContractTests(BusinessFixture):
    def test_activation_and_double_activation(self):
        hd=self.contract('cho_hieu_luc')
        self.post(views.xu_ly_hop_dong,hd,{'hanh_dong':'kich_hoat'},self.admin)
        hd.refresh_from_db();self.room.refresh_from_db()
        self.assertEqual(hd.trang_thai,'dang_hieu_luc');self.assertEqual(self.room.trang_thai,'dang_thue')
        effects=self.effects()
        self.post(views.xu_ly_hop_dong,hd,{'hanh_dong':'kich_hoat'},self.admin)
        self.assertEqual(self.effects(),effects)

    def test_conflicting_activation_blocked(self):
        self.contract()
        second=self.contract('cho_hieu_luc',tenant=self.other)
        self.post(views.xu_ly_hop_dong,second,{'hanh_dong':'kich_hoat'},self.admin)
        second.refresh_from_db();self.assertEqual(second.trang_thai,'cho_hieu_luc')

    def test_cancel_syncs_residents_and_permission(self):
        hd=self.contract();resident=self.resident(hd);permission=self.permission()
        fp=FaceProfile.objects.create(nguoi_thue=self.tenant,loai_chu_the='nguoi_thue')
        self.post(views.xu_ly_hop_dong,hd,{'hanh_dong':'huy'},self.admin)
        self.room.refresh_from_db();resident.refresh_from_db();permission.refresh_from_db()
        self.assertEqual(self.room.trang_thai,'trong');self.assertEqual(self.room.so_nguoi_dang_o,0)
        self.assertEqual(resident.trang_thai,'da_roi');self.assertEqual(resident.ngay_ra,self.today)
        self.assertEqual(permission.trang_thai,'bi_thu_hoi');self.assertTrue(FaceProfile.objects.filter(pk=fp.pk).exists())
        effects=self.effects();self.post(views.xu_ly_hop_dong,hd,{'hanh_dong':'huy'},self.admin)
        self.assertEqual(self.effects(),effects)

    def test_date_boundaries(self):
        hd=self.contract('cho_hieu_luc')
        for start,end,expected in [(1,60,'cho_hieu_luc'),(0,60,'dang_hieu_luc'),(-10,30,'sap_het_han'),(-10,0,'sap_het_han'),(-10,-1,'da_het_han')]:
            with self.subTest(start=start,end=end):
                hd.ngay_bat_dau=self.today+timedelta(days=start);hd.ngay_ket_thuc=self.today+timedelta(days=end);hd.save()
                views.cap_nhat_trang_thai_hop_dong(hd);hd.refresh_from_db()
                self.assertEqual(hd.trang_thai,expected)
                self.assertEqual(bool(hd.da_het_han),end<0)

    def test_expiry_command_twice(self):
        hd=self.contract(end=self.today-timedelta(days=1),start=self.today-timedelta(days=90))
        resident=self.resident(hd);permission=self.permission()
        call_command('dong_bo_hop_dong',stdout=StringIO(),stderr=StringIO())
        hd.refresh_from_db();resident.refresh_from_db();permission.refresh_from_db()
        self.assertEqual(hd.trang_thai,'da_het_han');self.assertEqual(resident.trang_thai,'da_roi')
        self.assertEqual(permission.trang_thai,'het_han')
        effects=self.effects();call_command('dong_bo_hop_dong',stdout=StringIO(),stderr=StringIO())
        self.assertEqual(self.effects(),effects)

    def test_expiry_command_continues_then_signals_partial_failure(self):
        successful = self.contract(
            end=self.today-timedelta(days=1), start=self.today-timedelta(days=90)
        )
        failed = self.contract(
            end=self.today-timedelta(days=1), start=self.today-timedelta(days=90)
        )
        original_sync = views.cap_nhat_trang_thai_hop_dong
        attempted = []

        def fail_one_contract(contract):
            attempted.append(contract.pk)
            if contract.pk == failed.pk:
                raise RuntimeError("controlled synchronization failure")
            return original_sync(contract)

        stdout, stderr = StringIO(), StringIO()
        with patch(
            "core.management.commands.dong_bo_hop_dong.cap_nhat_trang_thai_hop_dong",
            side_effect=fail_one_contract,
        ):
            with self.assertRaises(CommandError):
                call_command("dong_bo_hop_dong", stdout=stdout, stderr=stderr)

        failed.refresh_from_db()
        successful.refresh_from_db()
        self.assertEqual(attempted, [failed.pk, successful.pk])
        self.assertEqual(failed.trang_thai, "dang_hieu_luc")
        self.assertEqual(successful.trang_thai, "da_het_han")
        self.assertIn("Lỗi: 1", stdout.getvalue())
        self.assertIn("controlled synchronization failure", stderr.getvalue())

    def test_legacy_contract_action_no_longer_creates_contract(self):
        booking=self.booking()
        req=self.request(self.admin,{'so_nguoi_o':'1'})
        views.tao_hop_dong(req,booking.pk)
        self.assertEqual(HopDong.objects.count(),0)
        effects=self.effects();views.tao_hop_dong(self.request(self.admin,{'so_nguoi_o':'1'}),booking.pk)
        self.assertEqual(HopDong.objects.count(),0);self.assertEqual(self.effects(),effects)

"""Phase 5: synthetic fixtures only, guarded by BusinessFixture's test DB check."""
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from core.du_lieu_test import tap_hop_views as views
from core.models import (YeuCauGiaHanHopDong, HopDong, Phong, NguoiOCungPhong,
                     QuyenRaVao, FaceProfile, ThongBao, NhatKyThaoTac,
                     LichSuHopDong, HoaDon)
from core.du_lieu_test import du_lieu_test_nghiep_vu as baseline
from core.dich_vu.luu_tru import cap_nhat_trang_thai_luu_tru
from core.dich_vu.vong_doi_hop_dong import dong_bo_vong_doi_hop_dong


class LifecycleAuthorizationTests(baseline.BusinessFixture):
    recognize = access_tests.AccessTests.recognize

    def setUp(self):
        self.hd = self.contract(start=self.today-timedelta(days=60), end=self.today)
        FaceProfile.objects.create(nguoi_thue=self.tenant, loai_chu_the='nguoi_thue',
                                   trang_thai='da_xac_thuc', face_encoding='audit-vector',
                                   dong_y_du_lieu_khuon_mat=True)

    def test_canceled_contract_denies_even_active_permission(self):
        self.permission()
        self.hd.trang_thai = 'da_huy'; self.hd.save()
        self.assertEqual(self.recognize()['access'], 'denied')

    def test_cancel_action_denies(self):
        self.permission()
        self.post(views.xu_ly_hop_dong, self.hd, {'hanh_dong': 'huy'}, self.admin)
        self.assertEqual(self.recognize()['access'], 'denied')

    def test_final_day_at_midnight_noon_and_end_then_next_day(self):
        self.permission(ngay_ket_thuc=self.today)
        for hour, minute, second in [(0, 0, 0), (12, 0, 0), (23, 59, 59)]:
            now = timezone.make_aware(datetime.combine(self.today, time(hour, minute, second)))
            with self.subTest(now=now), patch('django.utils.timezone.now', return_value=now):
                self.assertEqual(self.recognize()['access'], 'granted')
        tomorrow = timezone.make_aware(datetime.combine(self.today+timedelta(days=1), time.min))
        with patch('django.utils.timezone.now', return_value=tomorrow):
            self.assertEqual(self.recognize()['access'], 'denied')

    def test_expired_contract_denies_with_unbounded_permission(self):
        self.permission(ngay_ket_thuc=None)
        self.hd.ngay_ket_thuc = self.today-timedelta(days=1); self.hd.save()
        self.assertEqual(self.recognize()['access'], 'denied')

    def test_resident_membership_exact_contract_and_room(self):
        FaceProfile.objects.all().delete()
        resident = self.resident(self.hd)
        FaceProfile.objects.create(nguoi_o_cung=resident, loai_chu_the='nguoi_o_cung',
                                   trang_thai='da_xac_thuc', face_encoding='audit-vector',
                                   dong_y_du_lieu_khuon_mat=True)
        self.permission(nguoi_thue=None, nguoi_o_cung=resident, loai_quyen='nguoi_o_cung')
        self.assertEqual(self.recognize()['access'], 'granted')
        resident.trang_thai = 'da_roi'; resident.save()
        self.assertEqual(self.recognize()['access'], 'denied')
        resident.trang_thai = 'dang_o'; resident.save()
        self.hd.trang_thai = 'da_huy'; self.hd.save()
        self.assertEqual(self.recognize()['access'], 'denied')

    def test_expiry_service_syncs_primary_resident_permissions_and_keeps_history(self):
        self.hd.ngay_ket_thuc = self.today - timedelta(days=1)
        self.hd.save(update_fields=['ngay_ket_thuc'])
        resident = self.resident(self.hd)
        owner_right = self.permission(ngay_ket_thuc=None)
        resident_right = self.permission(
            nguoi_thue=None,
            nguoi_o_cung=resident,
            loai_quyen='nguoi_o_cung',
            ngay_ket_thuc=None,
        )
        profile_id = FaceProfile.objects.get(nguoi_thue=self.tenant).pk
        LichSuRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.tenant,
            quyen_ra_vao=owner_right,
            ten_nguoi=self.tenant.ho_ten,
            loai_su_kien='vao',
            nguon='camera',
            thoi_diem=timezone.now(),
        )

        dong_bo_vong_doi_hop_dong(self.hd)
        self.hd.refresh_from_db()
        self.tenant.refresh_from_db()
        resident.refresh_from_db()
        owner_right.refresh_from_db()
        resident_right.refresh_from_db()

        self.assertEqual(self.hd.trang_thai, 'da_het_han')
        self.assertEqual(self.tenant.trang_thai_luu_tru, 'da_tra_phong')
        self.assertEqual(resident.trang_thai, 'da_roi')
        self.assertEqual(owner_right.trang_thai, 'het_han')
        self.assertEqual(resident_right.trang_thai, 'het_han')
        self.assertTrue(FaceProfile.objects.filter(pk=profile_id).exists())
        self.assertEqual(LichSuRaVao.objects.filter(nguoi_thue=self.tenant).count(), 1)

        snapshot = list(QuyenRaVao.objects.order_by('pk').values())
        dong_bo_vong_doi_hop_dong(self.hd)
        self.assertEqual(list(QuyenRaVao.objects.order_by('pk').values()), snapshot)

    def test_checkout_and_contract_sync_do_not_revoke_other_active_contract(self):
        old = self.hd
        old.ngay_ket_thuc = self.today - timedelta(days=1)
        old.save(update_fields=['ngay_ket_thuc'])
        old_right = self.permission(hop_dong=old, ngay_ket_thuc=None)
        other_room = Phong.objects.create(
            co_so=self.facility,
            so_phong='AUDIT-ACTIVE',
            gia_thue=1,
            dien_tich=1,
            so_nguoi_toi_da=2,
        )
        other_booking = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=other_room,
            ngay_nhan_phong=self.today,
            ngay_tra_du_kien=self.today + timedelta(days=30),
            so_thang_thue=1,
            trang_thai='da_duyet',
        )
        other_contract = HopDong.objects.create(
            dat_phong=other_booking,
            so_hop_dong='AUDIT-ACTIVE',
            ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today + timedelta(days=30),
            tien_thue_thang=1,
            trang_thai='dang_hieu_luc',
        )
        other_right = self.permission(
            hop_dong=other_contract,
            phong=other_room,
            ngay_ket_thuc=other_contract.ngay_ket_thuc,
        )

        revoked = cap_nhat_trang_thai_luu_tru(
            self.tenant,
            'da_tra_phong',
            nguoi_thuc_hien=self.admin,
            hop_dong=old,
        )
        self.tenant.refresh_from_db()
        self.assertEqual(revoked, 0)
        self.assertEqual(self.tenant.trang_thai_luu_tru, 'dang_o')

        dong_bo_vong_doi_hop_dong(old)
        self.tenant.refresh_from_db()
        old_right.refresh_from_db()
        other_right.refresh_from_db()
        self.assertEqual(self.tenant.trang_thai_luu_tru, 'dang_o')
        self.assertEqual(old_right.trang_thai, 'het_han')
        self.assertEqual(other_right.trang_thai, 'hoat_dong')

    def test_contract_get_pages_do_not_persist_lifecycle_writes(self):
        self.hd.ngay_ket_thuc = self.today - timedelta(days=1)
        self.hd.trang_thai = 'dang_hieu_luc'
        self.hd.save(update_fields=['ngay_ket_thuc', 'trang_thai'])
        right = self.permission(ngay_ket_thuc=None)

        self.client.force_login(self.admin)
        response = self.client.get(reverse('chi_tiet_hop_dong', args=[self.hd.pk]))
        self.assertEqual(response.status_code, 200)

        self.hd.refresh_from_db()
        self.tenant.refresh_from_db()
        right.refresh_from_db()
        self.assertEqual(self.hd.trang_thai, 'dang_hieu_luc')
        self.assertEqual(self.tenant.trang_thai_luu_tru, 'dang_o')
        self.assertEqual(right.trang_thai, 'hoat_dong')

from django.urls import reverse
from django.utils import timezone

from core.models import ChungTuThanhToan, FaceProfile, HopDong, NguoiOCungPhong, QuyenRaVao, ThanhToanCocDatPhong, ThongBao
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.dich_vu.tien_coc import report_paid


class Phase6AdminBookingContractTests(Phase5BookingFixture):
    def pending_report(self):
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="BANK-001")
        ChungTuThanhToan.objects.create(
            giao_dich_coc=payment, nguoi_tai_len=self.user,
            anh="payment_evidence/contract-test.png", mime_type="image/png",
            ma_doi_chieu=payment.ma_tham_chieu,
        )
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "cho_xac_nhan")
        return booking, payment

    def test_user_and_anonymous_cannot_confirm_admin_endpoint(self):
        booking, payment = self.pending_report()
        url = reverse("xac_nhan_dat_phong_va_tao_hop_dong", args=[booking.pk])

        self.client.logout()
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(HopDong.objects.count(), 0)

        self.client.force_login(self.user)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(HopDong.objects.count(), 0)
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "cho_xac_nhan")

    def test_confirm_is_post_only_and_requires_csrf(self):
        booking, payment = self.pending_report()
        url = reverse("xac_nhan_dat_phong_va_tao_hop_dong", args=[booking.pk])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        response = csrf_client.post(url, {"payment_id": payment.pk, "so_tien_thuc_nhan": payment.so_tien})
        self.assertEqual(response.status_code, 403)
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "cho_xac_nhan")
        self.assertEqual(HopDong.objects.count(), 0)

    def test_admin_confirm_records_deposit_without_creating_contract(self):
        booking, payment = self.pending_report()
        self.client.force_login(self.admin)
        url = reverse("xac_nhan_dat_phong_va_tao_hop_dong", args=[booking.pk])

        first = self.client.post(url, {"payment_id": payment.pk, "so_tien_thuc_nhan": payment.so_tien})
        self.assertEqual(first.status_code, 302)
        self.assertEqual(HopDong.objects.count(), 0)
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "da_xac_nhan")
        self.assertEqual(payment.so_tien_thuc_nhan, payment.so_tien)
        self.assertTrue(ThongBao.objects.filter(nguoi_thue=booking.nguoi_thue, ma_tham_chieu__contains="DEPOSIT_CONFIRMED").exists())

        second = self.client.post(url, {"payment_id": payment.pk, "so_tien_thuc_nhan": payment.so_tien})
        self.assertEqual(second.status_code, 302)
        self.assertEqual(HopDong.objects.count(), 0)

    def test_confirm_does_not_create_resident_face_or_access_permission(self):
        booking, payment = self.pending_report()
        self.client.force_login(self.admin)

        self.client.post(reverse("xac_nhan_dat_phong_va_tao_hop_dong", args=[booking.pk]), {"payment_id": payment.pk, "so_tien_thuc_nhan": payment.so_tien})

        self.assertEqual(HopDong.objects.count(), 0)
        self.assertEqual(NguoiOCungPhong.objects.count(), 0)
        self.assertEqual(FaceProfile.objects.count(), 0)
        self.assertEqual(QuyenRaVao.objects.count(), 0)

    def test_reject_deposit_requires_reason_and_does_not_create_contract(self):
        booking, payment = self.pending_report()
        self.client.force_login(self.admin)
        url = reverse("tu_choi_thanh_toan_coc", args=[booking.pk])

        self.client.post(url, {"payment_id": payment.pk, "ly_do": ""})
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "cho_xac_nhan")

        self.client.post(url, {"payment_id": payment.pk, "ly_do": "Sai noi dung chuyen khoan"})
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "tu_choi")
        self.assertEqual(HopDong.objects.count(), 0)
        self.assertTrue(ThongBao.objects.filter(nguoi_thue=booking.nguoi_thue, loai="dat_phong").exists())

    def test_reject_booking_creates_scoped_admin_notification(self):
        booking, payment = self.pending_report()
        self.client.force_login(self.admin)
        url = reverse("tu_choi_yeu_cau_dat_phong", args=[booking.pk])

        self.client.post(url, {"ly_do": "Thong tin khong hop le"})
        booking.refresh_from_db()

        self.assertEqual(booking.trang_thai, "tu_choi")
        self.assertEqual(HopDong.objects.count(), 0)
        admin_notice = ThongBao.objects.get(
            nguoi_nhan_user=self.admin,
            ma_tham_chieu=f"BOOKING:{booking.pk}:BOOKING_REJECTED:{self.admin.pk}",
        )
        self.assertEqual(admin_notice.url_lien_ket, f"/quan-ly-dat-phong/{booking.pk}/")

    def test_admin_and_tenant_polling_are_scoped(self):
        tenant_notice = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Tenant notice",
            noi_dung="Only tenant",
            loai="dat_phong",
        )
        admin_notice = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Admin notice",
            noi_dung="Only admin",
            loai="dat_phong",
        )

        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse("kiem_tra_thong_bao_admin_moi"))
        self.assertContains(admin_response, "Admin notice")
        self.assertNotContains(admin_response, "Tenant notice")

        self.client.force_login(self.user)
        tenant_response = self.client.get(reverse("kiem_tra_thong_bao_cua_toi_moi"))
        self.assertContains(tenant_response, "Tenant notice")
        self.assertNotContains(tenant_response, "Admin notice")

from unittest.mock import patch

from django.urls import reverse

from core.models import HopDong
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.dich_vu.hop_dong import confirm_deposit_and_create_contract
from core.dich_vu.tien_coc import report_paid


def _flatten_reportlab_text(items):
    values = []
    for item in items:
        if hasattr(item, "getPlainText"):
            values.append(item.getPlainText())
        elif hasattr(item, "_cellvalues"):
            values.extend(_flatten_reportlab_text(cell for row in item._cellvalues for cell in row))
        elif isinstance(item, (list, tuple)):
            values.extend(_flatten_reportlab_text(item))
    return values


class Phase6ContractPdfTests(Phase5BookingFixture):
    def _confirmed_contract(self, people=2):
        booking, payment = self.new_booking(people=people)
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="BANK-PDF-001")
        return confirm_deposit_and_create_contract(actor=self.admin, booking_id=booking.pk)

    def test_contract_detail_shows_declared_companions(self):
        contract = self._confirmed_contract(people=2)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("chi_tiet_hop_dong", args=[contract.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Companion 0")
        self.assertContains(response, "000000000003")

    def test_pdf_build_uses_snapshot_and_declared_companions(self):
        contract = self._confirmed_contract(people=2)
        captured = {}

        class FakeDoc:
            def __init__(self, response, *args, **kwargs):
                self.response = response
                self.page = 1

            def build(self, story, *args, **kwargs):
                captured["story"] = story

        self.client.force_login(self.admin)
        with patch("core.views_hop_dong.SimpleDocTemplate", FakeDoc):
            response = self.client.get(reverse("xuat_hop_dong_pdf", args=[contract.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        text = "\n".join(_flatten_reportlab_text(captured["story"]))
        self.assertIn(contract.so_hop_dong, text)
        self.assertIn("Companion 0", text)
        self.assertIn("000000000003", text)
        self.assertIn(str(int(contract.tien_coc)), text.replace(".", ""))

    def test_tenant_can_download_only_own_contract_pdf(self):
        own_contract = self._confirmed_contract(people=1)
        other_contract = self.contract(tenant=self.other)

        class FakeDoc:
            def __init__(self, response, *args, **kwargs):
                self.page = 1

            def build(self, story, *args, **kwargs):
                return None

        self.client.force_login(self.user)
        with patch("core.views_hop_dong.SimpleDocTemplate", FakeDoc):
            own_response = self.client.get(reverse("xuat_hop_dong_pdf", args=[own_contract.pk]))
            foreign_response = self.client.get(reverse("xuat_hop_dong_pdf", args=[other_contract.pk]))

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(foreign_response.status_code, 302)
        self.assertEqual(HopDong.objects.count(), 2)
