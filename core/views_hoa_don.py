"""Nghiep vu hoa don."""
import csv
import calendar
from datetime import date
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db.models import (
    Q, Count, Exists, OuterRef, Subquery, F, Sum, Value, DecimalField,
    ExpressionWrapper,
)
from django.db.models.functions import Coalesce
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods
from core.tien_ich import ghi_nhat_ky
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
from core.dich_vu.hoa_don import calculate_electricity_charge, review_invoice_draft


def hoa_don_cua_toi(request):

    # =====================================================
    # KIỂM TRA ĐĂNG NHẬP / QUYỀN USER
    # =====================================================

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard_admin")

    # =====================================================
    # LẤY HỒ SƠ NGƯỜI THUÊ
    # =====================================================

    nguoi_thue = (
        NguoiThue.objects
        .filter(
            tai_khoan=request.user,
            dang_hoat_dong=True,
        )
        .first()
    )

    if not nguoi_thue:
        messages.error(
            request,
            "Tài khoản chưa được liên kết với thông tin người thuê đang hoạt động."
        )
        return redirect("tai_khoan")

    ngay_hien_tai = timezone.localdate()

    # =====================================================
    # LẤY DANH SÁCH HÓA ĐƠN
    # =====================================================

    hoa_don = (
        HoaDon.objects
        .filter(
            hop_dong__dat_phong__nguoi_thue=nguoi_thue
        )
        .exclude(trang_thai="draft")
        .select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
        )
        .order_by(
            "-nam",
            "-thang",
            "-ngay_tao",
        )
    )

    # =====================================================
    # THỐNG KÊ
    # =====================================================

    tong_hoa_don = hoa_don.count()

    da_thanh_toan = hoa_don.filter(
        trang_thai="da_thanh_toan"
    ).count()

    chua_thanh_toan = hoa_don.filter(
        trang_thai="chua_thanh_toan"
    ).count()
    cho_xac_nhan = hoa_don.filter(
        trang_thai="cho_xac_nhan"
    ).count()

    qua_han = hoa_don.filter(
        trang_thai="qua_han"
    ).count()

    da_huy = hoa_don.filter(
        trang_thai="huy"
    ).count()

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "core/hoa_don_cua_toi.html",
        {
            "hoa_don": hoa_don,
            "nguoi_thue": nguoi_thue,
            "tong_hoa_don": tong_hoa_don,
            "da_thanh_toan": da_thanh_toan,
            "chua_thanh_toan": chua_thanh_toan,
            "cho_xac_nhan": cho_xac_nhan,
            "qua_han": qua_han,
            "da_huy": da_huy,
            "ngay_hien_tai": ngay_hien_tai,
        }
    )


def chi_tiet_hoa_don_cua_toi(request, id):

    # =====================================================
    # KIỂM TRA ĐĂNG NHẬP / QUYỀN USER
    # =====================================================

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard_admin")

    # =====================================================
    # LẤY HỒ SƠ NGƯỜI THUÊ
    # =====================================================

    nguoi_thue = (
        NguoiThue.objects
        .filter(
            tai_khoan=request.user,
            dang_hoat_dong=True,
        )
        .first()
    )

    if not nguoi_thue:
        messages.error(
            request,
            "Tài khoản chưa được liên kết với thông tin người thuê đang hoạt động."
        )
        return redirect("tai_khoan")

    # =====================================================
    # LẤY ĐÚNG HÓA ĐƠN THUỘC NGƯỜI ĐANG ĐĂNG NHẬP
    # =====================================================

    hoa_don = get_object_or_404(
        HoaDon.objects.select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__nguoi_thue",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
        ),
        id=id,
        hop_dong__dat_phong__nguoi_thue=nguoi_thue,
        trang_thai__in=("chua_thanh_toan", "cho_xac_nhan", "da_thanh_toan", "qua_han", "huy"),
    )

    ngay_hien_tai = timezone.localdate()

    # =====================================================
    # TỔNG TIỀN
    # =====================================================

    try:
        tong_tien = hoa_don.tong_tien
    except (AttributeError, TypeError):
        tong_tien = (
            (hoa_don.tien_phong or 0)
            + (hoa_don.tien_dien or 0)
            + (hoa_don.tien_nuoc or 0)
            + (hoa_don.tien_dich_vu or 0)
            + (hoa_don.phi_khac or 0)
        )

    hoa_don.tong_tien_hien_thi = (
        tong_tien
    )

    # =====================================================
    # LỊCH SỬ THANH TOÁN
    # =====================================================

    lich_su_thanh_toan = (
        LichSuThanhToan.objects
        .filter(
            hoa_don=hoa_don
        )
        .select_related(
            "nguoi_thuc_hien"
        )
        .order_by(
            "-thoi_diem"
        )
    )

    # =====================================================
    # CỜ GIAO DIỆN
    # =====================================================

    co_the_thanh_toan = (
        hoa_don.trang_thai
        in [
            "chua_thanh_toan",
            "qua_han",
        ]
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "core/chi_tiet_hoa_don_cua_toi.html",
        {
            "hoa_don":
                hoa_don,
            "nguoi_thue":
                nguoi_thue,
            "lich_su_thanh_toan":
                lich_su_thanh_toan,
            "tong_tien":
                tong_tien,
            "co_the_thanh_toan":
                co_the_thanh_toan,
            "payment_attempts": hoa_don.chung_tu_thanh_toan.select_related(
                "nguoi_xu_ly"
            ).order_by("-so_lan", "-pk"),
            "ngay_hien_tai":
                ngay_hien_tai,
        }
    )


