"""Read-only query and display-state contract for public room surfaces."""

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from core.dich_vu.dat_phong import room_has_hold
from core.models import DatPhong, Phong


TRANG_THAI_CONG_KHAI = {
    "trong": ("Có thể thuê", "Phòng đang sẵn sàng để thuê.", "trong", True),
    "da_dat": ("Đang giữ chỗ", "Phòng đang được giữ chỗ hợp lệ.", "da_dat", False),
    "dang_thue": ("Đang có người thuê", "Phòng hiện đang có người thuê.", "dang_thue", False),
    "bao_tri": ("Đang bảo trì", "Phòng đang bảo trì và chưa thể cho thuê.", "bao_tri", False),
    "chua_san_sang": (
        "Chưa thể cho thuê",
        "Thông tin vận hành, sức chứa hoặc giá thuê của phòng chưa sẵn sàng.",
        "chua_san_sang",
        False,
    ),
}


def dieu_kien_giu_cho_hop_le(now=None):
    """Return the booking predicate that reserves a room for public display."""
    now = now or timezone.now()
    cho_coc = Q(trang_thai="cho_duyet") & (
        Q(han_thanh_toan_coc__isnull=True)
        | Q(han_thanh_toan_coc__gt=now)
        | Q(giao_dich_coc__trang_thai__in=["cho_xac_nhan", "da_xac_nhan"])
    )
    da_duyet = Q(trang_thai="da_duyet") & (
        Q(hop_dong__isnull=True)
        | Q(hop_dong__trang_thai__in=["cho_hieu_luc", "dang_hieu_luc", "sap_het_han"])
    )
    return cho_coc | da_duyet


def them_giu_cho_cong_khai(queryset, now=None):
    """Annotate rooms with the same current hold predicate used by the UI."""
    return queryset.annotate(
        co_giu_cho_hop_le=Exists(
            DatPhong.objects.filter(phong=OuterRef("pk")).filter(
                dieu_kien_giu_cho_hop_le(now)
            )
        )
    )


def queryset_phong_cong_khai():
    """Return every public room in the single order used by room discovery."""
    return (
        Phong.objects.filter(co_so__trang_thai="hoat_dong")
        .select_related("co_so")
        .prefetch_related("hinh_anh")
        .order_by("co_so__quan", "co_so__ten_co_so", "so_phong", "id")
    )


def gan_trang_thai_cong_khai(phong, *, hop_dong_hien_tai=None, co_giu_cho_hop_le=None):
    """Attach the one current public status and presentation metadata to a room."""
    gia_thue_hop_le = phong.gia_thue is not None and phong.gia_thue > 0
    if co_giu_cho_hop_le is None:
        co_giu_cho_hop_le = room_has_hold(phong)
    if hop_dong_hien_tai:
        ma_trang_thai = "dang_thue"
    elif co_giu_cho_hop_le:
        ma_trang_thai = "da_dat"
    elif phong.trang_thai == "bao_tri":
        ma_trang_thai = "bao_tri"
    elif phong.so_nguoi_toi_da < 1 or not gia_thue_hop_le:
        ma_trang_thai = "chua_san_sang"
    else:
        ma_trang_thai = "trong"

    nhan, ly_do, lop_css, co_the_thue = TRANG_THAI_CONG_KHAI[ma_trang_thai]
    phong.trang_thai_cong_khai = ma_trang_thai
    phong.trang_thai_hien_thi = nhan
    phong.ly_do_trang_thai_cong_khai = ly_do
    phong.lop_trang_thai_cong_khai = lop_css
    phong.co_the_thue_cong_khai = co_the_thue
    phong.gia_thue_hop_le = gia_thue_hop_le
    return ma_trang_thai


def co_the_dat_phong_cong_khai(phong):
    """Match the read-only availability gate used before a tenant booking."""
    return gan_trang_thai_cong_khai(phong) == "trong"
