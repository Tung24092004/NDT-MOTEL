"""Deposit attempts and guarded state transitions, separate from monthly invoices."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from decimal import Decimal, InvalidOperation

from core.models import ChungTuThanhToan, DatPhong, HopDong, NhatKyThaoTac, Phong, QuyetToanCocDatPhong, ThanhToanCocDatPhong, ThongBao
from .chung_tu_thanh_toan import mark_reviewed
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
        du_lieu_cu={'trang_thai': old}, du_lieu_moi={
            'trang_thai': new,
            'so_tien': str(payment.so_tien),
            'so_tien_thuc_nhan': str(payment.so_tien_thuc_nhan) if payment.so_tien_thuc_nhan is not None else None,
        })


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
    try:
        initial = ThanhToanCocDatPhong.objects.get(pk=payment_id)
    except ThanhToanCocDatPhong.DoesNotExist:
        raise ValidationError('Giao dich coc khong hop le.')
    booking = locked_booking(initial.dat_phong_id)
    require_tenant(actor, booking.nguoi_thue)
    payment = ThanhToanCocDatPhong.objects.select_for_update().get(pk=payment_id)
    require_open(booking, allow_expired_report=payment.trang_thai == 'cho_xac_nhan')
    if payment.trang_thai == 'cho_xac_nhan':
        return payment
    if payment.trang_thai != 'chua_thanh_toan':
        raise ValidationError('Giao dich khong cho phep bao thanh toan.')
    bank_transaction = (bank_transaction or '').strip().upper()
    if len(bank_transaction) > 100:
        raise ValidationError('Ma giao dich qua dai.')
    if bank_transaction and ThanhToanCocDatPhong.objects.filter(
        ma_giao_dich=bank_transaction,
        trang_thai='da_xac_nhan',
    ).exclude(pk=payment.pk).exists():
        raise ValidationError('Ma giao dich da duoc xac nhan cho khoan coc khac.')
    payment.trang_thai = 'cho_xac_nhan'
    payment.thoi_diem_user_bao_da_thanh_toan = timezone.now()
    payment.ma_giao_dich = bank_transaction
    payment.save()
    audit(actor, payment, 'chua_thanh_toan', 'cho_xac_nhan')
    return payment


@transaction.atomic
def confirm_deposit(*, actor, payment_id, actual_amount, booking_id=None):
    require_admin(actor)
    try:
        payment_id = int(payment_id)
    except (TypeError, ValueError):
        raise ValidationError('Giao dich coc khong hop le.')
    try:
        initial = ThanhToanCocDatPhong.objects.get(pk=payment_id)
    except ThanhToanCocDatPhong.DoesNotExist:
        raise ValidationError('Giao dich coc khong hop le.')
    if booking_id is not None and initial.dat_phong_id != booking_id:
        raise ValidationError('Giao dich coc khong thuoc yeu cau dat phong nay.')
    booking = locked_booking(initial.dat_phong_id)
    require_open(booking, allow_expired_report=True)
    payment = ThanhToanCocDatPhong.objects.select_for_update().get(pk=payment_id)
    if payment.trang_thai != 'cho_xac_nhan':
        raise ValidationError('Chi xac nhan giao dich cho doi soat, khong xac nhan hai lan.')
    try:
        actual_amount = int(str(actual_amount).strip())
    except (TypeError, ValueError):
        raise ValidationError({'so_tien_thuc_nhan': 'Nhap so tien thuc nhan hop le.'})
    if actual_amount <= 0:
        raise ValidationError({'so_tien_thuc_nhan': 'So tien thuc nhan phai lon hon 0.'})
    evidence = ChungTuThanhToan.objects.select_for_update().filter(
        giao_dich_coc=payment,
        trang_thai='cho_doi_soat',
        ma_doi_chieu=payment.ma_tham_chieu,
    ).first()
    if not evidence:
        raise ValidationError('Can chung tu hop le dang cho doi soat truoc khi xac nhan.')
    payment.trang_thai = 'da_xac_nhan'
    payment.thoi_diem_admin_xac_nhan = timezone.now()
    payment.nguoi_xac_nhan = actor
    payment.so_tien_thuc_nhan = actual_amount
    payment.save()
    mark_reviewed(evidence, accepted=True, reviewer=actor)
    audit(actor, payment, 'cho_xac_nhan', 'da_xac_nhan')
    ThongBao.objects.get_or_create(
        nguoi_thue=booking.nguoi_thue,
        ma_tham_chieu=f'BOOKING:{booking.pk}:DEPOSIT_CONFIRMED:{payment.pk}',
        defaults={
            'loai': 'dat_phong', 'muc_do': 'quan_trong',
            'tieu_de': 'Tien coc da duoc xac nhan',
            'noi_dung': f'{booking.ma_yeu_cau}: Admin da xac nhan tien coc.',
            'url_lien_ket': f'/dat-phong-cua-toi/{booking.pk}/thanh-toan-coc/',
        },
    )
    return payment


@transaction.atomic
def reject_deposit(*, actor, payment_id, reason, booking_id=None):
    require_admin(actor)
    try:
        payment_id = int(payment_id)
    except (TypeError, ValueError):
        raise ValidationError('Giao dich coc khong hop le.')
    try:
        initial = ThanhToanCocDatPhong.objects.get(pk=payment_id)
    except ThanhToanCocDatPhong.DoesNotExist:
        raise ValidationError('Giao dich coc khong hop le.')
    if booking_id is not None and initial.dat_phong_id != booking_id:
        raise ValidationError('Giao dich coc khong thuoc yeu cau dat phong nay.')
    booking = locked_booking(initial.dat_phong_id)
    require_open(booking, allow_expired_report=True)
    payment = ThanhToanCocDatPhong.objects.select_for_update().get(pk=payment_id)
    reason = (reason or '').strip()
    if payment.trang_thai != 'cho_xac_nhan' or not reason:
        raise ValidationError('Can giao dich cho doi soat va ly do tu choi.')
    payment.trang_thai = 'tu_choi'
    payment.ly_do_tu_choi = reason
    payment.save()
    evidence = ChungTuThanhToan.objects.select_for_update().filter(giao_dich_coc=payment).first()
    if evidence:
        mark_reviewed(evidence, accepted=False, reviewer=actor, note=reason)
    audit(actor, payment, 'cho_xac_nhan', 'tu_choi')
    ThongBao.objects.get_or_create(
        nguoi_thue=booking.nguoi_thue,
        ma_tham_chieu=f'BOOKING:{booking.pk}:DEPOSIT_REJECTED:{payment.pk}',
        defaults={
            'loai': 'dat_phong', 'muc_do': 'quan_trong',
            'tieu_de': 'Giao dich coc bi tu choi',
            'noi_dung': f'{booking.ma_yeu_cau}: {reason}',
            'url_lien_ket': f'/dat-phong-cua-toi/{booking.pk}/thanh-toan-coc/',
        },
    )
    return payment


@transaction.atomic
def settle_confirmed_deposit(*, actor, payment_id, outcome, amount, reason):
    """Record one final external settlement without changing receipt facts."""
    require_admin(actor)
    try:
        initial = ThanhToanCocDatPhong.objects.get(pk=int(payment_id))
    except (TypeError, ValueError, ThanhToanCocDatPhong.DoesNotExist):
        raise ValidationError('Giao dich coc khong hop le.')

    # Match contract closure order: room, booking, contract, then deposit.
    booking = locked_booking(initial.dat_phong_id)
    contract = HopDong.objects.select_for_update().filter(dat_phong=booking).first()
    payment = ThanhToanCocDatPhong.objects.select_for_update().get(pk=initial.pk)
    if payment.trang_thai != 'da_xac_nhan' or not payment.so_tien_thuc_nhan or payment.so_tien_thuc_nhan <= 0:
        raise ValidationError('Chi giao dich coc da xac nhan voi so tien thuc nhan duong moi duoc quyet toan.')
    lifecycle_closed = (
        contract is not None and contract.trang_thai in ('da_huy', 'da_het_han')
    ) or (contract is None and booking.trang_thai == 'da_huy')
    if not lifecycle_closed:
        raise ValidationError('Chi duoc quyet toan sau khi dat phong/hop dong da ket thuc.')
    outcome = (outcome or '').strip()
    if outcome not in dict(QuyetToanCocDatPhong.KET_QUA):
        raise ValidationError({'ket_qua': 'Ket qua quyet toan khong hop le.'})
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError({'ly_do': 'Can ghi ro ly do quyet toan.'})
    try:
        amount = Decimal(str(amount).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({'so_tien': 'So tien quyet toan khong hop le.'})
    if amount != amount.to_integral_value() or amount <= 0 or amount > payment.so_tien_thuc_nhan:
        raise ValidationError({'so_tien': 'So tien quyet toan phai duong va khong vuot so tien thuc nhan.'})
    if QuyetToanCocDatPhong.objects.select_for_update().filter(giao_dich_coc=payment).exists():
        raise ValidationError('Giao dich coc da duoc quyet toan.')
    try:
        with transaction.atomic():
            settlement = QuyetToanCocDatPhong.objects.create(
                giao_dich_coc=payment, ket_qua=outcome, so_tien=amount,
                nguoi_quyet_toan=actor, ly_do=reason,
            )
    except IntegrityError as exc:
        # The one-to-one database constraint is the final concurrent-submission guard.
        if QuyetToanCocDatPhong.objects.filter(giao_dich_coc=payment).exists():
            raise ValidationError('Giao dich coc da duoc quyet toan.') from exc
        raise
    old_status = payment.trang_thai
    if outcome == 'hoan_tien':
        payment.trang_thai = 'da_hoan_tien'
        payment.save()
    NhatKyThaoTac.objects.create(
        nguoi_thuc_hien=actor, hanh_dong='cap_nhat', module='Quyet toan coc dat phong',
        doi_tuong='QuyetToanCocDatPhong', doi_tuong_id=settlement.pk,
        tieu_de=f'{payment.ma_tham_chieu}: {outcome}',
        du_lieu_cu={'trang_thai': old_status},
        du_lieu_moi={'ket_qua': outcome, 'so_tien': str(amount), 'giao_dich_coc_id': payment.pk},
    )
    return settlement


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