def quan_ly_hoa_don(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    # =========================================================
    # QUERYSET HÓA ĐƠN
    # =========================================================

    hoa_don = (
        HoaDon.objects
        .select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__nguoi_thue",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
        )
        .order_by(
            "-nam",
            "-thang",
            "-ngay_tao",
        )
    )

    # =========================================================
    # TÌM KIẾM
    # =========================================================

    tu_khoa = request.GET.get(
        "q",
        ""
    ).strip()

    if tu_khoa:
        hoa_don = hoa_don.filter(
            Q(
                hop_dong__so_hop_dong__icontains=tu_khoa
            )
            | Q(
                hop_dong__dat_phong__nguoi_thue__ho_ten__icontains=tu_khoa
            )
            | Q(
                hop_dong__dat_phong__phong__so_phong__icontains=tu_khoa
            )
        )

    # =========================================================
    # LỌC TRẠNG THÁI
    # =========================================================

    trang_thai = request.GET.get(
        "trang_thai",
        ""
    ).strip()

    cac_trang_thai = [
        "draft",
        "chua_thanh_toan",
        "cho_xac_nhan",
        "da_thanh_toan",
        "qua_han",
    ]

    if trang_thai in cac_trang_thai:
        hoa_don = hoa_don.filter(
            trang_thai=trang_thai
        )
    else:
        trang_thai = ""

    # =========================================================
    # TÍNH TỔNG TIỀN CHO TỪNG HÓA ĐƠN
    # =========================================================

    for hd in hoa_don:

        hd.tong_tien_hien_thi = (
            hd.tien_phong
            + hd.tien_dien
            + hd.tien_nuoc
            + hd.tien_dich_vu
            + hd.phi_khac
        )

    # =========================================================
    # THỐNG KÊ
    #
    # Các số này tính theo DANH SÁCH HIỆN TẠI sau tìm kiếm/lọc.
    # =========================================================

    tong_hoa_don = hoa_don.count()

    so_hoa_don_chua_thanh_toan = hoa_don.filter(
        trang_thai="chua_thanh_toan"
    ).count()
    so_hoa_don_cho_xac_nhan = hoa_don.filter(
        trang_thai="cho_xac_nhan"
    ).count()
    so_hoa_don_da_thanh_toan = hoa_don.filter(
        trang_thai="da_thanh_toan"
    ).count()

    so_hoa_don_qua_han = hoa_don.filter(
        trang_thai="qua_han"
    ).count()

    # =========================================================
    # CONTEXT
    # =========================================================

    context = {
        "hoa_don": hoa_don,

        "tu_khoa": tu_khoa,

        "trang_thai": trang_thai,

        "tong_hoa_don": tong_hoa_don,

        "so_hoa_don_chua_thanh_toan":
            so_hoa_don_chua_thanh_toan,

        "so_hoa_don_da_thanh_toan":
            so_hoa_don_da_thanh_toan,

        "so_hoa_don_qua_han":
            so_hoa_don_qua_han,
        "so_hoa_don_cho_xac_nhan":
            so_hoa_don_cho_xac_nhan,
    }

    return render(
        request,
        "core/quan_ly_hoa_don.html",
        context
    )


TRANG_THAI_CONG_NO = (
    "chua_thanh_toan",
    "cho_xac_nhan",
    "qua_han",
)

NHOM_TUOI_CONG_NO = (
    "chua_den_han",
    "qua_han_1_7",
    "qua_han_8_30",
    "qua_han_31_plus",
)


def _loc_nhom_tuoi_cong_no(queryset, nhom_tuoi, hom_nay):
    """Áp dụng một nhóm tuổi nợ với các biên ngày không giao nhau."""
    if nhom_tuoi == "chua_den_han":
        return queryset.filter(han_thanh_toan__gte=hom_nay)
    if nhom_tuoi == "qua_han_1_7":
        return queryset.filter(
            han_thanh_toan__gte=hom_nay - timedelta(days=7),
            han_thanh_toan__lt=hom_nay,
        )
    if nhom_tuoi == "qua_han_8_30":
        return queryset.filter(
            han_thanh_toan__gte=hom_nay - timedelta(days=30),
            han_thanh_toan__lte=hom_nay - timedelta(days=8),
        )
    if nhom_tuoi == "qua_han_31_plus":
        return queryset.filter(
            han_thanh_toan__lte=hom_nay - timedelta(days=31)
        )
    return queryset


def _tong_cong_no(queryset, money_field):
    return queryset.aggregate(
        tong=Coalesce(
            Sum("so_tien_con_no"),
            Value(Decimal("0")),
            output_field=money_field,
        )
    )["tong"]


