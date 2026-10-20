"""Admin actions for independent booking-deposit reconciliation."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .dich_vu import tien_coc


def _admin_required(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect("tai_khoan")
    return None


def _service_error(request, exc):
    messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))


@require_POST
@login_required(login_url="dang_nhap")
def xac_nhan_dat_phong_va_tao_hop_dong(request, id):
    """Confirm a deposit only; the legacy URL intentionally creates no contract."""
    guard = _admin_required(request)
    if guard:
        return guard
    try:
        tien_coc.confirm_deposit(
            actor=request.user,
            booking_id=id,
            payment_id=request.POST.get("payment_id"),
            actual_amount=request.POST.get("so_tien_thuc_nhan"),
        )
        messages.success(request, "Da xac nhan da nhan tien coc.")
    except (PermissionDenied, ValidationError) as exc:
        _service_error(request, exc)
    return redirect("chi_tiet_dat_phong", id=id)


@require_POST
@login_required(login_url="dang_nhap")
def tu_choi_thanh_toan_coc(request, id):
    """Reject submitted deposit evidence without contract side effects."""
    guard = _admin_required(request)
    if guard:
        return guard
    try:
        tien_coc.reject_deposit(
            actor=request.user,
            booking_id=id,
            payment_id=request.POST.get("payment_id"),
            reason=request.POST.get("ly_do", ""),
        )
        messages.warning(request, "Chung tu coc da bi tu choi.")
    except (PermissionDenied, ValidationError) as exc:
        _service_error(request, exc)
    return redirect("chi_tiet_dat_phong", id=id)
