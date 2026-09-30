"""Nghiep vu dang nhap."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib import messages
from django.db import transaction
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


def dang_ky(request):

    # -----------------------------------------------------
    # NẾU ĐÃ ĐĂNG NHẬP
    # -----------------------------------------------------

    if request.user.is_authenticated:

        if (
            request.user.is_staff
            or request.user.is_superuser
        ):
            return redirect(
                "dashboard_admin"
            )

        next_url = request.GET.get(
            "next",
            ""
        ).strip()

        if (
            next_url
            and next_url.startswith("/")
            and not next_url.startswith("//")
        ):
            return redirect(
                next_url
            )

        return redirect(
            "tai_khoan"
        )

    # -----------------------------------------------------
    # LẤY TRANG CẦN QUAY LẠI
    # -----------------------------------------------------

    next_url = (
        request.POST.get(
            "next",
            ""
        ).strip()
        or request.GET.get(
            "next",
            ""
        ).strip()
    )

    # Chỉ chấp nhận đường dẫn nội bộ
    if not (
        next_url
        and next_url.startswith("/")
        and not next_url.startswith("//")
    ):
        next_url = ""

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        ho_ten = request.POST.get(
            "ho_ten",
            ""
        ).strip()

        so_dien_thoai = request.POST.get(
            "so_dien_thoai",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        cccd = request.POST.get(
            "cccd",
            ""
        ).strip()

        form_data = {
            "username": username,
            "ho_ten": ho_ten,
            "so_dien_thoai": so_dien_thoai,
            "email": email,
            "cccd": cccd,
        }

        context = {
            "next": next_url,
            "form_data": form_data,
        }

        # -------------------------------------------------
        # THÔNG TIN BẮT BUỘC
        # -------------------------------------------------

        if not username or not password:

            messages.error(
                request,
                "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu."
            )

            return render(
                request,
                "core/dang_ky.html",
                context
            )

        if not ho_ten:

            messages.error(
                request,
                "Vui lòng nhập họ và tên."
            )

            return render(
                request,
                "core/dang_ky.html",
                context
            )

        if not so_dien_thoai:

            messages.error(
                request,
                "Vui lòng nhập số điện thoại."
            )

            return render(
                request,
                "core/dang_ky.html",
                context
            )

        # -------------------------------------------------
        # USERNAME
        # -------------------------------------------------

        if User.objects.filter(
            username=username
        ).exists():

            messages.error(
                request,
                "Tên đăng nhập đã tồn tại."
            )

            return render(
                request,
                "core/dang_ky.html",
                context
            )

        # -------------------------------------------------
        # CCCD
        # -------------------------------------------------

        if not cccd:

            messages.error(
                request,
                "Vui lòng nhập CCCD."
            )

            return render(
                request,
                "core/dang_ky.html",
                context
            )

        if NguoiThue.objects.filter(
            cccd=cccd
        ).exists():

            messages.error(
                request,
                "CCCD đã được đăng ký."
            )

            return render(
                request,
                "core/dang_ky.html",
                context
            )

        # -------------------------------------------------
        # TẠO TÀI KHOẢN
        # -------------------------------------------------

        with transaction.atomic():

            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
            )

            NguoiThue.objects.create(
                tai_khoan=user,
                ho_ten=ho_ten,
                so_dien_thoai=so_dien_thoai,
                email=email,
                cccd=cccd,
            )

        # -------------------------------------------------
        # ĐĂNG NHẬP NGAY SAU KHI ĐĂNG KÝ
        # -------------------------------------------------

        login(
            request,
            user
        )

        messages.success(
            request,
            "Đăng ký tài khoản thành công."
        )

        # Nếu đăng ký từ luồng đặt phòng / ở ghép,
        # tiếp tục đúng chức năng người dùng đang thực hiện.
        if next_url:
            return redirect(
                next_url
            )

        return redirect(
            "tai_khoan"
        )

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    return render(
        request,
        "core/dang_ky.html",
        {
            "next": next_url,
            "form_data": {},
        }
    )


def dang_nhap(request):

    # -----------------------------------------------------
    # NẾU ĐÃ ĐĂNG NHẬP
    # -----------------------------------------------------

    if request.user.is_authenticated:

        if (
            request.user.is_staff
            or request.user.is_superuser
        ):
            return redirect(
                "dashboard_admin"
            )

        next_url = request.GET.get(
            "next",
            ""
        ).strip()

        if (
            next_url
            and next_url.startswith("/")
            and not next_url.startswith("//")
        ):
            return redirect(
                next_url
            )

        return redirect(
            "tai_khoan"
        )

    # -----------------------------------------------------
    # LẤY TRANG CẦN QUAY LẠI
    # -----------------------------------------------------

    next_url = (
        request.POST.get(
            "next",
            ""
        ).strip()
        or request.GET.get(
            "next",
            ""
        ).strip()
    )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        if not username or not password:

            messages.error(
                request,
                "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu."
            )

            return render(
                request,
                "core/dang_nhap.html",
                {
                    "next": next_url,
                    "username": username,
                }
            )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(
                request,
                user
            )

            # -------------------------------------------------
            # ADMIN
            # -------------------------------------------------

            if (
                user.is_staff
                or user.is_superuser
            ):

                return redirect(
                    "dashboard_admin"
                )

            # -------------------------------------------------
            # USER - QUAY LẠI TRANG TRƯỚC ĐÓ
            # -------------------------------------------------

            if (
                next_url
                and next_url.startswith("/")
                and not next_url.startswith("//")
            ):

                return redirect(
                    next_url
                )

            return redirect(
                "tai_khoan"
            )

        messages.error(
            request,
            "Tên đăng nhập hoặc mật khẩu không đúng."
        )

        return render(
            request,
            "core/dang_nhap.html",
            {
                "next": next_url,
                "username": username,
            }
        )

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    return render(
        request,
        "core/dang_nhap.html",
        {
            "next": next_url,
        }
    )


def dang_xuat(request):

    logout(request)

    return redirect(
        "home"
    )
