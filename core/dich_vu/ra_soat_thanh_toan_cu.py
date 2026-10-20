"""Append-only review of legacy paid invoices; never reconstructs payment events."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from core.models import HoaDon, LichSuThanhToan, NhatKyThaoTac, RaSoatThanhToanHoaDonCu


def missing_paid_provenance(invoice):
    missing = []
    if not invoice.ngay_thanh_toan: missing.append('payment_date')
    if not invoice.phuong_thuc: missing.append('payment_method')
    if not invoice.ma_giao_dich: missing.append('transaction_reference')
    if not invoice.nguoi_xac_nhan_id: missing.append('admin_confirmer')
    if not invoice.ma_giao_dich or not LichSuThanhToan.objects.filter(hoa_don=invoice, ma_giao_dich=invoice.ma_giao_dich).exists():
        missing.append('payment_history')
    return missing


def _require_admin(actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not (actor.is_staff or actor.is_superuser):
        raise PermissionDenied('Chi Admin duoc ra soat thanh toan cu.')


@transaction.atomic
def reconcile_legacy_paid_invoice(*, actor, invoice_id, evidence_grade, note):
    _require_admin(actor)
    invoice = HoaDon.objects.select_for_update().get(pk=invoice_id)
    missing = missing_paid_provenance(invoice)
    if invoice.trang_thai != 'da_thanh_toan' or not missing:
        raise ValidationError('Chi hoa don da thanh toan nhung thieu provenance canonical moi duoc ra soat.')
    if evidence_grade not in dict(RaSoatThanhToanHoaDonCu.MUC_DO_BANG_CHUNG):
        raise ValidationError({'muc_do_bang_chung': 'Muc do bang chung khong hop le.'})
    if not (note or '').strip():
        raise ValidationError({'ghi_chu_ra_soat': 'Can ghi chu ra soat.'})
    if RaSoatThanhToanHoaDonCu.objects.select_for_update().filter(hoa_don=invoice).exists():
        raise ValidationError('Hoa don da duoc ra soat.')
    try:
        with transaction.atomic():
            review = RaSoatThanhToanHoaDonCu.objects.create(hoa_don=invoice, muc_do_bang_chung=evidence_grade,
                truong_canonical_con_thieu=missing, ghi_chu_ra_soat=note.strip(), nguoi_ra_soat=actor)
    except IntegrityError as exc:
        raise ValidationError('Hoa don da duoc ra soat.') from exc
    NhatKyThaoTac.objects.create(nguoi_thuc_hien=actor, hanh_dong='khac', module='Ra soat thanh toan cu',
        doi_tuong='RaSoatThanhToanHoaDonCu', doi_tuong_id=review.pk,
        tieu_de=f'Ra soat du lieu thanh toan cu hoa don {invoice.pk}',
        du_lieu_moi={'hoa_don_id': invoice.pk, 'muc_do_bang_chung': evidence_grade, 'truong_con_thieu': missing})
    return review
