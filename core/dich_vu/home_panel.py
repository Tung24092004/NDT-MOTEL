"""Read-only context for the role-aware quick-access panel on the homepage."""

from core.models import DatPhong, HoaDon, NguoiThue, Phong, QuyenRaVao, YeuCauSuaChua
from core.dich_vu.luu_tru import lay_hop_dong_luu_tru_hien_tai
from core.quy_tac_nghiep_vu import eligible_permissions


def lay_home_panel_context(request):
    """Return only data the current visitor is allowed to see; never mutate lifecycle state."""
    context = {
        "vai_tro": "guest",
        "nguoi_thue": None,
        "dat_phong_gan_nhat": None,
        "hop_dong_hien_tai": None,
        "hoa_don_gan_nhat": None,
        "quyen_ra_vao": None,
        "so_yeu_cau_sua_chua_dang_mo": 0,
        "so_dat_phong_cho_duyet": 0,
        "so_quyen_ra_vao_hieu_luc": 0,
        "so_phong": 0,
    }

    if not request.user.is_authenticated:
        return context

    if request.user.is_staff or request.user.is_superuser:
        context.update(
            vai_tro="admin",
            so_dat_phong_cho_duyet=DatPhong.objects.filter(trang_thai="cho_duyet").count(),
            so_yeu_cau_sua_chua_dang_mo=YeuCauSuaChua.objects.filter(
                trang_thai__in=("moi", "dang_xu_ly", "cho_thay_the")
            ).count(),
            so_quyen_ra_vao_hieu_luc=eligible_permissions(QuyenRaVao.objects.all()).count(),
            so_phong=Phong.objects.count(),
        )
        return context

    context["vai_tro"] = "tenant"
    nguoi_thue = (
        NguoiThue.objects.filter(tai_khoan=request.user, dang_hoat_dong=True)
        .select_related("tai_khoan")
        .first()
    )
    context["nguoi_thue"] = nguoi_thue

    if not nguoi_thue:
        return context

    context["dat_phong_gan_nhat"] = (
        DatPhong.objects.filter(nguoi_thue=nguoi_thue)
        .select_related("phong__co_so")
        .order_by("-ngay_dat", "-id")
        .first()
    )

    hop_dong = lay_hop_dong_luu_tru_hien_tai(nguoi_thue=nguoi_thue)
    context["hop_dong_hien_tai"] = hop_dong

    context["so_yeu_cau_sua_chua_dang_mo"] = YeuCauSuaChua.objects.filter(
        nguoi_thue=nguoi_thue,
        trang_thai__in=("moi", "dang_xu_ly", "cho_thay_the"),
    ).count()

    if not hop_dong:
        return context

    context["hoa_don_gan_nhat"] = (
        HoaDon.objects.filter(hop_dong=hop_dong)
        .order_by("-nam", "-thang", "-id")
        .first()
    )
    context["quyen_ra_vao"] = (
        eligible_permissions(
            QuyenRaVao.objects.filter(
                nguoi_thue=nguoi_thue,
                hop_dong=hop_dong,
                phong=hop_dong.dat_phong.phong,
                loai_quyen="chu_phong",
            )
        )
        .order_by("-id")
        .first()
    )

    return context
