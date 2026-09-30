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

class AccessTests(BusinessFixture):
    def setUp(self):
        self.hd=self.contract()
        FaceProfile.objects.create(nguoi_thue=self.tenant,loai_chu_the='nguoi_thue',
            trang_thai='da_xac_thuc',face_encoding='audit-vector')

    def recognize(self, room=None):
        # Mock image recognition only; execute the real authorization and history code.
        mocks=dict(_face_image_from_base64=object(),_face_load_models=(object(),object()),
            _face_detect=object(),_face_feature=object(),_face_feature_from_text=object(),_face_compare=.9)
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name,value in mocks.items():stack.enter_context(patch('core.views_smart_room.'+name,return_value=value))
            response=views.face_id_xac_thuc(self.request(self.admin,{'image':'test','phong':str((room or self.room).pk)}))
        import json
        return json.loads(response.content)

    def test_valid_permission_allowed_with_history(self):
        self.permission();self.assertEqual(self.recognize()['access'],'granted')
        self.assertEqual(LichSuRaVao.objects.count(),1)

    def test_wrong_room_denied(self):
        self.permission()
        other=Phong.objects.create(co_so=self.facility,so_phong='AUDIT-2',gia_thue=1,dien_tich=1)
        self.assertEqual(self.recognize(other)['access'],'denied')

    def test_inactive_denied(self):
        self.permission(trang_thai='tam_khoa');self.assertEqual(self.recognize()['access'],'denied')

    def test_expired_permission_denied(self):
        self.permission(ngay_ket_thuc=self.today-timedelta(days=1));self.assertEqual(self.recognize()['access'],'denied')

    def test_future_permission_denied(self):
        self.permission(ngay_bat_dau=self.today+timedelta(days=1));self.assertEqual(self.recognize()['access'],'denied')

    def test_end_day_inclusive(self):
        self.permission(ngay_ket_thuc=self.today);self.assertEqual(self.recognize()['access'],'granted')

    def test_expired_contract_cannot_use_longer_permission(self):
        self.permission()
        self.hd.ngay_bat_dau=self.today-timedelta(days=90);self.hd.ngay_ket_thuc=self.today-timedelta(days=1);self.hd.save()
        self.assertEqual(self.recognize()['access'],'denied')

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

class ManualResidentTests(BusinessFixture):
    def submit(self, hd, date):
        req=self.request(self.admin,{'hop_dong':str(hd.pk),'ho_ten':'Audit New Resident','ngay_vao':str(date)})
        with gia_lap_views('render',side_effect=lambda request,name,ctx:ctx):
            views.tao_nguoi_o_cung(req)
        return req

    def test_outside_contract_dates_rejected_without_crash(self):
        hd=self.contract()
        for date in [hd.ngay_bat_dau-timedelta(days=1),hd.ngay_ket_thuc+timedelta(days=1)]:
            with self.subTest(date=date):
                self.submit(hd,date)
                self.assertFalse(NguoiOCungPhong.objects.exists())

    def test_zero_capacity_is_unconfigured(self):
        hd=self.contract();self.room.so_nguoi_toi_da=0;self.room.save()
        req=self.submit(hd,self.today)
        self.assertFalse(NguoiOCungPhong.objects.exists())
        self.assertIn('chưa',' '.join(str(m) for m in get_messages(req)).lower())

    def test_zero_capacity_return_and_update(self):
        hd=self.contract();resident=self.resident(hd,'da_roi')
        self.room.so_nguoi_toi_da=0;self.room.save()
        for action in ['quay_lai','cap_nhat']:
            with self.subTest(action=action):
                _,req=self.post(views.xu_ly_nguoi_o_cung,resident,
                    {'hanh_dong':action,'trang_thai':'dang_o'},self.admin)
                resident.refresh_from_db();self.assertEqual(resident.trang_thai,'da_roi')
                self.assertIn('chưa',' '.join(str(m) for m in get_messages(req)).lower())

    def test_valid_resident_created(self):
        self.submit(self.contract(),self.today)
        self.assertEqual(NguoiOCungPhong.objects.count(),1)

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

class AccessSimulationTests(BusinessFixture):
    def test_expired_contract_denied(self):
        self.contract(start=self.today-timedelta(days=90),end=self.today-timedelta(days=1))
        self.permission()
        FaceProfile.objects.create(nguoi_thue=self.tenant,loai_chu_the='nguoi_thue',
            trang_thai='da_xac_thuc',anh_dai_dien='audit/nonexistent.jpg')
        req=self.request(self.admin,{'phong':str(self.room.pk),'chu_the':'nguoi_thue','nguoi_id':str(self.tenant.pk)})
        with gia_lap_views('render',side_effect=lambda request,name,ctx:ctx):
            ctx=views.smart_access_control(req)
        self.assertFalse(ctx['ket_qua']['duoc_phep'])