def _csv_an_toan(value):
    """Ngăn dữ liệu do người dùng nhập trở thành công thức bảng tính."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@require_GET
def bao_cao_cong_no(request):
    """Báo cáo tuổi nợ chỉ đọc dành cho quản trị viên."""
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    hom_nay = timezone.localdate()
    money_field = DecimalField(max_digits=14, decimal_places=0)
    amount_expression = ExpressionWrapper(
        F("tien_phong")
        + F("tien_dien")
        + F("tien_nuoc")
        + F("tien_dich_vu")
        + F("phi_khac"),
        output_field=money_field,
    )

    cong_no = (
        HoaDon.objects
        .filter(trang_thai__in=TRANG_THAI_CONG_NO)
        .select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__nguoi_thue",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
        )
        .annotate(so_tien_con_no=amount_expression)
    )

    tu_khoa = request.GET.get("q", "").strip()
    co_so = request.GET.get("co_so", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    nhom_tuoi = request.GET.get("nhom_tuoi", "").strip()
    tu_han_raw = request.GET.get("tu_han", "").strip()
    den_han_raw = request.GET.get("den_han", "").strip()
    tu_han = parse_date(tu_han_raw)
    den_han = parse_date(den_han_raw)

    if tu_khoa:
        cong_no = cong_no.filter(
            Q(hop_dong__so_hop_dong__icontains=tu_khoa)
            | Q(hop_dong__dat_phong__nguoi_thue__ho_ten__icontains=tu_khoa)
            | Q(hop_dong__dat_phong__phong__so_phong__icontains=tu_khoa)
        )
    if co_so.isdecimal():
        cong_no = cong_no.filter(
            hop_dong__dat_phong__phong__co_so_id=int(co_so)
        )
    else:
        co_so = ""
    if trang_thai in TRANG_THAI_CONG_NO:
        cong_no = cong_no.filter(trang_thai=trang_thai)
    else:
        trang_thai = ""
    if tu_han:
        cong_no = cong_no.filter(han_thanh_toan__gte=tu_han)
    else:
        tu_han_raw = ""
    if den_han:
        cong_no = cong_no.filter(han_thanh_toan__lte=den_han)
    else:
        den_han_raw = ""

    # Các thẻ thống kê cùng một scope nghiệp vụ, trước khi chọn nhóm tuổi.
    scope = cong_no
    nhom_queryset = {
        code: _loc_nhom_tuoi_cong_no(scope, code, hom_nay)
        for code in NHOM_TUOI_CONG_NO
    }
    thong_ke = {
        "tong_so": scope.count(),
        "tong_tien": _tong_cong_no(scope, money_field),
    }
    for code, queryset in nhom_queryset.items():
        thong_ke[code] = {
            "so_luong": queryset.count(),
            "tong_tien": _tong_cong_no(queryset, money_field),
        }

    if nhom_tuoi in NHOM_TUOI_CONG_NO:
        cong_no = nhom_queryset[nhom_tuoi]
    else:
        nhom_tuoi = ""
    cong_no = cong_no.order_by("han_thanh_toan", "id")

    if request.GET.get("xuat") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="bao-cao-cong-no-{hom_nay.isoformat()}.csv"'
        )
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow([
            "Mã hóa đơn", "Kỳ", "Hạn thanh toán", "Số ngày quá hạn",
            "Người thuê", "Hợp đồng", "Cơ sở", "Phòng",
            "Trạng thái", "Số tiền còn nợ (VND)",
        ])
        for item in cong_no.iterator():
            so_ngay_qua_han = max((hom_nay - item.han_thanh_toan).days, 0)
            writer.writerow([
                f"HD-{item.pk}",
                f"{item.thang:02d}/{item.nam}",
                item.han_thanh_toan.isoformat(),
                so_ngay_qua_han,
                _csv_an_toan(item.hop_dong.dat_phong.nguoi_thue.ho_ten),
                _csv_an_toan(item.hop_dong.so_hop_dong),
                _csv_an_toan(item.hop_dong.dat_phong.phong.co_so.ten_co_so),
                _csv_an_toan(item.hop_dong.dat_phong.phong.so_phong),
                item.get_trang_thai_display(),
                item.so_tien_con_no,
            ])
        return response

    page_obj = Paginator(cong_no, 20).get_page(request.GET.get("page"))
    for item in page_obj.object_list:
        item.so_ngay_qua_han = max((hom_nay - item.han_thanh_toan).days, 0)

    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    pagination_params.pop("xuat", None)
    export_params = pagination_params.copy()
    export_params["xuat"] = "csv"

    return render(request, "core/bao_cao_cong_no.html", {
        "page_obj": page_obj,
        "hoa_don": page_obj.object_list,
        "co_so_list": CoSo.objects.order_by("ten_co_so", "id"),
        "tu_khoa": tu_khoa,
        "co_so": co_so,
        "trang_thai": trang_thai,
        "nhom_tuoi": nhom_tuoi,
        "tu_han": tu_han_raw,
        "den_han": den_han_raw,
        "thong_ke": thong_ke,
        "hom_nay": hom_nay,
        "query_string": pagination_params.urlencode(),
        "export_query": export_params.urlencode(),
    })


TRANG_THAI_HOP_DONG_CHOT_CHI_SO = (
    "dang_hieu_luc",
    "sap_het_han",
)


def _pham_vi_ky_hoa_don(thang, nam):
    ngay_dau = date(nam, thang, 1)
    ngay_cuoi = date(nam, thang, calendar.monthrange(nam, thang)[1])
    return ngay_dau, ngay_cuoi


def _doc_ky_hoa_don(request):
    hom_nay = timezone.localdate()
    thang_raw = request.POST.get("thang") if request.method == "POST" else request.GET.get("thang")
    nam_raw = request.POST.get("nam") if request.method == "POST" else request.GET.get("nam")
    try:
        thang = int((thang_raw or hom_nay.month))
        nam = int((nam_raw or hom_nay.year))
    except (TypeError, ValueError):
        raise ValueError("Tháng và năm chốt chỉ số phải là số hợp lệ.")
    if not 1 <= thang <= 12 or not 2000 <= nam <= 2100:
        raise ValueError("Kỳ chốt chỉ số không hợp lệ.")
    return thang, nam


def _hop_dong_cho_chot_chi_so(thang, nam):
    ky_truoc = Q(nam__lt=nam) | Q(nam=nam, thang__lt=thang)
    ky_sau = Q(nam__gt=nam) | Q(nam=nam, thang__gt=thang)
    hoa_don_truoc = (
        HoaDon.objects
        .filter(hop_dong=OuterRef("pk"))
        .filter(ky_truoc)
        .order_by("-nam", "-thang", "-id")
    )
    ngay_dau, ngay_cuoi = _pham_vi_ky_hoa_don(thang, nam)
    return (
        HopDong.objects
        .filter(
            trang_thai__in=TRANG_THAI_HOP_DONG_CHOT_CHI_SO,
            ngay_bat_dau__lte=ngay_cuoi,
            ngay_ket_thuc__gte=ngay_dau,
        )
        .select_related(
            "dat_phong__nguoi_thue",
            "dat_phong__phong",
            "dat_phong__phong__co_so",
        )
        .annotate(
            da_co_hoa_don=Exists(
                HoaDon.objects.filter(
                    hop_dong=OuterRef("pk"),
                    thang=thang,
                    nam=nam,
                )
            ),
            co_hoa_don_sau=Exists(
                HoaDon.objects
                .filter(hop_dong=OuterRef("pk"))
                .filter(ky_sau)
            ),
            chi_so_dien_cu_goi_y=Subquery(
                hoa_don_truoc.values("chi_so_dien_moi")[:1],
                output_field=DecimalField(max_digits=12, decimal_places=0),
            ),
        )
        .order_by(
            "dat_phong__phong__co_so__ten_co_so",
            "dat_phong__phong__so_phong",
            "id",
        )
    )


def _gan_du_lieu_chot_chi_so(hop_dongs, request):
    selected = set(request.POST.getlist("hop_dong_ids")) if request.method == "POST" else set()
    for hop_dong in hop_dongs:
        phong = hop_dong.dat_phong.phong
        hop_dong.tien_nuoc_du_kien = phong.tien_nuoc_moi_khoi * hop_dong.so_nguoi_o
        hop_dong.tien_dich_vu_du_kien = phong.phi_dich_vu
        hop_dong.tong_phi_co_dinh = (
            hop_dong.tien_thue_thang
            + hop_dong.tien_nuoc_du_kien
            + hop_dong.tien_dich_vu_du_kien
        )
        hop_dong.co_the_chot = (
            not hop_dong.da_co_hoa_don
            and not hop_dong.co_hoa_don_sau
            and phong.tien_dien_moi_so > 0
        )
        hop_dong.da_chon = str(hop_dong.pk) in selected
        goi_y = hop_dong.chi_so_dien_cu_goi_y
        hop_dong.gia_tri_chi_so_cu = request.POST.get(
            f"chi_so_cu_{hop_dong.pk}",
            "" if goi_y is None else f"{goi_y:.0f}",
        )
        hop_dong.gia_tri_chi_so_moi = request.POST.get(
            f"chi_so_moi_{hop_dong.pk}",
            "",
        )
    return hop_dongs


@require_http_methods(["GET", "POST"])
def chot_chi_so_dien_hang_loat(request):
    """Chốt chỉ số điện và phát hành nhiều hóa đơn trong một transaction."""
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    ky_hop_le = True
    try:
        thang, nam = _doc_ky_hoa_don(request)
    except ValueError as error:
        messages.error(request, str(error))
        if request.method == "POST":
            return render(request, "core/chot_chi_so_dien_hang_loat.html", {
                "hop_dongs": [],
                "thang": request.POST.get("thang", ""),
                "nam": request.POST.get("nam", ""),
                "han_thanh_toan": request.POST.get("han_thanh_toan", ""),
                "so_co_the_chot": 0,
                "so_da_co_hoa_don": 0,
                "so_bi_chan": 0,
            })
        ky_hop_le = False
        hom_nay = timezone.localdate()
        thang, nam = hom_nay.month, hom_nay.year

    if request.method == "POST" and ky_hop_le:
        try:
            han_thanh_toan = parse_date(request.POST.get("han_thanh_toan", "").strip())
            if not han_thanh_toan:
                raise ValueError("Vui lòng nhập hạn thanh toán hợp lệ.")

            raw_ids = request.POST.getlist("hop_dong_ids")
            if not raw_ids:
                raise ValueError("Vui lòng chọn ít nhất một hợp đồng để chốt chỉ số.")
            try:
                hop_dong_ids = sorted({int(value) for value in raw_ids})
            except (TypeError, ValueError):
                raise ValueError("Danh sách hợp đồng được chọn không hợp lệ.")
            if len(hop_dong_ids) > 100:
                raise ValueError("Mỗi lượt chỉ được chốt tối đa 100 hợp đồng.")

            ngay_dau, ngay_cuoi = _pham_vi_ky_hoa_don(thang, nam)
            with transaction.atomic():
                hop_dongs_khoa = list(
                    HopDong.objects
                    .select_for_update()
                    .select_related(
                        "dat_phong__nguoi_thue",
                        "dat_phong__phong",
                        "dat_phong__phong__co_so",
                    )
                    .filter(pk__in=hop_dong_ids)
                    .order_by("pk")
                )
                if len(hop_dongs_khoa) != len(hop_dong_ids):
                    raise ValueError("Có hợp đồng được chọn không còn tồn tại.")

                ke_hoach = []
                for hop_dong in hop_dongs_khoa:
                    if (
                        hop_dong.trang_thai not in TRANG_THAI_HOP_DONG_CHOT_CHI_SO
                        or hop_dong.ngay_bat_dau > ngay_cuoi
                        or hop_dong.ngay_ket_thuc < ngay_dau
                    ):
                        raise ValueError(
                            f"Hợp đồng {hop_dong.so_hop_dong} không có hiệu lực trong kỳ đã chọn."
                        )

                    hoa_don_cua_hop_dong = list(
                        HoaDon.objects
                        .select_for_update()
                        .filter(hop_dong=hop_dong)
                        .order_by("-nam", "-thang", "-id")
                    )
                    if any(item.thang == thang and item.nam == nam for item in hoa_don_cua_hop_dong):
                        raise ValueError(
                            f"Hợp đồng {hop_dong.so_hop_dong} đã có hóa đơn kỳ {thang:02d}/{nam}."
                        )
                    if any((item.nam, item.thang) > (nam, thang) for item in hoa_don_cua_hop_dong):
                        raise ValueError(
                            f"Hợp đồng {hop_dong.so_hop_dong} đã có hóa đơn ở kỳ mới hơn."
                        )

                    hoa_don_truoc = next(
                        (
                            item for item in hoa_don_cua_hop_dong
                            if (item.nam, item.thang) < (nam, thang)
                        ),
                        None,
                    )
                    phong = hop_dong.dat_phong.phong
                    chi_so_cu, chi_so_moi, don_gia, tien_dien = calculate_electricity_charge(
                        previous_reading=request.POST.get(f"chi_so_cu_{hop_dong.pk}", ""),
                        current_reading=request.POST.get(f"chi_so_moi_{hop_dong.pk}", ""),
                        unit_price=phong.tien_dien_moi_so,
                    )
                    if (
                        hoa_don_truoc is not None
                        and hoa_don_truoc.chi_so_dien_moi is not None
                        and chi_so_cu != hoa_don_truoc.chi_so_dien_moi
                    ):
                        raise ValueError(
                            f"Chỉ số cũ của hợp đồng {hop_dong.so_hop_dong} "
                            "không khớp kỳ hóa đơn gần nhất."
                        )

                    tien_nuoc = phong.tien_nuoc_moi_khoi * hop_dong.so_nguoi_o
                    tien_dich_vu = phong.phi_dich_vu
                    tong_tien = (
                        hop_dong.tien_thue_thang
                        + tien_dien
                        + tien_nuoc
                        + tien_dich_vu
                    )
                    if tong_tien <= 0:
                        raise ValueError(
                            f"Tổng tiền của hợp đồng {hop_dong.so_hop_dong} phải lớn hơn 0."
                        )
                    ke_hoach.append({
                        "hop_dong": hop_dong,
                        "chi_so_cu": chi_so_cu,
                        "chi_so_moi": chi_so_moi,
                        "don_gia": don_gia,
                        "tien_dien": tien_dien,
                        "tien_nuoc": tien_nuoc,
                        "tien_dich_vu": tien_dich_vu,
                        "tong_tien": tong_tien,
                    })

                hoa_don_da_tao = []
                for item in ke_hoach:
                    hop_dong = item["hop_dong"]
                    phong = hop_dong.dat_phong.phong
                    nguoi_thue = hop_dong.dat_phong.nguoi_thue
                    hoa_don = HoaDon.objects.create(
                        hop_dong=hop_dong,
                        thang=thang,
                        nam=nam,
                        tien_phong=hop_dong.tien_thue_thang,
                        tien_dien=item["tien_dien"],
                        chi_so_dien_cu=item["chi_so_cu"],
                        chi_so_dien_moi=item["chi_so_moi"],
                        don_gia_dien=item["don_gia"],
                        tien_nuoc=item["tien_nuoc"],
                        tien_dich_vu=item["tien_dich_vu"],
                        phi_khac=0,
                        chi_tiet_phi="Chốt chỉ số điện hàng loạt",
                        han_thanh_toan=han_thanh_toan,
                        trang_thai="chua_thanh_toan",
                        nguoi_lap=request.user,
                    )
                    thong_bao = ThongBao.objects.create(
                        nguoi_thue=nguoi_thue,
                        tieu_de=f"Hóa đơn tháng {thang}/{nam} đã được tạo",
                        noi_dung=(
                            f"Hóa đơn tháng {thang}/{nam} cho phòng {phong.so_phong} "
                            f"đã được tạo. Tổng số tiền cần thanh toán là "
                            f"{item['tong_tien']:,.0f} đồng. Hạn thanh toán: "
                            f"{han_thanh_toan.strftime('%d/%m/%Y')}."
                        ),
                        loai="thanh_toan",
                        muc_do="binh_thuong",
                    )
                    ghi_nhat_ky(
                        request=request,
                        hanh_dong="Tạo hàng loạt",
                        module="Hóa đơn",
                        doi_tuong="HoaDon",
                        doi_tuong_id=hoa_don.pk,
                        tieu_de=f"Chốt chỉ số và tạo hóa đơn {thang}/{nam}",
                        noi_dung=(
                            f"Admin {request.user.username} chốt chỉ số điện và tạo "
                            f"hóa đơn cho hợp đồng {hop_dong.so_hop_dong}, "
                            f"phòng {phong.so_phong}."
                        ),
                        du_lieu_cu={},
                        du_lieu_moi={
                            "hoa_don_id": hoa_don.pk,
                            "so_hop_dong": hop_dong.so_hop_dong,
                            "thang": thang,
                            "nam": nam,
                            "chi_so_dien_cu": str(item["chi_so_cu"]),
                            "chi_so_dien_moi": str(item["chi_so_moi"]),
                            "don_gia_dien": str(item["don_gia"]),
                            "tien_dien": str(item["tien_dien"]),
                            "tien_nuoc": str(item["tien_nuoc"]),
                            "tien_dich_vu": str(item["tien_dich_vu"]),
                            "tong_tien": str(item["tong_tien"]),
                            "han_thanh_toan": str(han_thanh_toan),
                            "thong_bao_id": thong_bao.pk,
                        },
                    )
                    hoa_don_da_tao.append(hoa_don)

            messages.success(
                request,
                f"Đã chốt chỉ số và tạo {len(hoa_don_da_tao)} hóa đơn kỳ {thang:02d}/{nam}.",
            )
            return redirect("quan_ly_hoa_don")
        except (ValueError, InvalidOperation) as error:
            messages.error(request, str(error))
        except IntegrityError:
            messages.error(
                request,
                "Dữ liệu hóa đơn vừa thay đổi. Không có hóa đơn nào được tạo; vui lòng tải lại.",
            )

    hop_dongs = list(_hop_dong_cho_chot_chi_so(thang, nam))
    _gan_du_lieu_chot_chi_so(hop_dongs, request)
    han_thanh_toan = request.POST.get("han_thanh_toan", "")
    return render(request, "core/chot_chi_so_dien_hang_loat.html", {
        "hop_dongs": hop_dongs,
        "thang": thang,
        "nam": nam,
        "han_thanh_toan": han_thanh_toan,
        "so_co_the_chot": sum(1 for item in hop_dongs if item.co_the_chot),
        "so_da_co_hoa_don": sum(1 for item in hop_dongs if item.da_co_hoa_don),
        "so_bi_chan": sum(
            1 for item in hop_dongs
            if not item.da_co_hoa_don and not item.co_the_chot
        ),
    })


def chi_tiet_hoa_don(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    # ---------------------------------------------------------
    # LẤY HÓA ĐƠN
    # ---------------------------------------------------------

    hoa_don = get_object_or_404(
        HoaDon.objects.select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__nguoi_thue",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
        ),
        id=id
    )

    # ---------------------------------------------------------
    # TÍNH TỔNG TIỀN
    # ---------------------------------------------------------

    hoa_don.tong_tien_hien_thi = (
        hoa_don.tien_phong
        + hoa_don.tien_dien
        + hoa_don.tien_nuoc
        + hoa_don.tien_dich_vu
        + hoa_don.phi_khac
    )

    # ---------------------------------------------------------
    # LẤY LỊCH SỬ THANH TOÁN
    # ---------------------------------------------------------

    lich_su_thanh_toan = (
        LichSuThanhToan.objects
        .filter(
            hoa_don=hoa_don
        )
        .select_related(
            "nguoi_thuc_hien"
        )
        .order_by(
            "-thoi_diem"
        )
    )

    # ---------------------------------------------------------
    # TRẢ VỀ TRANG CHI TIẾT
    # ---------------------------------------------------------

    return render(
        request,
        "core/chi_tiet_hoa_don.html",
        {
            "hoa_don": hoa_don,
            "lich_su_thanh_toan": lich_su_thanh_toan,
            "draft_review": review_invoice_draft(hoa_don),
            "payment_attempts": hoa_don.chung_tu_thanh_toan.select_related(
                "nguoi_tai_len", "nguoi_xu_ly"
            ).order_by("-so_lan", "-pk"),
        }
    )


def tao_hoa_don(request):

    # =====================================================
    # KIỂM TRA ĐĂNG NHẬP / QUYỀN ADMIN
    # =====================================================

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    # =====================================================
    # HÀM RENDER FORM
    # =====================================================

    def render_form():

        hop_dongs = (
            HopDong.objects
            .filter(
                trang_thai__in=[
                    "dang_hieu_luc",
                    "sap_het_han",
                ]
            )
            .select_related(
                "dat_phong__nguoi_thue",
                "dat_phong__phong",
                "dat_phong__phong__co_so",
            )
            .order_by("-ngay_bat_dau")
        )

        return render(
            request,
            "core/tao_hoa_don.html",
            {
                "hop_dongs": hop_dongs,
                "form_data": (
                    request.POST
                    if request.method == "POST"
                    else None
                ),
            }
        )

    # =====================================================
    # GET
    # =====================================================

    if request.method != "POST":
        return render_form()

    # =====================================================
    # POST
    # =====================================================

    try:

        # -------------------------------------------------
        # DỮ LIỆU ĐẦU VÀO
        # -------------------------------------------------

        hop_dong_id = request.POST.get(
            "hop_dong",
            ""
        ).strip()

        thang_raw = request.POST.get(
            "thang",
            ""
        ).strip()

        nam_raw = request.POST.get(
            "nam",
            ""
        ).strip()

        han_thanh_toan_raw = request.POST.get(
            "han_thanh_toan",
            ""
        ).strip()

        chi_tiet_phi = request.POST.get(
            "chi_tiet_phi",
            ""
        ).strip()

        ghi_chu = request.POST.get(
            "ghi_chu",
            ""
        ).strip()

        if (
            not hop_dong_id
            or not thang_raw
            or not nam_raw
            or not han_thanh_toan_raw
        ):
            messages.error(
                request,
                "Vui lòng nhập đầy đủ hợp đồng, tháng, năm và hạn thanh toán."
            )
            return render_form()

        # -------------------------------------------------
        # THÁNG / NĂM
        # -------------------------------------------------

        thang = int(thang_raw)
        nam = int(nam_raw)

        if thang < 1 or thang > 12:
            messages.error(
                request,
                "Tháng phải nằm trong khoảng từ 1 đến 12."
            )
            return render_form()

        if nam < 2000 or nam > 2100:
            messages.error(
                request,
                "Năm hóa đơn không hợp lệ."
            )
            return render_form()

        # -------------------------------------------------
        # HẠN THANH TOÁN
        # -------------------------------------------------

        han_thanh_toan = parse_date(
            han_thanh_toan_raw
        )

        if not han_thanh_toan:
            messages.error(
                request,
                "Vui lòng nhập hạn thanh toán hợp lệ."
            )
            return render_form()

        # -------------------------------------------------
        # CÁC KHOẢN TIỀN
        # -------------------------------------------------

        def parse_tien(field_name, mac_dinh="0"):

            raw = request.POST.get(
                field_name,
                ""
            ).strip()

            if raw == "":
                raw = str(mac_dinh or "0")

            return Decimal(raw)

        # =================================================
        # TRANSACTION
        # =================================================

        with transaction.atomic():

            # ---------------------------------------------
            # KHÓA HỢP ĐỒNG
            # ---------------------------------------------

            hop_dong = get_object_or_404(
                HopDong.objects
                .select_for_update()
                .select_related(
                    "dat_phong__nguoi_thue",
                    "dat_phong__phong",
                    "dat_phong__phong__co_so",
                ),
                id=hop_dong_id,
            )

            # ---------------------------------------------
            # CHỈ HỢP ĐỒNG ĐANG / SẮP HẾT HẠN
            # ---------------------------------------------

            if hop_dong.trang_thai not in [
                "dang_hieu_luc",
                "sap_het_han",
            ]:
                messages.error(
                    request,
                    "Chỉ có thể tạo hóa đơn cho hợp đồng đang có hiệu lực."
                )
                return render_form()

            nguoi_thue = (
                hop_dong
                .dat_phong
                .nguoi_thue
            )

            phong = (
                hop_dong
                .dat_phong
                .phong
            )

            # ---------------------------------------------
            # CHỐNG TRÙNG HÓA ĐƠN
            # ---------------------------------------------

            hoa_don_da_co = (
                HoaDon.objects
                .select_for_update()
                .filter(
                    hop_dong=hop_dong,
                    thang=thang,
                    nam=nam,
                )
                .exists()
            )

            if hoa_don_da_co:
                messages.error(
                    request,
                    (
                        f"Hợp đồng {hop_dong.so_hop_dong} "
                        f"đã có hóa đơn tháng {thang}/{nam}."
                    )
                )
                return render_form()

            # ---------------------------------------------
            # PARSE TIỀN
            # ---------------------------------------------

            tien_phong = parse_tien(
                "tien_phong",
                hop_dong.tien_thue_thang
            )

            (
                chi_so_dien_cu,
                chi_so_dien_moi,
                don_gia_dien,
                tien_dien,
            ) = calculate_electricity_charge(
                previous_reading=request.POST.get("chi_so_dien_cu", ""),
                current_reading=request.POST.get("chi_so_dien_moi", ""),
                unit_price=request.POST.get("don_gia_dien", ""),
            )

            tien_nuoc = parse_tien(
                "tien_nuoc"
            )

            tien_dich_vu = parse_tien(
                "tien_dich_vu"
            )

            phi_khac = parse_tien(
                "phi_khac"
            )

            # ---------------------------------------------
            # KHÔNG CHO TIỀN ÂM
            # ---------------------------------------------

            cac_khoan_tien = [
                tien_phong,
                tien_dien,
                tien_nuoc,
                tien_dich_vu,
                phi_khac,
            ]

            if any(
                tien < 0
                for tien in cac_khoan_tien
            ):
                messages.error(
                    request,
                    "Các khoản tiền không được nhỏ hơn 0."
                )
                return render_form()

            tong_tien = sum(
                cac_khoan_tien,
                Decimal("0")
            )

            if tong_tien <= 0:
                messages.error(
                    request,
                    "Tổng tiền hóa đơn phải lớn hơn 0."
                )
                return render_form()

            # ---------------------------------------------
            # TẠO HÓA ĐƠN
            # ---------------------------------------------

            hoa_don = HoaDon.objects.create(
                hop_dong=hop_dong,
                thang=thang,
                nam=nam,
                tien_phong=tien_phong,
                tien_dien=tien_dien,
                chi_so_dien_cu=chi_so_dien_cu,
                chi_so_dien_moi=chi_so_dien_moi,
                don_gia_dien=don_gia_dien,
                tien_nuoc=tien_nuoc,
                tien_dich_vu=tien_dich_vu,
                phi_khac=phi_khac,
                chi_tiet_phi=chi_tiet_phi,
                han_thanh_toan=han_thanh_toan,
                ghi_chu=ghi_chu,
                trang_thai="chua_thanh_toan",
            )

            # ---------------------------------------------
            # THÔNG BÁO USER
            # ---------------------------------------------

            thong_bao_moi = ThongBao.objects.create(
                nguoi_thue=nguoi_thue,
                tieu_de=(
                    f"Hóa đơn tháng {thang}/{nam} đã được tạo"
                ),
                noi_dung=(
                    f"Hóa đơn tháng {thang}/{nam} "
                    f"cho phòng {phong.so_phong} "
                    f"đã được tạo. "
                    f"Tổng số tiền cần thanh toán là "
                    f"{tong_tien:,.0f} đồng. "
                    f"Hạn thanh toán: "
                    f"{han_thanh_toan.strftime('%d/%m/%Y')}."
                ),
                loai="thanh_toan",
                muc_do="binh_thuong",
            )

            # ---------------------------------------------
            # AUDIT HÓA ĐƠN
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Hóa đơn",
                doi_tuong="HoaDon",
                doi_tuong_id=hoa_don.id,
                tieu_de=(
                    f"Tạo hóa đơn {thang}/{nam}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} "
                    f"tạo hóa đơn tháng {thang}/{nam} "
                    f"cho hợp đồng {hop_dong.so_hop_dong}, "
                    f"phòng {phong.so_phong}."
                ),
                du_lieu_cu={},
                du_lieu_moi={
                    "hoa_don_id":
                        hoa_don.id,
                    "so_hop_dong":
                        hop_dong.so_hop_dong,
                    "nguoi_thue":
                        nguoi_thue.ho_ten,
                    "phong":
                        phong.so_phong,
                    "thang":
                        thang,
                    "nam":
                        nam,
                    "tien_phong":
                        str(tien_phong),
                    "tien_dien":
                        str(tien_dien),
                    "chi_so_dien_cu":
                        str(chi_so_dien_cu),
                    "chi_so_dien_moi":
                        str(chi_so_dien_moi),
                    "don_gia_dien":
                        str(don_gia_dien),
                    "tien_nuoc":
                        str(tien_nuoc),
                    "tien_dich_vu":
                        str(tien_dich_vu),
                    "phi_khac":
                        str(phi_khac),
                    "tong_tien":
                        str(tong_tien),
                    "han_thanh_toan":
                        str(han_thanh_toan),
                    "trang_thai":
                        hoa_don.trang_thai,
                    "thong_bao_id":
                        thong_bao_moi.id,
                },
            )

            # ---------------------------------------------
            # AUDIT THÔNG BÁO
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Thông báo",
                doi_tuong="ThongBao",
                doi_tuong_id=thong_bao_moi.id,
                tieu_de=(
                    f"Tạo thông báo hóa đơn "
                    f"{thang}/{nam}"
                ),
                noi_dung=(
                    f"Tạo thông báo hóa đơn "
                    f"{thang}/{nam} cho "
                    f"{nguoi_thue.ho_ten}."
                ),
                du_lieu_cu={},
                du_lieu_moi={
                    "thong_bao_id":
                        thong_bao_moi.id,
                    "hoa_don_id":
                        hoa_don.id,
                    "nguoi_thue_id":
                        nguoi_thue.id,
                    "loai":
                        thong_bao_moi.loai,
                    "muc_do":
                        thong_bao_moi.muc_do,
                },
            )

        messages.success(
            request,
            "Tạo hóa đơn thành công và đã gửi thông báo cho người thuê."
        )

        return redirect(
            "chi_tiet_hoa_don",
            id=hoa_don.id
        )

    except (
        ValueError,
        InvalidOperation,
    ):
        messages.error(
            request,
            "Dữ liệu hóa đơn không hợp lệ. Vui lòng kiểm tra lại các khoản tiền."
        )

        return render_form()
