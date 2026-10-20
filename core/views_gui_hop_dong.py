"""Admin action for sending a frozen contract review version."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from core.dich_vu.hop_dong import send_contract_for_tenant_confirmation


@require_POST
def gui_hop_dong_xac_nhan(request, id):
    try:
        _, created = send_contract_for_tenant_confirmation(actor=request.user, contract_id=id)
    except PermissionDenied:
        return redirect("dang_nhap" if not request.user.is_authenticated else "tai_khoan")
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(
            request,
            "Hợp đồng đã được gửi để bạn kiểm tra và xác nhận." if created else "Hợp đồng đã được gửi trước đó.",
        )
    return redirect("chi_tiet_hop_dong", id=id)
