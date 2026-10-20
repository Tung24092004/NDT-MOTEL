"""Transactional repair-request lifecycle services."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.dich_vu.dat_phong import require_tenant
from core.dich_vu.hop_dong import require_admin
from core.dich_vu.luu_tru import queryset_hop_dong_luu_tru_hien_tai
from core.models import LichSuSuaChua, NguoiThue, Phong, YeuCauSuaChua


_FORWARD_TRANSITIONS = {
    "moi": {"dang_xu_ly", "tu_choi"},
    "dang_xu_ly": {"cho_thay_the", "hoan_thanh"},
    "cho_thay_the": {"hoan_thanh"},
    "hoan_thanh": set(),
    "tu_choi": set(),
}

_HISTORY_ACTIONS = {
    "dang_xu_ly": "xu_ly",
    "cho_thay_the": "cho_thay_the",
    "hoan_thanh": "hoan_thanh",
    "tu_choi": "tu_choi",
}


def _current_tenant_for_actor(actor, tenant_id):
    if not actor or not actor.is_authenticated or actor.is_staff or actor.is_superuser:
        raise PermissionDenied("Chi nguoi thue duoc gui yeu cau sua chua.")
    tenant = NguoiThue.objects.select_for_update().filter(pk=tenant_id).first()
    if not tenant:
        raise ValidationError("Khong tim thay ho so nguoi thue.")
    require_tenant(actor, tenant)
    return tenant


@transaction.atomic
def create_repair_request(*, actor, tenant_id, room_id, title, content, issue_type,
                          priority, image=None, cost=Decimal("0"), cost_detail="",
                          admin_note=""):
    """Create a repair request only for a tenant's current primary tenancy."""
    if actor and (actor.is_staff or actor.is_superuser):
        require_admin(actor)
        tenant = NguoiThue.objects.select_for_update().filter(
            pk=tenant_id, dang_hoat_dong=True
        ).first()
        if not tenant:
            raise ValidationError("Khong tim thay ho so nguoi thue dang hoat dong.")
    else:
        tenant = _current_tenant_for_actor(actor, tenant_id)

    room = Phong.objects.select_for_update().get(pk=room_id)
    if not queryset_hop_dong_luu_tru_hien_tai(nguoi_thue=tenant, phong=room).select_for_update().exists():
        raise ValidationError("Phong khong thuoc hop dong luu tru hien tai cua nguoi thue.")

    repair = YeuCauSuaChua.objects.create(
        nguoi_thue=tenant, phong=room, tieu_de=title, noi_dung=content,
        loai_su_co=issue_type, muc_do=priority, hinh_anh=image,
        trang_thai="moi", nguoi_xu_ly="", chi_phi=cost,
        chi_tiet_chi_phi=cost_detail, ghi_chu_admin=admin_note,
    )
    LichSuSuaChua.objects.create(
        yeu_cau=repair, hanh_dong="tao", trang_thai_moi="moi",
        noi_dung="Tao yeu cau sua chua.", nguoi_thuc_hien=actor,
    )
    return repair


@transaction.atomic
def transition_repair_request(*, actor, repair_id, target_status, handler, cost,
                              cost_detail, admin_note):
    """Advance one repair request once, under a row lock and with history."""
    require_admin(actor)
    repair = YeuCauSuaChua.objects.select_for_update().get(pk=repair_id)
    allowed = _FORWARD_TRANSITIONS.get(repair.trang_thai, set())
    if target_status not in allowed:
        raise ValidationError("Chuyen trang thai sua chua khong hop le.")
    if target_status == "dang_xu_ly" and not handler:
        raise ValidationError("Khi chuyen sang Dang xu ly, vui long nhap nguoi xu ly.")

    old_status = repair.trang_thai
    now = timezone.now()
    repair.trang_thai = target_status
    repair.nguoi_xu_ly = handler
    repair.chi_phi = cost
    repair.chi_tiet_chi_phi = cost_detail
    repair.ghi_chu_admin = admin_note
    repair.nguoi_xu_ly_user = actor
    if target_status == "dang_xu_ly":
        repair.ngay_bat_dau_xu_ly = now
    if target_status == "hoan_thanh":
        repair.ngay_hoan_thanh = now
    repair.save()
    LichSuSuaChua.objects.create(
        yeu_cau=repair, hanh_dong=_HISTORY_ACTIONS[target_status],
        trang_thai_cu=old_status, trang_thai_moi=target_status,
        noi_dung="Chuyen trang thai sua chua: %s -> %s." % (old_status, target_status),
        nguoi_thuc_hien=actor,
    )
    return repair
