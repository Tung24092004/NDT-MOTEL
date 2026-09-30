"""Tenant-only booking UI; all financial writers delegate to phase4 services."""
from functools import wraps
from urllib.parse import urlencode, quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import DatPhong, NguoiThue, NhatKyThaoTac, Phong, ThongBao
from .bieu_mau_dat_phong import BookingForm, CompanionFormSet
from .dich_vu import dat_phong as dich_vu_dat_phong, tien_coc
from .dich_vu.thong_bao_dat_phong import notify_admins


def tenant_only(view):
    @login_required(login_url='dang_nhap')
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard_admin')
        tenant = NguoiThue.objects.filter(tai_khoan=request.user, dang_hoat_dong=True).first()
        if tenant is None:
            messages.error(request, 'Vui lòng cập nhật hồ sơ người thuê.')
            return redirect('cap_nhat_thong_tin')
        request.booking_tenant = tenant
        return view(request, *args, **kwargs)
    return guarded


def own_booking(request, id):
    return get_object_or_404(DatPhong.objects.select_related('phong__co_so', 'nguoi_thue', 'hop_dong')
                             .prefetch_related('giao_dich_coc', 'nguoi_di_cung_khai_bao'),
                             pk=id, nguoi_thue=request.booking_tenant)


def payment_state(booking):
    attempts = list(booking.giao_dich_coc.all())
    payment = next((p for p in attempts if p.active_slot == 1), None)
    latest = payment or max(attempts, key=lambda p: p.pk, default=None)
    expired = bool(booking.han_thanh_toan_coc and booking.han_thanh_toan_coc <= timezone.now()
                   and not (payment and payment.trang_thai in ('cho_xac_nhan', 'da_xac_nhan')))
    snapshot = bool(booking.da_dong_y_dieu_khoan and booking.gia_thue_thang_tai_thoi_diem_dat is not None)
    status = latest.trang_thai if latest else 'legacy'
    labels = {'chua_thanh_toan': 'Chờ thanh toán', 'cho_xac_nhan': 'Chờ quản lý xác nhận',
              'da_xac_nhan': 'Đã xác nhận cọc', 'tu_choi': 'Cọc bị từ chối', 'da_huy': 'Đã hủy giao dịch',
              'da_hoan_tien': 'Đã hoàn tiền', 'legacy': 'Đơn cũ - chưa có giao dịch cọc'}
    contract = getattr(booking, 'hop_dong', None)
    can_cancel = booking.trang_thai == 'cho_duyet' and not contract and not any(
        p.trang_thai in ('cho_xac_nhan', 'da_xac_nhan', 'da_hoan_tien') for p in attempts)
    can_pay = booking.trang_thai == 'cho_duyet' and snapshot and not expired and (
        not latest or status in ('chua_thanh_toan', 'tu_choi'))
    return {'booking': booking, 'payment': latest, 'payment_status': labels[status],
            'expired': expired, 'can_pay': can_pay,
            'can_view_qr': bool(payment and snapshot and booking.trang_thai in ('cho_duyet', 'da_duyet') and not expired),
            'can_cancel': can_cancel, 'contract': contract,
            'can_request_cancel': bool(not contract and booking.trang_thai == 'cho_duyet' and payment and payment.trang_thai in ('cho_xac_nhan', 'da_xac_nhan'))}


