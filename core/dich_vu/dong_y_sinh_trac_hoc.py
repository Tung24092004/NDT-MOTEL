"""Canonical, append-only consent events for co-tenant biometrics."""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from core.models import DanhTinhNguoiOCung, SuKienDongYSinhTracHoc


def _require_admin(actor):
    if not actor or not actor.is_authenticated or not (actor.is_staff or actor.is_superuser):
        raise PermissionDenied("Chi Quan tri vien duoc ghi nhan dong y sinh trac hoc.")


@transaction.atomic
def record_consent(*, identity_id, actor, purpose="face_id_v1", occurred_at=None):
    _require_admin(actor)
    identity = DanhTinhNguoiOCung.objects.select_for_update().get(pk=identity_id)
    latest = identity.su_kien_dong_y_sinh_trac_hoc.filter(
        ma_muc_dich=purpose
    ).select_for_update().order_by("-thoi_diem", "-pk").first()
    if latest and latest.su_kien == "dong_y":
        return latest, False
    event = SuKienDongYSinhTracHoc.objects.create(
        danh_tinh=identity, su_kien="dong_y", thoi_diem=occurred_at or timezone.now(),
        nguoi_ghi_nhan=actor, ma_muc_dich=purpose,
    )
    return event, True


@transaction.atomic
def withdraw_consent(*, identity_id, actor, purpose="face_id_v1", occurred_at=None):
    _require_admin(actor)
    identity = DanhTinhNguoiOCung.objects.select_for_update().get(pk=identity_id)
    latest = identity.su_kien_dong_y_sinh_trac_hoc.filter(
        ma_muc_dich=purpose
    ).select_for_update().order_by("-thoi_diem", "-pk").first()
    if latest and latest.su_kien == "rut_lai":
        return latest, False
    event = SuKienDongYSinhTracHoc.objects.create(
        danh_tinh=identity, su_kien="rut_lai", thoi_diem=occurred_at or timezone.now(),
        nguoi_ghi_nhan=actor, ma_muc_dich=purpose,
    )
    return event, True


def has_effective_consent(identity, *, purpose="face_id_v1"):
    if not identity:
        return False
    latest = identity.su_kien_dong_y_sinh_trac_hoc.filter(ma_muc_dich=purpose).order_by("-thoi_diem", "-pk").first()
    return bool(latest and latest.su_kien == "dong_y")
