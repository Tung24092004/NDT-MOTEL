"""Nghiep vu nguoi thue."""
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count, Exists, OuterRef
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


def quan_ly_nguoi_thue(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    tu_khoa = request.GET.get("q", "").strip()
    nguoi_thue = NguoiThue.objects.select_related("tai_khoan").order_by("ho_ten", "id")
    if tu_khoa:
        nguoi_thue = nguoi_thue.filter(
            Q(ho_ten__icontains=tu_khoa)
            | Q(so_dien_thoai__icontains=tu_khoa)
            | Q(cccd__icontains=tu_khoa)
            | Q(email__icontains=tu_khoa)
        )
    return render(request, "core/quan_ly_nguoi_thue.html", {
        "nguoi_thue": nguoi_thue,
        "tu_khoa": tu_khoa,
    })


def chi_tiet_nguoi_thue(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    nguoi_thue = get_object_or_404(NguoiThue.objects.select_related("tai_khoan"), id=id)
    hop_dong = HopDong.objects.filter(
        dat_phong__nguoi_thue=nguoi_thue
    ).select_related("dat_phong__phong", "dat_phong__phong__co_so").order_by("-ngay_tao")
    hoa_don = HoaDon.objects.filter(
        hop_dong__dat_phong__nguoi_thue=nguoi_thue
    ).select_related("hop_dong").order_by("-nam", "-thang")
    return render(request, "core/chi_tiet_nguoi_thue.html", {
        "nguoi_thue": nguoi_thue,
        "hop_dong": hop_dong,
        "hoa_don": hoa_don,
    })
