"""Nghiep vu hoa don."""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Exists, OuterRef
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
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

            tien_dien = parse_tien(
                "tien_dien"
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
