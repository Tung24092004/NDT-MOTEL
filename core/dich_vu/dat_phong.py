"""Booking foundation without contract, resident or access side effects."""
import calendar
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import DatPhong, KhaiBaoNguoiOCungDatPhong, NguoiThue, Phong


def require_tenant(actor, tenant):
    if not actor or not actor.is_authenticated or not actor.is_active or actor.is_staff or actor.is_superuser:
        raise PermissionDenied('Chi User thue phong duoc thao tac.')
    if not tenant.dang_hoat_dong or tenant.tai_khoan_id != actor.pk:
        raise PermissionDenied('Ho so nguoi thue khong thuoc tai khoan.')


def calculate_checkout(checkin, months):
    if type(months) is not int or not 1 <= months <= 36:
        raise ValidationError('So thang thue phai tu 1 den 36.')
    total = checkin.year * 12 + checkin.month - 1 + months
    year, month = total // 12, total % 12 + 1
    last = calendar.monthrange(year, month)[1]
    target = checkin.replace(year=year, month=month, day=min(checkin.day, last))
    return target - timedelta(days=1) if checkin.day <= last else target


def room_has_hold(room, now=None):
    now = now or timezone.now()
    pending = Q(trang_thai='cho_duyet') & (
        Q(han_thanh_toan_coc__isnull=True) | Q(han_thanh_toan_coc__gt=now)
        | Q(giao_dich_coc__trang_thai__in=('cho_xac_nhan', 'da_xac_nhan'))
    )
    approved = Q(trang_thai='da_duyet') & (
        Q(hop_dong__isnull=True)
        | Q(hop_dong__trang_thai__in=('cho_hieu_luc', 'dang_hieu_luc', 'sap_het_han'))
    )
    return DatPhong.objects.filter(phong=room).filter(pending | approved).exists()


def hold_deadline(now=None):
    hours = getattr(settings, 'BOOKING_DEPOSIT_HOLD_HOURS', 24)
    if type(hours) is not int or hours < 1:
        raise ValidationError('BOOKING_DEPOSIT_HOLD_HOURS phai la so nguyen duong.')
    return (now or timezone.now()) + timedelta(hours=hours)


def terms_policy():
    text = getattr(settings, 'BOOKING_TERMS_TEXT', '')
    rate = getattr(settings, 'BOOKING_REFUND_PERCENT', None)
    if not isinstance(text, str) or not text.strip() or rate is None:
        raise ValidationError('Chua cau hinh dieu khoan/ty le hoan coc tai backend.')
    try:
        rate = Decimal(str(rate))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Ty le hoan coc khong hop le.') from exc
    if not rate.is_finite() or not 0 <= rate <= 100 or rate != rate.quantize(Decimal('.01')):
        raise ValidationError('Ty le hoan coc phai tu 0 den 100, toi da 2 so le.')
    return text, rate


@transaction.atomic
def create_booking(*, actor, room_id, checkin, months, people=1,
                   companions=(), accept_terms=False, allow_sharing=False, note=''):
    if not actor or not actor.is_authenticated or not actor.is_active or actor.is_staff or actor.is_superuser:
        raise PermissionDenied('Chi User thue phong duoc dat phong.')
    # The room lock serializes holds created through this service and existing writers.
    room = Phong.objects.select_for_update().select_related('co_so').get(pk=room_id)
    tenant = NguoiThue.objects.select_for_update().filter(tai_khoan=actor).first()
    if tenant is None:
        raise PermissionDenied('Tai khoan chua co ho so thue.')
    require_tenant(actor, tenant)
    if checkin < timezone.localdate():
        raise ValidationError('Ngay nhan phong khong o qua khu.')
    checkout = calculate_checkout(checkin, months)
    if type(people) is not int or not 1 <= people <= room.so_nguoi_toi_da:
        raise ValidationError('So nguoi vuot suc chua hoac khong duong.')
    if len(companions) + 1 != people:
        raise ValidationError('Phai khai bao du nguoi di cung, khong tinh nguoi thue chinh hai lan.')
    if accept_terms is not True or type(allow_sharing) is not bool:
        raise ValidationError('Can dong y dieu khoan va nhu cau ghep hop le.')
    text, rate = terms_policy()
    if room.co_so.trang_thai != 'hoat_dong' or room.trang_thai == 'bao_tri' or room.trang_thai_nghiep_vu() != 'trong' or room_has_hold(room):
        raise ValidationError('Phong khong kha dung hoac da co don giu cho.')
    booking = DatPhong(
        nguoi_thue=tenant, phong=room, ngay_nhan_phong=checkin,
        so_thang_thue=months, ngay_tra_du_kien=checkout, so_nguoi_o=people,
        dong_y_nhan_yeu_cau_ghep=allow_sharing,
        gia_thue_thang_tai_thoi_diem_dat=room.gia_thue,
        tien_coc_du_kien=room.tien_coc_mac_dinh,
        da_dong_y_dieu_khoan=True, thoi_diem_dong_y_dieu_khoan=timezone.now(),
        noi_dung_dieu_khoan_snapshot=text, ty_le_hoan_coc_snapshot=rate,
        han_thanh_toan_coc=hold_deadline(), ghi_chu=note,
    )
    booking.full_clean()
    booking.save()
    allowed = {'ho_ten', 'ngay_sinh', 'gioi_tinh', 'cccd', 'so_dien_thoai', 'email', 'quan_he', 'ghi_chu'}
    for data in companions:
        if set(data) - allowed:
            raise ValidationError('Du lieu nguoi khai bao chua field khong duoc phep.')
        KhaiBaoNguoiOCungDatPhong.objects.create(dat_phong=booking, **data)
    return booking


