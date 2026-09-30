from core.du_lieu_test.gia_lap_views import gia_lap_views
from core.tests import test_hoa_don as invoice_tests
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

class CrudHardeningTests(BusinessFixture):
    def notification_payload(self, **overrides):
        data = {
            'nguoi_thue': str(self.tenant.pk),
            'tieu_de': 'Audit notice',
            'noi_dung': 'Audit notification body',
            'loai': 'he_thong',
            'muc_do': 'binh_thuong',
        }
        data.update(overrides)
        return data

    def policy_payload(self, **overrides):
        data = {
            'ten_chinh_sach': 'Audit policy',
            'doi_tuong': 'sinh_vien',
            'loai_ho_tro': 'phan_tram',
            'gia_tri_ho_tro': '10',
            'ngan_sach': '1000000',
            'so_luong_nguoi_duoc_ap_dung': '5',
            'ngay_bat_dau': str(self.today),
            'ngay_ket_thuc': str(self.today + timedelta(days=30)),
            'dieu_kien': 'Audit',
            'mo_ta': 'Audit',
            'trang_thai': 'on',
        }
        data.update(overrides)
        return data

    def facility_payload(self, **overrides):
        data = {
            'ten_co_so': 'Audit Facility B',
            'dia_chi': 'Audit address',
            'quan': 'Audit district',
            'so_tang': '2',
            'so_phong': '10',
            'trang_thai': 'hoat_dong',
        }
        data.update(overrides)
        return data

    def test_tenant_cannot_create_notification(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('tao_thong_bao'), self.notification_payload())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('tai_khoan'), response.url)
        self.assertEqual(ThongBao.objects.count(), 0)

    def test_tenant_cannot_mutate_or_delete_notification(self):
        notification = ThongBao.objects.create(
            nguoi_thue=self.tenant, tieu_de='Keep', noi_dung='Keep',
            loai='he_thong', muc_do='binh_thuong'
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('xu_ly_thong_bao', args=[notification.pk]),
            {'hanh_dong': 'xoa'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ThongBao.objects.filter(pk=notification.pk).exists())

    def test_notification_get_does_not_mutate(self):
        notification = ThongBao.objects.create(
            nguoi_thue=self.tenant, tieu_de='Unread', noi_dung='Body',
            loai='he_thong', muc_do='binh_thuong', da_doc=False
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('xu_ly_thong_bao', args=[notification.pk]))
        notification.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(notification.da_doc)

    def test_notification_invalid_action_is_rejected_without_mutation(self):
        notification = ThongBao.objects.create(
            nguoi_thue=self.tenant, tieu_de='Title', noi_dung='Body',
            loai='he_thong', muc_do='binh_thuong'
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('xu_ly_thong_bao', args=[notification.pk]),
            {'hanh_dong': 'khong_hop_le', 'tieu_de': 'Changed'})
        notification.refresh_from_db()
        self.assertEqual(notification.tieu_de, 'Title')

    def test_admin_create_notification_validates_and_creates_once(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('tao_thong_bao'), self.notification_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ThongBao.objects.count(), 1)
        self.assertEqual(NhatKyThaoTac.objects.filter(module='Thông báo').count(), 1)

    def test_admin_create_notification_rejects_blank_title(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('tao_thong_bao'),
            self.notification_payload(tieu_de='   '))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ThongBao.objects.count(), 0)

    def test_admin_update_notification_validates_choices(self):
        notification = ThongBao.objects.create(
            nguoi_thue=self.tenant, tieu_de='Title', noi_dung='Body',
            loai='he_thong', muc_do='binh_thuong'
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse('xu_ly_thong_bao', args=[notification.pk]), {
            'hanh_dong': 'cap_nhat',
            'tieu_de': 'Updated',
            'noi_dung': 'Updated body',
            'loai': 'khong_hop_le',
            'muc_do': 'binh_thuong',
        })
        notification.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(notification.tieu_de, 'Title')

        self.client.post(reverse('xu_ly_thong_bao', args=[notification.pk]), {
            'hanh_dong': 'cap_nhat',
            'tieu_de': 'Updated',
            'noi_dung': 'Updated body',
            'loai': 'he_thong',
            'muc_do': 'quan_trong',
        })
        notification.refresh_from_db()
        self.assertEqual(notification.tieu_de, 'Updated')
        self.assertEqual(notification.muc_do, 'quan_trong')

    def test_policy_create_rejects_invalid_input_rejected_by_update(self):
        self.client.force_login(self.admin)
        invalid_cases = [
            self.policy_payload(ten_chinh_sach='   '),
            self.policy_payload(doi_tuong='khong_hop_le'),
            self.policy_payload(loai_ho_tro='khong_hop_le'),
            self.policy_payload(gia_tri_ho_tro='-1'),
            self.policy_payload(ngan_sach='-1'),
            self.policy_payload(so_luong_nguoi_duoc_ap_dung='-1'),
            self.policy_payload(ngay_ket_thuc=str(self.today - timedelta(days=1))),
        ]
        for payload in invalid_cases:
            with self.subTest(payload=payload):
                response = self.client.post(reverse('tao_chinh_sach'), payload)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(ChinhSachHoTro.objects.count(), 0)

    def test_policy_create_valid_input_succeeds(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('tao_chinh_sach'), self.policy_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ChinhSachHoTro.objects.count(), 1)

    def test_facility_create_rejects_invalid_input_rejected_by_update(self):
        self.client.force_login(self.admin)
        invalid_cases = [
            self.facility_payload(ten_co_so='   '),
            self.facility_payload(dia_chi='   '),
            self.facility_payload(quan='   '),
            self.facility_payload(so_tang='0'),
            self.facility_payload(so_phong='-1'),
            self.facility_payload(trang_thai='khong_hop_le'),
        ]
        for payload in invalid_cases:
            with self.subTest(payload=payload):
                response = self.client.post(reverse('tao_co_so'), payload)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(CoSo.objects.filter(ten_co_so='Audit Facility B').count(), 0)

    def test_facility_create_valid_input_succeeds(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('tao_co_so'), self.facility_payload())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CoSo.objects.filter(ten_co_so='Audit Facility B').exists())

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

