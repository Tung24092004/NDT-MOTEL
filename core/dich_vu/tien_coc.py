"""Deposit attempts and guarded state transitions, separate from monthly invoices."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import DatPhong, NhatKyThaoTac, Phong, ThanhToanCocDatPhong
from .dat_phong import require_tenant


def locked_booking(booking_id):
    room_id = DatPhong.objects.values_list('phong_id', flat=True).get(pk=booking_id)
    Phong.objects.select_for_update().get(pk=room_id)
    return DatPhong.objects.select_for_update().select_related('nguoi_thue').get(pk=booking_id)


def require_open(booking, allow_expired_report=False):
    if booking.trang_thai not in ('cho_duyet', 'da_duyet'):
        raise ValidationError('Don da huy/tu choi khong duoc giao dich coc.')
    if not booking.da_dong_y_dieu_khoan or not booking.noi_dung_dieu_khoan_snapshot.strip() or not booking.thoi_diem_dong_y_dieu_khoan or booking.ty_le_hoan_coc_snapshot is None or booking.gia_thue_thang_tai_thoi_diem_dat is None:
        raise ValidationError('Don chua hoan tat snapshot/dong y dieu khoan.')
    if not allow_expired_report and booking.han_thanh_toan_coc and booking.han_thanh_toan_coc <= timezone.now():
        raise ValidationError('Da het han thanh toan coc.')


def require_admin(actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not (actor.is_staff or actor.is_superuser):
        raise PermissionDenied('Chi Admin duoc doi soat coc.')


def audit(actor, payment, old, new):
    NhatKyThaoTac.objects.create(nguoi_thuc_hien=actor, hanh_dong='cap_nhat',
        module='Coc dat phong', doi_tuong='ThanhToanCocDatPhong', doi_tuong_id=payment.pk,
        tieu_de=f'{payment.ma_tham_chieu}: {old} -> {new}',
        du_lieu_cu={'trang_thai': old}, du_lieu_moi={'trang_thai': new, 'so_tien': str(payment.so_tien)})


@transaction.atomic
def get_or_create_deposit(*, actor, booking_id):
    booking = locked_booking(booking_id)
    require_tenant(actor, booking.nguoi_thue)
    payment = ThanhToanCocDatPhong.objects.select_for_update().filter(dat_phong=booking, active_slot=1).first()
    require_open(booking, allow_expired_report=bool(payment and payment.trang_thai in ('cho_xac_nhan', 'da_xac_nhan')))
    if payment:
        return payment
    # No client amount parameter: the persisted snapshot is the sole amount source.
    return ThanhToanCocDatPhong.objects.create(dat_phong=booking, so_tien=booking.tien_coc_du_kien)


@transaction.atomic
def report_paid(*, actor, payment_id, bank_transaction=''):
    initial = ThanhToanCocDatPhong.objects.get(pk=payment_id)
    booking = locked_booking(initial.dat_phong_id)
    require_tenant(actor, booking.nguoi_thue)
    payment = ThanhToanCocDatPhong.objects.select_for_update().get(pk=payment_id)
    require_open(booking, allow_expired_report=payment.trang_thai == 'cho_xac_nhan')
    if payment.trang_thai == 'cho_xac_nhan':
        return payment
    if payment.trang_thai != 'chua_thanh_toan':
        raise ValidationError('Giao dich khong cho phep bao thanh toan.')
    payment.trang_thai = 'cho_xac_nhan'
    payment.thoi_diem_user_bao_da_thanh_toan = timezone.now()
    payment.ma_giao_dich = bank_transaction
    payment.save()
    audit(actor, payment, 'chua_thanh_toan', 'cho_xac_nhan')
    return payment


@transaction.atomic
def confirm_deposit(*, actor, payment_id):
    require_admin(actor)
    initial = ThanhToanCocDatPhong.objects.get(pk=payment_id)
    booking = locked_booking(initial.dat_phong_id)
    require_open(booking, allow_expired_report=True)
    payment = ThanhToanCocDatPhong.objects.select_for_update().get(pk=payment_id)
    if payment.trang_thai != 'cho_xac_nhan':
        raise ValidationError('Chi xac nhan giao dich cho doi soat, khong xac nhan hai lan.')
    payment.trang_thai = 'da_xac_nhan'
    payment.thoi_diem_admin_xac_nhan = timezone.now()
    payment.nguoi_xac_nhan = actor
    payment.save()
    audit(actor, payment, 'cho_xac_nhan', 'da_xac_nhan')
    return payment


@transaction.atomic
def reject_deposit(*, actor, payment_id, reason):
    require_admin(actor)
    initial = ThanhToanCocDatPhong.objects.get(pk=payment_id)
    booking = locked_booking(initial.dat_phong_id)
    require_open(booking, allow_expired_report=True)
    payment = ThanhToanCocDatPhong.objects.select_for_update().get(pk=payment_id)
    if payment.trang_thai != 'cho_xac_nhan' or not reason.strip():
        raise ValidationError('Can giao dich cho doi soat va ly do tu choi.')
    payment.trang_thai = 'tu_choi'
    payment.ly_do_tu_choi = reason
    payment.save()
    audit(actor, payment, 'cho_xac_nhan', 'tu_choi')
    return payment


def vietqr_data(payment):
    bank = getattr(settings, 'BOOKING_DEPOSIT_BANK_CODE', '')
    account = getattr(settings, 'BOOKING_DEPOSIT_BANK_ACCOUNT', '')
    name = getattr(settings, 'BOOKING_DEPOSIT_ACCOUNT_NAME', '')
    if not bank or not account or not name:
        raise ValidationError('Chua cau hinh tai khoan nhan coc tai backend.')
    return {'bank_code': bank, 'account_number': account, 'account_name': name,
            'bank_name': getattr(settings, 'BOOKING_DEPOSIT_BANK_NAME', bank),
            'amount': int(payment.so_tien), 'add_info': payment.noi_dung_chuyen_khoan,
            'reference': payment.ma_tham_chieu}
