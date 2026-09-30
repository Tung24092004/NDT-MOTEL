"""Dieu kien o ghep dung chung cho chi tiet phong va dang ky."""
from django.utils import timezone

from core.models import HopDong
from core.dich_vu.dat_phong import room_has_hold


def dieu_kien_o_ghep(phong):
    today = timezone.localdate()
    contract = HopDong.objects.filter(
        dat_phong__phong=phong, dat_phong__trang_thai="da_duyet",
        dat_phong__nguoi_thue__dang_hoat_dong=True,
        trang_thai__in=("dang_hieu_luc", "sap_het_han"),
        ngay_bat_dau__lte=today, ngay_ket_thuc__gte=today,
    ).select_related("dat_phong__nguoi_thue").order_by("-id").first()
    capacity = phong.so_nguoi_toi_da or 0
    occupants = 1 + contract.nguoi_o_cung.filter(trang_thai="dang_o").count() if contract else 0
    remaining = max(capacity - occupants, 0) if contract else 0
    enabled = bool(contract and contract.cho_phep_ghep)
    empty = not contract and phong.trang_thai == "trong" and not room_has_hold(phong)
    if phong.trang_thai == "bao_tri":
        reason = "Phòng đang bảo trì, không tiếp nhận đăng ký ở ghép."
    elif empty:
        reason = "Phòng này hiện đang trống. Người thuê có thể gửi yêu cầu đặt phòng."
    elif not contract:
        reason = "Phòng chưa có hợp đồng đang hiệu lực nên chưa mở đăng ký ở ghép."
    elif capacity <= 0:
        reason = "Phòng chưa cấu hình sức chứa."
    elif remaining <= 0:
        reason = "Phòng đã đủ sức chứa"
    elif not enabled:
        reason = "Phòng hiện chưa mở đăng ký ở ghép"
    else:
        reason = ""
    return {
        "hop_dong": contract, "so_nguoi_hien_tai": occupants,
        "cho_con_lai": remaining, "phong_trong_de_dat": empty,
        "phong_co_the_ghep": not reason,
        "phong_dang_cho_phep_ghep": enabled,
        "phong_con_cho_ghep": bool(contract and capacity > 0 and remaining > 0),
        "ly_do_khong_the_ghep": reason,
    }
