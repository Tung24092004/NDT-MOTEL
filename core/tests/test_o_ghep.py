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

class RoommateTests(BusinessFixture):
    def room_detail(self):
        self.client.force_login(self.other_user)
        return self.client.get(reverse('chi_tiet_phong', args=[self.room.pk]))

    def assert_sharing_blocked(self, expected_text):
        response = self.room_detail()
        self.assertContains(response, expected_text)
        self.assertFalse(response.context['phong_co_the_ghep'])
        self.assertNotContains(response, f'href="{reverse("dang_ky_ghep_phong", args=[self.room.pk])}"')
        self.assertNotContains(response, f'href="{reverse("yeu_cau_ghep_cua_toi")}"')
        before = YeuCauGhepNguoi.objects.count()
        for method in ('get', 'post'):
            result = getattr(self.client, method)(
                reverse('dang_ky_ghep_phong', args=[self.room.pk]), self.payload(),
            )
            self.assertRedirects(result, reverse('chi_tiet_phong', args=[self.room.pk]))
        self.assertEqual(YeuCauGhepNguoi.objects.count(), before)
        return response

    def test_empty_room_only_offers_booking_not_sharing(self):
        response = self.assert_sharing_blocked('Phòng này hiện đang trống. Người thuê có thể gửi yêu cầu đặt phòng.')
        self.assertContains(response, f'href="{reverse("dat_phong", args=[self.room.pk])}"')
        self.assertNotContains(response, 'Thao tác nhanh')

    def test_booked_room_without_active_contract_blocks_sharing(self):
        self.booking()
        self.room.dong_bo_trang_thai()
        self.assert_sharing_blocked('Phòng chưa có hợp đồng đang hiệu lực')

    def test_disabled_room_sharing_has_no_registration_action(self):
        contract = self.contract()
        contract.cho_phep_ghep = False
        contract.save(update_fields=['cho_phep_ghep'])
        self.assert_sharing_blocked('Phòng hiện chưa mở đăng ký ở ghép')

    def test_enabled_room_with_capacity_offers_registration(self):
        self.contract()
        response = self.room_detail()
        self.assertContains(response, 'Phòng đang mở đăng ký ở ghép')
        self.assertTrue(response.context['phong_co_the_ghep'])
        self.assertTrue(response.context['phong_dang_cho_phep_ghep'])
        self.assertTrue(response.context['phong_con_cho_ghep'])
        self.assertEqual(response.context['cho_con_lai'], 2)
        self.assertContains(response, f'href="{reverse("dang_ky_ghep_phong", args=[self.room.pk])}"')
        self.client.post(reverse('dang_ky_ghep_phong', args=[self.room.pk]), self.payload())
        self.assertEqual(YeuCauGhepNguoi.objects.count(), 1)

    def test_full_room_does_not_offer_or_create_sharing_request(self):
        contract = self.contract()
        self.resident(contract)
        self.resident(contract)
        response = self.assert_sharing_blocked('Phòng đã đủ sức chứa')
        self.assertFalse(response.context['phong_con_cho_ghep'])
        self.assertEqual(response.context['cho_con_lai'], 0)

    def test_contract_dates_must_currently_be_effective(self):
        contract = self.contract(start=self.today-timedelta(days=90), end=self.today-timedelta(days=1))
        self.assert_sharing_blocked('Phòng chưa có hợp đồng đang hiệu lực')
        contract.ngay_bat_dau = self.today+timedelta(days=1)
        contract.ngay_ket_thuc = self.today+timedelta(days=90)
        contract.save(update_fields=['ngay_bat_dau', 'ngay_ket_thuc'])
        self.assert_sharing_blocked('Phòng chưa có hợp đồng đang hiệu lực')

    def test_inactive_contract_owner_blocks_sharing(self):
        self.contract()
        self.tenant.dang_hoat_dong = False
        self.tenant.save(update_fields=['dang_hoat_dong'])
        self.assert_sharing_blocked('Phòng chưa có hợp đồng đang hiệu lực')

    def payload(self):
        return {'ho_ten':'Audit Applicant','ngay_du_kien_vao':str(self.today),'cccd':self.other.cccd}

    def test_disabled_and_full_blocked(self):
        hd=self.contract();hd.cho_phep_ghep=False;hd.save()
        self.post(views.dang_ky_ghep_phong,self.room,self.payload(),self.other_user)
        self.assertFalse(YeuCauGhepNguoi.objects.exists())
        hd.cho_phep_ghep=True;hd.save();self.room.so_nguoi_toi_da=1;self.room.save()
        self.post(views.dang_ky_ghep_phong,self.room,self.payload(),self.other_user)
        self.assertFalse(YeuCauGhepNguoi.objects.exists())

    def test_zero_capacity_message_is_not_full(self):
        self.contract();self.room.so_nguoi_toi_da=0;self.room.save()
        _,req=self.post(views.dang_ky_ghep_phong,self.room,self.payload(),self.other_user)
        messages=' '.join(str(m) for m in get_messages(req))
        self.assertIn('chưa',messages.lower());self.assertNotIn('/1',messages)

    def test_zero_capacity_toggle(self):
        hd=self.contract();hd.cho_phep_ghep=False;hd.save()
        self.room.so_nguoi_toi_da=0;self.room.save()
        _,req=self.post(views.bat_tat_cho_phep_ghep,hd,{},self.user)
        hd.refresh_from_db();self.assertFalse(hd.cho_phep_ghep)
        self.assertIn('chưa',' '.join(str(m) for m in get_messages(req)).lower())

    def test_zero_capacity_approval(self):
        hd=self.contract();yc=self.sharing_request(hd)
        self.room.so_nguoi_toi_da=0;self.room.save()
        _,req=self.post(views.xu_ly_yeu_cau_ghep,yc,{'hanh_dong':'duyet'},self.admin)
        yc.refresh_from_db();self.assertEqual(yc.trang_thai,'cho_duyet')
        self.assertFalse(NguoiOCungPhong.objects.exists())
        self.assertIn('chưa',' '.join(str(m) for m in get_messages(req)).lower())

    def test_valid_request_and_duplicate(self):
        self.contract()
        self.post(views.dang_ky_ghep_phong,self.room,self.payload(),self.other_user)
        self.post(views.dang_ky_ghep_phong,self.room,self.payload(),self.other_user)
        self.assertEqual(YeuCauGhepNguoi.objects.count(),1)

    def test_stale_approval_when_full(self):
        hd=self.contract();self.resident(hd);yc=self.sharing_request(hd)
        self.resident(hd)
        self.post(views.xu_ly_yeu_cau_ghep,yc,{'hanh_dong':'duyet'},self.admin)
        yc.refresh_from_db();self.assertEqual(yc.trang_thai,'cho_duyet')
        self.assertEqual(NguoiOCungPhong.objects.count(),2);self.assertFalse(QuyenRaVao.objects.exists())

    def test_stale_approval_after_contract_date_ends(self):
        hd=self.contract();yc=self.sharing_request(hd)
        hd.ngay_bat_dau=self.today-timedelta(days=90);hd.ngay_ket_thuc=self.today-timedelta(days=1);hd.save()
        self.post(views.xu_ly_yeu_cau_ghep,yc,{'hanh_dong':'duyet'},self.admin)
        yc.refresh_from_db();self.assertEqual(yc.trang_thai,'cho_duyet')
        self.assertFalse(NguoiOCungPhong.objects.exists())

    def test_approval_double_submit_creates_one_subject(self):
        hd=self.contract();yc=self.sharing_request(hd)
        self.post(views.xu_ly_yeu_cau_ghep,yc,{'hanh_dong':'duyet'},self.admin)
        self.post(views.xu_ly_yeu_cau_ghep,yc,{'hanh_dong':'duyet'},self.admin)
        self.assertEqual(NguoiOCungPhong.objects.count(),1)
        self.assertEqual(FaceProfile.objects.count(),1);self.assertEqual(QuyenRaVao.objects.count(),1)
        right = QuyenRaVao.objects.get()
        self.assertEqual(right.hop_dong_id, right.nguoi_o_cung.hop_dong_id)
        self.assertEqual(right.nguon_cap, 'duyet_ghep')

    def test_roommate_request_detail_keeps_owner_context_and_permission(self):
        hd = self.contract()
        yc = self.sharing_request(hd)
        self.client.force_login(self.user)
        response = self.client.get(reverse('chi_tiet_yeu_cau_ghep', args=[yc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['yeu_cau'], yc)
        self.assertEqual(response.context['phong'], self.room)
        self.assertEqual(response.context['hop_dong'], hd)
        self.assertTrue(response.context['is_owner'])
        self.assertFalse(response.context['is_requester'])
        self.assertTrue(response.context['co_quyen_xu_ly'])
        self.assertIn('so_cho_con_lai', response.context)

    def test_roommate_request_detail_blocks_unrelated_tenant(self):
        hd = self.contract()
        yc = self.sharing_request(hd)
        stranger_user = User.objects.create_user('audit-stranger')
        NguoiThue.objects.create(tai_khoan=stranger_user, ho_ten='Audit Stranger',
            so_dien_thoai='0900000003', cccd='000000000003')
        self.client.force_login(stranger_user)
        response = self.client.get(reverse('chi_tiet_yeu_cau_ghep', args=[yc.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('yeu_cau_ghep_cua_toi'), response.url)
