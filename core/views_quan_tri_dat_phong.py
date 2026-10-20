from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Case, Exists, IntegerField, OuterRef, Prefetch, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import DatPhong, HopDong, KhaiBaoNguoiOCungDatPhong, ThanhToanCocDatPhong
from .dich_vu import hop_dong


def _admin_required(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect("tai_khoan")
    return None


def _payment_label(payment):
    labels = {
        "chua_thanh_toan": "Chờ thanh toán",
        "cho_xac_nhan": "Chờ đối soát",
        "da_xac_nhan": "Đã xác nhận cọc",
        "tu_choi": "Cọc bị từ chối",
        "da_huy": "Đã hủy giao dịch",
        "da_hoan_tien": "Đã hoàn tiền",
    }
    return labels.get(getattr(payment, "trang_thai", ""), "Chưa có giao dịch")


def _decorate_booking(booking):
    payments = list(booking.giao_dich_coc.all())
    active = next((payment for payment in payments if payment.active_slot == 1), None)
    latest = active or max(payments, key=lambda payment: payment.pk, default=None)
    booking.coc_hien_tai = latest
    booking.trang_thai_coc_hien_thi = _payment_label(latest)
    booking.co_the_xac_nhan_coc = bool(
        latest
        and latest.trang_thai == "cho_xac_nhan"
        and booking.trang_thai in ("cho_duyet", "da_duyet")
    )
    booking.co_the_tao_hop_dong = hop_dong.co_the_tao_hop_dong_nhap(booking, latest)
    return booking


@login_required(login_url="dang_nhap")
def quan_ly_dat_phong(request):
    guard = _admin_required(request)
    if guard:
        return guard

    bookings = (
        DatPhong.objects.select_related("nguoi_thue", "nguoi_thue__tai_khoan", "nguoi_xu_ly", "phong", "phong__co_so")
        .prefetch_related(Prefetch("giao_dich_coc", queryset=ThanhToanCocDatPhong.objects.select_related("chung_tu").order_by("-ngay_tao")))
        .annotate(co_hop_dong=Exists(HopDong.objects.filter(dat_phong_id=OuterRef("pk"))))
        .annotate(
            doi_soat_priority=Case(
                When(giao_dich_coc__trang_thai="cho_xac_nhan", then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("doi_soat_priority", "-ngay_dat", "-id")
        .distinct()
    )

    query = request.GET.get("q", "").strip()
    if query:
        bookings = bookings.filter(
            Q(ma_yeu_cau__icontains=query)
            | Q(nguoi_thue__ho_ten__icontains=query)
            | Q(nguoi_thue__cccd__icontains=query)
            | Q(nguoi_thue__so_dien_thoai__icontains=query)
            | Q(phong__so_phong__icontains=query)
            | Q(phong__co_so__ten_co_so__icontains=query)
        )

    status = request.GET.get("trang_thai", "").strip()
    if status in {"cho_duyet", "da_duyet", "tu_choi", "da_huy"}:
        bookings = bookings.filter(trang_thai=status)
    else:
        status = ""

    deposit = request.GET.get("coc", "").strip()
    if deposit in {"chua_thanh_toan", "cho_xac_nhan", "da_xac_nhan", "tu_choi", "da_huy", "da_hoan_tien"}:
        bookings = bookings.filter(giao_dich_coc__trang_thai=deposit)
    elif deposit == "chua_co":
        bookings = bookings.filter(giao_dich_coc__isnull=True)
    else:
        deposit = ""

    contract_filter = request.GET.get("hop_dong", "").strip()
    if contract_filter == "da_co":
        bookings = bookings.filter(co_hop_dong=True)
    elif contract_filter == "chua_co":
        bookings = bookings.filter(co_hop_dong=False)
    else:
        contract_filter = ""

    total_filtered = bookings.count()
    page_obj = Paginator(bookings, 10).get_page(request.GET.get("page"))
    rows = [_decorate_booking(booking) for booking in page_obj.object_list]

    context = {
        "dat_phong": rows,
        "page_obj": page_obj,
        "tong_don": DatPhong.objects.count(),
        "cho_duyet": DatPhong.objects.filter(trang_thai="cho_duyet").count(),
        "da_duyet": DatPhong.objects.filter(trang_thai="da_duyet").count(),
        "tu_choi": DatPhong.objects.filter(trang_thai="tu_choi").count(),
        "da_huy": DatPhong.objects.filter(trang_thai="da_huy").count(),
        "cho_doi_soat": ThanhToanCocDatPhong.objects.filter(trang_thai="cho_xac_nhan").count(),
        "tong_ket_qua": total_filtered,
        "tu_khoa": query,
        "trang_thai": status,
        "coc": deposit,
        "hop_dong": contract_filter,
    }
    return render(request, "core/quan_ly_dat_phong.html", context)


@login_required(login_url="dang_nhap")
def chi_tiet_dat_phong(request, id):
    guard = _admin_required(request)
    if guard:
        return guard

    booking = get_object_or_404(
        DatPhong.objects.select_related("nguoi_thue", "nguoi_thue__tai_khoan", "nguoi_xu_ly", "phong", "phong__co_so")
        .prefetch_related(Prefetch("giao_dich_coc", queryset=ThanhToanCocDatPhong.objects.select_related("chung_tu").order_by("-ngay_tao")), "nguoi_di_cung_khai_bao"),
        id=id,
    )
    contract = HopDong.objects.filter(dat_phong=booking).first()
    booking.co_hop_dong = bool(contract)
    _decorate_booking(booking)

    progress = {
        "da_dat": True,
        "da_bao_thanh_toan": bool(booking.coc_hien_tai and booking.coc_hien_tai.thoi_diem_user_bao_da_thanh_toan),
        "da_xac_nhan_coc": bool(booking.coc_hien_tai and booking.coc_hien_tai.trang_thai == "da_xac_nhan"),
        "da_co_hop_dong": bool(contract),
    }
    return render(
        request,
        "core/chi_tiet_dat_phong.html",
        {
            "dat_phong": booking,
            "hop_dong": contract,
            "da_co_hop_dong": bool(contract),
            "co_the_xac_nhan_coc": booking.co_the_xac_nhan_coc,
            "so_nguoi_dang_o": booking.phong.so_nguoi_dang_o,
            "so_cho_con_lai": booking.phong.so_cho_con_lai,
            "tien_trinh": progress,
            "giao_dich_coc": list(booking.giao_dich_coc.all()),
            "nguoi_di_cung_khai_bao": list(booking.nguoi_di_cung_khai_bao.all()),
        },
    )


def _service_error(request, exc):
    if isinstance(exc, PermissionDenied):
        messages.error(request, str(exc))
    elif isinstance(exc, ValidationError):
        messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, str(exc))


@require_POST
@login_required(login_url="dang_nhap")
def tu_choi_yeu_cau_dat_phong(request, id):
    guard = _admin_required(request)
    if guard:
        return guard
    try:
        hop_dong.reject_booking(actor=request.user, booking_id=id, reason=request.POST.get("ly_do", ""))
        messages.warning(request, "Yêu cầu đặt phòng đã bị từ chối.")
    except (PermissionDenied, ValidationError) as exc:
        _service_error(request, exc)
    return redirect("chi_tiet_dat_phong", id=id)
