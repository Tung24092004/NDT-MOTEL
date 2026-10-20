"""Các trang hướng dẫn công khai của NDT MOTEL."""

from django.conf import settings
from django.shortcuts import render


def huong_dan_thue_phong(request):
    return render(request, "core/huong_dan_thue_phong.html")


def trung_tam_tro_giup(request):
    """Trung tâm trợ giúp công khai, không đọc hoặc thay đổi dữ liệu nghiệp vụ."""
    lien_he = {
        "so_dien_thoai": getattr(settings, "NDT_SUPPORT_PHONE", ""),
        "email": getattr(settings, "NDT_SUPPORT_EMAIL", ""),
        "thoi_gian": getattr(settings, "NDT_SUPPORT_HOURS", ""),
    }
    return render(
        request,
        "core/trung_tam_tro_giup.html",
        {"lien_he_ho_tro": lien_he},
    )