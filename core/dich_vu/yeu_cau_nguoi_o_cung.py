"""Atomic co-tenant request and direct-admit core; HTTP/UI layers are absent."""
from hashlib import sha256
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.booking_identifiers import normalize_cccd, normalize_companion_cccd
from core.dich_vu.luu_tru import (
    danh_gia_hop_dong, nguoi_thue_dang_luu_tru, thu_hoi_quyen_nguoi_o_cung,
)
from core.dich_vu.phu_luc_hop_dong import ghi_nhan_thay_doi_cu_tru
from core.models import (
    DanhTinhNguoiOCung, HopDong, NguoiOCungPhong, NguoiThue, PhuLucHopDong,
    ThongBao, YeuCauNguoiOCung,
)
from core.tien_ich import ghi_nhat_ky


PENDING_STATES = ("cho_xac_minh", "cho_bo_sung")
TERMINAL_STATES = ("da_duyet", "tu_choi", "da_huy")


def _audit(actor, action, request):
    # ghi_nhat_ky is intentionally best-effort project-wide.  It owns its
    # exception handling, so an audit storage error never undoes domain core.
    try:
        ghi_nhat_ky(
            SimpleNamespace(user=actor, META={}), action, module="nguoi_o_cung",
            doi_tuong="YeuCauNguoiOCung", doi_tuong_id=request.pk,
            tieu_de="Co-tenant request", noi_dung=request.trang_thai,
            du_lieu_moi={"revision": request.revision, "trang_thai": request.trang_thai},
        )
    except Exception:
        pass


def _audit_direct_admit(actor, resident, idempotency_key):
    try:
        ghi_nhat_ky(
            SimpleNamespace(user=actor, META={}), "direct_admit_nguoi_o_cung",
            module="nguoi_o_cung", doi_tuong="NguoiOCungPhong",
            doi_tuong_id=resident.pk, tieu_de="Admin direct-admit co-tenant",
            noi_dung="Direct-admit da co hieu luc.",
            du_lieu_moi={"idempotency_key": idempotency_key},
        )
    except Exception:
        pass


def _audit_residency_lifecycle(actor, action, resident, idempotency_key):
    """Best-effort audit, consistent with the project-wide audit policy."""
    try:
        ghi_nhat_ky(
            SimpleNamespace(user=actor, META={}), action, module="nguoi_o_cung",
            doi_tuong="NguoiOCungPhong", doi_tuong_id=resident.pk,
            tieu_de="Co-tenant residency lifecycle",
            noi_dung=resident.trang_thai,
            du_lieu_moi={"idempotency_key": idempotency_key},
        )
    except Exception:
        pass


def _locked_request(request_id):
    request = YeuCauNguoiOCung.objects.select_for_update().select_related("hop_dong__dat_phong__phong", "nguoi_yeu_cau").get(pk=request_id)
    return request


def _require_active_request_contract(request):
    if not danh_gia_hop_dong(request.hop_dong).du_dieu_kien:
        raise ValidationError("Hop dong khong con hieu luc.")
    if not nguoi_thue_dang_luu_tru(
        request.hop_dong.dat_phong.nguoi_thue, request.hop_dong
    ):
        raise ValidationError("Nguoi thue chinh khong con o trang thai luu tru.")


def _lock_contract_context(contract_id):
    """Canonical write lock order: room, contract, then request/identity."""
    contract = HopDong.objects.select_related("dat_phong__phong", "dat_phong__nguoi_thue").get(pk=contract_id)
    room_model = contract.dat_phong.phong.__class__
    room_model.objects.select_for_update().get(pk=contract.dat_phong.phong_id)
    return HopDong.objects.select_for_update().select_related(
        "dat_phong__phong", "dat_phong__nguoi_thue"
    ).get(pk=contract_id)


def _direct_admit_appendix_code(contract_id, idempotency_key):
    digest = sha256(idempotency_key.encode("utf-8")).hexdigest()[:32]
    return f"PL-DA-{contract_id}-{digest}"


def _residency_lifecycle_appendix_code(prefix, residency_id, idempotency_key):
    digest = sha256(idempotency_key.encode("utf-8")).hexdigest()[:32]
    return f"PL-{prefix}-{residency_id}-{digest}"


