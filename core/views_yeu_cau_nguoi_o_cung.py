"""Admin review surface for the co-tenant request domain."""
import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from core.dich_vu.phan_quyen import la_admin
from core.dich_vu.yeu_cau_nguoi_o_cung import (
    approve_request, reject_request, request_supplement,
)
from core.models import Phong, YeuCauNguoiOCung


logger = logging.getLogger(__name__)
def _admin_or_redirect(request):
    if not request.user.is_authenticated:
        return None, redirect("dang_nhap")
    if not la_admin(request):
        return None, redirect("tai_khoan")
    return request.user, None


def _request_or_404(request_id):
    return get_object_or_404(
        YeuCauNguoiOCung.objects.select_related(
            "hop_dong", "hop_dong__dat_phong", "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so", "nguoi_yeu_cau", "nguoi_xu_ly",
            "identity", "residency",
        ).prefetch_related("chung_tu_danh_tinh_gui_len"),
        pk=request_id,
    )


def quan_ly_yeu_cau_nguoi_o_cung(request):
    _, redirect_response = _admin_or_redirect(request)
    if redirect_response:
        return redirect_response
    query = request.GET.get("q", "").strip()
    room_id = request.GET.get("phong", "").strip()
    status = request.GET.get("trang_thai", "").strip()
    requests = YeuCauNguoiOCung.objects.select_related(
        "hop_dong", "hop_dong__dat_phong", "hop_dong__dat_phong__phong",
        "hop_dong__dat_phong__phong__co_so", "nguoi_yeu_cau", "residency",
    ).order_by("-ngay_tao", "-pk")
    if query:
        from django.db.models import Q
        requests = requests.filter(
            Q(ho_ten__icontains=query) | Q(cccd__icontains=query)
            | Q(hop_dong__so_hop_dong__icontains=query)
            | Q(hop_dong__dat_phong__phong__so_phong__icontains=query)
            | Q(nguoi_yeu_cau__ho_ten__icontains=query)
        )
    if room_id.isdigit():
        requests = requests.filter(hop_dong__dat_phong__phong_id=int(room_id))
    if status in dict(YeuCauNguoiOCung.TRANG_THAI):
        requests = requests.filter(trang_thai=status)
    return render(request, "core/quan_ly_yeu_cau_nguoi_o_cung.html", {
        "ds": requests,
        "cac_phong": Phong.objects.select_related("co_so").order_by("co_so__ten_co_so", "tang", "so_phong"),
        "tu_khoa": query, "phong_id": room_id, "trang_thai_filter": status,
        "trang_thai_choices": YeuCauNguoiOCung.TRANG_THAI,
        "cho_xac_minh": YeuCauNguoiOCung.objects.filter(trang_thai="cho_xac_minh").count(),
        "cho_bo_sung": YeuCauNguoiOCung.objects.filter(trang_thai="cho_bo_sung").count(),
    })


def chi_tiet_yeu_cau_nguoi_o_cung(request, request_id):
    _, redirect_response = _admin_or_redirect(request)
    if redirect_response:
        return redirect_response
    return render(request, "core/chi_tiet_yeu_cau_nguoi_o_cung.html", {
        "yeu_cau": _request_or_404(request_id),
    })


def _review(request, request_id, action):
    actor, redirect_response = _admin_or_redirect(request)
    if redirect_response:
        return redirect_response
    request_obj = _request_or_404(request_id)
    if request.method != "POST":
        return redirect("chi_tiet_yeu_cau_nguoi_o_cung", request_id=request_obj.pk)
    try:
        revision = int(request.POST.get("expected_revision", ""))
        if action == "supplement":
            result, changed = request_supplement(
                request_id=request_obj.pk, actor=actor, expected_revision=revision,
                reason=request.POST.get("reason", "").strip(),
            )
        elif action == "approve":
            result, changed = approve_request(
                request_id=request_obj.pk, actor=actor, expected_revision=revision,
            )
        else:
            result, changed = reject_request(
                request_id=request_obj.pk, actor=actor, expected_revision=revision,
                reason=request.POST.get("reason", "").strip(),
            )
    except (TypeError, ValueError, ValidationError) as exc:
        messages.error(request, str(exc) or "Dữ liệu xử lý không hợp lệ.")
    except Exception:
        logger.exception("Co-tenant request review failed")
        messages.error(request, "Không thể xử lý yêu cầu lúc này. Vui lòng thử lại.")
    else:
        if changed:
            messages.success(request, {
                "supplement": "Đã yêu cầu người thuê bổ sung thông tin.",
                "approve": "Đã duyệt yêu cầu người ở cùng.",
                "reject": "Đã từ chối yêu cầu người ở cùng.",
            }[action])
        else:
            messages.warning(request, "Yêu cầu đã được xử lý hoặc thay đổi; không có dữ liệu nào được cập nhật.")
    return redirect("chi_tiet_yeu_cau_nguoi_o_cung", request_id=request_obj.pk)


def yeu_cau_nguoi_o_cung_bo_sung(request, request_id):
    return _review(request, request_id, "supplement")


def duyet_yeu_cau_nguoi_o_cung(request, request_id):
    return _review(request, request_id, "approve")


def tu_choi_yeu_cau_nguoi_o_cung(request, request_id):
    return _review(request, request_id, "reject")
