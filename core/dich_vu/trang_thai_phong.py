"""Atomic room operational-state transitions."""

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from core.dich_vu.dat_phong import room_has_hold
from core.dich_vu.hop_dong import require_admin
from core.models import DatPhong, HopDong, Phong


def _lock_room_context(room):
    """Keep room -> booking -> contract order used by booking and activation."""
    list(DatPhong.objects.select_for_update().filter(phong=room).only("pk"))
    today = timezone.localdate()
    contract_conflict = HopDong.objects.select_for_update().filter(
        dat_phong__phong=room,
    ).filter(
        # A draft/review/accepted contract has already consumed this room's
        # booking hold.  Current contracts are also an occupancy conflict.
        # Lock the matching rows after their bookings, matching activation.
        (
            models.Q(trang_thai__in=(
                "nhap", "cho_nguoi_thue_xac_nhan", "yeu_cau_chinh_sua",
                "cho_kich_hoat", "cho_hieu_luc",
            ))
            | models.Q(
                trang_thai__in=("dang_hieu_luc", "sap_het_han"),
                ngay_bat_dau__lte=today,
                ngay_ket_thuc__gte=today,
            )
        )
    ).exists()
    return contract_conflict


@transaction.atomic
def transition_room_maintenance(*, actor, room_id, entering):
    """Enter or leave maintenance only after current room facts are locked."""
    require_admin(actor)
    room = Phong.objects.select_for_update().select_related("co_so").get(pk=room_id)
    contract_conflict = _lock_room_context(room)
    has_hold = room_has_hold(room)

    if entering:
        if has_hold or contract_conflict or room.trang_thai_nghiep_vu() != "trong":
            raise ValidationError(
                "Không thể chuyển phòng sang bảo trì vì phòng đang có lượt giữ chỗ hoặc hợp đồng còn hiệu lực."
            )
        if room.trang_thai != "bao_tri":
            room.trang_thai = "bao_tri"
            room.save(update_fields=["trang_thai", "ngay_cap_nhat"])
        return room

    # Do not restore a stale "trong" value over a hold or current tenancy.
    if contract_conflict:
        target_status = "dang_thue"
    elif has_hold:
        target_status = "da_dat"
    else:
        target_status = room.trang_thai_nghiep_vu()
    if room.trang_thai != target_status:
        room.trang_thai = target_status
        room.save(update_fields=["trang_thai", "ngay_cap_nhat"])
    return room