def _require_admin(actor):
    if not getattr(actor, "is_authenticated", False) or not (
        actor.is_staff or actor.is_superuser
    ):
        raise ValidationError("Khong co quyen xu ly luu tru nguoi o cung.")


def _require_idempotency_key(idempotency_key):
    if not idempotency_key or len(idempotency_key) > 64:
        raise ValidationError("Idempotency key khong hop le.")


def _resolve_locked_identity(cccd):
    try:
        return DanhTinhNguoiOCung.objects.select_for_update().get(cccd=cccd)
    except DanhTinhNguoiOCung.DoesNotExist:
        try:
            with transaction.atomic():
                return DanhTinhNguoiOCung.objects.create(cccd=cccd)
        except IntegrityError:
            return DanhTinhNguoiOCung.objects.select_for_update().get(cccd=cccd)


@transaction.atomic
def direct_admit(*, contract_id, actor, idempotency_key, **candidate):
    """Admit a verified co-tenant without manufacturing a tenant request.

    Lock order remains room -> contract -> identity -> active residency.  The
    unique active-identity key is the final database protection; the uniquely
    keyed appendix is the durable direct-admit idempotency record.
    """
    if not getattr(actor, "is_authenticated", False) or not (actor.is_staff or actor.is_superuser):
        raise ValidationError("Khong co quyen direct-admit nguoi o cung.")
    _require_idempotency_key(idempotency_key)
    ho_ten = (candidate.get("ho_ten") or "").strip()
    if not ho_ten:
        raise ValidationError("Ho ten la bat buoc.")
    cccd = normalize_companion_cccd(candidate.get("cccd"))
    if not cccd:
        raise ValidationError("CCCD hop le la bat buoc.")
    ngay_vao = candidate.get("ngay_vao")
    if not ngay_vao:
        raise ValidationError("Ngay vao la bat buoc.")

    contract = _lock_contract_context(contract_id)
    if not danh_gia_hop_dong(contract).du_dieu_kien:
        raise ValidationError("Hop dong khong con hieu luc.")
    if ngay_vao < contract.ngay_bat_dau or ngay_vao > contract.ngay_ket_thuc:
        raise ValidationError("Ngay vao nam ngoai thoi han hop dong.")
    if NguoiThue.objects.filter(cccd=cccd).exists():
        raise ValidationError("CCCD nay thuoc nguoi thue chinh.")

    appendix_code = _direct_admit_appendix_code(contract.pk, idempotency_key)
    prior_appendix = PhuLucHopDong.objects.filter(ma_phu_luc=appendix_code).first()
    if prior_appendix:
        if prior_appendix.hop_dong_id != contract.pk:
            raise ValidationError("Idempotency key da thuoc direct-admit khac.")
        resident_id = (prior_appendix.du_lieu_snapshot or {}).get("resident_id")
        resident = NguoiOCungPhong.objects.select_for_update().get(pk=resident_id)
        return resident, False

    room = contract.dat_phong.phong
    active_count = NguoiOCungPhong.objects.filter(
        hop_dong=contract, trang_thai="dang_o"
    ).count()
    if room.so_nguoi_toi_da <= 0 or 1 + active_count >= room.so_nguoi_toi_da:
        raise ValidationError("Phong da du suc chua.")

    identity = _resolve_locked_identity(cccd)
    active_residency = (
        NguoiOCungPhong.objects.select_for_update()
        .filter(identity=identity, trang_thai="dang_o").first()
    )
    if active_residency:
        raise ValidationError("CCCD da thuoc mot nguoi o cung dang luu tru.")

    try:
        resident = NguoiOCungPhong.objects.create(
            hop_dong=contract, identity=identity, ho_ten=ho_ten,
            ngay_sinh=candidate.get("ngay_sinh"),
            gioi_tinh=candidate.get("gioi_tinh", ""), cccd=cccd,
            so_dien_thoai=candidate.get("so_dien_thoai", ""),
            quan_he=candidate.get("quan_he", ""), ngay_vao=ngay_vao,
            trang_thai="dang_o", da_xac_minh_boi_admin=True,
        )
    except IntegrityError as exc:
        raise ValidationError("CCCD da thuoc mot nguoi o cung dang luu tru.") from exc

    ghi_nhan_thay_doi_cu_tru(
        resident=resident, event="them_sau_ky", actor=actor,
        reason="Admin direct-admit verified co-tenant.",
        ma_tham_chieu=appendix_code,
    )
    ThongBao.objects.get_or_create(
        nguoi_thue=contract.dat_phong.nguoi_thue,
        ma_tham_chieu=f"COTENANT_DIRECT_ADMIT:{contract.pk}:{idempotency_key}",
        defaults={
            "loai": "hop_dong", "tieu_de": "Nguoi o cung da duoc them",
            "noi_dung": "Admin da ghi nhan nguoi o cung da xac minh.",
            "url_lien_ket": f"/hop-dong-cua-toi/{contract.pk}/",
        },
    )
    _audit_direct_admit(actor, resident, idempotency_key)
    return resident, True


