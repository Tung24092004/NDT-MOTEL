from core.tests import test_phong_thong_minh as access_tests
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


class RenewalTests(baseline.BusinessFixture):
    def setUp(self):
        self.hd = self.contract('sap_het_han', start=self.today-timedelta(days=60),
                                end=self.today+timedelta(days=10))

    def renewal(self, **overrides):
        data = dict(hop_dong=self.hd, nguoi_yeu_cau=self.tenant, so_thang_gia_han=2,
                    ngay_ket_thuc_cu=self.hd.ngay_ket_thuc,
                    ngay_ket_thuc_de_xuat=self.hd.ngay_ket_thuc+timedelta(days=60))
        data.update(overrides)
        return YeuCauGiaHanHopDong.objects.create(**data)

    def process(self, renewal, action='duyet', user=None):
        return self.post(views.xu_ly_yeu_cau_gia_han, renewal,
                         {'hanh_dong': action, 'ly_do_tu_choi': 'Audit reason'}, user or self.admin)

    def test_owner_request_and_duplicate(self):
        data = {'so_thang_gia_han': '2', 'ngay_ket_thuc_de_xuat': '2000-01-01'}
        self.post(views.gui_yeu_cau_gia_han, self.hd, data)
        renewal = YeuCauGiaHanHopDong.objects.get()
        self.assertEqual(renewal.nguoi_yeu_cau, self.tenant)
        self.assertEqual(renewal.ngay_ket_thuc_cu, self.hd.ngay_ket_thuc)
        self.assertEqual(renewal.ngay_ket_thuc_de_xuat,
                         views.tinh_ngay_ket_thuc_theo_thang(self.hd.ngay_ket_thuc+timedelta(days=1), 2))
        effects = self.effects()
        self.post(views.gui_yeu_cau_gia_han, self.hd, data)
        self.assertEqual(YeuCauGiaHanHopDong.objects.count(), 1)
        self.assertEqual(self.effects(), effects)
        self.assertEqual(ThongBao.objects.get().nguoi_thue, self.tenant)

    def test_guest_admin_and_wrong_owner_blocked(self):
        self.client.post(reverse('gui_yeu_cau_gia_han', args=[self.hd.pk]), {'so_thang_gia_han': '2'})
        self.post(views.gui_yeu_cau_gia_han, self.hd, {'so_thang_gia_han': '2'}, self.admin)
        with self.assertRaises(Http404):
            self.post(views.gui_yeu_cau_gia_han, self.hd, {'so_thang_gia_han': '2'}, self.other_user)
        self.assertFalse(YeuCauGiaHanHopDong.objects.exists())

    def test_request_ineligible_states(self):
        for state, start, end in [('da_huy', -60, 10), ('da_het_han', -60, -1),
                                  ('cho_hieu_luc', 1, 60), ('dang_hieu_luc', -60, 31)]:
            with self.subTest(state=state):
                self.hd.trang_thai = state
                self.hd.ngay_bat_dau = self.today+timedelta(days=start)
                self.hd.ngay_ket_thuc = self.today+timedelta(days=end)
                self.hd.save()
                self.post(views.gui_yeu_cau_gia_han, self.hd, {'so_thang_gia_han': '2'})
                self.assertFalse(YeuCauGiaHanHopDong.objects.exists())

    def test_invalid_months(self):
        for value in ['', '0', '-1', '37', '1.5', 'abc']:
            with self.subTest(value=value):
                self.post(views.gui_yeu_cau_gia_han, self.hd, {'so_thang_gia_han': value})
                self.assertFalse(YeuCauGiaHanHopDong.objects.exists())

    def test_calendar_boundaries(self):
        for start, months, end in [(date(2024, 2, 1), 1, date(2024, 2, 29)),
                                    (date(2025, 2, 1), 1, date(2025, 2, 28)),
                                    (date(2024, 1, 31), 1, date(2024, 2, 29)),
                                    (date(2026, 12, 1), 1, date(2026, 12, 31))]:
            with self.subTest(start=start):
                self.assertEqual(views.tinh_ngay_ket_thuc_theo_thang(start, months), end)

    def test_cancel_pending_twice_preserves_contract_and_access(self):
        renewal = self.renewal()
        permission = self.permission(ngay_ket_thuc=self.hd.ngay_ket_thuc)
        before = (self.hd.ngay_ket_thuc, permission.ngay_ket_thuc, self.room.trang_thai)
        self.post(views.huy_yeu_cau_gia_han, renewal, {})
        renewal.refresh_from_db()
        self.assertEqual(renewal.trang_thai, 'da_huy')
        effects = self.effects()
        self.post(views.huy_yeu_cau_gia_han, renewal, {})
        self.assertEqual(self.effects(), effects)
        self.hd.refresh_from_db(); permission.refresh_from_db(); self.room.refresh_from_db()
        self.assertEqual((self.hd.ngay_ket_thuc, permission.ngay_ket_thuc, self.room.trang_thai), before)

    def test_wrong_owner_cancel_and_nonadmin_approval_blocked(self):
        renewal = self.renewal()
        self.post(views.huy_yeu_cau_gia_han, renewal, {}, self.other_user)
        self.process(renewal, user=self.user)
        renewal.refresh_from_db()
        self.assertEqual(renewal.trang_thai, 'cho_duyet')
        self.assertEqual(self.effects(), (0, 0, 0, 0))

    def test_stale_end_change_blocks_approval(self):
        renewal = self.renewal()
        self.hd.ngay_ket_thuc += timedelta(days=1); self.hd.save()
        before = self.hd.ngay_ket_thuc
        self.process(renewal)
        self.hd.refresh_from_db(); renewal.refresh_from_db()
        self.assertEqual(self.hd.ngay_ket_thuc, before)
        self.assertEqual(renewal.trang_thai, 'cho_duyet')

    def test_canceled_or_expired_contract_blocks_stale_approval(self):
        renewal = self.renewal()
        for state in ['da_huy', 'da_het_han']:
            with self.subTest(state=state):
                self.hd.trang_thai = state
                if state == 'da_het_han':
                    self.hd.ngay_ket_thuc = self.today-timedelta(days=1)
                self.hd.save()
                before = self.hd.ngay_ket_thuc
                self.process(renewal)
                self.hd.refresh_from_db(); renewal.refresh_from_db()
                self.assertEqual(self.hd.ngay_ket_thuc, before)
                self.assertEqual(renewal.trang_thai, 'cho_duyet')

    def test_equal_or_earlier_proposed_end_rejected(self):
        renewal = self.renewal()
        for delta in [0, -1]:
            renewal.ngay_ket_thuc_de_xuat = self.hd.ngay_ket_thuc+timedelta(days=delta)
            renewal.save()
            self.process(renewal)
            renewal.refresh_from_db()
            self.assertEqual(renewal.trang_thai, 'cho_duyet')

    def test_one_day_extension_uses_existing_date_policy(self):
        renewal = self.renewal(ngay_ket_thuc_de_xuat=self.hd.ngay_ket_thuc+timedelta(days=1))
        self.process(renewal)
        self.hd.refresh_from_db()
        self.assertEqual(self.hd.ngay_ket_thuc, renewal.ngay_ket_thuc_de_xuat)
        self.assertEqual(self.hd.trang_thai, 'sap_het_han')

    def test_approval_twice_preserves_occupancy_and_history(self):
        renewal = self.renewal()
        active = self.resident(self.hd)
        departed = self.resident(self.hd, 'da_roi')
        profile = FaceProfile.objects.create(nguoi_o_cung=active, loai_chu_the='nguoi_o_cung')
        invoice = HoaDon.objects.create(hop_dong=self.hd, thang=9, nam=2026, han_thanh_toan=self.today)
        self.process(renewal)
        self.hd.refresh_from_db(); self.room.refresh_from_db()
        active.refresh_from_db(); departed.refresh_from_db(); profile.refresh_from_db(); invoice.refresh_from_db()
        self.assertEqual(self.hd.ngay_ket_thuc, renewal.ngay_ket_thuc_de_xuat)
        self.assertEqual(self.hd.trang_thai, 'dang_hieu_luc')
        self.assertEqual(self.room.trang_thai, 'dang_thue')
        self.assertEqual(self.room.trang_thai_nghiep_vu(), 'dang_thue')
        self.assertEqual(self.room.so_nguoi_dang_o, 2)
        self.assertEqual(active.ngay_vao, self.today)
        self.assertEqual(departed.trang_thai, 'da_roi')
        self.assertEqual(profile.trang_thai, 'chua_co_anh')
        self.assertEqual(invoice.trang_thai, 'chua_thanh_toan')
        history = LichSuHopDong.objects.get(hanh_dong='gia_han')
        self.assertEqual(history.nguoi_thuc_hien, self.admin)
        self.assertIn(renewal.ngay_ket_thuc_cu.strftime('%d/%m/%Y'), history.noi_dung)
        self.assertIn(renewal.ngay_ket_thuc_de_xuat.strftime('%d/%m/%Y'), history.noi_dung)
        audit = NhatKyThaoTac.objects.get()
        self.assertEqual(audit.du_lieu_cu['ngay_ket_thuc'], str(renewal.ngay_ket_thuc_cu))
        effects = self.effects()
        self.process(renewal)
        self.assertEqual(self.effects(), effects)
        self.hd.refresh_from_db(); renewal.refresh_from_db()
        self.assertEqual(self.hd.ngay_ket_thuc, renewal.ngay_ket_thuc_de_xuat)
        self.assertEqual(renewal.trang_thai, 'da_duyet')
        self.assertEqual(renewal.nguoi_xu_ly, self.admin)
        self.assertIsNotNone(renewal.ngay_xu_ly)
        self.assertEqual(NguoiOCungPhong.objects.count(), 2)

    def test_reject_twice_and_approve_after_reject(self):
        renewal = self.renewal()
        permission = self.permission(ngay_ket_thuc=self.hd.ngay_ket_thuc)
        before = self.hd.ngay_ket_thuc
        self.process(renewal, 'tu_choi')
        effects = self.effects()
        self.process(renewal, 'tu_choi'); self.process(renewal)
        self.assertEqual(self.effects(), effects)
        renewal.refresh_from_db(); self.hd.refresh_from_db(); permission.refresh_from_db()
        self.assertEqual(renewal.trang_thai, 'tu_choi')
        self.assertEqual(self.hd.ngay_ket_thuc, before)
        self.assertEqual(permission.ngay_ket_thuc, before)
        self.assertEqual(ThongBao.objects.get().nguoi_thue, self.tenant)

    def test_processed_request_cannot_cancel_or_reject(self):
        renewal = self.renewal()
        self.process(renewal)
        effects = self.effects()
        self.post(views.huy_yeu_cau_gia_han, renewal, {})
        self.process(renewal, 'tu_choi')
        self.assertEqual(self.effects(), effects)
        renewal.refresh_from_db()
        self.assertEqual(renewal.trang_thai, 'da_duyet')

    def test_bound_active_and_locked_access_extend_without_unlock(self):
        renewal = self.renewal()
        active = self.resident(self.hd)
        rights = [self.permission(ngay_ket_thuc=self.hd.ngay_ket_thuc, trang_thai=state)
                  for state in ['hoat_dong', 'tam_khoa']]
        rights.append(self.permission(nguoi_thue=None, nguoi_o_cung=active,
                      loai_quyen='nguoi_o_cung', ngay_ket_thuc=self.hd.ngay_ket_thuc))
        self.process(renewal)
        for right in rights:
            state = right.trang_thai
            right.refresh_from_db()
            self.assertEqual(right.ngay_ket_thuc, renewal.ngay_ket_thuc_de_xuat)
            self.assertEqual(right.trang_thai, state)
        snapshot = list(QuyenRaVao.objects.values())
        self.process(renewal)
        self.assertEqual(list(QuyenRaVao.objects.values()), snapshot)

    def test_unrelated_guest_manual_and_revoked_access_unchanged(self):
        renewal = self.renewal()
        other_room = Phong.objects.create(co_so=self.facility, so_phong='AUDIT-OTHER', gia_thue=1, dien_tich=1)
        for overrides in [{'phong': other_room}, {'nguoi_thue': self.other},
                          {'loai_quyen': 'khach_tam_thoi'}, {'trang_thai': 'bi_thu_hoi'},
                          {'trang_thai': 'het_han'}, {'ngay_ket_thuc': None},
                          {'ngay_ket_thuc': self.today+timedelta(days=3)}]:
            data = {'ngay_ket_thuc': self.hd.ngay_ket_thuc}; data.update(overrides)
            self.permission(**data)
        before = list(QuyenRaVao.objects.values())
        self.process(renewal)
        self.assertEqual(list(QuyenRaVao.objects.values()), before)

    def test_departed_resident_access_not_extended(self):
        renewal = self.renewal()
        departed = self.resident(self.hd, 'da_roi')
        right = self.permission(nguoi_thue=None, nguoi_o_cung=departed, loai_quyen='nguoi_o_cung',
                                ngay_ket_thuc=self.hd.ngay_ket_thuc)
        old_end = right.ngay_ket_thuc
        self.process(renewal)
        right.refresh_from_db(); departed.refresh_from_db()
        self.assertEqual(right.ngay_ket_thuc, old_end)
        self.assertEqual(departed.trang_thai, 'da_roi')

    def test_renewal_does_not_change_other_stay_legacy_or_manual(self):
        renewal = self.renewal()
        other_stay = self.contract()
        untouched = [
            self.permission(hop_dong=other_stay, ngay_ket_thuc=self.hd.ngay_ket_thuc),
            self.permission(hop_dong=None, nguon_cap='legacy_unknown', ngay_ket_thuc=self.hd.ngay_ket_thuc),
            self.permission(hop_dong=self.hd, nguon_cap='legacy_unknown', ngay_ket_thuc=self.hd.ngay_ket_thuc),
            self.permission(hop_dong=self.hd, nguon_cap='thu_cong', ngay_ket_thuc=self.hd.ngay_ket_thuc),
        ]
        snapshots = {q.pk: QuyenRaVao.objects.values().get(pk=q.pk) for q in untouched}
        right = self.permission(hop_dong=self.hd, trang_thai='tam_khoa', ngay_ket_thuc=self.hd.ngay_ket_thuc)
        self.process(renewal)
        right.refresh_from_db()
        self.assertEqual(right.ngay_ket_thuc, renewal.ngay_ket_thuc_de_xuat)
        self.assertEqual(right.trang_thai, 'tam_khoa')
        for pk, before in snapshots.items():
            self.assertEqual(QuyenRaVao.objects.values().get(pk=pk), before)

    def test_renewed_tenant_and_roommate_can_access_after_old_end(self):
        renewal = self.renewal()
        active = self.resident(self.hd)
        self.permission(ngay_ket_thuc=self.hd.ngay_ket_thuc)
        self.permission(nguoi_thue=None, nguoi_o_cung=active, loai_quyen='nguoi_o_cung',
                        ngay_ket_thuc=self.hd.ngay_ket_thuc)
        self.process(renewal)
        after_old_end = timezone.make_aware(datetime.combine(
            renewal.ngay_ket_thuc_cu+timedelta(days=1), time(12)))
        for fields in [dict(nguoi_thue=self.tenant, loai_chu_the='nguoi_thue'),
                       dict(nguoi_o_cung=active, loai_chu_the='nguoi_o_cung')]:
            profile = FaceProfile.objects.create(**fields, trang_thai='da_xac_thuc',
                                                  face_encoding='audit-vector')
            with patch('django.utils.timezone.now', return_value=after_old_end):
                self.assertEqual(access_tests.AccessTests.recognize(self)['access'], 'granted')
            profile.delete()

    def test_request_on_30_day_and_final_day_boundaries(self):
        for days in [30, 0]:
            with self.subTest(days=days):
                self.hd.ngay_ket_thuc = self.today+timedelta(days=days); self.hd.save()
                self.post(views.gui_yeu_cau_gia_han, self.hd, {'so_thang_gia_han': '1'})
                renewal = YeuCauGiaHanHopDong.objects.get(trang_thai='cho_duyet')
                self.assertGreater(renewal.ngay_ket_thuc_de_xuat, self.hd.ngay_ket_thuc)
                self.post(views.huy_yeu_cau_gia_han, renewal, {})

    def test_approval_transaction_rolls_back_on_notification_failure(self):
        renewal = self.renewal()
        right = self.permission(ngay_ket_thuc=self.hd.ngay_ket_thuc)
        before = self.hd.ngay_ket_thuc
        with patch('core.views_hop_dong.ThongBao.objects.create', side_effect=RuntimeError('audit rollback')):
            with self.assertRaisesRegex(RuntimeError, 'audit rollback'):
                self.process(renewal)
        renewal.refresh_from_db(); self.hd.refresh_from_db(); right.refresh_from_db()
        self.assertEqual(renewal.trang_thai, 'cho_duyet')
        self.assertEqual(self.hd.ngay_ket_thuc, before)
        self.assertEqual(right.ngay_ket_thuc, before)
        self.assertEqual(self.effects(), (0, 0, 0, 0))

    def test_reject_requires_reason(self):
        renewal = self.renewal()
        self.post(views.xu_ly_yeu_cau_gia_han, renewal,
                  {'hanh_dong': 'tu_choi'}, self.admin)
        renewal.refresh_from_db()
        self.assertEqual(renewal.trang_thai, 'cho_duyet')
        self.assertEqual(self.effects(), (0, 0, 0, 0))
