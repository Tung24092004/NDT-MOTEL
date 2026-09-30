from core.du_lieu_test.gia_lap_views import gia_lap_views
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

class CapacityTests(BusinessFixture):
    def test_empty_configured(self):
        self.assertEqual(self.room.so_nguoi_dang_o,0);self.assertEqual(self.room.so_cho_con_lai,3)

    def test_resident_count_ignores_departed_and_declared_count(self):
        hd=self.contract();hd.so_nguoi_o=9;hd.save()
        self.resident(hd);self.resident(hd,'da_roi')
        self.assertEqual(self.room.so_nguoi_dang_o,2);self.assertEqual(self.room.so_cho_con_lai,1)

    def test_noncurrent_contracts_do_not_count(self):
        hd=self.contract('cho_hieu_luc');self.resident(hd)
        for status in ['cho_hieu_luc','da_het_han','da_huy']:
            hd.trang_thai=status;hd.save()
            self.assertEqual(self.room.so_nguoi_dang_o,0)

    def test_zero_capacity_public_semantics(self):
        self.room.so_nguoi_toi_da=0;self.room.save()
        with gia_lap_views('render',side_effect=lambda request,name,ctx:ctx):
            ctx=views.chi_tiet_phong(self.request(method='get'),self.room.pk)
        self.assertFalse(ctx['suc_chua_da_cau_hinh']);self.assertEqual(ctx['suc_chua'],0)
        self.assertFalse(ctx['co_the_dang_ky_ghep'])

    def test_remaining_never_negative(self):
        hd=self.contract();self.resident(hd)
        self.room.so_nguoi_toi_da=1;self.room.save()
        self.assertEqual(self.room.so_cho_con_lai,0)
