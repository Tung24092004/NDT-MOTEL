"""Action tao hop dong nhap tu booking da xac nhan coc."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .dich_vu.hop_dong import create_draft_contract


@require_POST
@login_required(login_url="dang_nhap")
def tao_hop_dong(request, dat_phong_id):
    try:
        contract, created = create_draft_contract(
            actor=request.user, booking_id=dat_phong_id
        )
    except PermissionDenied:
        messages.error(request, "Chi Admin duoc tao hop dong.")
        return redirect("tai_khoan")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("chi_tiet_dat_phong", id=dat_phong_id)
    if created:
        messages.success(request, "Hop dong nhap da duoc tao va dang cho kiem tra.")
    else:
        messages.warning(request, "Hop dong da duoc tao.")
    return redirect("chi_tiet_hop_dong", id=contract.pk)
