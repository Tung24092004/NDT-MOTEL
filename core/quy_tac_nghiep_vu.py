"""Small read-only rules shared by business writers; no lifecycle side effects."""
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q
from core.dich_vu.luu_tru import (
    TRANG_THAI_DA_TRA_PHONG,
    hop_dong_dang_hieu_luc,
)


KNOWN_PERMISSION_SOURCES = ("thu_cong", "face_id", "duyet_ghep")
AUTO_PERMISSION_SOURCES = ("face_id", "duyet_ghep")


def dong_bo_hoa_don_qua_han(queryset=None, today=None):
    """Persist overdue invoices from an explicit job/command only."""
    from .models import HoaDon

    if today is None:
        today = timezone.localdate()

    if queryset is None:
        queryset = HoaDon.objects.all()

    with transaction.atomic():
        return queryset.filter(
            trang_thai="chua_thanh_toan",
            han_thanh_toan__isnull=False,
            han_thanh_toan__lt=today,
        ).update(
            trang_thai="qua_han",
            ngay_cap_nhat=timezone.now(),
        )


def contract_is_current(contract):
    return hop_dong_dang_hieu_luc(contract)


def permission_binding_is_valid(permission):
    """Structural provenance only; never infer a contract for legacy rows."""
    if not permission.hop_dong_id or permission.nguon_cap not in KNOWN_PERMISSION_SOURCES:
        return False
    booking = permission.hop_dong.dat_phong
    if permission.phong_id != booking.phong_id:
        return False
    if permission.loai_quyen == "chu_phong":
        return bool(permission.nguoi_thue_id == booking.nguoi_thue_id
                    and not permission.nguoi_o_cung_id)
    if permission.loai_quyen == "nguoi_o_cung":
        return bool(permission.nguoi_o_cung_id and not permission.nguoi_thue_id
                    and permission.nguoi_o_cung.hop_dong_id == permission.hop_dong_id)
    return False  # No supported guest provenance workflow yet.


def eligible_permissions(queryset):
    """Filter before selecting a row, shared by camera and access simulation."""
    today = timezone.localdate()
    return queryset.filter(
        hop_dong__isnull=False, nguon_cap__in=KNOWN_PERMISSION_SOURCES,
        trang_thai="hoat_dong", ngay_bat_dau__lte=today,
        phong_id=F("hop_dong__dat_phong__phong_id"),
        hop_dong__dat_phong__trang_thai="da_duyet",
        hop_dong__trang_thai__in=("dang_hieu_luc", "sap_het_han"),
        hop_dong__ngay_bat_dau__lte=today, hop_dong__ngay_ket_thuc__gte=today,
    ).filter(Q(ngay_ket_thuc__isnull=True) | Q(ngay_ket_thuc__gte=today)).filter(
        Q(
            loai_quyen="chu_phong",
            nguoi_o_cung__isnull=True,
            nguoi_thue_id=F("hop_dong__dat_phong__nguoi_thue_id"),
            nguoi_thue__dang_hoat_dong=True,
            nguoi_thue__trang_thai_luu_tru__in=("dang_o", "tam_vang"),
        )
        | Q(
            loai_quyen="nguoi_o_cung",
            nguoi_thue__isnull=True,
            nguoi_o_cung__hop_dong_id=F("hop_dong_id"),
            nguoi_o_cung__trang_thai="dang_o",
            nguoi_o_cung__da_xac_minh_boi_admin=True,
            nguoi_o_cung__ngay_vao__lte=today,
        ) & (
            Q(nguoi_o_cung__ngay_ra__isnull=True)
            | Q(nguoi_o_cung__ngay_ra__gte=today)
        )
    )
