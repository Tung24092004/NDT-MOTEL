from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import ChungTuThanhToan


@require_GET
def xem_anh_chung_tu_thanh_toan(request, id):
    if not request.user.is_authenticated:
        raise Http404("Không tìm thấy chứng từ.")
    evidence = get_object_or_404(
        ChungTuThanhToan.objects.select_related(
            "giao_dich_coc__dat_phong__nguoi_thue__tai_khoan",
            "hoa_don__hop_dong__dat_phong__nguoi_thue__tai_khoan",
        ),
        pk=id,
    )
    owner_id = (
        evidence.giao_dich_coc.dat_phong.nguoi_thue.tai_khoan_id
        if evidence.giao_dich_coc_id
        else evidence.hoa_don.hop_dong.dat_phong.nguoi_thue.tai_khoan_id
    )
    if not (request.user.is_staff or request.user.is_superuser or request.user.id == owner_id):
        raise Http404("Không tìm thấy chứng từ.")
    if not evidence.anh:
        raise Http404("Không tìm thấy chứng từ.")
    try:
        file_handle = evidence.anh.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("Không tìm thấy chứng từ.")
    response = FileResponse(file_handle, content_type=evidence.mime_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