@transaction.atomic
def leave_residency(*, residency_id, actor, idempotency_key, leave_date=None):
    """Close an active residency without deleting its identity or history.

    Lock order is room -> contract -> identity -> residency/active-key, matching
    direct-admit and approval.  Access revocation is a transactional existing
    service; audit is deliberately best-effort.  There is no DB notification
    convention for leave/return, so this service does not introduce one.
    """
    _require_admin(actor)
    _require_idempotency_key(idempotency_key)
    stub = NguoiOCungPhong.objects.only("hop_dong_id", "identity_id").get(pk=residency_id)
    contract = _lock_contract_context(stub.hop_dong_id)
    identity = DanhTinhNguoiOCung.objects.select_for_update().get(pk=stub.identity_id)
    resident = NguoiOCungPhong.objects.select_for_update().get(pk=residency_id)
    if resident.hop_dong_id != contract.pk or resident.identity_id != identity.pk:
        raise ValidationError("Residency khong con khop hop dong hoac danh tinh.")
    if resident.trang_thai == "da_roi":
        return resident, False
    if resident.trang_thai != "dang_o":
        raise ValidationError("Chi residency dang o moi co the ghi nhan roi phong.")
    if not danh_gia_hop_dong(contract).du_dieu_kien:
        raise ValidationError("Hop dong khong con hieu luc.")
    leave_date = leave_date or timezone.localdate()
    if leave_date < resident.ngay_vao:
        raise ValidationError("Ngay roi khong duoc truoc ngay vao.")

    appendix_code = _residency_lifecycle_appendix_code("LV", resident.pk, idempotency_key)
    resident.trang_thai = "da_roi"
    resident.ngay_ra = leave_date
    resident.save(update_fields=["trang_thai", "ngay_ra", "active_identity_key", "ngay_cap_nhat"])
    ghi_nhan_thay_doi_cu_tru(
        resident=resident, event="roi_sau_ky", actor=actor,
        reason="Admin ghi nhan nguoi o cung roi phong.",
        ma_tham_chieu=appendix_code,
    )
    thu_hoi_quyen_nguoi_o_cung(
        resident, ngay_thu_hoi=leave_date, nguon="Admin", trang_thai="bi_thu_hoi"
    )
    _audit_residency_lifecycle(actor, "cotenant_residency_left", resident, idempotency_key)
    return resident, True


