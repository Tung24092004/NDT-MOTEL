"""Contract lifecycle writers shared by views and background commands."""
from django.db import transaction
from django.utils import timezone

from core.dich_vu.luu_tru import (
    TRANG_THAI_DA_TRA_PHONG,
    nguoi_thue_con_hop_dong_luu_tru_hieu_luc,
)
from core.dich_vu.yeu_cau_nguoi_o_cung import close_active_residencies_for_contract
from core.models import HopDong, LichSuHopDong


ACTIVE_CONTRACT_STATUSES = ("dang_hieu_luc", "sap_het_han")
TERMINAL_CONTRACT_STATUSES = ("da_huy", "da_het_han")


def du_doan_trang_thai_hop_dong(hop_dong, today=None):
    """Return the lifecycle status implied by dates without writing data."""
    if today is None:
        today = timezone.localdate()

    if hop_dong.trang_thai in (
        "nhap", "cho_nguoi_thue_xac_nhan", "yeu_cau_chinh_sua",
        "cho_kich_hoat", "da_huy",
    ):
        return hop_dong.trang_thai
    if today < hop_dong.ngay_bat_dau:
        return "cho_hieu_luc"
    if today > hop_dong.ngay_ket_thuc:
        return "da_het_han"
    if 0 <= (hop_dong.ngay_ket_thuc - today).days <= 30:
        return "sap_het_han"
    return "dang_hieu_luc"


def gan_trang_thai_hien_thi_hop_dong(hop_dong, today=None):
    """Mutate only the in-memory instance so GET pages can display fresh status."""
    hop_dong.trang_thai = du_doan_trang_thai_hop_dong(hop_dong, today=today)
    return hop_dong


def _append_note(value, note):
    value = (value or "").strip()
    note = (note or "").strip()
    return f"{value}\n{note}".strip() if value else note


def _permission_queryset_for_contract(hop_dong):
    return (
        hop_dong.quyen_ra_vao_theo_hop_dong.select_for_update()
        .exclude(nguon_cap="legacy_unknown")
        .filter(hop_dong=hop_dong)
    )


def _expire_or_revoke_permissions(hop_dong, *, status, end_date, reason):
    count = 0
    qs = (
        _permission_queryset_for_contract(hop_dong)
        .exclude(trang_thai__in=("het_han", "bi_thu_hoi"))
        .filter(phong_id=hop_dong.dat_phong.phong_id)
    )
    for right in qs:
        if right.loai_quyen == "chu_phong":
            valid_subject = (
                right.nguoi_thue_id == hop_dong.dat_phong.nguoi_thue_id
                and right.nguoi_o_cung_id is None
            )
        elif right.loai_quyen == "nguoi_o_cung":
            valid_subject = (
                right.nguoi_thue_id is None
                and right.nguoi_o_cung_id
                and right.nguoi_o_cung.hop_dong_id == hop_dong.id
            )
        else:
            valid_subject = False

        if not valid_subject:
            continue

        right.trang_thai = status
        right.active_access_key = None
        right.ngay_ket_thuc = end_date
        right.ghi_chu = _append_note(right.ghi_chu, reason)
        right.save(
            update_fields=[
                "trang_thai",
                "active_access_key",
                "ngay_ket_thuc",
                "ghi_chu",
                "ngay_cap_nhat",
            ]
        )
        count += 1
    return count


def _mark_companions_left(hop_dong, left_date, *, access_status, access_source):
    return close_active_residencies_for_contract(
        contract=hop_dong, leave_date=left_date, access_status=access_status,
        access_source=access_source,
    )


def _sync_primary_tenant_checkout(hop_dong, *, actor=None, reason=""):
    tenant = hop_dong.dat_phong.nguoi_thue
    if tenant.trang_thai_luu_tru == TRANG_THAI_DA_TRA_PHONG:
        return False
    if nguoi_thue_con_hop_dong_luu_tru_hieu_luc(
        tenant,
        exclude_contract_id=hop_dong.id,
    ):
        return False

    tenant.trang_thai_luu_tru = TRANG_THAI_DA_TRA_PHONG
    tenant.save(update_fields=["trang_thai_luu_tru", "ngay_cap_nhat"])
    return True


def _create_status_history(hop_dong, old_status, new_status):
    if old_status == new_status:
        return

    if new_status == "sap_het_han":
        action = "sap_het_han"
        text = (
            f"Hop dong {hop_dong.so_hop_dong} chuyen sang trang thai sap het han. "
            f"Ngay ket thuc: {hop_dong.ngay_ket_thuc.strftime('%d/%m/%Y')}."
        )
    elif new_status == "da_het_han":
        action = "het_han"
        text = (
            f"Hop dong {hop_dong.so_hop_dong} da het han sau ngay "
            f"{hop_dong.ngay_ket_thuc.strftime('%d/%m/%Y')}."
        )
    else:
        action = "cap_nhat"
        text = (
            f"He thong cap nhat trang thai hop dong {hop_dong.so_hop_dong} "
            f"tu {old_status} sang {new_status}."
        )

    LichSuHopDong.objects.get_or_create(
        hop_dong=hop_dong,
        hanh_dong=action,
        trang_thai_cu=old_status,
        trang_thai_moi=new_status,
        defaults={"noi_dung": text, "nguoi_thuc_hien": None, "dia_chi_ip": None},
    )


@transaction.atomic
def dong_bo_vong_doi_hop_dong(hop_dong, *, actor=None, today=None, reason=""):
    """Persist contract lifecycle side effects exactly once per current state."""
    if today is None:
        today = timezone.localdate()

    # Match co-tenant writers: room -> contract -> identity -> residency.
    stub = HopDong.objects.select_related("dat_phong__phong").get(pk=hop_dong.pk)
    stub.dat_phong.phong.__class__.objects.select_for_update().get(pk=stub.dat_phong.phong_id)
    hop_dong = HopDong.objects.select_for_update().select_related(
        "dat_phong", "dat_phong__nguoi_thue", "dat_phong__phong"
    ).get(pk=hop_dong.pk)
    old_status = hop_dong.trang_thai

    if old_status == "da_huy":
        _mark_companions_left(
            hop_dong, today, access_status="bi_thu_hoi", access_source="Contract cancelled",
        )
        _expire_or_revoke_permissions(
            hop_dong,
            status="bi_thu_hoi",
            end_date=today,
            reason=reason or "Thu hoi do hop dong da huy.",
        )
        _sync_primary_tenant_checkout(hop_dong, actor=actor, reason=reason)
        hop_dong.dat_phong.phong.dong_bo_trang_thai()
        return hop_dong

    new_status = du_doan_trang_thai_hop_dong(hop_dong, today=today)
    if old_status != new_status:
        hop_dong.trang_thai = new_status
        hop_dong.save(update_fields=["trang_thai", "ngay_cap_nhat"])
        _create_status_history(hop_dong, old_status, new_status)

    if new_status == "da_het_han":
        _mark_companions_left(
            hop_dong, today, access_status="het_han", access_source="Contract expired",
        )
        _expire_or_revoke_permissions(
            hop_dong,
            status="het_han",
            end_date=hop_dong.ngay_ket_thuc,
            reason=reason or "Het han theo vong doi hop dong.",
        )
        _sync_primary_tenant_checkout(hop_dong, actor=actor, reason=reason)

    hop_dong.dat_phong.phong.dong_bo_trang_thai()
    return hop_dong