class StateConsistencyTests(BusinessFixture):
    def test_room_hold_and_maintenance_precedence(self):
        self.room.trang_thai='bao_tri';self.room.save()
        self.assertEqual(self.room.dong_bo_trang_thai(),'bao_tri')
        booking=self.booking()
        self.room.refresh_from_db();self.assertEqual(self.room.trang_thai,'da_dat')
        booking.trang_thai='da_huy';booking.save()
        self.room.refresh_from_db();self.assertEqual(self.room.trang_thai,'trong')

    def test_command_date_boundaries_room_and_occupancy(self):
        hd=self.contract('cho_hieu_luc')
        for start,end,status,room,count in [(1,60,'cho_hieu_luc','da_dat',0),
                (0,60,'dang_hieu_luc','dang_thue',1),(-10,0,'sap_het_han','dang_thue',1),
                (-10,-1,'da_het_han','trong',0)]:
            with self.subTest(start=start,end=end):
                hd.ngay_bat_dau=self.today+timedelta(days=start)
                hd.ngay_ket_thuc=self.today+timedelta(days=end);hd.save()
                call_command('dong_bo_hop_dong',stdout=StringIO(),stderr=StringIO())
                hd.refresh_from_db();self.room.refresh_from_db()
                self.assertEqual(hd.trang_thai,status);self.assertEqual(self.room.trang_thai,room)
                self.assertEqual(self.room.so_nguoi_dang_o,count)

    def test_cancel_retains_booking_request_invoice_and_history(self):
        hd=self.contract();yc=self.sharing_request(hd)
        invoice=HoaDon.objects.create(hop_dong=hd,thang=9,nam=2026,han_thanh_toan=self.today)
        self.post(views.xu_ly_hop_dong,hd,{'hanh_dong':'huy'},self.admin)
        hd.dat_phong.refresh_from_db();yc.refresh_from_db();invoice.refresh_from_db()
        self.assertEqual(hd.dat_phong.trang_thai,'da_duyet')
        self.assertEqual(yc.trang_thai,'cho_duyet');self.assertEqual(invoice.trang_thai,'chua_thanh_toan')
        self.assertEqual(ThongBao.objects.count(),1);self.assertEqual(NhatKyThaoTac.objects.count(),1)

    def test_public_reads_stored_contract_until_date_sync(self):
        # Characterization of existing cache semantics, not a date-correctness guarantee.
        hd=self.contract(start=self.today-timedelta(days=90),end=self.today-timedelta(days=1))
        self.assertEqual(self.room.so_nguoi_dang_o,1)
        self.assertEqual(self.room.trang_thai_nghiep_vu(),'dang_thue')
        views.cap_nhat_trang_thai_hop_dong(hd)
        self.assertEqual(self.room.so_nguoi_dang_o,0)
        self.assertEqual(self.room.trang_thai_nghiep_vu(),'trong')

    def test_phase8b1_views_have_single_canonical_definition(self):
        import ast,inspect
        from pathlib import Path
        for name in ['tao_thong_bao','xu_ly_thong_bao','chi_tiet_yeu_cau_ghep']:
            fn=getattr(views,name)
            tree=ast.parse(Path(inspect.getsourcefile(inspect.unwrap(fn))).read_text(encoding='utf-8-sig'))
            nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name]
            self.assertEqual(len(nodes),1)
            self.assertEqual(inspect.unwrap(fn).__code__.co_firstlineno,
                min([nodes[0].lineno]+[d.lineno for d in nodes[0].decorator_list]))
            self.assertIs(resolve(reverse(name,kwargs={} if name=='tao_thong_bao' else {'id':1})).func,fn)