@transaction.atomic
def cancel_booking(*, actor, booking_id, reason):
    from core.models import HopDong, NhatKyThaoTac, ThanhToanCocDatPhong, ThongBao
    from .tien_coc import locked_booking

    booking = locked_booking(booking_id)
    require_tenant(actor, booking.nguoi_thue)
    if not reason or len(reason) > 2000:
        raise ValidationError('Vui lòng nhập lý do hủy (tối đa 2000 ký tự).')
    if booking.trang_thai != 'cho_duyet' or HopDong.objects.filter(dat_phong=booking).exists():
        raise ValidationError('Đơn đã xử lý/phát sinh hợp đồng không thể tự hủy.')
    payments = list(ThanhToanCocDatPhong.objects.select_for_update().filter(dat_phong=booking))
    if any(p.trang_thai in ('cho_xac_nhan', 'da_xac_nhan', 'da_hoan_tien') for p in payments):
        from .thong_bao_dat_phong import notify_admins
        marker = f'BOOKING_CANCEL_REQUEST:{booking.pk}'
        if not ThongBao.objects.filter(nguoi_thue=booking.nguoi_thue, ma_tham_chieu=marker).exists():
            ThongBao.objects.create(nguoi_thue=booking.nguoi_thue, loai='dat_phong',
                ma_tham_chieu=marker, tieu_de='Đã gửi yêu cầu xử lý hủy',
                noi_dung=f'{booking.ma_yeu_cau}: chờ quản lý đối soát; không tự hoàn tiền. Lý do: {reason}')
            notify_admins(booking=booking, event='CANCEL_REQUEST', title='Yêu cầu xử lý hủy và cọc',
                text=f'{booking.ma_yeu_cau}: {reason}. Áp dụng điều khoản snapshot; không tự hoàn tiền.')
            NhatKyThaoTac.objects.create(nguoi_thuc_hien=actor, hanh_dong='khac', module='Dat phong',
                doi_tuong='DatPhong', doi_tuong_id=booking.pk, tieu_de='Yêu cầu quản lý xử lý hủy', noi_dung=reason)
        return booking
    for payment in payments:
        if payment.trang_thai == 'chua_thanh_toan':
            payment.trang_thai = 'da_huy'
            payment.save()
    booking.trang_thai = 'da_huy'
    booking.save(update_fields=['trang_thai'])
    booking.nguoi_di_cung_khai_bao.filter(trang_thai_xac_minh__in=('cho_xac_minh', 'da_xac_minh')).update(
        trang_thai_xac_minh='da_huy', ngay_cap_nhat=timezone.now())
    NhatKyThaoTac.objects.create(nguoi_thuc_hien=actor, hanh_dong='huy', module='Dat phong',
        doi_tuong='DatPhong', doi_tuong_id=booking.pk, tieu_de=f'Hủy {booking.ma_yeu_cau}',
        noi_dung=reason, du_lieu_cu={'trang_thai': 'cho_duyet'}, du_lieu_moi={'trang_thai': 'da_huy'})
    ThongBao.objects.create(nguoi_thue=booking.nguoi_thue, loai='dat_phong',
        tieu_de='Đã hủy yêu cầu đặt phòng', noi_dung=f'{booking.ma_yeu_cau}. Lý do: {reason}')
    return booking
