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


class BusinessFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Fail closed before creating any fixtures if the runner is misconfigured.
        if connection.settings_dict['NAME'] != 'test_ndt_motel':
            raise RuntimeError('These tests require the isolated test_ndt_motel database.')
        cls.today = timezone.localdate()
        cls.admin = User.objects.create_user('audit-admin', is_staff=True)
        cls.user = User.objects.create_user('audit-tenant')
        cls.other_user = User.objects.create_user('audit-applicant')
        cls.tenant = NguoiThue.objects.create(tai_khoan=cls.user, ho_ten='Audit Tenant',
            so_dien_thoai='0900000001', cccd='000000000001')
        cls.other = NguoiThue.objects.create(tai_khoan=cls.other_user, ho_ten='Audit Applicant',
            so_dien_thoai='0900000002', cccd='000000000002')
        cls.facility = CoSo.objects.create(ten_co_so='Audit Facility', dia_chi='Test', quan='Test')
        cls.room = Phong.objects.create(co_so=cls.facility, so_phong='AUDIT-1',
            gia_thue=Decimal('2500000'), dien_tich=25, so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal('500000'))

    def request(self, user=None, data=None, method='post'):
        req = getattr(RequestFactory(), method)('/audit/', data or {})
        req.user = user or self.user
        req.session = {}
        req._messages = FallbackStorage(req)
        return req

    def post(self, view, obj, data, user=None):
        req = self.request(user, data)
        response = view(req, obj.pk)
        self.assertIn(response.status_code, [200, 302, 400, 403])
        return response, req

    def booking(self, status='da_duyet', tenant=None):
        return DatPhong.objects.create(nguoi_thue=tenant or self.tenant, phong=self.room,
            ngay_nhan_phong=self.today, ngay_tra_du_kien=self.today+timedelta(days=90),
            so_thang_thue=3, trang_thai=status)

    def contract(self, status='dang_hieu_luc', start=None, end=None, tenant=None):
        booking = self.booking(tenant=tenant)
        hd = HopDong.objects.create(dat_phong=booking, so_hop_dong='AUDIT-'+str(booking.pk),
            ngay_bat_dau=start or self.today, ngay_ket_thuc=end or self.today+timedelta(days=90),
            tien_thue_thang=Decimal('2500000'), trang_thai=status, cho_phep_ghep=True)
        self.room.dong_bo_trang_thai()
        self.fixture_contract = hd  # Explicit synthetic stay used by permission fixtures.
        return hd

    def resident(self, hd, status='dang_o'):
        return NguoiOCungPhong.objects.create(hop_dong=hd, ho_ten='Audit Resident',
            ngay_vao=self.today, trang_thai=status,
            da_xac_minh_boi_admin=status in ('dang_o', 'da_xac_minh'))

    def sharing_request(self, hd):
        return YeuCauGhepNguoi.objects.create(hop_dong=hd, nguoi_dang_ky=self.other,
            ho_ten='Audit Applicant', cccd=self.other.cccd, ngay_du_kien_vao=self.today)

    def permission(self, **kwargs):
        defaults = dict(phong=self.room, nguoi_thue=self.tenant, loai_quyen='chu_phong',
            trang_thai='hoat_dong', ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today+timedelta(days=90),
            hop_dong=getattr(self, 'fixture_contract', None), nguon_cap='face_id')
        defaults.update(kwargs)
        return QuyenRaVao.objects.create(**defaults)

    def effects(self):
        return (ThongBao.objects.count(), NhatKyThaoTac.objects.count(),
                LichSuHopDong.objects.count(), LichSuThanhToan.objects.count())
