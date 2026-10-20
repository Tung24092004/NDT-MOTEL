"""Fail-closed private serving for co-tenant identity evidence."""
from pathlib import PurePath

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.dich_vu.phan_quyen import la_admin
from core.dich_vu.chung_tu_danh_tinh_nguoi_o_cung import PENDING_STATES
from core.models import ChungTuDanhTinhNguoiOCung


@require_GET
def xem_chung_tu_danh_tinh_nguoi_o_cung(request, evidence_id):
    """Serve a verified private image only after an authorization check."""
    if not request.user.is_authenticated:
        raise Http404("Khong tim thay chung tu.")

    evidence = get_object_or_404(
        ChungTuDanhTinhNguoiOCung.objects.select_related(
            "yeu_cau_nguon__nguoi_yeu_cau__tai_khoan",
        ),
        pk=evidence_id,
    )
    tenant_allowed = bool(
        evidence.yeu_cau_nguon_id
        and evidence.nguoi_tai_len_id == request.user.id
        and evidence.yeu_cau_nguon.nguoi_yeu_cau.tai_khoan_id == request.user.id
        and evidence.yeu_cau_nguon.trang_thai in PENDING_STATES
    )
    if not (la_admin(request) or tenant_allowed) or not evidence.tep:
        raise Http404("Khong tim thay chung tu.")

    content_types = {"image/jpeg", "image/png", "image/webp"}
    if evidence.mime_type not in content_types:
        raise Http404("Khong tim thay chung tu.")
    try:
        file_handle = evidence.tep.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("Khong tim thay chung tu.")

    suffix = PurePath(evidence.tep.name).suffix.lower()
    response = FileResponse(
        file_handle,
        content_type=evidence.mime_type,
        as_attachment=True,
        filename=f"identity-evidence-v{evidence.so_phien_ban}{suffix}",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