@transaction.atomic
def return_as_new_residency(*, residency_id, actor, idempotency_key, entry_date=None):
    """Return a departed person as a new residency row, never reactivate history."""
    _require_admin(actor)
    _require_idempotency_key(idempotency_key)
    stub = NguoiOCungPhong.objects.only("hop_dong_id", "identity_id").get(pk=residency_id)
    contract = _lock_contract_context(stub.hop_dong_id)
    identity = DanhTinhNguoiOCung.objects.select_for_update().get(pk=stub.identity_id)
    previous = NguoiOCungPhong.objects.select_for_update().get(pk=residency_id)
    if previous.hop_dong_id != contract.pk or previous.identity_id != identity.pk:
        raise ValidationError("Residency khong con khop hop dong hoac danh tinh.")
    if previous.trang_thai != "da_roi":
        raise ValidationError("Chi residency da roi moi co the quay lai bang dot moi.")
    if not previous.da_xac_minh_boi_admin:
        raise ValidationError("Can Admin xac minh ho so truoc khi ghi nhan quay lai.")
    if not danh_gia_hop_dong(contract).du_dieu_kien:
        raise ValidationError("Hop dong khong con hieu luc.")
    entry_date = entry_date or timezone.localdate()
    if entry_date < contract.ngay_bat_dau or entry_date > contract.ngay_ket_thuc:
        raise ValidationError("Ngay vao nam ngoai thoi han hop dong.")

    appendix_code = _residency_lifecycle_appendix_code("RT", previous.pk, idempotency_key)
    prior_appendix = PhuLucHopDong.objects.filter(ma_phu_luc=appendix_code).first()
    if prior_appendix:
        resident_id = (prior_appendix.du_lieu_snapshot or {}).get("resident_id")
        if not resident_id:
            raise ValidationError("Du lieu idempotency quay lai khong hop le.")
        return NguoiOCungPhong.objects.select_for_update().get(pk=resident_id), False

    active = NguoiOCungPhong.objects.select_for_update().filter(
        identity=identity, trang_thai="dang_o"
    ).first()
    if active:
        raise ValidationError("CCCD da thuoc mot nguoi o cung dang luu tru.")
    room = contract.dat_phong.phong
    active_count = NguoiOCungPhong.objects.filter(hop_dong=contract, trang_thai="dang_o").count()
    if room.so_nguoi_toi_da <= 0 or 1 + active_count >= room.so_nguoi_toi_da:
        raise ValidationError("Phong da du suc chua.")
    try:
        resident = NguoiOCungPhong.objects.create(
            hop_dong=contract, identity=identity, ho_ten=previous.ho_ten,
            ngay_sinh=previous.ngay_sinh, gioi_tinh=previous.gioi_tinh,
            cccd=identity.cccd or previous.cccd, so_dien_thoai=previous.so_dien_thoai,
            quan_he=previous.quan_he, ngay_vao=entry_date, trang_thai="dang_o",
            da_xac_minh_boi_admin=True, ghi_chu=previous.ghi_chu,
        )
    except IntegrityError as exc:
        raise ValidationError("CCCD da thuoc mot nguoi o cung dang luu tru.") from exc
    ghi_nhan_thay_doi_cu_tru(
        resident=resident, event="them_sau_ky", actor=actor,
        reason="Admin ghi nhan nguoi o cung quay lai bang dot luu tru moi.",
        ma_tham_chieu=appendix_code,
    )
    _audit_residency_lifecycle(actor, "cotenant_residency_returned", resident, idempotency_key)
    return resident, True


def close_active_residencies_for_contract(*, contract, leave_date, access_status, access_source):
    """Close active co-tenant stays because their parent tenancy has ended.

    The caller owns the parent contract lifecycle transaction.  This primitive
    deliberately creates neither per-person appendices nor notifications: the
    contract termination is the effective parent event.  It locks identities
    before their residency rows, matching voluntary leave/return.
    """
    resident_refs = list(
        NguoiOCungPhong.objects.filter(hop_dong=contract, trang_thai="dang_o")
        .order_by("identity_id", "pk")
        .values_list("pk", "identity_id")
    )
    closed = 0
    for resident_id, identity_id in resident_refs:
        DanhTinhNguoiOCung.objects.select_for_update().get(pk=identity_id)
        resident = NguoiOCungPhong.objects.select_for_update().get(pk=resident_id)
        if resident.hop_dong_id != contract.pk or resident.trang_thai != "dang_o":
            continue
        resident.trang_thai = "da_roi"
        resident.ngay_ra = leave_date
        resident.save(update_fields=["trang_thai", "ngay_ra", "active_identity_key", "ngay_cap_nhat"])
        thu_hoi_quyen_nguoi_o_cung(
            resident, ngay_thu_hoi=leave_date, nguon=access_source,
            trang_thai=access_status,
        )
        closed += 1
    return closed


