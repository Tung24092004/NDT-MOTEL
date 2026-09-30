"""Backend role, ownership, HTTP method and Django admin audit regressions."""
from urllib.parse import urlsplit
from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_phan_quyen import RoleAccessFixture
from core.models import LichSuRaVao, NguoiThue, Phong, ThongBao


AUDIT_MODELS = (
    'NhatKyThaoTac', 'LichSuRaVao', 'LichSuThanhToan', 'LichSuHopDong',
    'LichSuSuaChua', 'LichSuThongBao', 'LichSuTrangThai',
)


class RoleAccessMatrixTests(RoleAccessFixture):
    def admin_pages(self):
        return [(name, []) for name in (
            'dashboard_admin', 'nhat_ky_thao_tac', 'quan_ly_co_so', 'tao_co_so',
            'quan_ly_phong', 'tao_phong', 'quan_ly_dat_phong', 'quan_ly_hop_dong',
            'quan_ly_hoa_don', 'quan_ly_sua_chua', 'quan_ly_chinh_sach',
            'quan_ly_nguoi_thue', 'quan_ly_yeu_cau_ghep',
            'quan_ly_thong_bao', 'smart_room_dashboard', 'smart_access_control',
            'quan_ly_nguoi_o_cung', 'quan_ly_face_profile', 'quan_ly_quyen_ra_vao',
            'quan_ly_lich_su_ra_vao', 'tao_nguoi_o_cung', 'tao_face_profile',
            'tao_quyen_ra_vao', 'tao_lich_su_ra_vao', 'tao_hoa_don',
            'tao_sua_chua', 'tao_chinh_sach', 'tao_thong_bao',
            'trang_xac_thuc_face_id',
        )] + [
            ('chi_tiet_dat_phong', [self.booking_b.pk]),
            ('chi_tiet_hop_dong', [self.contract_b.pk]),
            ('chi_tiet_hoa_don', [self.invoice_b.pk]),
            ('chi_tiet_sua_chua', [self.repair_b.pk]),
            ('chi_tiet_co_so', [self.facility_b.pk]),
            ('chi_tiet_thong_bao', [self.notice_b.pk]),
            ('chi_tiet_chinh_sach', [self.policy.pk]),
            ('chi_tiet_nhat_ky_thao_tac', [self.audit_log.pk]),
            ('chi_tiet_nguoi_o_cung', [self.resident_b.pk]),
            ('chi_tiet_quyen_ra_vao', [self.permission_b.pk]),
            ('chi_tiet_lich_su_ra_vao', [self.access_log_b.pk]),
            ('sua_phong', [self.room_b.pk]),
            ('sua_hop_dong', [self.contract_b.pk]),
        ]

    def admin_writes(self):
        common = {
            'co_so': self.facility_b.pk, 'so_phong': 'ATTACK-ROOM',
            'gia_thue': '2500000', 'dien_tich': '25', 'so_nguoi_toi_da': '3',
            'loai_phong': self.room_b.loai_phong, 'tang': '1', 'trang_thai': 'trong',
        }
        return [
            ('tao_phong', [], common),
            ('sua_phong', [self.room_b.pk], common),
            ('xoa_phong', [self.room_b.pk], {}),
            ('xu_ly_dat_phong', [self.pending_booking_b.pk], {'hanh_dong': 'duyet'}),
            ('tao_hop_dong', [self.booking_b.pk], {'so_nguoi_o': '1'}),
            ('sua_hop_dong', [self.contract_b.pk], {'tien_thue_thang': '1'}),
            ('xu_ly_hop_dong', [self.contract_b.pk], {'hanh_dong': 'huy'}),
            ('xu_ly_yeu_cau_gia_han', [self.renewal_b.pk], {'hanh_dong': 'duyet'}),
            ('tao_hoa_don', [], {'hop_dong': self.contract_b.pk, 'thang': '1',
                               'nam': '2030', 'han_thanh_toan': str(self.today)}),
            ('xu_ly_hoa_don', [self.invoice_b.pk],
             {'hanh_dong': 'xac_nhan_thanh_toan', 'phuong_thuc': 'tien_mat'}),
            ('xu_ly_sua_chua', [self.repair_b.pk], {'trang_thai': 'hoan_thanh'}),
            ('tao_sua_chua', [], {'nguoi_thue': self.other.pk, 'phong': self.room_b.pk,
                                  'tieu_de': 'Attack', 'noi_dung': 'Attack',
                                  'loai_su_co': 'dien', 'muc_do': 'binh_thuong'}),
            ('tao_thong_bao', [], {'nguoi_thue': self.other.pk, 'tieu_de': 'Attack',
                                   'noi_dung': 'Attack', 'loai': 'he_thong',
                                   'muc_do': 'binh_thuong'}),
            ('xu_ly_thong_bao', [self.notice_b.pk], {'hanh_dong': 'xoa'}),
            ('tao_co_so', [], {'ten_co_so': 'Attack', 'dia_chi': 'Attack',
                               'quan': 'Attack', 'so_tang': '1', 'so_phong': '1',
                               'trang_thai': 'hoat_dong'}),
            ('xu_ly_co_so', [self.facility_b.pk], {'hanh_dong': 'dong_cua'}),
            ('tao_chinh_sach', [], {'ten_chinh_sach': 'Attack'}),
            ('xu_ly_chinh_sach', [self.policy.pk], {'hanh_dong': 'xoa'}),
            ('tao_nguoi_o_cung', [], {'hop_dong': self.contract_b.pk,
                                     'ho_ten': 'Attack', 'ngay_vao': str(self.today)}),
            ('xu_ly_nguoi_o_cung', [self.resident_b.pk], {'hanh_dong': 'roi_phong'}),
            ('tao_face_profile', [], {'nguoi_thue': self.applicant.pk,
                                      'loai_chu_the': 'nguoi_thue'}),
            ('xu_ly_face_profile', [self.face_b.pk], {'hanh_dong': 'xoa'}),
            ('tao_quyen_ra_vao', [], {'phong': self.room_b.pk,
                                      'nguoi_thue': self.other.pk,
                                      'loai_quyen': 'chu_phong',
                                      'ngay_bat_dau': str(self.today),
                                      'ngay_ket_thuc': str(self.contract_b.ngay_ket_thuc)}),
            ('xu_ly_quyen_ra_vao', [self.permission_b.pk], {'hanh_dong': 'xoa'}),
            ('tao_lich_su_ra_vao', [], {'phong': self.room_b.pk,
                                       'nguoi_thue': self.other.pk,
                                       'loai_su_kien': 'vao',
                                       'thoi_diem': timezone.localtime().isoformat()}),
            ('xu_ly_lich_su_ra_vao', [self.access_log_b.pk], {'hanh_dong': 'xoa'}),
            ('smart_access_control', [], {'phong': self.room_b.pk,
                                          'chu_the': 'nguoi_thue',
                                          'nguoi_id': self.other.pk}),
        ]

    def assert_denied(self, response, anonymous=False):
        self.assertEqual(response.status_code, 302)
        target = urlsplit(response.url).path
        if anonymous:
            self.assertEqual(target, reverse('dang_nhap'))
        else:
            self.assertIn(target, [reverse('tai_khoan'), reverse('home'),
                                   reverse('dang_nhap')])

    def test_admin_get_matrix_rejects_guest_and_both_tenants(self):
        for actor in [self.anonymous, self.user_a, self.user_b]:
            self.login_as(actor)
            for name, args in self.admin_pages():
                with self.subTest(actor=str(actor), route=name):
                    before = self.business_snapshot()
                    response = self.client.get(reverse(name, args=args))
                    self.assert_denied(response, not actor.is_authenticated)
                    self.assertEqual(self.business_snapshot(), before)

    def test_staff_and_superuser_without_staff_can_open_admin_pages(self):
        self.assertFalse(self.superuser.is_staff)
        for actor in [self.admin, self.superuser]:
            self.login_as(actor)
            for name, args in self.admin_pages():
                with self.subTest(actor=actor.username, route=name):
                    self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_admin_post_matrix_cannot_write_as_guest_or_tenant(self):
        for actor in [self.anonymous, self.user_a, self.user_b]:
            self.login_as(actor)
            for name, args, data in self.admin_writes():
                with self.subTest(actor=str(actor), route=name):
                    before = self.business_snapshot()
                    response = self.client.post(reverse(name, args=args), data)
                    self.assert_denied(response, not actor.is_authenticated)
                    self.assertEqual(self.business_snapshot(), before)

    def test_staff_and_superuser_can_perform_authorized_notification_write(self):
        for actor in [self.admin, self.superuser]:
            self.login_as(actor)
            response = self.client.post(reverse('tao_thong_bao'), {
                'nguoi_thue': self.tenant.pk, 'tieu_de': actor.username,
                'noi_dung': 'Authorized write', 'loai': 'he_thong',
                'muc_do': 'binh_thuong',
            })
            self.assertEqual(response.status_code, 302)
            self.assertTrue(ThongBao.objects.filter(tieu_de=actor.username).exists())

    def foreign_cases(self, suffix):
        obj = lambda name: getattr(self, name + '_' + suffix).pk
        return [
            ('post', 'huy_dat_phong_cua_toi', obj('pending_booking'), {'ly_do_huy': 'Attack'}, 404),
            ('get', 'chi_tiet_hop_dong_cua_toi', obj('contract'), {}, 404),
            ('get', 'xuat_hop_dong_pdf', obj('contract'), {}, 302),
            ('post', 'gui_yeu_cau_gia_han', obj('contract'), {'so_thang_gia_han': '1'}, 404),
            ('post', 'huy_yeu_cau_gia_han', obj('renewal'), {}, 302),
            ('get', 'chi_tiet_hoa_don_cua_toi', obj('invoice'), {}, 404),
            ('get', 'thanh_toan_hoa_don_cua_toi', obj('invoice'), {}, 404),
            ('post', 'thanh_toan_hoa_don_cua_toi', obj('invoice'),
             {'buoc': 'xac_thuc', 'phuong_thuc': 'chuyen_khoan', 'xac_nhan': 'dong_y'}, 404),
            ('get', 'chi_tiet_thong_bao_cua_toi', obj('notice'), {}, 404),
            ('post', 'chi_tiet_thong_bao_cua_toi', obj('notice'), {}, 404),
            ('get', 'chi_tiet_yeu_cau_sua_chua_cua_toi', obj('repair'), {}, 404),
            ('get', 'chi_tiet_yeu_cau_ghep', obj('sharing'), {}, 302),
            ('post', 'xu_ly_yeu_cau_ghep', obj('sharing'), {'hanh_dong': 'duyet'}, 302),
            ('post', 'xu_ly_yeu_cau_ghep', obj('sharing'), {'hanh_dong': 'tu_choi'}, 302),
            ('post', 'bat_tat_cho_phep_ghep', obj('contract'), {}, 302),
            ('get', 'chi_tiet_face_profile', obj('face'), {}, 302),
            ('post', 'face_id_dang_ky', obj('face'), {'image': 'foreign-image'}, 403),
            ('post', 'xu_ly_face_profile', obj('face'), {'hanh_dong': 'xoa'}, 302),
        ]

    def test_idor_matrix_is_symmetric_and_preserves_all_business_data(self):
        for actor, suffix in [(self.user_a, 'b'), (self.user_b, 'a')]:
            self.login_as(actor)
            for method, name, pk, data, status in self.foreign_cases(suffix):
                with self.subTest(actor=actor.username, route=name, method=method, data=data):
                    before = self.business_snapshot()
                    with patch('core.views_smart_room._face_image_from_base64') as decode:
                        response = getattr(self.client, method)(reverse(name, args=[pk]), data)
                        decode.assert_not_called()
                    self.assertEqual(response.status_code, status)
                    if status == 302:
                        self.assertIn(urlsplit(response.url).path, [
                            reverse('tai_khoan'), reverse('hop_dong_cua_toi'),
                            reverse('yeu_cau_ghep_cua_toi'),
                            reverse('chi_tiet_phong', args=[getattr(self, 'room_b' if suffix == 'b' else 'room').pk]),
                        ])
                    if name == 'face_id_dang_ky':
                        self.assertFalse(response.json()['success'])
                    self.assertEqual(self.business_snapshot(), before)

    def test_owner_can_open_private_pages_and_pdf(self):
        for actor, suffix in [(self.user_a, 'a'), (self.user_b, 'b')]:
            self.login_as(actor)
            for name, key in [('chi_tiet_hop_dong_cua_toi', 'contract'),
                              ('chi_tiet_hoa_don_cua_toi', 'invoice'),
                              ('thanh_toan_hoa_don_cua_toi', 'invoice'),
                              ('chi_tiet_yeu_cau_sua_chua_cua_toi', 'repair'),
                              ('chi_tiet_face_profile', 'face'), ('xuat_hop_dong_pdf', 'contract')]:
                with self.subTest(actor=actor.username, route=name):
                    pk = getattr(self, key + '_' + suffix).pk
                    before = self.business_snapshot()
                    response = self.client.get(reverse(name, args=[pk]))
                    self.assertEqual(response.status_code, 200)
                    if name == 'xuat_hop_dong_pdf':
                        self.assertEqual(response['Content-Type'], 'application/pdf')
                        after = self.business_snapshot()
                        logs = after.pop('core.NhatKyThaoTac')
                        old_logs = before.pop('core.NhatKyThaoTac')
                        self.assertEqual(logs[:-1], old_logs)
                        self.assertEqual(logs[-1]['nguoi_thuc_hien_id'], actor.pk)
                        self.assertEqual(logs[-1]['doi_tuong_id'], pk)
                        self.assertEqual(after, before)
                    else:
                        self.assertEqual(self.business_snapshot(), before)

    def test_reading_own_notification_never_marks_other_tenant_notification(self):
        self.login_as(self.user_a)
        before_b = ThongBao.objects.values().get(pk=self.notice_b.pk)
        response = self.client.get(reverse('chi_tiet_thong_bao_cua_toi', args=[self.notice_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.notice_a.refresh_from_db()
        self.assertTrue(self.notice_a.da_doc)
        self.assertEqual(ThongBao.objects.values().get(pk=self.notice_b.pk), before_b)

    def test_sharing_detail_allows_requester_owner_and_admin_only(self):
        for actor, requester, owner in [(self.stranger, True, False),
                                        (self.user_b, False, True),
                                        (self.admin, False, False),
                                        (self.superuser, False, False)]:
            self.login_as(actor)
            before = self.business_snapshot()
            response = self.client.get(reverse('chi_tiet_yeu_cau_ghep', args=[self.sharing_b.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['is_requester'], requester)
            self.assertEqual(response.context['is_owner'], owner)
            self.assertEqual(self.business_snapshot(), before)

    def test_requester_cannot_approve_or_reject_their_own_sharing_request(self):
        self.login_as(self.stranger)
        for action in ['duyet', 'tu_choi']:
            before = self.business_snapshot()
            response = self.client.post(reverse('xu_ly_yeu_cau_ghep', args=[self.sharing_b.pk]),
                                        {'hanh_dong': action})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(self.business_snapshot(), before)

    def test_sharing_user_context_contains_only_owned_or_sent_requests(self):
        for actor, suffix in [(self.user_a, 'a'), (self.user_b, 'b')]:
            self.login_as(actor)
            before = self.business_snapshot()
            response = self.client.get(reverse('yeu_cau_ghep_cua_toi'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(list(response.context['yeu_cau_can_duyet']),
                             [getattr(self, 'sharing_' + suffix)])
            self.assertEqual(list(response.context['yeu_cau_da_gui']), [])
            if 'yeu_cau' in response.context:
                self.assertEqual(list(response.context['yeu_cau']),
                                 [getattr(self, 'sharing_' + suffix)])
            self.assertEqual(self.business_snapshot(), before)
        for actor in [self.admin, self.superuser]:
            self.login_as(actor)
            response = self.client.get(reverse('yeu_cau_ghep_cua_toi'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(set(response.context['yeu_cau_can_duyet'].values_list('pk', flat=True)),
                             {self.sharing_a.pk, self.sharing_b.pk})

    def test_other_user_list_contexts_do_not_contain_foreign_data(self):
        self.login_as(self.user_a)
        foreign_ids = {
            'DatPhong': {self.booking_b.pk, self.pending_booking_b.pk},
            'HopDong': {self.contract_b.pk}, 'HoaDon': {self.invoice_b.pk},
            'ThongBao': {self.notice_b.pk}, 'YeuCauSuaChua': {self.repair_b.pk},
        }
        for name in ['tai_khoan', 'hop_dong_cua_toi', 'hoa_don_cua_toi',
                     'thong_bao_cua_toi', 'yeu_cau_sua_chua_cua_toi']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            values = [value for context in response.context
                      for value in context.flatten().values()]
            for value in values:
                model = getattr(value, 'model', None)
                if model and model.__name__ in foreign_ids:
                    self.assertFalse(set(value.values_list('pk', flat=True)) & foreign_ids[model.__name__])

    def test_superuser_navigation_matches_staff_navigation(self):
        for actor in [self.admin, self.superuser]:
            self.login_as(actor)
            response = self.client.get(reverse('chi_tiet_face_profile', args=[self.face_a.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'class="tenant-navigation"')
        self.login_as(self.user_a)
        response = self.client.get(reverse('chi_tiet_face_profile', args=[self.face_a.pk]))
        self.assertContains(response, 'class="tenant-navigation"')

    def test_admin_cannot_use_tenant_only_business_routes_even_with_tenant_profile(self):
        for index, actor in enumerate([self.admin, self.superuser], 6):
            NguoiThue.objects.create(tai_khoan=actor, ho_ten='Admin tenant',
                                     cccd='00000000000' + str(index))
            self.login_as(actor)
            cases = [
                ('get', 'tai_khoan', []), ('get', 'cap_nhat_thong_tin', []),
                ('get', 'hop_dong_cua_toi', []), ('get', 'hoa_don_cua_toi', []),
                ('get', 'thong_bao_cua_toi', []),
                ('get', 'chi_tiet_thong_bao_cua_toi', [self.notice_a.pk]),
                ('get', 'dat_phong', [self.room.pk]),
                ('get', 'nhan_dien_su_dung_phong', []),
                ('get', 'yeu_cau_sua_chua_cua_toi', []),
                ('get', 'tao_yeu_cau_sua_chua', []),
                ('post', 'huy_dat_phong_cua_toi', [self.pending_booking_a.pk]),
                ('post', 'gui_yeu_cau_gia_han', [self.contract_a.pk]),
                ('post', 'huy_yeu_cau_gia_han', [self.renewal_a.pk]),
                ('post', 'dang_ky_ghep_phong', [self.room.pk]),
                ('post', 'bat_tat_cho_phep_ghep', [self.contract_a.pk]),
            ]
            cases += [
                ('get', 'chi_tiet_hop_dong_cua_toi', [self.contract_a.pk]),
                ('get', 'chi_tiet_hoa_don_cua_toi', [self.invoice_a.pk]),
                ('get', 'thanh_toan_hoa_don_cua_toi', [self.invoice_a.pk]),
                ('post', 'thanh_toan_hoa_don_cua_toi', [self.invoice_a.pk]),
                ('get', 'chi_tiet_yeu_cau_sua_chua_cua_toi', [self.repair_a.pk]),
            ]
            for method, name, args in cases:
                with self.subTest(actor=actor.username, route=name):
                    before = self.business_snapshot()
                    response = getattr(self.client, method)(reverse(name, args=args))
                    self.assertEqual(response.status_code, 302)
                    self.assertIn(urlsplit(response.url).path,
                                  [reverse('dashboard_admin'), reverse('quan_ly_face_profile'),
                                   reverse('quan_ly_sua_chua'), reverse('tao_sua_chua'),
                                   reverse('chi_tiet_sua_chua', args=[self.repair_a.pk])])
                    self.assertEqual(self.business_snapshot(), before)

    def test_get_on_action_endpoints_never_mutates_business_database(self):
        for actor in [self.user_a, self.admin, self.superuser]:
            self.login_as(actor)
            actions = [(name, args) for name, args, data in self.admin_writes()
                       if name.startswith('xu_ly_') or name == 'xoa_phong']
            actions += [
                ('huy_dat_phong_cua_toi', [self.pending_booking_a.pk]),
                ('huy_yeu_cau_gia_han', [self.renewal_a.pk]),
                ('gui_yeu_cau_gia_han', [self.contract_a.pk]),
                ('bat_tat_cho_phep_ghep', [self.contract_a.pk]),
                ('xu_ly_yeu_cau_ghep', [self.sharing_a.pk]),
                ('face_id_dang_ky', [self.face_a.pk]), ('face_id_xac_thuc', []),
            ]
            for name, args in actions:
                with self.subTest(actor=actor.username, route=name):
                    before = self.business_snapshot()
                    response = self.client.get(reverse(name, args=args), {'hanh_dong': 'xoa'})
                    self.assertIn(response.status_code, [302, 403, 405])
                    self.assertEqual(self.business_snapshot(), before)

    def test_face_terminal_requires_admin_and_registration_checks_owner_before_decode(self):
        for actor, status in [(self.anonymous, 401), (self.user_a, 403), (self.user_b, 403)]:
            self.login_as(actor)
            before = self.business_snapshot()
            with patch('core.views_smart_room._face_image_from_base64') as decode:
                response = self.client.post(reverse('face_id_xac_thuc'), {'image': 'attack'})
                self.assertEqual(response.status_code, status)
                decode.assert_not_called()
            self.assertEqual(self.business_snapshot(), before)
        self.login_as(self.anonymous)
        response = self.client.post(reverse('face_id_dang_ky', args=[self.face_b.pk]), {'image': 'attack'})
        self.assertEqual(response.status_code, 401)


class AuditAdminAccessTests(RoleAccessFixture):
    def test_django_admin_denies_audit_mutations_for_every_model(self):
        self.superuser.is_staff = True
        self.superuser.save(update_fields=['is_staff'])
        self.login_as(self.superuser)
        for obj in self.audit_records:
            with self.subTest(model=obj._meta.model_name):
                prefix = 'admin:core_' + obj._meta.model_name + '_'
                before = self.business_snapshot()
                self.assertEqual(self.client.get(reverse(prefix + 'change', args=[obj.pk])).status_code, 200)
                self.assertEqual(self.client.post(reverse(prefix + 'change', args=[obj.pk]),
                                                 {'noi_dung': 'Forged'}).status_code, 403)
                self.assertEqual(self.client.post(reverse(prefix + 'delete', args=[obj.pk]),
                                                 {'post': 'yes'}).status_code, 403)
                self.assertEqual(self.client.post(reverse(prefix + 'add'), {}).status_code, 403)
                response = self.client.post(reverse(prefix + 'changelist'), {
                    'action': 'delete_selected', '_selected_action': [obj.pk], 'post': 'yes',
                })
                self.assertIn(response.status_code, [200, 302])
                self.assertEqual(self.business_snapshot(), before)

    def test_every_audit_model_is_viewable_but_cannot_add_change_or_delete(self):
        request = RequestFactory().get('/admin/')
        request.user = self.superuser
        for name in AUDIT_MODELS:
            with self.subTest(model=name):
                model = apps.get_model('core', name)
                self.assertIn(model, admin.site._registry)
                model_admin = admin.site._registry[model]
                self.assertTrue(model_admin.has_view_permission(request))
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))
                self.assertTrue({f.name for f in model._meta.fields}.issubset(
                    set(model_admin.get_readonly_fields(request))))
                self.assertNotIn('delete_selected', model_admin.get_actions(request))

    def test_django_admin_audit_list_preserves_staff_view_permission(self):
        view_permissions = Permission.objects.filter(
            content_type__app_label='core',
            codename__in=['view_' + name.lower() for name in AUDIT_MODELS],
        )
        self.admin.user_permissions.add(*view_permissions)
        for actor in [self.admin, self.superuser]:
            # Django admin itself requires is_staff; the application does not.
            actor.is_staff = True
            actor.save(update_fields=['is_staff'])
            self.login_as(actor)
            for name in AUDIT_MODELS:
                with self.subTest(actor=actor.username, model=name):
                    before = self.business_snapshot()
                    response = self.client.get(reverse('admin:core_' + name.lower() + '_changelist'))
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(self.business_snapshot(), before)

    def test_access_log_admin_blocks_edit_direct_delete_and_bulk_delete(self):
        self.superuser.is_staff = True
        self.superuser.save(update_fields=['is_staff'])
        self.login_as(self.superuser)
        prefix = 'admin:core_lichsuravao_'
        before = self.business_snapshot()
        detail = self.client.get(reverse(prefix + 'change', args=[self.access_log_b.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self.client.post(reverse(prefix + 'change', args=[self.access_log_b.pk]),
                                         {'ten_nguoi': 'Forged'}).status_code, 403)
        self.assertEqual(self.client.post(reverse(prefix + 'delete', args=[self.access_log_b.pk]),
                                         {'post': 'yes'}).status_code, 403)
        response = self.client.post(reverse(prefix + 'changelist'), {
            'action': 'delete_selected', '_selected_action': [self.access_log_b.pk], 'post': 'yes',
        })
        self.assertIn(response.status_code, [200, 302])
        self.assertEqual(self.business_snapshot(), before)

    def test_django_admin_cannot_cascade_delete_room_with_access_audit(self):
        room = Phong.objects.create(co_so=self.facility_b, so_phong='AUDIT-ONLY',
                                    gia_thue=1, dien_tich=1)
        LichSuRaVao.objects.create(phong=room, loai_su_kien='vao',
                                   thoi_diem=timezone.now())
        self.superuser.is_staff = True
        self.superuser.save(update_fields=['is_staff'])
        self.login_as(self.superuser)
        before = self.business_snapshot()
        response = self.client.post(reverse('admin:core_phong_delete', args=[room.pk]),
                                    {'post': 'yes'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.business_snapshot(), before)

"""Role navigation and invoice/deposit workflow closeout regressions."""

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.urls import reverse

from core.models import (
    FaceProfile,
    HoaDon,
    LichSuThanhToan,
    NguoiOCungPhong,
    QuyenRaVao,
    ThongBao,
)
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.hrefs_by_region = {}
        self.panel_triggers = []
        self.regions = ["document"]

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        pushed = None
        element_id = attrs.get("id", "")
        classes = set(attrs.get("class", "").split())
        if element_id == "ndtSidebar":
            pushed = "sidebar"
        elif "ndt-shell-topbar" in classes:
            pushed = "topbar"
        elif "ndt-flyout" in classes:
            pushed = f"flyout:{attrs.get('data-panel-id', 'unknown')}"
        elif tag == "main" or "site-main" in classes:
            pushed = "main"
        elif "ndt-public-footer" in classes or "site-footer" in classes:
            pushed = "footer"
        elif "breadcrumb" in element_id or any("breadcrumb" in class_name for class_name in classes):
            pushed = "breadcrumb"
        if pushed:
            self.regions.append(pushed)

        if attrs.get("data-panel"):
            self.panel_triggers.append(attrs["data-panel"])

        if tag == "a":
            href = attrs.get("href")
            if href:
                self.hrefs.append(href)
                for region in self.regions:
                    self.hrefs_by_region.setdefault(region, set()).add(href)

    def handle_endtag(self, tag):
        if len(self.regions) > 1:
            current = self.regions[-1]
            if (
                (tag == "aside" and current == "sidebar")
                or (tag == "header" and current == "topbar")
                or (tag == "section" and current.startswith("flyout:"))
                or (tag == "main" and current == "main")
                or (tag == "footer" and current == "footer")
                or (tag == "div" and current == "breadcrumb")
                or (tag == "nav" and current == "breadcrumb")
            ):
                self.regions.pop()


def rendered_navigation(response):
    parser = LinkCollector()
    parser.feed(response.content.decode(response.charset or "utf-8"))
    return parser


class RoleUiPaymentAuditTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.invoice = HoaDon.objects.create(
            hop_dong=self.contract_obj,
            thang=9,
            nam=2026,
            tien_phong=2500000,
            tien_dich_vu=50000,
            han_thanh_toan=self.today,
        )

    def test_tenant_invoice_chain_is_owned_and_qr_uses_current_invoice(self):
        self.client.force_login(self.user)
        listing = self.client.get(reverse("hoa_don_cua_toi"))
        detail_url = reverse("chi_tiet_hoa_don_cua_toi", args=[self.invoice.pk])
        payment_url = reverse("thanh_toan_hoa_don_cua_toi", args=[self.invoice.pk])
        self.assertContains(listing, detail_url)

        detail = self.client.get(detail_url)
        self.assertContains(detail, payment_url)

        payment = self.client.get(payment_url)
        self.assertEqual(payment.context["tong_tien_goc"], self.invoice.tong_tien)
        self.assertEqual(payment.context["noi_dung_chuyen_khoan"], f"NDTMOTEL HD{self.invoice.pk}")
        query = parse_qs(urlparse(payment.context["qr_url"]).query)
        self.assertEqual(query["amount"], [str(int(self.invoice.tong_tien))])
        self.assertEqual(query["addInfo"], [f"NDTMOTEL HD{self.invoice.pk}"])

        foreign = HoaDon.objects.create(
            hop_dong=self.contract(tenant=self.other), thang=10, nam=2026,
            tien_phong=9000000, han_thanh_toan=self.today,
        )
        self.assertEqual(
            self.client.get(reverse("chi_tiet_hoa_don_cua_toi", args=[foreign.pk])).status_code,
            404,
        )

    def test_tenant_report_is_pending_deduped_and_has_no_unrelated_side_effects(self):
        self.client.force_login(self.user)
        url = reverse("thanh_toan_hoa_don_cua_toi", args=[self.invoice.pk])
        before = (
            NguoiOCungPhong.objects.count(),
            FaceProfile.objects.count(),
            QuyenRaVao.objects.count(),
        )
        data = {
            "buoc": "xac_thuc",
            "phuong_thuc": "chuyen_khoan",
            "xac_nhan": "dong_y",
        }
        self.client.post(url, data)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.trang_thai, "cho_xac_nhan")
        self.assertIsNone(self.invoice.ngay_thanh_toan)
        self.assertIsNone(self.invoice.nguoi_xac_nhan)
        self.assertEqual(LichSuThanhToan.objects.filter(hoa_don=self.invoice).count(), 0)
        self.assertEqual(
            ThongBao.objects.filter(
                ma_tham_chieu=f"INVOICE:{self.invoice.pk}:PAYMENT_REPORTED:USER"
            ).count(),
            1,
        )
        admin_notice = ThongBao.objects.get(
            nguoi_nhan_user=self.admin,
            ma_tham_chieu=f"INVOICE:{self.invoice.pk}:PAYMENT_REPORTED:{self.admin.pk}",
        )
        self.assertEqual(admin_notice.url_lien_ket, reverse("chi_tiet_hoa_don", args=[self.invoice.pk]))

        self.client.post(url, data)
        self.assertEqual(
            ThongBao.objects.filter(ma_tham_chieu__startswith=f"INVOICE:{self.invoice.pk}:PAYMENT_REPORTED").count(),
            2,
        )
        self.assertEqual(before, (
            NguoiOCungPhong.objects.count(),
            FaceProfile.objects.count(),
            QuyenRaVao.objects.count(),
        ))

    def test_only_admin_can_settle_invoice(self):
        self.invoice.trang_thai = "cho_xac_nhan"
        self.invoice.phuong_thuc = "chuyen_khoan"
        self.invoice.save(update_fields=["trang_thai", "phuong_thuc"])
        action = reverse("xu_ly_hoa_don", args=[self.invoice.pk])

        self.client.force_login(self.user)
        self.client.post(action, {"hanh_dong": "xac_nhan_thanh_toan"})
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.trang_thai, "cho_xac_nhan")

        self.client.force_login(self.admin)
        response = self.client.post(action, {"hanh_dong": "xac_nhan_thanh_toan"})
        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.trang_thai, "da_thanh_toan")
        self.assertEqual(self.invoice.nguoi_xac_nhan, self.admin)
        self.assertIsNotNone(self.invoice.ngay_thanh_toan)

    def test_admin_cannot_settle_invoice_before_tenant_reports_payment(self):
        action = reverse("xu_ly_hoa_don", args=[self.invoice.pk])
        self.client.force_login(self.admin)
        detail = self.client.get(reverse("chi_tiet_hoa_don", args=[self.invoice.pk]))
        self.assertNotContains(detail, 'value="xac_nhan_thanh_toan"')

        before = (LichSuThanhToan.objects.count(), ThongBao.objects.count())
        response = self.client.post(action, {
            "hanh_dong": "xac_nhan_thanh_toan",
            "phuong_thuc": "chuyen_khoan",
        })
        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.trang_thai, "chua_thanh_toan")
        self.assertIsNone(self.invoice.ngay_thanh_toan)
        self.assertIsNone(self.invoice.nguoi_xac_nhan)
        self.assertEqual((LichSuThanhToan.objects.count(), ThongBao.objects.count()), before)

    def test_role_menus_and_tenant_management_routes_are_scoped(self):
        self.client.force_login(self.user)
        tenant_page = self.client.get(reverse("hoa_don_cua_toi"))
        self.assertContains(tenant_page, 'class="ndt-premium-ui ndt-role-tenant"')
        self.assertContains(tenant_page, "css/ui-system.css")
        self.assertContains(tenant_page, "js/ui-system.js")
        for route in ("dat_phong_cua_toi", "hoa_don_cua_toi", "thong_bao_cua_toi"):
            self.assertContains(tenant_page, reverse(route))
        self.assertNotContains(tenant_page, reverse("quan_ly_hoa_don"))
        self.assertEqual(self.client.get(reverse("quan_ly_nguoi_thue")).status_code, 302)
        self.assertEqual(self.client.get(reverse("quan_ly_yeu_cau_ghep")).status_code, 302)
        self.assertEqual(
            self.client.get(reverse("chi_tiet_nguoi_thue", args=[self.tenant.pk])).status_code,
            302,
        )

        self.client.force_login(self.admin)
        admin_page = self.client.get(reverse("dashboard_admin"))
        self.assertContains(admin_page, 'class="ndt-premium-ui ndt-role-admin"')
        for route in ("quan_ly_hoa_don", "quan_ly_nguoi_thue", "thong_bao_admin"):
            self.assertContains(admin_page, reverse(route))
        self.assertNotContains(admin_page, reverse("hoa_don_cua_toi"))
        self.assertEqual(self.client.get(reverse("quan_ly_nguoi_thue")).status_code, 200)
        detail = self.client.get(reverse("chi_tiet_nguoi_thue", args=[self.tenant.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.tenant.ho_ten)

    def test_primary_shell_links_and_sharing_page_use_the_correct_role_context(self):
        self.client.force_login(self.user)
        tenant_page = self.client.get(reverse("hoa_don_cua_toi"))
        self.assertContains(tenant_page, reverse("dat_phong_cua_toi"))
        self.assertContains(tenant_page, reverse("tai_khoan"))

        self.client.force_login(self.admin)
        admin_page = self.client.get(reverse("dashboard_admin"))
        self.assertContains(admin_page, reverse("quan_ly_nguoi_thue"))
        self.assertContains(admin_page, reverse("doi_mat_khau"))
        self.assertContains(admin_page, '>Quản trị</a>')

        sharing_page = self.client.get(reverse("quan_ly_yeu_cau_ghep"))
        self.assertEqual(sharing_page.status_code, 200)
        self.assertTrue(sharing_page.context["admin_mode"])
        self.assertContains(sharing_page, "Khu quản trị")
        self.assertContains(sharing_page, "Yêu cầu chờ xét duyệt")
        self.assertNotContains(sharing_page, "Yêu cầu tôi đã gửi")

    def test_rendered_navigation_contains_only_links_for_the_logged_in_role(self):
        tenant_routes = {
            reverse(name) for name in (
                "tai_khoan", "dat_phong_cua_toi", "hop_dong_cua_toi",
                "hoa_don_cua_toi", "yeu_cau_sua_chua_cua_toi",
                "yeu_cau_ghep_cua_toi", "thong_bao_cua_toi",
                "nhan_dien_su_dung_phong",
            )
        }
        admin_routes = {
            reverse(name) for name in (
                "dashboard_admin", "quan_ly_co_so", "quan_ly_phong",
                "quan_ly_dat_phong", "quan_ly_hop_dong", "quan_ly_hoa_don",
                "quan_ly_nguoi_thue", "quan_ly_sua_chua",
                "quan_ly_chinh_sach", "quan_ly_thong_bao",
                "quan_ly_yeu_cau_ghep", "quan_ly_nguoi_o_cung",
                "quan_ly_face_profile", "quan_ly_quyen_ra_vao",
                "quan_ly_lich_su_ra_vao", "smart_room_dashboard",
                "smart_access_control", "nhat_ky_thao_tac", "thong_bao_admin",
            )
        }
        tenant_panels = {"tenant-stay", "tenant-payment", "tenant-support", "account-panel"}
        admin_panels = {
            "admin-operations", "admin-finance", "admin-service",
            "admin-smart", "admin-system", "account-panel",
        }

        def assert_role_clean(response, allowed_routes, forbidden_routes, role, required_panels, forbidden_panels):
            nav = rendered_navigation(response)
            hrefs = set(nav.hrefs)
            self.assertTrue(allowed_routes.issubset(hrefs), allowed_routes - hrefs)
            self.assertTrue(forbidden_routes.isdisjoint(hrefs), forbidden_routes & hrefs)
            self.assertTrue(required_panels.issubset(set(nav.panel_triggers)))
            self.assertTrue(forbidden_panels.isdisjoint(set(nav.panel_triggers)))
            self.assertFalse(any(
                path.startswith(("/quan-ly-", "/smart-room/", "/nhat-ky-thao-tac/", "/thong-bao-admin/"))
                for path in hrefs
            ) if role == "tenant" else any(
                "-cua-toi" in path or path.startswith("/tai-khoan/")
                for path in hrefs
            ))
            for region, region_hrefs in nav.hrefs_by_region.items():
                with self.subTest(role=role, region=region):
                    self.assertTrue(
                        forbidden_routes.isdisjoint(region_hrefs),
                        f"{role} forbidden hrefs in {region}: {forbidden_routes & region_hrefs}",
                    )
                    if role == "tenant":
                        self.assertFalse(any(
                            path.startswith(("/quan-ly-", "/smart-room/", "/nhat-ky-thao-tac/", "/thong-bao-admin/"))
                            for path in region_hrefs
                        ), f"tenant admin path leaked in {region}: {region_hrefs}")
                    else:
                        self.assertFalse(any(
                            "-cua-toi" in path or path.startswith("/tai-khoan/")
                            for path in region_hrefs
                        ), f"admin tenant path leaked in {region}: {region_hrefs}")

        self.client.force_login(self.user)
        tenant_pages = (
            "home", "danh_sach_phong", "tai_khoan", "dat_phong_cua_toi",
            "hop_dong_cua_toi", "hoa_don_cua_toi",
            "yeu_cau_sua_chua_cua_toi", "yeu_cau_ghep_cua_toi",
            "thong_bao_cua_toi",
        )
        for page_name in tenant_pages:
            with self.subTest(role="tenant", page=page_name):
                tenant_page = self.client.get(reverse(page_name))
                self.assertEqual(tenant_page.status_code, 200)
                assert_role_clean(
                    tenant_page, tenant_routes, admin_routes, "tenant",
                    tenant_panels, admin_panels - {"account-panel"},
                )
                self.assertNotContains(tenant_page, 'id="adminMegaMenu"')
                self.assertNotContains(tenant_page, 'class="site-header"')

        self.client.force_login(self.admin)
        admin_pages = (
            "home", "danh_sach_phong", "dashboard_admin", "quan_ly_co_so", "quan_ly_phong",
            "quan_ly_dat_phong", "quan_ly_hop_dong", "quan_ly_hoa_don",
            "quan_ly_nguoi_thue", "quan_ly_sua_chua",
            "quan_ly_chinh_sach", "quan_ly_thong_bao",
            "quan_ly_yeu_cau_ghep", "smart_room_dashboard",
            "smart_access_control", "quan_ly_nguoi_o_cung",
            "quan_ly_face_profile", "quan_ly_quyen_ra_vao",
            "quan_ly_lich_su_ra_vao", "nhat_ky_thao_tac", "thong_bao_admin",
        )
        for page_name in admin_pages:
            with self.subTest(role="admin", page=page_name):
                admin_page = self.client.get(reverse(page_name))
                self.assertEqual(admin_page.status_code, 200)
                assert_role_clean(
                    admin_page, admin_routes, tenant_routes, "admin",
                    admin_panels, tenant_panels - {"account-panel"},
                )
                self.assertNotContains(admin_page, 'id="adminMegaMenu"')
                self.assertNotContains(admin_page, 'class="site-header"')

        room_page = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertEqual(room_page.status_code, 200)
        assert_role_clean(
            room_page, admin_routes, tenant_routes, "admin",
            admin_panels, tenant_panels - {"account-panel"},
        )

    def test_all_active_admins_receive_one_invoice_notice(self):
        second_admin = User.objects.create_user("payment-admin-2", is_superuser=True)
        self.client.force_login(self.user)
        url = reverse("thanh_toan_hoa_don_cua_toi", args=[self.invoice.pk])
        self.client.post(url, {
            "buoc": "xac_thuc", "phuong_thuc": "chuyen_khoan", "xac_nhan": "dong_y",
        })
        for admin in (self.admin, second_admin):
            self.assertEqual(ThongBao.objects.filter(
                nguoi_nhan_user=admin,
                ma_tham_chieu=f"INVOICE:{self.invoice.pk}:PAYMENT_REPORTED:{admin.pk}",
            ).count(), 1)
