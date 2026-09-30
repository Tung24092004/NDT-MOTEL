"""Nghiep vu nhat ky."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Exists, OuterRef
from django.utils import timezone
from django.core.paginator import Paginator
from core.models import (
    CoSo,
    Phong,
    HinhAnhPhong,
    NguoiThue,
    DatPhong,
    HopDong,
    LichSuHopDong,
    YeuCauGiaHanHopDong,
    HoaDon,
    YeuCauSuaChua,
    ChinhSachHoTro,
    ThongBao,
    YeuCauGhepNguoi,
    LichSuThanhToan,

    # Smart Room — Phase 1
    NguoiOCungPhong,
    FaceProfile,
    QuyenRaVao,
    LichSuRaVao,

    # Nhật ký thao tác
    NhatKyThaoTac,
)
from core.dich_vu.phan_quyen import la_admin


@login_required(login_url="dang_nhap")
def nhat_ky_thao_tac(request):
    """
    Danh sách nhật ký thao tác hệ thống.
    Chỉ quản trị viên được phép xem.
    """

    if not la_admin(request):
        messages.error(
            request,
            "Bạn không có quyền truy cập nhật ký thao tác."
        )
        return redirect("home")

    ds = (
        NhatKyThaoTac.objects
        .select_related("nguoi_thuc_hien")
        .order_by("-thoi_diem")
    )

    # =========================
    # BỘ LỌC
    # =========================

    q = request.GET.get("q", "").strip()
    module = request.GET.get("module", "").strip()
    hanh_dong = request.GET.get("hanh_dong", "").strip()
    nguoi_thuc_hien_id = request.GET.get(
        "nguoi_thuc_hien",
        ""
    ).strip()
    tu_ngay = request.GET.get("tu_ngay", "").strip()
    den_ngay = request.GET.get("den_ngay", "").strip()

    if q:
        ds = ds.filter(
            Q(tieu_de__icontains=q)
            | Q(noi_dung__icontains=q)
            | Q(doi_tuong__icontains=q)
            | Q(doi_tuong_id__icontains=q)
        )

    if module:
        ds = ds.filter(module=module)

    if hanh_dong:
        ds = ds.filter(hanh_dong=hanh_dong)

    if nguoi_thuc_hien_id:
        ds = ds.filter(
            nguoi_thuc_hien_id=nguoi_thuc_hien_id
        )

    if tu_ngay:
        ds = ds.filter(
            thoi_diem__date__gte=tu_ngay
        )

    if den_ngay:
        ds = ds.filter(
            thoi_diem__date__lte=den_ngay
        )

    # =========================
    # THỐNG KÊ
    # =========================

    tong_nhat_ky = NhatKyThaoTac.objects.count()

    nhat_ky_hom_nay = (
        NhatKyThaoTac.objects
        .filter(
            thoi_diem__date=timezone.localdate()
        )
        .count()
    )

    so_nguoi_thao_tac = (
        NhatKyThaoTac.objects
        .filter(
            nguoi_thuc_hien__isnull=False
        )
        .values("nguoi_thuc_hien")
        .distinct()
        .count()
    )

    nhat_ky_moi_nhat = (
        NhatKyThaoTac.objects
        .select_related("nguoi_thuc_hien")
        .order_by("-thoi_diem")
        .first()
    )

    # =========================
    # DANH SÁCH MODULE / HÀNH ĐỘNG
    # =========================

    modules = (
        NhatKyThaoTac.objects
        .exclude(module="")
        .values_list("module", flat=True)
        .distinct()
        .order_by("module")
    )

    hanh_dongs = (
        NhatKyThaoTac.objects
        .exclude(hanh_dong="")
        .values_list("hanh_dong", flat=True)
        .distinct()
        .order_by("hanh_dong")
    )

    nguoi_thuc_hien_ds = (
        User.objects
        .filter(
            nhat_ky_thao_tac__isnull=False
        )
        .distinct()
        .order_by("username")
    )

    # =========================
    # PHÂN TRANG
    # =========================

    paginator = Paginator(ds, 20)
    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    query_string = request.GET.copy()

    if "page" in query_string:
        del query_string["page"]

    context = {
        "nhat_ky": page_obj.object_list,
        "page_obj": page_obj,

        "tong_nhat_ky": tong_nhat_ky,
        "nhat_ky_hom_nay": nhat_ky_hom_nay,
        "so_nguoi_thao_tac": so_nguoi_thao_tac,
        "nhat_ky_moi_nhat": nhat_ky_moi_nhat,

        "modules": modules,
        "hanh_dongs": hanh_dongs,
        "nguoi_thuc_hien_ds": nguoi_thuc_hien_ds,

        "q": q,
        "module": module,
        "hanh_dong": hanh_dong,
        "nguoi_thuc_hien_id": nguoi_thuc_hien_id,
        "tu_ngay": tu_ngay,
        "den_ngay": den_ngay,

        "query_string": query_string.urlencode(),
    }

    return render(
        request,
        "core/nhat_ky_thao_tac.html",
        context
    )


@login_required(login_url="dang_nhap")
def chi_tiet_nhat_ky_thao_tac(request, id):
    """
    Xem chi tiết một bản ghi nhật ký thao tác.
    Chỉ quản trị viên được phép xem.
    """

    if not la_admin(request):
        messages.error(
            request,
            "Bạn không có quyền truy cập nhật ký thao tác."
        )
        return redirect("home")

    log = get_object_or_404(
        NhatKyThaoTac.objects.select_related(
            "nguoi_thuc_hien"
        ),
        id=id
    )

    return render(
        request,
        "core/chi_tiet_nhat_ky_thao_tac.html",
        {
            "log": log,
        }
    )