@transaction.atomic
def create_request(*, contract_id, actor, idempotency_key, **candidate):
    """Create once for a stable client key; pending records are not residencies."""
    if not idempotency_key or len(idempotency_key) > 64:
        raise ValidationError("Idempotency key khong hop le.")
    contract = _lock_contract_context(contract_id)
    if contract.dat_phong.nguoi_thue.tai_khoan_id != actor.id:
        raise ValidationError("Khong co quyen tao request cho hop dong nay.")
    if not danh_gia_hop_dong(contract).du_dieu_kien:
        raise ValidationError("Hop dong khong con hieu luc.")
    cccd = normalize_companion_cccd(candidate.get("cccd"))
    if not cccd:
        raise ValidationError("CCCD hop le la bat buoc.")
    existing = YeuCauNguoiOCung.objects.filter(ma_idempotency=idempotency_key).first()
    if existing:
        if existing.hop_dong_id != contract.pk or existing.nguoi_yeu_cau_id != contract.dat_phong.nguoi_thue_id:
            raise ValidationError("Idempotency key da thuoc request khac.")
        return existing, False
    identity = DanhTinhNguoiOCung.objects.filter(cccd=cccd).first()
    try:
        request = YeuCauNguoiOCung.objects.create(
            hop_dong=contract, nguoi_yeu_cau=contract.dat_phong.nguoi_thue,
            identity=identity, ma_idempotency=idempotency_key, cccd=cccd,
            ho_ten=candidate["ho_ten"], ngay_vao=candidate["ngay_vao"],
            ngay_sinh=candidate.get("ngay_sinh"), gioi_tinh=candidate.get("gioi_tinh", ""),
            so_dien_thoai=candidate.get("so_dien_thoai", ""), quan_he=candidate.get("quan_he", ""),
        )
    except IntegrityError:
        # A concurrent retry can win the unique key; resolve only that key.
        request = YeuCauNguoiOCung.objects.get(ma_idempotency=idempotency_key)
        if request.hop_dong_id != contract.pk:
            raise ValidationError("Idempotency key da thuoc request khac.")
        return request, False
    _audit(actor, "tao_yeu_cau_nguoi_o_cung", request)
    return request, True


def _transition(*, request_id, actor, expected_revision, allowed, target, reason=""):
    request = _locked_request(request_id)
    _require_active_request_contract(request)
    if request.revision != expected_revision or request.trang_thai not in allowed:
        return request, False
    request.trang_thai = target
    request.revision += 1
    request.ly_do = reason
    if target in ("da_huy", "tu_choi"):
        request.nguoi_xu_ly, request.ngay_xu_ly = actor, timezone.now()
    request.save()
    _audit(actor, f"cotenant_request_{target}", request)
    return request, True


@transaction.atomic
def cancel_request(*, request_id, actor, expected_revision):
    request = _locked_request(request_id)
    if request.nguoi_yeu_cau.tai_khoan_id != actor.id:
        raise ValidationError("Khong co quyen huy request nay.")
    _require_active_request_contract(request)
    if request.revision != expected_revision or request.trang_thai not in ("cho_xac_minh", "cho_bo_sung"):
        return request, False
    request.trang_thai, request.revision, request.nguoi_xu_ly, request.ngay_xu_ly = "da_huy", request.revision + 1, actor, timezone.now()
    request.save()
    _audit(actor, "cotenant_request_da_huy", request)
    return request, True


@transaction.atomic
def request_supplement(*, request_id, actor, expected_revision, reason):
    if not reason.strip(): raise ValidationError("Can ly do bo sung.")
    return _transition(request_id=request_id, actor=actor, expected_revision=expected_revision, allowed=("cho_xac_minh",), target="cho_bo_sung", reason=reason)


