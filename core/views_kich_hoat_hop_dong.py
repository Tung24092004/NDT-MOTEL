"""Dedicated Admin POST endpoint for accepted-contract activation."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from core.dich_vu.kich_hoat_hop_dong import activate_accepted_contract


@require_POST
def kich_hoat_hop_dong(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    try:
        _, created = activate_accepted_contract(
            actor=request.user, contract_id=id, ip_address=request.META.get("REMOTE_ADDR")
        )
    except PermissionDenied:
        return redirect("tai_khoan")
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, "Hop dong da duoc kich hoat." if created else "Hop dong da duoc kich hoat truoc do.")
    return redirect("chi_tiet_hop_dong", id=id)
