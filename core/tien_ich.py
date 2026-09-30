import logging

from .models import NhatKyThaoTac


logger = logging.getLogger(__name__)


def ghi_nhat_ky(
    request,
    hanh_dong,
    module="",
    doi_tuong="",
    doi_tuong_id=None,
    tieu_de="",
    noi_dung="",
    du_lieu_cu=None,
    du_lieu_moi=None,
):
    """
    Ghi nhật ký thao tác hệ thống.

    Nếu việc ghi nhật ký gặp lỗi thì không làm ảnh hưởng
    đến nghiệp vụ chính của hệ thống.
    """

    try:
        # ==========================================
        # NGƯỜI THỰC HIỆN
        # ==========================================
        nguoi_thuc_hien = None

        if (
            request is not None
            and hasattr(request, "user")
            and request.user.is_authenticated
        ):
            nguoi_thuc_hien = request.user

        # ==========================================
        # LẤY ĐỊA CHỈ IP
        # ==========================================
        dia_chi_ip = None

        if request is not None:
            x_forwarded_for = request.META.get(
                "HTTP_X_FORWARDED_FOR"
            )

            if x_forwarded_for:
                dia_chi_ip = x_forwarded_for.split(",")[0].strip()
            else:
                dia_chi_ip = request.META.get("REMOTE_ADDR")

        # ==========================================
        # USER AGENT
        # ==========================================
        user_agent = ""

        if request is not None:
            user_agent = request.META.get(
                "HTTP_USER_AGENT",
                ""
            )[:1000]

        # ==========================================
        # DỮ LIỆU TRƯỚC / SAU
        # ==========================================
        if du_lieu_cu is None:
            du_lieu_cu = {}

        if du_lieu_moi is None:
            du_lieu_moi = {}

        # ==========================================
        # TẠO NHẬT KÝ
        # ==========================================
        return NhatKyThaoTac.objects.create(
            nguoi_thuc_hien=nguoi_thuc_hien,
            hanh_dong=hanh_dong or "",
            module=module or "",
            doi_tuong=doi_tuong or "",
            doi_tuong_id=doi_tuong_id,
            tieu_de=tieu_de or "",
            noi_dung=noi_dung or "",
            du_lieu_cu=du_lieu_cu,
            du_lieu_moi=du_lieu_moi,
            dia_chi_ip=dia_chi_ip,
            user_agent=user_agent,
        )

    except Exception as exc:
        logger.error("Khong the ghi nhat ky thao tac (%s).", type(exc).__name__)
        return None