"""Phase 5B regression tests; all mutations use the guarded test fixture."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.template.loader import get_template
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import TransactionTestCase

from core.du_lieu_test import du_lieu_test_nghiep_vu as baseline
from core.du_lieu_test import tap_hop_views as views
from core.models import (Phong, DatPhong, HopDong, HoaDon, QuyenRaVao,
                     NguoiOCungPhong, FaceProfile, YeuCauGiaHanHopDong)


class AdminWorkflowTests(baseline.BusinessFixture):
    def test_lifecycle_fields_not_editable_in_admin_change_form(self):
        hd = self.contract()
        invoice = HoaDon.objects.create(hop_dong=hd, thang=9, nam=2026, han_thanh_toan=self.today)
        resident = self.resident(hd)
        right = self.permission()
        cases = [
            (hd, {'dat_phong', 'trang_thai', 'ngay_bat_dau', 'ngay_ket_thuc'}),
            (invoice, {'hop_dong', 'trang_thai', 'ngay_thanh_toan', 'ma_giao_dich'}),
            (right, {'hop_dong', 'nguon_cap', 'phong', 'nguoi_thue', 'nguoi_o_cung', 'trang_thai', 'ngay_bat_dau', 'ngay_ket_thuc'}),
            (resident, {'hop_dong', 'trang_thai', 'ngay_vao', 'ngay_ra'}),
            (hd.dat_phong, {'phong', 'nguoi_thue', 'trang_thai'}),
            (self.room, {'trang_thai'}),
        ]
        for obj, critical in cases:
            with self.subTest(model=type(obj).__name__):
                model_admin = admin.site._registry[type(obj)]
                fields = model_admin.get_form(self.request(self.admin), obj).base_fields
                self.assertFalse(critical.intersection(fields), critical.intersection(fields))

    def test_workflow_records_require_application_create_and_delete_actions(self):
        req = self.request(self.admin)
        req.user.is_superuser = True
        for model in [DatPhong, HopDong, HoaDon, NguoiOCungPhong, QuyenRaVao]:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(req))
                self.assertFalse(model_admin.has_delete_permission(req))

    def test_non_lifecycle_metadata_remains_editable(self):
        hd = self.contract()
        fields = admin.site._registry[HopDong].get_form(self.request(self.admin), hd).base_fields
        self.assertIn('ghi_chu', fields)

    def test_face_verification_cannot_be_forged_in_admin(self):
        fp = FaceProfile.objects.create(nguoi_thue=self.tenant, loai_chu_the='nguoi_thue')
        model_admin = admin.site._registry[FaceProfile]
        req = self.request(self.admin)
        fields = model_admin.get_form(req, fp).base_fields
        self.assertFalse({'nguoi_thue', 'nguoi_o_cung', 'loai_chu_the',
            'trang_thai', 'face_encoding', 'anh_dai_dien'}.intersection(fields))
        self.assertIn('ghi_chu', fields)
        self.assertFalse(model_admin.has_add_permission(req))


class WriterGuardTests(baseline.BusinessFixture):
    def submit_permission(self, hd, resident=None, room=None):
        fields = {'nguoi_o_cung': str(resident.pk), 'loai_quyen': 'nguoi_o_cung'} if resident else {
            'nguoi_thue': str(self.tenant.pk), 'loai_quyen': 'chu_phong'}
        fields.update(phong=str((room or self.room).pk), ngay_bat_dau=str(self.today),
                      ngay_ket_thuc=str(hd.ngay_ket_thuc))
        with gia_lap_views('render', side_effect=lambda request, name, ctx: ctx):
            views.tao_quyen_ra_vao(self.request(self.admin, fields))

    def test_wrong_room_permission_writer_blocked(self):
        hd = self.contract()
        other = Phong.objects.create(co_so=self.facility, so_phong='AUDIT-OTHER', gia_thue=1, dien_tich=1)
        resident = self.resident(hd)
        FaceProfile.objects.create(nguoi_o_cung=resident, loai_chu_the='nguoi_o_cung', trang_thai='da_xac_thuc')
        self.submit_permission(hd, resident, other)
        self.assertFalse(QuyenRaVao.objects.exists())

    def test_departed_resident_cannot_receive_active_permission(self):
        hd = self.contract()
        resident = self.resident(hd, 'da_roi')
        FaceProfile.objects.create(nguoi_o_cung=resident, loai_chu_the='nguoi_o_cung', trang_thai='da_xac_thuc')
        self.submit_permission(hd, resident)
        self.assertFalse(QuyenRaVao.objects.exists())

    def test_expired_contract_cannot_add_resident_or_restore_departed(self):
        hd = self.contract(start=self.today-timedelta(days=90), end=self.today-timedelta(days=1))
        resident = self.resident(hd, 'da_roi')
        with gia_lap_views('render', side_effect=lambda request, name, ctx: ctx):
            views.tao_nguoi_o_cung(self.request(self.admin, {
                'hop_dong': str(hd.pk), 'ho_ten': 'Audit New', 'ngay_vao': str(hd.ngay_bat_dau)}))
        with self.subTest(action='create'):
            self.assertEqual(NguoiOCungPhong.objects.count(), 1)
        for action in ['quay_lai', 'cap_nhat', 'unknown']:
            with self.subTest(action=action):
                self.post(views.xu_ly_nguoi_o_cung, resident,
                          {'hanh_dong': action, 'ho_ten': resident.ho_ten,
                           'trang_thai': ' dang_o '}, self.admin)
                resident.refresh_from_db()
                self.assertEqual(resident.trang_thai, 'da_roi')

    def test_room_edit_form_preserves_zero_capacity(self):
        self.room.so_nguoi_toi_da = 0; self.room.save()
        html = get_template('core/sua_phong.html').render({'phong': self.room}, self.request(self.admin))
        import re
        field = re.search(r'<input[^>]*name="so_nguoi_toi_da"[^>]*>', html).group()
        self.assertIn('value="0"', field)
        self.assertIn('min="0"', field)

    def test_zero_capacity_edit_post_saves_other_metadata(self):
        self.room.so_nguoi_toi_da = 0
        self.room.save()
        response = views.sua_phong(self.request(self.admin, {
            'co_so': str(self.facility.pk), 'so_phong': self.room.so_phong,
            'tang': '1', 'loai_phong': self.room.loai_phong,
            'gia_thue': '2500000', 'dien_tich': '25', 'so_nguoi_toi_da': '0',
            'trang_thai': 'trong', 'mo_ta': 'Preserved zero',
        }), self.room.pk)
        self.assertEqual(response.status_code, 302)
        self.room.refresh_from_db()
        self.assertEqual(self.room.so_nguoi_toi_da, 0)
        self.assertEqual(self.room.mo_ta, 'Preserved zero')

    def test_current_resident_permission_and_creation_remain_valid(self):
        hd = self.contract()
        resident = self.resident(hd)
        FaceProfile.objects.create(nguoi_o_cung=resident, loai_chu_the='nguoi_o_cung', trang_thai='da_xac_thuc')
        self.submit_permission(hd, resident)
        right = QuyenRaVao.objects.get()
        self.assertEqual(right.nguoi_o_cung_id, resident.pk)
        self.assertEqual((right.hop_dong_id, right.nguon_cap), (hd.pk, 'thu_cong'))
        views.tao_nguoi_o_cung(self.request(self.admin, {
            'hop_dong': str(hd.pk), 'ho_ten': 'Valid New', 'ngay_vao': str(self.today)}))
        self.assertEqual(NguoiOCungPhong.objects.count(), 2)

    def test_canceled_future_and_unapproved_contract_cannot_add_resident(self):
        for state in ['da_huy', 'future', 'unapproved']:
            with self.subTest(state=state):
                hd = self.contract('da_huy' if state == 'da_huy' else 'dang_hieu_luc',
                    start=self.today+timedelta(days=1) if state == 'future' else self.today)
                if state == 'unapproved':
                    hd.dat_phong.trang_thai = 'huy'
                    hd.dat_phong.save()
                with gia_lap_views('render', side_effect=lambda request, name, ctx: ctx):
                    views.tao_nguoi_o_cung(self.request(self.admin, {
                        'hop_dong': str(hd.pk), 'ho_ten': 'Invalid New', 'ngay_vao': str(hd.ngay_bat_dau)}))
                self.assertFalse(NguoiOCungPhong.objects.exists())


class HistoricalAccessTests(baseline.BusinessFixture):
    recognize = access_tests.AccessTests.recognize

    def profile(self, resident=None):
        return FaceProfile.objects.create(
            nguoi_thue=None if resident else self.tenant, nguoi_o_cung=resident,
            loai_chu_the='nguoi_o_cung' if resident else 'nguoi_thue',
            trang_thai='da_xac_thuc', face_encoding='audit-vector', anh_dai_dien='audit.jpg')

    def test_old_permission_does_not_inherit_new_contract(self):
        old_contract = self.contract('da_het_han', start=self.today-timedelta(days=200), end=self.today-timedelta(days=100))
        old_right = self.permission(hop_dong=old_contract, ngay_bat_dau=self.today-timedelta(days=200), ngay_ket_thuc=None)
        self.contract(start=self.today, end=self.today+timedelta(days=90))
        FaceProfile.objects.create(nguoi_thue=self.tenant, loai_chu_the='nguoi_thue',
                                   trang_thai='da_xac_thuc', face_encoding='audit-vector')
        self.assertEqual(self.recognize()['access'], 'denied')
        old_right.refresh_from_db()
        self.assertEqual(old_right.trang_thai, 'hoat_dong')

    def test_bound_new_stay_allowed_even_with_newer_legacy_and_wrong_binding(self):
        old = self.contract('da_het_han', start=self.today-timedelta(days=200), end=self.today-timedelta(days=100))
        current = self.contract()
        valid = self.permission(hop_dong=current)
        self.permission(hop_dong=None, nguon_cap='legacy_unknown')
        self.permission(hop_dong=old)
        self.profile()
        self.assertEqual(self.recognize()['access'], 'granted')
        self.assertEqual(baseline.LichSuRaVao.objects.get().quyen_ra_vao_id, valid.pk)
        with gia_lap_views('render', side_effect=lambda request, name, ctx: ctx):
            views.smart_access_control(self.request(self.admin, {
                'phong': str(self.room.pk), 'chu_the': 'nguoi_thue', 'nguoi_id': str(self.tenant.pk)}))
        self.assertEqual(baseline.LichSuRaVao.objects.order_by('-pk').first().quyen_ra_vao_id, valid.pk)

    def test_null_unknown_guest_denied_and_legacy_never_mutated(self):
        hd = self.contract()
        self.profile()
        for overrides in [dict(hop_dong=None), dict(nguon_cap='legacy_unknown'),
                          dict(hop_dong=None, nguon_cap='legacy_unknown'), dict(loai_quyen='khach_tam_thoi')]:
            with self.subTest(overrides=overrides):
                right = self.permission(hop_dong=overrides.pop('hop_dong', hd), **overrides)
                before = QuyenRaVao.objects.filter(pk=right.pk).values().get()
                self.assertEqual(self.recognize()['access'], 'denied')
                self.assertEqual(QuyenRaVao.objects.filter(pk=right.pk).values().get(), before)

    def test_legacy_action_cannot_activate_update_or_revoke(self):
        self.contract()
        right = self.permission(hop_dong=None, nguon_cap='legacy_unknown')
        before = QuyenRaVao.objects.values().get(pk=right.pk)
        for action in ['hoat_dong', 'cap_nhat', 'bi_thu_hoi', 'xoa']:
            self.post(views.xu_ly_quyen_ra_vao, right, {'hanh_dong': action}, self.admin)
            self.assertEqual(QuyenRaVao.objects.values().get(pk=right.pk), before)

    def test_roommate_wrong_binding_or_type_denied(self):
        hd = self.contract()
        resident = self.resident(hd)
        other = self.contract(tenant=self.other)
        self.profile(resident)
        for binding, kind in [(other, 'nguoi_o_cung'), (hd, 'chu_phong')]:
            right = self.permission(hop_dong=binding, nguoi_thue=None,
                nguoi_o_cung=resident, loai_quyen=kind)
            self.assertEqual(self.recognize()['access'], 'denied')
            from django.core.exceptions import ValidationError
            with self.assertRaises(ValidationError):
                right.full_clean()

    def test_face_sync_creates_new_bound_right_without_reusing_legacy(self):
        hd = self.contract()
        fp = self.profile()
        legacy = self.permission(hop_dong=None, nguon_cap='legacy_unknown')
        before = QuyenRaVao.objects.values().get(pk=legacy.pk)
        right, created = views._smart_room_dong_bo_quyen_sau_dang_ky(fp, hd, self.request(self.admin))
        self.assertTrue(created)
        self.assertEqual((right.hop_dong_id, right.nguon_cap), (hd.pk, 'face_id'))
        self.assertEqual(QuyenRaVao.objects.values().get(pk=legacy.pk), before)
        again, created = views._smart_room_dong_bo_quyen_sau_dang_ky(fp, hd, self.request(self.admin))
        self.assertFalse(created)
        self.assertEqual(again.pk, right.pk)

    def test_face_sync_preserves_manual_locked_revoked_expired(self):
        hd = self.contract()
        fp = self.profile()
        for state, source in [('tam_khoa', 'face_id'), ('bi_thu_hoi', 'face_id'),
                              ('het_han', 'face_id'), ('hoat_dong', 'thu_cong')]:
            with self.subTest(state=state, source=source):
                right = self.permission(hop_dong=hd, nguon_cap=source, trang_thai=state,
                    ngay_ket_thuc=self.today+timedelta(days=3))
                synced, created = views._smart_room_dong_bo_quyen_sau_dang_ky(fp, hd, self.request(self.admin))
                self.assertFalse(created)
                self.assertEqual(synced.pk, right.pk)
                self.assertEqual(synced.trang_thai, state)
                if source == 'thu_cong' or state in ('bi_thu_hoi', 'het_han'):
                    self.assertEqual(synced.ngay_ket_thuc, right.ngay_ket_thuc)

    def test_ambiguous_contract_rejects_manual_grant_and_face_resolution(self):
        hd = self.contract()
        self.contract()
        fp = self.profile()
        self.assertIsNone(views._smart_room_hop_dong_hop_le_cua_face_profile(fp))
        WriterGuardTests.submit_permission(self, hd)
        self.assertFalse(QuyenRaVao.objects.exists())

    def test_face_disable_revokes_bound_rights_across_stays_but_preserves_legacy(self):
        a = self.contract()
        b = self.contract()
        rights = [self.permission(hop_dong=h) for h in (a, b)]
        legacy = self.permission(hop_dong=None, nguon_cap='legacy_unknown')
        before = QuyenRaVao.objects.values().get(pk=legacy.pk)
        fp = self.profile()
        self.post(views.xu_ly_face_profile, fp, {'hanh_dong': 'xoa'}, self.admin)
        for right in rights:
            right.refresh_from_db()
            self.assertEqual(right.trang_thai, 'bi_thu_hoi')
        self.assertEqual(QuyenRaVao.objects.values().get(pk=legacy.pk), before)

    def test_expire_and_cancel_a_do_not_touch_b_or_legacy(self):
        for action in ['expire', 'cancel']:
            with self.subTest(action=action):
                a = self.contract(start=self.today-timedelta(days=50), end=self.today-timedelta(days=1))
                b = self.contract()
                old = self.permission(hop_dong=a)
                protected = [self.permission(hop_dong=b), self.permission(hop_dong=None, nguon_cap='legacy_unknown')]
                snapshots = {q.pk: QuyenRaVao.objects.values().get(pk=q.pk) for q in protected}
                if action == 'expire':
                    views.cap_nhat_trang_thai_hop_dong(a)
                else:
                    self.post(views.xu_ly_hop_dong, a, {'hanh_dong': 'huy', 'ly_do_huy': 'Audit'}, self.admin)
                old.refresh_from_db()
                self.assertEqual(old.trang_thai, 'het_han' if action == 'expire' else 'bi_thu_hoi')
                for pk, snapshot in snapshots.items():
                    self.assertEqual(QuyenRaVao.objects.values().get(pk=pk), snapshot)

    def test_departure_keeps_legacy_record_unchanged(self):
        hd = self.contract()
        resident = self.resident(hd)
        right = self.permission(hop_dong=hd, nguoi_thue=None, nguoi_o_cung=resident, loai_quyen='nguoi_o_cung')
        legacy = self.permission(hop_dong=None, nguon_cap='legacy_unknown', nguoi_thue=None,
                                 nguoi_o_cung=resident, loai_quyen='nguoi_o_cung')
        before = QuyenRaVao.objects.values().get(pk=legacy.pk)
        self.post(views.xu_ly_nguoi_o_cung, resident, {'hanh_dong': 'roi_phong'}, self.admin)
        right.refresh_from_db()
        self.assertEqual(right.trang_thai, 'het_han')
        self.assertEqual(QuyenRaVao.objects.values().get(pk=legacy.pk), before)
        self.post(views.xu_ly_nguoi_o_cung, resident, {'hanh_dong': 'xoa'}, self.admin)
        self.assertTrue(NguoiOCungPhong.objects.filter(pk=resident.pk).exists())

    def test_manual_tenant_grant_binds_current_stay_and_ignores_legacy_duplicate(self):
        hd = self.contract()
        self.profile()
        legacy = self.permission(hop_dong=None, nguon_cap='legacy_unknown')
        before = QuyenRaVao.objects.values().get(pk=legacy.pk)
        WriterGuardTests.submit_permission(self, hd)
        right = QuyenRaVao.objects.exclude(pk=legacy.pk).get()
        self.assertEqual((right.hop_dong_id, right.nguon_cap), (hd.pk, 'thu_cong'))
        self.assertEqual(self.recognize()['access'], 'granted')
        self.assertEqual(QuyenRaVao.objects.values().get(pk=legacy.pk), before)

    def test_manual_log_never_links_legacy_or_previous_stay(self):
        from django.utils import timezone
        a = self.contract('da_het_han', start=self.today-timedelta(days=50), end=self.today-timedelta(days=1))
        b = self.contract()
        valid = self.permission(hop_dong=b)
        self.permission(hop_dong=a)
        self.permission(hop_dong=None, nguon_cap='legacy_unknown')
        views.tao_lich_su_ra_vao(self.request(self.admin, {
            'phong': str(self.room.pk), 'nguoi_thue': str(self.tenant.pk),
            'loai_su_kien': 'vao', 'thoi_diem': timezone.localtime().isoformat(),
        }))
        self.assertEqual(baseline.LichSuRaVao.objects.get().quyen_ra_vao_id, valid.pk)

    def test_manual_log_rejects_ambiguous_contract(self):
        from django.utils import timezone
        self.contract()
        self.contract()
        with gia_lap_views('render', side_effect=lambda request, name, ctx: ctx):
            views.tao_lich_su_ra_vao(self.request(self.admin, {
                'phong': str(self.room.pk), 'nguoi_thue': str(self.tenant.pk),
                'loai_su_kien': 'vao', 'thoi_diem': timezone.localtime().isoformat(),
            }))
        self.assertFalse(baseline.LichSuRaVao.objects.exists())

    def test_bound_contract_protected_from_deletion(self):
        from django.db.models.deletion import ProtectedError
        hd = self.contract()
        self.permission(hop_dong=hd)
        with self.assertRaises(ProtectedError):
            hd.delete()


class LockOrderTests(baseline.BusinessFixture):
    def test_mutations_lock_room_before_dependent_rows(self):
        hd = self.contract('sap_het_han', end=self.today+timedelta(days=10))
        renewal = YeuCauGiaHanHopDong.objects.create(hop_dong=hd, nguoi_yeu_cau=self.tenant,
            so_thang_gia_han=2, ngay_ket_thuc_cu=hd.ngay_ket_thuc,
            ngay_ket_thuc_de_xuat=hd.ngay_ket_thuc+timedelta(days=60))
        for view, obj, payload in [
            (views.xu_ly_yeu_cau_gia_han, renewal, {'hanh_dong': 'tu_choi', 'ly_do_tu_choi': 'Audit'}),
            (views.xu_ly_hop_dong, hd, {'hanh_dong': 'cap_nhat_trang_thai'}),
            (views.xu_ly_dat_phong, hd.dat_phong, {'hanh_dong': 'duyet'}),
        ]:
            with self.subTest(view=view.__name__), CaptureQueriesContext(connection) as queries:
                self.post(view, obj, payload, self.admin)
                locks = [q['sql'] for q in queries.captured_queries if 'FOR UPDATE' in q['sql'].upper()]
                self.assertTrue(locks)
                self.assertIn('FROM `core_phong`', locks[0])
                self.assertNotIn('JOIN', locks[0].upper())


class PaymentAtomicTests(baseline.BusinessFixture):
    invoice = invoice_tests.InvoiceTests.invoice

    def test_stale_overdue_read_cannot_overwrite_pending_request(self):
        invoice = self.invoice()
        invoice.han_thanh_toan = self.today - timedelta(days=1)
        invoice.save()
        original_get = views.get_object_or_404
        first = True

        def concurrent_request(*args, **kwargs):
            nonlocal first
            obj = original_get(*args, **kwargs)
            if first:
                first = False
                # Another request commits after this request's initial read.
                HoaDon.objects.filter(pk=invoice.pk).update(trang_thai='cho_xac_nhan')
            return obj

        effects = self.effects()
        with gia_lap_views('get_object_or_404', side_effect=concurrent_request):
            self.post(views.thanh_toan_hoa_don_cua_toi, invoice, {
                'buoc': 'xac_thuc', 'phuong_thuc': 'chuyen_khoan', 'xac_nhan': 'dong_y'})
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, 'cho_xac_nhan')
        self.assertEqual(self.effects(), effects)

    def test_pending_and_confirmation_roll_back_on_notification_failure(self):
        invoice = self.invoice()
        for state, view, payload, user in [
            ('chua_thanh_toan', views.thanh_toan_hoa_don_cua_toi,
             {'buoc': 'xac_thuc', 'phuong_thuc': 'chuyen_khoan', 'xac_nhan': 'dong_y'}, self.user),
            ('cho_xac_nhan', views.xu_ly_hoa_don,
             {'hanh_dong': 'xac_nhan_thanh_toan', 'phuong_thuc': 'chuyen_khoan'}, self.admin),
        ]:
            with self.subTest(state=state):
                invoice.trang_thai = state
                invoice.save()
                effects = self.effects()
                with patch('core.views_hop_dong.ThongBao.objects.create', side_effect=RuntimeError('audit rollback')):
                    with self.assertRaises(RuntimeError):
                        self.post(view, invoice, payload, user)
                invoice.refresh_from_db()
                self.assertEqual(invoice.trang_thai, state)
                self.assertIsNone(invoice.ngay_thanh_toan)
                self.assertEqual(self.effects(), effects)

    def test_overdue_pending_is_not_reclassified_or_paid_by_tenant(self):
        invoice = self.invoice()
        invoice.trang_thai = 'cho_xac_nhan'
        invoice.han_thanh_toan = self.today - timedelta(days=1)
        invoice.save()
        effects = self.effects()
        self.post(views.thanh_toan_hoa_don_cua_toi, invoice, {
            'buoc': 'xac_thuc', 'phuong_thuc': 'tien_mat', 'xac_nhan': 'dong_y'})
        invoice.refresh_from_db()
        self.assertEqual(invoice.trang_thai, 'cho_xac_nhan')
        self.assertEqual(self.effects(), effects)


class LegacyDiagnosticTests(baseline.BusinessFixture):
    def test_diagnostic_uses_only_select_and_does_not_repair_legacy(self):
        from io import StringIO
        from django.core.management import call_command
        hd = self.contract('da_huy')
        resident = self.resident(hd)
        right = self.permission()
        output = StringIO()

        def read_only(execute, sql, params, many, context):
            self.assertTrue(sql.lstrip().upper().startswith('SELECT'), sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(read_only):
            call_command('kiem_tra_toan_ven_du_lieu', stdout=output)
        self.assertIn(f'resident_inactive_contract: count=1 ids=[{resident.pk}]', output.getvalue())
        self.assertIn(f'active_permission_invalid_relationship: count=1 ids=[{right.pk}]', output.getvalue())
        self.assertNotIn(self.tenant.ho_ten, output.getvalue())
        resident.refresh_from_db()
        self.assertEqual(resident.trang_thai, 'dang_o')

    def test_diagnostic_reports_legacy_wrong_type_binding_and_eligible(self):
        from io import StringIO
        from django.core.management import call_command
        hd = self.contract()
        valid = self.permission(hop_dong=hd)
        legacy = self.permission(hop_dong=None, nguon_cap='legacy_unknown')
        wrong_type = self.permission(hop_dong=hd, loai_quyen='nguoi_o_cung')
        wrong_binding = self.permission(hop_dong=hd, nguoi_thue=self.other)
        before = list(QuyenRaVao.objects.values())
        output = StringIO()
        call_command('kiem_tra_toan_ven_du_lieu', stdout=output)
        for label, pk in [('legacy_null_or_unknown', legacy.pk),
                          ('permission_invalid_subject_type', wrong_type.pk),
                          ('permission_authorizable', valid.pk)]:
            self.assertIn(f'{label}: count=1 ids=[{pk}]', output.getvalue())
        self.assertIn(f'permission_invalid_binding: count=2', output.getvalue())
        self.assertIn(str(wrong_binding.pk), output.getvalue())
        self.assertEqual(list(QuyenRaVao.objects.values()), before)


class PermissionMigrationTests(TransactionTestCase):
    def test_0020_preserves_legacy_without_backfill(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.utils import timezone
        self.assertEqual(connection.settings_dict['NAME'], 'test_ndt_motel')
        before = [('core', '0019_alter_hoadon_trang_thai')]
        after = [('core', '0020_quyenravao_contract_provenance')]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(before)
            apps = executor.loader.project_state(before).apps
            facility = apps.get_model('core', 'CoSo').objects.create(ten_co_so='Migration fixture')
            room = apps.get_model('core', 'Phong').objects.create(co_so=facility, so_phong='MIG', gia_thue=1, dien_tich=1)
            tenant = apps.get_model('core', 'NguoiThue').objects.create(ho_ten='Migration fixture', cccd='migration-test')
            old = apps.get_model('core', 'QuyenRaVao').objects.create(
                phong=room, nguoi_thue=tenant, loai_quyen='chu_phong',
                trang_thai='hoat_dong', ngay_bat_dau=timezone.localdate(), ngay_ket_thuc=None)
            snapshot = apps.get_model('core', 'QuyenRaVao').objects.values().get(pk=old.pk)
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            new_apps = executor.loader.project_state(after).apps
            result = new_apps.get_model('core', 'QuyenRaVao').objects.values().get(pk=old.pk)
            self.assertIsNone(result.pop('hop_dong_id'))
            self.assertEqual(result.pop('nguon_cap'), 'legacy_unknown')
            self.assertEqual(result, snapshot)
        finally:
            MigrationExecutor(connection).migrate(after)
