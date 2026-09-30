"""Read-only legacy diagnostics: counts and record IDs only; never repair data."""
from django.core.management.base import BaseCommand
from django.db.models import Count

from core.quy_tac_nghiep_vu import contract_is_current, permission_binding_is_valid, eligible_permissions
from core.models import Phong, HopDong, NguoiOCungPhong, QuyenRaVao, HoaDon, LichSuThanhToan
from django.utils import timezone


class Command(BaseCommand):
    help = 'Read-only integrity diagnostics (no --fix; no personal information).'

    def handle(self, *args, **options):
        def report(label, ids):
            ids = list(ids)
            self.stdout.write(f'{label}: count={len(ids)} ids={ids}')

        report('resident_inactive_contract', (
            r.pk for r in NguoiOCungPhong.objects.filter(trang_thai='dang_o')
            .select_related('hop_dong__dat_phong') if not contract_is_current(r.hop_dong)
        ))
        report('room_stored_derived_mismatch', (
            r.pk for r in Phong.objects.all() if r.trang_thai != r.trang_thai_nghiep_vu()
        ))
        today = timezone.localdate()
        current = HopDong.objects.filter(
            trang_thai__in=['dang_hieu_luc', 'sap_het_han'],
            dat_phong__trang_thai='da_duyet', ngay_bat_dau__lte=today, ngay_ket_thuc__gte=today)
        report('multiple_current_contracts_room', current.order_by().values('dat_phong__phong_id')
            .annotate(n=Count('pk')).filter(n__gt=1).values_list('dat_phong__phong_id', flat=True))

        legacy, invalid_type, invalid_binding, ambiguous, invalid_active = [], [], [], [], []
        eligible = set(eligible_permissions(QuyenRaVao.objects.all()).values_list('pk', flat=True))
        for right in QuyenRaVao.objects.select_related('hop_dong__dat_phong', 'nguoi_o_cung'):
            unbound = not right.hop_dong_id or right.nguon_cap == 'legacy_unknown'
            if unbound:
                legacy.append(right.pk)
                if right.nguoi_thue_id and HopDong.objects.filter(
                    dat_phong__phong_id=right.phong_id,
                    dat_phong__nguoi_thue_id=right.nguoi_thue_id,
                ).count() > 1:
                    ambiguous.append(right.pk)
            if not (
                (right.loai_quyen == 'chu_phong' and right.nguoi_thue_id and not right.nguoi_o_cung_id)
                or (right.loai_quyen == 'nguoi_o_cung' and right.nguoi_o_cung_id and not right.nguoi_thue_id)
            ):
                invalid_type.append(right.pk)
            if not unbound and not permission_binding_is_valid(right):
                invalid_binding.append(right.pk)
            if right.trang_thai == 'hoat_dong' and right.pk not in eligible:
                invalid_active.append(right.pk)
        report('legacy_null_or_unknown', legacy)
        report('permission_invalid_subject_type', invalid_type)
        report('permission_invalid_binding', invalid_binding)
        report('unbound_multiple_contract_candidates', ambiguous)
        report('active_permission_invalid_relationship', invalid_active)
        report('permission_authorizable', sorted(eligible))

        report('paid_invoice_missing_metadata', (
            invoice.pk for invoice in HoaDon.objects.filter(trang_thai='da_thanh_toan')
            if not (invoice.ngay_thanh_toan and invoice.ma_giao_dich and invoice.nguoi_xac_nhan_id
                and LichSuThanhToan.objects.filter(hoa_don=invoice, ma_giao_dich=invoice.ma_giao_dich).exists())
        ))
        report('pending_invoice_has_settlement_metadata', (
            invoice.pk for invoice in HoaDon.objects.filter(trang_thai='cho_xac_nhan')
            if invoice.ngay_thanh_toan or invoice.ma_giao_dich or invoice.nguoi_xac_nhan_id
        ))
