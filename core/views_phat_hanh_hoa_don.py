from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect

from core.dich_vu.hoa_don import publish_invoice_draft


def phat_hanh_hoa_don(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect("tai_khoan")
    if request.method != "POST":
        return redirect("chi_tiet_hoa_don", id=id)
    try:
        _, published = publish_invoice_draft(actor=request.user, invoice_id=id)
        messages.success(request, "Da phat hanh hoa don." if published else "Hoa don da duoc phat hanh truoc do.")
    except (ValidationError, PermissionDenied) as error:
        messages.error(request, str(error))
    return redirect("chi_tiet_hoa_don", id=id)
