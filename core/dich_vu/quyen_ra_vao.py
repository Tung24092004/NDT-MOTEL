"""Canonical room-access grant lifecycle; a FaceProfile never grants access."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.dich_vu.luu_tru import danh_gia_hop_dong, nguoi_o_cung_du_dieu_kien, nguoi_thue_dang_luu_tru
from core.models import HopDong, NguoiOCungPhong, NguoiThue, Phong, QuyenRaVao
from core.quy_tac_nghiep_vu import KNOWN_PERMISSION_SOURCES


def _key(contract_id, room_id, tenant_id=None, resident_id=None):
    subject = f"tenant:{tenant_id}" if tenant_id else f"resident:{resident_id}"
    return f"contract:{contract_id}:room:{room_id}:{subject}"


def _lock_context(contract_id):
    # Lock order shared with residency writers: room -> contract -> subject -> right.
    stub = HopDong.objects.select_related("dat_phong").get(pk=contract_id)
    room = Phong.objects.select_for_update().get(pk=stub.dat_phong.phong_id)
    contract = HopDong.objects.select_for_update().select_related("dat_phong").get(pk=contract_id)
    return room, contract


@transaction.atomic
def grant_access(*, contract_id, tenant_id=None, resident_id=None, source, actor=None,
                 start_date=None, end_date=None, card_code="", note=""):
    """Create one active entitlement or return its existing equivalent."""
    if source not in KNOWN_PERMISSION_SOURCES or source == "duyet_ghep":
        raise ValidationError("Nguon cap quyen khong hop le cho luong hien tai.")
    if bool(tenant_id) == bool(resident_id):
        raise ValidationError("Quyen ra vao phai co dung mot chu the.")
    room, contract = _lock_context(contract_id)
    if not danh_gia_hop_dong(contract).du_dieu_kien:
        raise ValidationError("Hop dong khong con hieu luc de cap quyen ra vao.")
    if tenant_id:
        subject = NguoiThue.objects.select_for_update().get(pk=tenant_id)
        kind = "chu_phong"
        if subject.pk != contract.dat_phong.nguoi_thue_id or not nguoi_thue_dang_luu_tru(subject):
            raise ValidationError("Nguoi thue khong con du dieu kien luu tru.")
    else:
        subject = NguoiOCungPhong.objects.select_for_update().get(pk=resident_id)
        kind = "nguoi_o_cung"
        if subject.hop_dong_id != contract.pk or not nguoi_o_cung_du_dieu_kien(subject):
            raise ValidationError("Nguoi o cung khong con du dieu kien luu tru.")
    start_date = start_date or timezone.localdate()
    end_date = end_date or contract.ngay_ket_thuc
    if start_date < contract.ngay_bat_dau or start_date > contract.ngay_ket_thuc or end_date < start_date or end_date > contract.ngay_ket_thuc:
        raise ValidationError("Thoi han quyen nam ngoai thoi han hop dong.")
    key = _key(contract.pk, room.pk, tenant_id=tenant_id, resident_id=resident_id)
    existing = QuyenRaVao.objects.select_for_update().filter(active_access_key=key).first()
    if existing:
        return existing, False
    try:
        # Keep the unique-key race isolated in a savepoint so the outer
        # lifecycle transaction remains queryable on an idempotent retry.
        with transaction.atomic():
            right = QuyenRaVao.objects.create(
                hop_dong=contract, phong=room, nguon_cap=source, loai_quyen=kind,
                trang_thai="hoat_dong", ngay_bat_dau=start_date, ngay_ket_thuc=end_date,
                ma_the=card_code, ghi_chu=note, nguoi_tao=actor,
                nguoi_thue_id=tenant_id, nguoi_o_cung_id=resident_id,
                active_access_key=key,
            )
        return right, True
    except IntegrityError:
        return QuyenRaVao.objects.select_for_update().get(active_access_key=key), False


@transaction.atomic
def revoke_access(*, permission_id, status="bi_thu_hoi", end_date=None, note=""):
    """Idempotently close a grant while retaining its history."""
    if status not in ("bi_thu_hoi", "het_han"):
        raise ValidationError("Trang thai thu hoi quyen khong hop le.")
    right = QuyenRaVao.objects.select_for_update().get(pk=permission_id)
    if right.trang_thai in ("bi_thu_hoi", "het_han"):
        return right, False
    right.trang_thai, right.active_access_key = status, None
    end_date = end_date or timezone.localdate()
    if not right.ngay_ket_thuc or right.ngay_ket_thuc > end_date:
        right.ngay_ket_thuc = end_date
    if note and note not in (right.ghi_chu or ""):
        right.ghi_chu = f"{right.ghi_chu or ''}\n{note}".strip()
    right.save(update_fields=["trang_thai", "active_access_key", "ngay_ket_thuc", "ghi_chu", "ngay_cap_nhat"])
    return right, True
