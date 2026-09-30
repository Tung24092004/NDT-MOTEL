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
from django.db import connection, IntegrityError, transaction
from django.test import TestCase, RequestFactory
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

    def test_create_contract_double_submit(self):
        booking=self.booking()
        req=self.request(self.admin,{'so_nguoi_o':'1'})
        views.tao_hop_dong(req,booking.pk)
        self.assertEqual(HopDong.objects.count(),1)
        effects=self.effects();views.tao_hop_dong(self.request(self.admin,{'so_nguoi_o':'1'}),booking.pk)
        self.assertEqual(HopDong.objects.count(),1);self.assertEqual(self.effects(),effects)

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


class LifecycleAuthorizationTests(baseline.BusinessFixture):
    recognize = access_tests.AccessTests.recognize

    def setUp(self):
        self.hd = self.contract(start=self.today-timedelta(days=60), end=self.today)
        FaceProfile.objects.create(nguoi_thue=self.tenant, loai_chu_the='nguoi_thue',
                                   trang_thai='da_xac_thuc', face_encoding='audit-vector')

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
                                   trang_thai='da_xac_thuc', face_encoding='audit-vector')
        self.permission(nguoi_thue=None, nguoi_o_cung=resident, loai_quyen='nguoi_o_cung')
        self.assertEqual(self.recognize()['access'], 'granted')
        resident.trang_thai = 'da_roi'; resident.save()
        self.assertEqual(self.recognize()['access'], 'denied')
        resident.trang_thai = 'dang_o'; resident.save()
        self.hd.trang_thai = 'da_huy'; self.hd.save()
        self.assertEqual(self.recognize()['access'], 'denied')

from django.urls import reverse
from django.utils import timezone

from core.models import FaceProfile, HopDong, NguoiOCungPhong, QuyenRaVao, ThanhToanCocDatPhong, ThongBao
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.dich_vu.tien_coc import report_paid


class Phase6AdminBookingContractTests(Phase5BookingFixture):
    def pending_report(self):
        booking, payment = self.new_booking()
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="BANK-001")
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

    def test_admin_confirm_creates_one_contract_from_snapshot(self):
        booking, payment = self.pending_report()
        self.client.force_login(self.admin)
        url = reverse("xac_nhan_dat_phong_va_tao_hop_dong", args=[booking.pk])

        first = self.client.post(url)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(HopDong.objects.count(), 1)
        contract = HopDong.objects.get()
        self.assertEqual(contract.dat_phong_id, booking.pk)
        self.assertEqual(contract.tien_coc, booking.tien_coc_du_kien)
        self.assertEqual(contract.tien_thue_thang, booking.gia_thue_thang_tai_thoi_diem_dat)
        self.assertEqual(contract.so_nguoi_o, booking.so_nguoi_o)
        self.assertEqual(contract.dieu_khoan, booking.noi_dung_dieu_khoan_snapshot)
        self.assertTrue(ThongBao.objects.filter(nguoi_thue=booking.nguoi_thue, loai="hop_dong").exists())

        second = self.client.post(url)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(HopDong.objects.count(), 1)
        self.assertEqual(ThongBao.objects.filter(nguoi_thue=booking.nguoi_thue, loai="hop_dong").count(), 1)
        self.assertEqual(
            ThongBao.objects.filter(
                nguoi_nhan_user=self.admin,
                ma_tham_chieu=f"BOOKING:{booking.pk}:CONTRACT_CREATED:{contract.pk}:{self.admin.pk}",
            ).count(),
            1,
        )

    def test_confirm_does_not_create_resident_face_or_access_permission(self):
        booking, payment = self.pending_report()
        self.client.force_login(self.admin)

        self.client.post(reverse("xac_nhan_dat_phong_va_tao_hop_dong", args=[booking.pk]))

        self.assertEqual(HopDong.objects.count(), 1)
        self.assertEqual(NguoiOCungPhong.objects.count(), 0)
        self.assertEqual(FaceProfile.objects.count(), 0)
        self.assertEqual(QuyenRaVao.objects.count(), 0)

    def test_reject_deposit_requires_reason_and_does_not_create_contract(self):
        booking, payment = self.pending_report()
        self.client.force_login(self.admin)
        url = reverse("tu_choi_thanh_toan_coc", args=[booking.pk])

        self.client.post(url, {"ly_do": ""})
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "cho_xac_nhan")

        self.client.post(url, {"ly_do": "Sai noi dung chuyen khoan"})
        payment.refresh_from_db()
        self.assertEqual(payment.trang_thai, "tu_choi")
        self.assertEqual(HopDong.objects.count(), 0)
        self.assertTrue(ThongBao.objects.filter(nguoi_thue=booking.nguoi_thue, loai="dat_phong").exists())
        admin_notice = ThongBao.objects.get(
            nguoi_nhan_user=self.admin,
            ma_tham_chieu=f"BOOKING:{booking.pk}:DEPOSIT_REJECTED:{payment.pk}:{self.admin.pk}",
        )
        self.assertEqual(admin_notice.url_lien_ket, f"/quan-ly-dat-phong/{booking.pk}/")

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
