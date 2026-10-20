from .models import NguoiThue, ThongBao


def thong_bao_header(request):
    """
    Cung cấp badge chưa đọc theo đúng người nhận User hoặc Admin.
    """

    so_thong_bao_chua_doc = 0

    if not request.user.is_authenticated:
        return {
            "so_thong_bao_chua_doc": 0,
            "so_thong_bao_admin_chua_doc": 0,
            "hien_thi_lien_ket_face_id": False,
        }

    if request.user.is_staff or request.user.is_superuser:
        return {
            "so_thong_bao_chua_doc": 0,
            "so_thong_bao_admin_chua_doc": ThongBao.objects.filter(
                nguoi_nhan_user=request.user,
                da_doc=False,
            ).count(),
            "hien_thi_lien_ket_face_id": False,
        }

    nguoi_thue = (
        NguoiThue.objects
        .filter(
            tai_khoan=request.user,
            dang_hoat_dong=True,
        )
        .first()
    )

    if nguoi_thue:
        so_thong_bao_chua_doc = (
            ThongBao.objects
            .filter(
                nguoi_thue=nguoi_thue,
                da_doc=False,
            )
            .count()
        )

    return {
        "so_thong_bao_chua_doc": so_thong_bao_chua_doc,
        "so_thong_bao_admin_chua_doc": 0,
        "hien_thi_lien_ket_face_id": bool(
            nguoi_thue and nguoi_thue.trang_thai_luu_tru != "da_tra_phong"
        ),
    }