@tenant_only
@require_http_methods(['GET', 'POST'])
def dat_phong(request, id):
    room = get_object_or_404(Phong.objects.select_related('co_so'), pk=id)
    tenant = request.booking_tenant
    # Match existing mandatory identity rules; optional profile fields are displayed, not cloned.
    identity_valid = bool(tenant.ho_ten.strip() and len(tenant.cccd) == 12 and tenant.cccd.isascii()
                          and tenant.cccd.isdigit() and tenant.so_dien_thoai.isdigit()
                          and 9 <= len(tenant.so_dien_thoai) <= 11)
    if not identity_valid:
        messages.error(request, 'Hồ sơ cần họ tên, CCCD 12 số và số điện thoại hợp lệ trước khi đặt phòng.')
        return redirect('cap_nhat_thong_tin')
    if room.so_nguoi_toi_da < 1 or room.co_so.trang_thai != 'hoat_dong' or room.trang_thai == 'bao_tri' or room.trang_thai_nghiep_vu() != 'trong' or dich_vu_dat_phong.room_has_hold(room):
        messages.warning(request, 'Phòng không còn khả dụng hoặc chưa được cấu hình sức chứa.')
        return redirect('chi_tiet_phong', id=room.pk)
    form = BookingForm(request.POST if request.method == 'POST' else None, capacity=room.so_nguoi_toi_da)
    companions = CompanionFormSet(request.POST if request.method == 'POST' else None, prefix='companions')
    terms, refund, deadline, configuration_error = '', None, None, ''
    try:
        terms, refund = dich_vu_dat_phong.terms_policy()
        deadline = dich_vu_dat_phong.hold_deadline()
    except ValidationError:
        configuration_error = 'Chưa có chính sách đặt phòng được cấu hình. Vui lòng liên hệ quản lý.'
    if request.method == 'POST' and request.POST.get('action') == 'prepare_occupants':
        try:
            count = int(request.POST.get('so_nguoi_o', '1')) - 1
            if not 0 <= count < min(room.so_nguoi_toi_da, 101):
                raise ValueError
            fields = ('ho_ten', 'ngay_sinh', 'gioi_tinh', 'cccd', 'so_dien_thoai', 'email', 'quan_he', 'ghi_chu')
            initial = [{key: request.POST.get(f'companions-{i}-{key}', '') for key in fields} for i in range(count)]
            companions = CompanionFormSet(initial=initial, prefix='companions')
            form = BookingForm(initial=request.POST, capacity=room.so_nguoi_toi_da)
        except (TypeError, ValueError):
            form.is_valid()
            form.add_error('so_nguoi_o', 'Số người không hợp lệ hoặc vượt sức chứa.')
    elif request.method == 'POST':
        form_valid, companions_valid = form.is_valid(), companions.is_valid()
        if form_valid and companions_valid:
            data = form.cleaned_data
            occupants = [{k: v for k, v in f.cleaned_data.items() if k != 'DELETE'}
                         for f in companions.forms if f.cleaned_data and not f.cleaned_data.get('DELETE')]
            if len(occupants) + 1 != data['so_nguoi_o']:
                form.add_error('so_nguoi_o', 'Danh sách người đi cùng phải đúng số người đã chọn, không gồm người thuê chính.')
            else:
                try:
                    with transaction.atomic():
                        booking = dich_vu_dat_phong.create_booking(actor=request.user, room_id=room.pk,
                            checkin=data['ngay_nhan_phong'], months=data['so_thang_thue'],
                            people=data['so_nguoi_o'], companions=occupants,
                            accept_terms=data['da_dong_y_dieu_khoan'],
                            allow_sharing=data['dong_y_nhan_yeu_cau_ghep'], note=data['ghi_chu'])
                        tien_coc.get_or_create_deposit(actor=request.user, booking_id=booking.pk)
                        NhatKyThaoTac.objects.create(nguoi_thuc_hien=request.user, hanh_dong='tao',
                            module='Dat phong', doi_tuong='DatPhong', doi_tuong_id=booking.pk,
                            tieu_de=f'Gửi yêu cầu {booking.ma_yeu_cau}', du_lieu_moi={'so_nguoi_o': booking.so_nguoi_o})
                    return redirect('thanh_toan_coc_cua_toi', id=booking.pk)
                except ValidationError as exc:
                    form.add_error(None, exc.messages)
                except IntegrityError:
                    form.add_error(None, 'Yêu cầu vừa thay đổi. Vui lòng kiểm tra lại phòng và thử lại.')
    return render(request, 'core/tenant/booking/create.html', {'phong': room, 'nguoi_thue': tenant,
        'form': form, 'companions': companions, 'terms': terms, 'refund': refund,
        'deadline': deadline, 'configuration_error': configuration_error,
        'expected_refund': room.tien_coc_mac_dinh * refund / 100 if refund is not None else None})


@tenant_only
@require_http_methods(['GET'])
def dat_phong_cua_toi(request):
    bookings = DatPhong.objects.filter(nguoi_thue=request.booking_tenant).select_related('phong__co_so', 'hop_dong')
    bookings = bookings.prefetch_related('giao_dich_coc').order_by('-ngay_dat', '-pk')
    rows = [payment_state(booking) for booking in bookings]
    selected = request.GET.get('status', '')
    filters = {
        'unpaid': lambda r: r['can_pay'], 'pending': lambda r: r['payment'] and r['payment'].trang_thai == 'cho_xac_nhan',
        'confirmed': lambda r: r['booking'].trang_thai == 'da_duyet' or (r['payment'] and r['payment'].trang_thai == 'da_xac_nhan'),
        'rejected': lambda r: r['booking'].trang_thai == 'tu_choi' or (r['payment'] and r['payment'].trang_thai == 'tu_choi'),
        'cancelled': lambda r: r['booking'].trang_thai == 'da_huy', 'expired': lambda r: r['expired'] and r['booking'].trang_thai == 'cho_duyet',
    }
    if selected in filters:
        rows = [row for row in rows if filters[selected](row)]
    page = Paginator(rows, 20).get_page(request.GET.get('page'))
    return render(request, 'core/tenant/booking/list.html', {'rows': page, 'selected': selected})


