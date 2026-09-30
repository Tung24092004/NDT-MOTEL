"""Nghiep vu tai khoan."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
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


def doi_mat_khau(request):
    """
    Cho phép người dùng đổi mật khẩu tài khoản.
    """
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if (
        request.user.is_staff or request.user.is_superuser
    ) and request.resolver_match.url_name == "doi_mat_khau_user":
        return redirect("dashboard_admin")

    if request.method == "POST":
        mat_khau_hien_tai = request.POST.get("mat_khau_hien_tai", "")
        mat_khau_moi = request.POST.get("mat_khau_moi", "")
        xac_nhan_mat_khau = request.POST.get("xac_nhan_mat_khau", "")

        # Kiểm tra mật khẩu hiện tại
        if not request.user.check_password(mat_khau_hien_tai):
            messages.error(
                request,
                "Mật khẩu hiện tại không chính xác."
            )
            return render(
                request,
                "core/doi_mat_khau.html"
            )

        # Kiểm tra mật khẩu mới
        if not mat_khau_moi:
            messages.error(
                request,
                "Vui lòng nhập mật khẩu mới."
            )
            return render(
                request,
                "core/doi_mat_khau.html"
            )

        if len(mat_khau_moi) < 6:
            messages.error(
                request,
                "Mật khẩu mới phải có ít nhất 6 ký tự."
            )
            return render(
                request,
                "core/doi_mat_khau.html"
            )

        # Không cho đặt lại đúng mật khẩu cũ
        if request.user.check_password(mat_khau_moi):
            messages.error(
                request,
                "Mật khẩu mới phải khác mật khẩu hiện tại."
            )
            return render(
                request,
                "core/doi_mat_khau.html"
            )

        # Xác nhận mật khẩu
        if mat_khau_moi != xac_nhan_mat_khau:
            messages.error(
                request,
                "Mật khẩu xác nhận không khớp."
            )
            return render(
                request,
                "core/doi_mat_khau.html"
            )

        # Đổi mật khẩu
        request.user.set_password(mat_khau_moi)
        request.user.save()

        # Giữ trạng thái đăng nhập sau khi đổi mật khẩu
        update_session_auth_hash(request, request.user)

        messages.success(
            request,
            "Đổi mật khẩu thành công."
        )

        return redirect("tai_khoan")

    return render(
        request,
        "core/doi_mat_khau.html"
    )


def cap_nhat_thong_tin(request):

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard_admin")

    nguoi_thue = get_object_or_404(
        NguoiThue,
        tai_khoan=request.user
    )

    if request.method == "POST":

        ho_ten = request.POST.get("ho_ten", "").strip()
        so_dien_thoai = request.POST.get(
            "so_dien_thoai",
            ""
        ).strip()
        email = request.POST.get(
            "email",
            ""
        ).strip()
        que_quan = request.POST.get(
            "que_quan",
            ""
        ).strip()
        dia_chi_thuong_tru = request.POST.get(
            "dia_chi_thuong_tru",
            ""
        ).strip()
        nghe_nghiep = request.POST.get(
            "nghe_nghiep",
            ""
        ).strip()
        nguoi_lien_he = request.POST.get(
            "nguoi_lien_he",
            ""
        ).strip()
        sdt_nguoi_lien_he = request.POST.get(
            "sdt_nguoi_lien_he",
            ""
        ).strip()

        if not ho_ten:
            messages.error(
                request,
                "Họ tên không được để trống."
            )
            return render(
                request,
                "core/cap_nhat_thong_tin.html",
                {
                    "nguoi_thue": nguoi_thue
                }
            )

        if email:
            

            try:
                validate_email(email)
            except ValidationError:
                messages.error(
                    request,
                    "Email không đúng định dạng."
                )
                return render(
                    request,
                    "core/cap_nhat_thong_tin.html",
                    {
                        "nguoi_thue": nguoi_thue
                    }
                )

        nguoi_thue.ho_ten = ho_ten
        nguoi_thue.so_dien_thoai = so_dien_thoai
        nguoi_thue.email = email
        nguoi_thue.que_quan = que_quan
        nguoi_thue.dia_chi_thuong_tru = dia_chi_thuong_tru
        nguoi_thue.nghe_nghiep = nghe_nghiep
        nguoi_thue.nguoi_lien_he = nguoi_lien_he
        nguoi_thue.sdt_nguoi_lien_he = sdt_nguoi_lien_he

        nguoi_thue.save()

        messages.success(
            request,
            "Cập nhật thông tin cá nhân thành công."
        )

        return redirect("tai_khoan")

    return render(
        request,
        "core/cap_nhat_thong_tin.html",
        {
            "nguoi_thue": nguoi_thue
        }
    )


def tai_khoan(request):

    if not request.user.is_authenticated:

        return redirect(
            "dang_nhap"
        )

    if (
        request.user.is_staff
        or request.user.is_superuser
    ):

        return redirect(
            "dashboard_admin"
        )

    nguoi_thue = get_object_or_404(
        NguoiThue,
        tai_khoan=request.user
    )

    # =====================================================
    # ĐẶT PHÒNG
    # =====================================================

    danh_sach_dat_phong = (
        DatPhong.objects
        .filter(
            nguoi_thue=nguoi_thue
        )
        .select_related(
            "phong",
            "phong__co_so",
            "nguoi_xu_ly",
        )
        .order_by(
            "-ngay_dat",
            "-id",
        )
    )

    dat_phong_gan_nhat = (
        danh_sach_dat_phong
        .first()
    )

    so_dat_phong_cho_duyet = (
        danh_sach_dat_phong
        .filter(
            trang_thai="cho_duyet"
        )
        .count()
    )

    # =====================================================
    # HỢP ĐỒNG
    # =====================================================

    danh_sach_hop_dong = (
        HopDong.objects
        .filter(
            dat_phong__nguoi_thue=nguoi_thue
        )
        .select_related(
            "dat_phong",
            "dat_phong__phong",
            "dat_phong__phong__co_so",
        )
        .order_by(
            "-ngay_tao",
            "-id",
        )
    )

    hop_dong_hien_tai = (
        danh_sach_hop_dong
        .filter(
            trang_thai__in=[
                "dang_hieu_luc",
                "sap_het_han",
            ]
        )
        .first()
    )

    so_hop_dong = (
        danh_sach_hop_dong
        .count()
    )

    # =====================================================
    # HÓA ĐƠN
    # =====================================================

    danh_sach_hoa_don = (
        HoaDon.objects
        .filter(
            hop_dong__dat_phong__nguoi_thue=nguoi_thue
        )
        .select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__phong",
        )
        .order_by(
            "-nam",
            "-thang",
            "-id",
        )
    )

    hoa_don_gan_nhat = (
        danh_sach_hoa_don
        .first()
    )

    so_hoa_don_chua_thanh_toan = (
        danh_sach_hoa_don
        .filter(
            trang_thai__in=[
                "chua_thanh_toan",
                "qua_han",
            ]
        )
        .count()
    )

    # =====================================================
    # THÔNG BÁO
    # =====================================================

    danh_sach_thong_bao = (
        ThongBao.objects
        .filter(
            nguoi_thue=nguoi_thue
        )
        .order_by(
            "-ngay_tao",
            "-id",
        )
    )

    thong_bao_gan_day = (
        danh_sach_thong_bao[:5]
    )

    so_thong_bao_chua_doc = (
        danh_sach_thong_bao
        .filter(
            da_doc=False
        )
        .count()
    )

    # =====================================================
    # SỬA CHỮA
    # =====================================================
    # Model YeuCauSuaChua hiện tại liên kết trực tiếp:
    #
    # YeuCauSuaChua
    #     -> nguoi_thue
    #     -> phong
    #
    # Không đi qua HopDong.

    danh_sach_sua_chua = (
        YeuCauSuaChua.objects
        .filter(
            nguoi_thue=nguoi_thue
        )
        .select_related(
            "nguoi_thue",
            "phong",
            "phong__co_so",
            "nguoi_xu_ly_user",
        )
        .order_by(
            "-ngay_tao",
            "-id",
        )
    )

    so_sua_chua_dang_xu_ly = (
        danh_sach_sua_chua
        .filter(
            trang_thai__in=[
                "da_gui",
                "tiep_nhan",
                "dang_xu_ly",
            ]
        )
        .count()
    )

    # =====================================================
    # PHÒNG HIỆN TẠI
    # =====================================================

    phong_hien_tai = None

    if hop_dong_hien_tai:

        phong_hien_tai = (
            hop_dong_hien_tai
            .dat_phong
            .phong
        )

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {

        "nguoi_thue": nguoi_thue,

        # Đặt phòng
        "danh_sach_dat_phong": danh_sach_dat_phong,
        "dat_phong_gan_nhat": dat_phong_gan_nhat,
        "so_dat_phong_cho_duyet": so_dat_phong_cho_duyet,

        # Hợp đồng
        "danh_sach_hop_dong": danh_sach_hop_dong,
        "hop_dong_hien_tai": hop_dong_hien_tai,
        "so_hop_dong": so_hop_dong,

        # Phòng
        "phong_hien_tai": phong_hien_tai,

        # Hóa đơn
        "danh_sach_hoa_don": danh_sach_hoa_don,
        "hoa_don_gan_nhat": hoa_don_gan_nhat,
        "so_hoa_don_chua_thanh_toan": so_hoa_don_chua_thanh_toan,

        # Thông báo
        "thong_bao_gan_day": thong_bao_gan_day,
        "so_thong_bao_chua_doc": so_thong_bao_chua_doc,

        # Sửa chữa
        "danh_sach_sua_chua": danh_sach_sua_chua,
        "so_sua_chua_dang_xu_ly": so_sua_chua_dang_xu_ly,
    }

    return render(
        request,
        "core/tai_khoan.html",
        context
    )


def _lay_nguoi_thue_dang_dang_nhap(request):
    if not request.user.is_authenticated:
        return None

    return NguoiThue.objects.filter(
        tai_khoan=request.user,
        dang_hoat_dong=True,
    ).first()
