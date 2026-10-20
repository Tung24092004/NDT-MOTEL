"""Tenant contract-review responses and admin revision reopening."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from core.dich_vu.hop_dong import respond_to_contract_review, reopen_contract_for_revision


def _respond(request, id, action):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    try:
        respond_to_contract_review(actor=request.user, contract_id=id,
            version_id=int(request.POST.get("phien_ban_id", "0")),
            version_hash=request.POST.get("ma_bam_phien_ban", ""), action=action,
            password=request.POST.get("mat_khau", ""), reason=request.POST.get("ly_do", ""),
            ip_address=request.META.get("REMOTE_ADDR"))
    except PermissionDenied:
        return redirect("dang_nhap" if not request.user.is_authenticated else "tai_khoan")
    except Http404:
        raise
    except (ValidationError, ValueError) as error:
        messages.error(request, error.messages[0] if isinstance(error, ValidationError) else "Phien ban hop dong khong hop le.")
    else:
        messages.success(request, "Phan hoi hop dong da duoc ghi nhan.")
    return redirect("chi_tiet_hop_dong_cua_toi", id=id)


@require_POST
def chap_thuan_hop_dong(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if request.POST.get("da_doc_va_chap_thuan") != "on":
        messages.error(request, "Ban can xac nhan da doc hop dong.")
        return redirect("chi_tiet_hop_dong_cua_toi", id=id)
    return _respond(request, id, "chap_thuan")


@require_POST
def yeu_cau_chinh_sua_hop_dong(request, id):
    return _respond(request, id, "yeu_cau_chinh_sua")


@require_POST
def mo_lai_hop_dong_de_sua(request, id):
    try:
        reopen_contract_for_revision(actor=request.user, contract_id=id)
    except PermissionDenied:
        return redirect("dang_nhap" if not request.user.is_authenticated else "tai_khoan")
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("chi_tiet_hop_dong", id=id)
    return redirect("sua_hop_dong", id=id)