@tenant_only
@require_http_methods(['GET'])
def chi_tiet_dat_phong_cua_toi(request, id):
    return render(request, 'core/tenant/booking/detail.html', payment_state(own_booking(request, id)))


@tenant_only
@require_http_methods(['GET', 'POST'])
def thanh_toan_coc_cua_toi(request, id):
    booking = own_booking(request, id)
    state = payment_state(booking)
    payment = state['payment']
    error, qr = '', None
    if request.method == 'POST':
        try:
            with transaction.atomic():
                if request.POST.get('action') == 'retry':
                    if not state['can_pay'] or not payment or payment.trang_thai != 'tu_choi':
                        raise ValidationError('Không thể tạo lại giao dịch ở trạng thái này.')
                    tien_coc.get_or_create_deposit(actor=request.user, booking_id=booking.pk)
                    return redirect('thanh_toan_coc_cua_toi', id=booking.pk)
                if request.POST.get('action') != 'report' or not payment or payment.active_slot != 1 or payment.phuong_thuc != 'chuyen_khoan':
                    raise ValidationError('Giao dịch không hỗ trợ hành động này.')
                # Bank configuration must be valid before accepting a payment report.
                tien_coc.vietqr_data(payment)
                locked = tien_coc.locked_booking(booking.pk)
                current = locked.giao_dich_coc.select_for_update().get(pk=payment.pk)
                first_report = current.trang_thai == 'chua_thanh_toan'
                tien_coc.report_paid(actor=request.user, payment_id=current.pk,
                                           bank_transaction=request.POST.get('ma_giao_dich', '').strip())
                if first_report:
                    ThongBao.objects.create(nguoi_thue=request.booking_tenant, loai='dat_phong',
                        tieu_de='Đã gửi báo chuyển tiền cọc', noi_dung=f'{booking.ma_yeu_cau} đang chờ quản lý đối soát.',
                        ma_tham_chieu=f'COC_REPORT:{current.pk}:TENANT')
                    notify_admins(booking=locked, event=f'DEPOSIT_REPORT:{current.pk}',
                        title='Yêu cầu đối soát cọc', text=f'{booking.ma_yeu_cau}: User báo chuyển {current.so_tien} đồng, chờ xác nhận. Mã: {current.ma_tham_chieu}.',
                        url=reverse('chi_tiet_dat_phong', args=[locked.pk]))
                messages.success(request, 'Đã gửi báo chuyển khoản. Yêu cầu đang chờ quản lý xác nhận.')
            return redirect('chi_tiet_dat_phong_cua_toi', id=booking.pk)
        except ValidationError as exc:
            error = ' '.join(exc.messages)
            booking = own_booking(request, id)
            state = payment_state(booking)
            payment = state['payment']
    try:
        if payment and payment.active_slot == 1 and state['can_view_qr'] and payment.phuong_thuc == 'chuyen_khoan':
            qr = tien_coc.vietqr_data(payment)
            qr['url'] = 'https://img.vietqr.io/image/' + quote(str(qr['bank_code']), safe='') + '-' + quote(str(qr['account_number']), safe='') + '-compact2.png?' + urlencode({'amount': qr['amount'], 'addInfo': qr['add_info'], 'accountName': qr['account_name']})
    except ValidationError:
        error = 'Chưa có thông tin ngân hàng nhận cọc. Vui lòng liên hệ quản lý; không chuyển tiền theo thông tin khác.'
    state.update(qr=qr, error=error)
    return render(request, 'core/tenant/booking/deposit_payment.html', state)


@tenant_only
@require_http_methods(['GET', 'POST'])
def huy_dat_phong_cua_toi(request, id):
    booking = own_booking(request, id)
    if request.method != 'POST':
        return redirect('chi_tiet_dat_phong_cua_toi', id=booking.pk)
    try:
        result = dich_vu_dat_phong.cancel_booking(actor=request.user, booking_id=booking.pk,
                                                reason=request.POST.get('ly_do_huy', '').strip())
        messages.success(request, 'Đã hủy yêu cầu. Không xóa lịch sử giao dịch.' if result.trang_thai == 'da_huy'
                         else 'Đã gửi yêu cầu xử lý hủy cho quản lý. Đơn và cọc giữ nguyên chờ đối soát; không tự hoàn tiền.')
    except ValidationError as exc:
        messages.warning(request, ' '.join(exc.messages))
    return redirect('chi_tiet_dat_phong_cua_toi', id=booking.pk)
