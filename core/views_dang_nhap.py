"""Nghiep vu dang nhap."""
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


def _safe_next_url(request, next_url):
    if not (
        next_url
        and next_url.startswith("/")
        and not next_url.startswith("//")
    ):
        return ""
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return ""
    return next_url


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

        next_url = _safe_next_url(
            request,
            request.GET.get("next", "").strip(),
        )

        if next_url:
            return redirect(
                next_url
            )

        return redirect(
            "tai_khoan"
        )

    # -----------------------------------------------------
    # LẤY TRANG CẦN QUAY LẠI
    # -----------------------------------------------------

    next_url = _safe_next_url(
        request,
        request.POST.get("next", "").strip()
        or request.GET.get("next", "").strip(),
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

            if next_url:

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


@require_POST
def dang_xuat(request):

    logout(request)

    return redirect(
        "home"
    )