@transaction.atomic
def resubmit_request(*, request_id, actor, expected_revision, **changes):
    request = _locked_request(request_id)
    if request.nguoi_yeu_cau.tai_khoan_id != actor.id: raise ValidationError("Khong co quyen sua request nay.")
    _require_active_request_contract(request)
    if request.revision != expected_revision or request.trang_thai != "cho_bo_sung": return request, False
    for field in ("ho_ten", "ngay_sinh", "gioi_tinh", "cccd", "so_dien_thoai", "quan_he", "ngay_vao"):
        if field in changes: setattr(request, field, changes[field])
    request.cccd = normalize_companion_cccd(request.cccd) or ""
    if not request.cccd:
        raise ValidationError("CCCD hop le la bat buoc.")
    request.identity = DanhTinhNguoiOCung.objects.filter(cccd=request.cccd).first()
    request.trang_thai, request.revision, request.ly_do = "cho_xac_minh", request.revision + 1, ""
    request.save()
    _audit(actor, "cotenant_request_resubmit", request)
    return request, True


@transaction.atomic
def reject_request(*, request_id, actor, expected_revision, reason):
    if not reason.strip(): raise ValidationError("Can ly do tu choi.")
    return _transition(request_id=request_id, actor=actor, expected_revision=expected_revision, allowed=("cho_xac_minh", "cho_bo_sung"), target="tu_choi", reason=reason)


@transaction.atomic
def approve_request(*, request_id, actor, expected_revision):
    """Approve one pending request after rechecking the active residency gates."""
    _require_admin(actor)
    request_stub = YeuCauNguoiOCung.objects.only("hop_dong_id").get(pk=request_id)
    contract = _lock_contract_context(request_stub.hop_dong_id)
    request = _locked_request(request_id)
    if request.revision != expected_revision or request.trang_thai != "cho_xac_minh":
        return request, False
    _require_active_request_contract(request)
    if request.nguoi_yeu_cau_id != contract.dat_phong.nguoi_thue_id:
        raise ValidationError("Owner request khong khop hop dong.")

    # ``_lock_contract_context`` already holds room -> contract.  Reuse the
    # direct-admit capacity rule before locking the candidate identity.
    room = contract.dat_phong.phong
    active_count = NguoiOCungPhong.objects.filter(
        hop_dong=contract, trang_thai="dang_o"
    ).count()
    if room.so_nguoi_toi_da <= 0 or 1 + active_count >= room.so_nguoi_toi_da:
        raise ValidationError("Phong da du suc chua.")

    identity = _resolve_locked_identity(request.cccd)
    active_residency = NguoiOCungPhong.objects.select_for_update().filter(
        identity=identity, trang_thai="dang_o"
    ).first()
    if active_residency:
        raise ValidationError("CCCD da thuoc mot nguoi o cung dang luu tru.")
    try:
        resident = NguoiOCungPhong.objects.create(
            hop_dong=contract, identity=identity, ho_ten=request.ho_ten,
            ngay_sinh=request.ngay_sinh, gioi_tinh=request.gioi_tinh,
            cccd=request.cccd, so_dien_thoai=request.so_dien_thoai,
            quan_he=request.quan_he, ngay_vao=request.ngay_vao,
            trang_thai="dang_o", da_xac_minh_boi_admin=True,
        )
    except IntegrityError as exc:
        raise ValidationError("CCCD da thuoc mot nguoi o cung dang luu tru.") from exc
    request.identity = resident.identity
    request.residency = resident
    request.trang_thai = "da_duyet"
    request.revision += 1
    request.nguoi_xu_ly = actor
    request.ngay_xu_ly = timezone.now()
    request.save(update_fields=["identity", "residency", "trang_thai", "revision", "nguoi_xu_ly", "ngay_xu_ly", "ngay_cap_nhat"])
    ghi_nhan_thay_doi_cu_tru(resident=resident, event="them_sau_ky", actor=actor, reason="Admin approved co-tenant request.")
    ThongBao.objects.get_or_create(nguoi_thue=request.nguoi_yeu_cau, ma_tham_chieu=f"COTENANT_REQUEST:{request.pk}:APPROVED", defaults={"loai":"hop_dong", "tieu_de":"Yeu cau nguoi o cung da duoc duyet", "noi_dung":"Yeu cau da co hieu luc.", "url_lien_ket":f"/hop-dong-cua-toi/{contract.pk}/"})
    _audit(actor, "cotenant_request_da_duyet", request)
    return request, True
