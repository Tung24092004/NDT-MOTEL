"""Nghiep vu dang ky."""
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from core.booking_identifiers import normalize_cccd
from core.models import NguoiThue


def _normalize_phone_number(raw_phone):
    if raw_phone is None:
        return ""
    normalized = re.sub(r"[\s().-]+", "", raw_phone).strip()
    if normalized.startswith("+84"):
        return "0" + normalized[3:]
    if normalized.startswith("84"):
        return "0" + normalized[2:]
    return normalized


def _is_valid_phone_number(raw_phone):
    normalized = _normalize_phone_number(raw_phone)
    return bool(re.fullmatch(r"0[3-9]\d{8}", normalized))


def _safe_next_url(request, next_url):
    if not (next_url and next_url.startswith("/") and not next_url.startswith("//")):
        return ""
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return ""
    return next_url


def _build_registration_errors(post_data):
    field_errors = {}
    username = (post_data.get("username") or "").strip()
    password = post_data.get("password") or ""
    confirm_password = (
        post_data.get("password_confirm")
        or post_data.get("confirm_password")
        or post_data.get("xac_nhan_mat_khau")
        or ""
    )
    ho_ten = (post_data.get("ho_ten") or "").strip()
    so_dien_thoai = (post_data.get("so_dien_thoai") or "").strip()
    email = (post_data.get("email") or "").strip()
    cccd = normalize_cccd(post_data.get("cccd") or "")

    if not username:
        field_errors["username"] = "Vui lòng nhập tên đăng nhập."
    else:
        try:
            User._meta.get_field("username").clean(username, None)
        except DjangoValidationError as exc:
            field_errors["username"] = "; ".join(exc.messages)
        else:
            if User.objects.filter(username__iexact=username).exists():
                field_errors["username"] = "Tên đăng nhập đã tồn tại."

    if not ho_ten:
        field_errors["ho_ten"] = "Vui lòng nhập họ và tên."

    if not so_dien_thoai:
        field_errors["so_dien_thoai"] = "Vui lòng nhập số điện thoại."
    else:
        normalized_phone = _normalize_phone_number(so_dien_thoai)
        if not _is_valid_phone_number(so_dien_thoai):
            field_errors["so_dien_thoai"] = "Số điện thoại không đúng định dạng."
        elif NguoiThue.objects.filter(so_dien_thoai=normalized_phone).exists():
            field_errors["so_dien_thoai"] = "Số điện thoại đã được đăng ký."

    if not email:
        field_errors["email"] = "Vui lòng nhập email."
    else:
        try:
            validate_email(email)
        except DjangoValidationError:
            field_errors["email"] = "Email không đúng định dạng."
        else:
            normalized_email = email.strip()
            if User.objects.filter(email__iexact=normalized_email).exists() or NguoiThue.objects.filter(email__iexact=normalized_email).exists():
                field_errors["email"] = "Email đã được đăng ký."

    if not password:
        field_errors["password"] = "Vui lòng nhập mật khẩu."
    elif not confirm_password:
        field_errors["password_confirm"] = "Vui lòng xác nhận mật khẩu."
    elif password != confirm_password:
        field_errors["password_confirm"] = "Xác nhận mật khẩu không khớp."
    else:
        try:
            validate_password(password, user=User(username=username or "guest"))
        except DjangoValidationError as exc:
            field_errors["password"] = "; ".join(exc.messages)

    if not cccd:
        field_errors["cccd"] = "Vui lòng nhập CCCD."
    else:
        if not re.fullmatch(r"\d{12}", cccd):
            field_errors["cccd"] = "CCCD phải gồm 12 chữ số."
        elif NguoiThue.objects.filter(cccd=cccd).exists():
            field_errors["cccd"] = "CCCD đã được đăng ký."

    return {
        "username": username,
        "ho_ten": ho_ten,
        "so_dien_thoai": so_dien_thoai,
        "email": email,
        "cccd": cccd,
    }, field_errors


def dang_ky(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect("dashboard_admin")

        next_url = _safe_next_url(request, request.GET.get("next", "").strip())
        if next_url:
            return redirect(next_url)
        return redirect("tai_khoan")

    next_url = _safe_next_url(request, (
        request.POST.get("next", "").strip()
        or request.GET.get("next", "").strip()
    ))

    if request.method == "POST":
        form_data, field_errors = _build_registration_errors(request.POST)
        context = {
            "next": next_url,
            "form_data": form_data,
            "field_errors": field_errors,
        }

        if field_errors:
            messages.error(request, "Vui lòng kiểm tra lại thông tin đăng ký.")
            return render(request, "core/dang_ky.html", context)

        username = form_data["username"]
        password = request.POST.get("password") or ""
        ho_ten = form_data["ho_ten"]
        so_dien_thoai = _normalize_phone_number(form_data["so_dien_thoai"])
        email = form_data["email"]
        cccd = normalize_cccd(form_data["cccd"])

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                )
                NguoiThue.objects.create(
                    tai_khoan=user,
                    ho_ten=ho_ten,
                    so_dien_thoai=so_dien_thoai,
                    email=email,
                    cccd=cccd,
                    trang_thai_luu_tru="tam_vang",
                )
        except IntegrityError:
            messages.error(request, "Đăng ký không thành công do dữ liệu trùng hoặc không hợp lệ.")
            return render(request, "core/dang_ky.html", context)

        messages.success(request, "Đăng ký tài khoản thành công.")
        if next_url:
            return redirect(f"{reverse('dang_nhap')}?{urlencode({'next': next_url})}")
        return redirect("dang_nhap")

    return render(
        request,
        "core/dang_ky.html",
        {
            "next": next_url,
            "form_data": {},
            "field_errors": {},
        }
    )
