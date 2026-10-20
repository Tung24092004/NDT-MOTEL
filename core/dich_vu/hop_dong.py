"""Admin booking confirmation and contract creation service."""
import hashlib
import json
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import (
    DatPhong,
    HopDong,
    PhienBanHopDong,
    PhanHoiHopDong,
    KhaiBaoNguoiOCungDatPhong,
    LichSuHopDong,
    NhatKyThaoTac,
    Phong,
    ThanhToanCocDatPhong,
    ChungTuThanhToan,
    ThongBao,
)
from core.dich_vu.thong_bao_quan_tri import notify_admin_event, notify_booking_event
from core.dich_vu.dat_phong import room_has_rental_period_conflict
from core.dich_vu.ngay_thue import tinh_ngay_ket_thuc_theo_thang
from core.dich_vu.chung_tu_thanh_toan import mark_reviewed
from core.dich_vu.phu_luc_hop_dong import (
    dam_bao_ban_chup_hop_dong,
    du_lieu_phien_ban_review,
    snapshot_nguoi_o_cung_khi_ky,
)


def require_admin(actor):
    if not actor or not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Can dang nhap bang tai khoan Admin.")
    if not (actor.is_staff or actor.is_superuser):
        raise PermissionDenied("Chi Admin duoc xu ly doi soat dat phong.")


def _contract_status(start_date, end_date):
    today = timezone.localdate()
    if today < start_date:
        return "cho_hieu_luc"
    if today > end_date:
        return "da_het_han"
    if 0 <= (end_date - today).days <= 30:
        return "sap_het_han"
    return "dang_hieu_luc"


def _next_contract_number():
    year = timezone.localdate().year
    last = (
        HopDong.objects.select_for_update()
        .filter(so_hop_dong__startswith=f"HD-{year}-")
        .order_by("-id")
        .first()
    )
    number = 1
    if last:
        try:
            number = int(last.so_hop_dong.split("-")[-1]) + 1
        except (TypeError, ValueError, IndexError):
            number = 1
    return f"HD-{year}-{number:03d}"


def _validated_booking(booking):
    if booking.trang_thai not in ("cho_duyet", "da_duyet"):
        raise ValidationError("Yeu cau dat phong da ket thuc, khong the xac nhan.")
    if HopDong.objects.filter(dat_phong=booking).exists():
        raise ValidationError("Yeu cau dat phong da co hop dong.")
    if not booking.da_dong_y_dieu_khoan or not booking.noi_dung_dieu_khoan_snapshot.strip():
        raise ValidationError("Yeu cau chua co bang chung dong y dieu khoan.")
    if booking.gia_thue_thang_tai_thoi_diem_dat is None:
        raise ValidationError("Yeu cau thieu snapshot gia thue.")
    if booking.tien_coc_du_kien is None:
        raise ValidationError("Yeu cau thieu snapshot tien coc.")
    if not booking.so_thang_thue:
        raise ValidationError("Yeu cau thieu thoi han thue.")
    if booking.so_nguoi_o < 1 or booking.so_nguoi_o > booking.phong.so_nguoi_toi_da:
        raise ValidationError("So nguoi o khong phu hop suc chua phong.")


def _active_payment(booking):
    payment = (
        ThanhToanCocDatPhong.objects.select_for_update()
        .filter(dat_phong=booking, active_slot=1)
        .first()
    )
    if not payment:
        raise ValidationError("Yeu cau chua co giao dich coc dang hieu luc.")
    if payment.trang_thai != "cho_xac_nhan":
        raise ValidationError("Chi xac nhan giao dich coc dang cho doi soat.")
    if payment.so_tien != booking.tien_coc_du_kien:
        raise ValidationError("So tien coc khong khop snapshot dat phong.")
    return payment


def room_contract_range_conflicts(
    room, start_date, end_date, *, exclude_contract_id=None, exclude_booking_id=None,
):
    """Lock and test the canonical inclusive rental-period conflict for one room."""
    return room_has_rental_period_conflict(
        room,
        start_date,
        end_date,
        exclude_contract_id=exclude_contract_id,
        exclude_booking_id=exclude_booking_id,
        lock=True,
    )


def _assert_room_available_for_booking(booking):
    room = Phong.objects.select_for_update().get(pk=booking.phong_id)
    if room.co_so.trang_thai != "hoat_dong" or room.trang_thai == "bao_tri":
        raise ValidationError("Phong khong con kha dung.")
    if room_contract_range_conflicts(
        room,
        booking.ngay_nhan_phong,
        booking.ngay_tra_du_kien,
        exclude_booking_id=booking.pk,
    ):
        raise ValidationError("Phong da co hop dong trung thoi gian.")
    return room


def co_the_tao_hop_dong_nhap(booking, payment=None):
    """Kiem tra hien thi cho action tao hop dong nhap."""
    payment = payment or next(
        (item for item in booking.giao_dich_coc.all() if item.active_slot == 1), None
    )
    return bool(
        booking.trang_thai in ("cho_duyet", "da_duyet")
        and not getattr(booking, "co_hop_dong", False)
        and booking.ngay_nhan_phong
        and booking.ngay_tra_du_kien
        and booking.so_thang_thue
        and booking.gia_thue_thang_tai_thoi_diem_dat is not None
        and booking.tien_coc_du_kien is not None
        and payment
        and payment.trang_thai == "da_xac_nhan"
        and payment.so_tien_thuc_nhan is not None
        and payment.so_tien_thuc_nhan > 0
        and booking.phong.trang_thai != "bao_tri"
        and booking.phong.co_so.trang_thai == "hoat_dong"
    )


@transaction.atomic
def create_draft_contract(*, actor, booking_id):
    """Create one non-effective contract from a confirmed deposit."""
    require_admin(actor)
    # Deposit reconciliation and cancellation lock room before booking.  Keep the
    # bridge in that same order so a concurrent reconciliation cannot deadlock
    # against draft creation.
    from .tien_coc import locked_booking
    locked_booking(booking_id)
    booking = (
        DatPhong.objects.select_for_update()
        .select_related("nguoi_thue", "nguoi_thue__tai_khoan", "phong", "phong__co_so")
        .get(pk=booking_id)
    )
    existing = HopDong.objects.select_for_update().filter(dat_phong=booking).first()
    if existing:
        return existing, False

    _validated_booking(booking)
    expected_end = tinh_ngay_ket_thuc_theo_thang(
        booking.ngay_nhan_phong, int(booking.so_thang_thue)
    )
    if booking.ngay_tra_du_kien != expected_end:
        raise ValidationError("Ngay ket thuc booking khong hop le.")
    payment = (
        ThanhToanCocDatPhong.objects.select_for_update()
        .filter(dat_phong=booking, active_slot=1)
        .first()
    )
    if not payment or payment.trang_thai != "da_xac_nhan":
        raise ValidationError("Tien coc chua duoc Admin xac nhan.")
    if payment.so_tien_thuc_nhan is None or payment.so_tien_thuc_nhan <= 0:
        raise ValidationError("So tien coc thuc nhan khong hop le.")
    room = _assert_room_available_for_booking(booking)
    contract = HopDong.objects.create(
        dat_phong=booking,
        so_hop_dong=_next_contract_number(),
        ngay_bat_dau=booking.ngay_nhan_phong,
        ngay_ket_thuc=booking.ngay_tra_du_kien,
        tien_coc=booking.tien_coc_du_kien,
        tien_coc_thuc_nhan=payment.so_tien_thuc_nhan,
        tien_thue_thang=booking.gia_thue_thang_tai_thoi_diem_dat,
        phuong_thuc_thanh_toan=payment.phuong_thuc,
        so_nguoi_o=booking.so_nguoi_o,
        cho_phep_ghep=booking.dong_y_nhan_yeu_cau_ghep,
        dieu_khoan=booking.noi_dung_dieu_khoan_snapshot,
        ghi_chu=f"Tao nhap tu yeu cau {booking.ma_yeu_cau}; coc {payment.ma_tham_chieu}.",
        trang_thai="nhap",
        nguoi_tao=actor,
        nguoi_cap_nhat=actor,
    )
    dam_bao_ban_chup_hop_dong(contract, actor=actor, source="tao_hop_dong_nhap")
    snapshot_nguoi_o_cung_khi_ky(contract)
    LichSuHopDong.objects.create(
        hop_dong=contract, hanh_dong="tao", trang_thai_moi="nhap",
        noi_dung=f"Admin tao hop dong nhap tu {booking.ma_yeu_cau}.",
        nguoi_thuc_hien=actor,
    )
    ThongBao.objects.get_or_create(
        nguoi_thue=booking.nguoi_thue,
        ma_tham_chieu=f"BOOKING:{booking.pk}:DRAFT_CONTRACT_CREATED",
        defaults={
            "loai": "hop_dong", "muc_do": "quan_trong",
            "tieu_de": "Hop dong nhap da duoc tao",
            "noi_dung": "Hop dong nhap da duoc tao va dang cho kiem tra.",
            "url_lien_ket": f"/hop-dong-cua-toi/{contract.pk}/",
        },
    )
    NhatKyThaoTac.objects.create(
        nguoi_thuc_hien=actor, hanh_dong="tao", module="Hop dong",
        doi_tuong="HopDong", doi_tuong_id=contract.pk,
        tieu_de=f"Tao hop dong nhap {contract.so_hop_dong}",
        du_lieu_moi={"payment_id": payment.pk, "trang_thai": "nhap"},
    )
    return contract, True


@transaction.atomic
def close_pre_activation_contract(*, actor, contract_id, reason="", ip_address=None):
    """Cancel an unaccepted contract and release its booking hold atomically.

    This is intentionally narrower than the legacy contract-cancellation
    action: an accepted contract must continue through its own activation or
    established cancellation lifecycle.
    """
    require_admin(actor)
    reason = (reason or "").strip() or "Dong hop dong truoc kich hoat boi quan tri vien."

    try:
        room_id = HopDong.objects.values_list("dat_phong__phong_id", flat=True).get(pk=contract_id)
    except HopDong.DoesNotExist as error:
        raise ValidationError("Khong tim thay hop dong.") from error

    # Keep the same room -> booking -> contract -> deposit order as activation.
    room = Phong.objects.select_for_update().select_related("co_so").get(pk=room_id)
    booking = DatPhong.objects.select_for_update().select_related("nguoi_thue").get(hop_dong__pk=contract_id)
    contract = HopDong.objects.select_for_update().select_related(
        "dat_phong__nguoi_thue", "dat_phong__phong"
    ).get(pk=contract_id)
    payment = ThanhToanCocDatPhong.objects.select_for_update().filter(
        dat_phong=booking, active_slot=1
    ).first()
    reference = f"CONTRACT:{contract.pk}:PRE_ACTIVATION_CLOSED"

    if contract.trang_thai == "da_huy":
        if booking.trang_thai == "da_huy" and ThongBao.objects.filter(ma_tham_chieu=reference).exists():
            return contract, False
        raise ValidationError("Hop dong da huy khong co dau vet dong truoc kich hoat hop le; can xu ly du lieu rieng.")

    allowed = {"nhap", "cho_nguoi_thue_xac_nhan", "yeu_cau_chinh_sua"}
    if contract.trang_thai not in allowed:
        raise ValidationError("Chi hop dong nhap, cho nguoi thue xac nhan hoac yeu cau chinh sua moi duoc dong theo luong nay.")
    if booking.trang_thai not in {"cho_duyet", "da_duyet"}:
        raise ValidationError("Booking khong con o trang thai co the dong truoc kich hoat.")

    old_status = contract.trang_thai
    today = timezone.localdate()
    contract.trang_thai = "da_huy"
    contract.ngay_huy = timezone.now()
    contract.ly_do_huy = reason
    contract.nguoi_cap_nhat = actor
    contract.save(update_fields=["trang_thai", "ngay_huy", "ly_do_huy", "nguoi_cap_nhat", "ngay_cap_nhat"])

    booking.trang_thai = "da_huy"
    booking.nguoi_xu_ly = actor
    booking.save(update_fields=["trang_thai", "nguoi_xu_ly", "ngay_cap_nhat"])
    booking.nguoi_di_cung_khai_bao.filter(trang_thai_xac_minh="cho_xac_minh").update(
        trang_thai_xac_minh="da_huy", ngay_cap_nhat=timezone.now()
    )

    # Pre-activation contracts should not have access rights, but revoke any
    # anomalous contract-derived rights without touching legacy/manual rights.
    contract.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown").exclude(
        trang_thai="bi_thu_hoi"
    ).update(trang_thai="bi_thu_hoi", active_access_key=None, ngay_ket_thuc=today)

    room.dong_bo_trang_thai()
    room.refresh_from_db()
    LichSuHopDong.objects.create(
        hop_dong=contract, hanh_dong="huy", trang_thai_cu=old_status, trang_thai_moi="da_huy",
        noi_dung="Dong hop dong truoc kich hoat va giai phong booking; khong tu dong hoan coc.",
        nguoi_thuc_hien=actor, dia_chi_ip=ip_address,
    )
    NhatKyThaoTac.objects.create(
        nguoi_thuc_hien=actor, hanh_dong="huy", module="Hop dong", doi_tuong="HopDong",
        doi_tuong_id=contract.pk, tieu_de=f"Dong hop dong truoc kich hoat {contract.so_hop_dong}",
        noi_dung=reason, du_lieu_cu={"trang_thai": old_status},
        du_lieu_moi={"trang_thai": "da_huy", "booking_trang_thai": "da_huy",
                     "payment_id": payment.pk if payment else None,
                     "payment_trang_thai": payment.trang_thai if payment else None,
                     "trang_thai_phong": room.trang_thai},
    )
    ThongBao.objects.get_or_create(
        nguoi_thue=booking.nguoi_thue, ma_tham_chieu=reference,
        defaults={"loai": "hop_dong", "muc_do": "quan_trong",
                  "tieu_de": "Hop dong da duoc dong truoc kich hoat",
                  "noi_dung": "Booking da duoc giai phong; tien coc da xac nhan duoc giu de xu ly tai chinh rieng.",
                  "url_lien_ket": f"/quan-ly-hop-dong/{contract.pk}/"},
    )
    return contract, True


def hash_canonical_json(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tenant_review_contract(*, actor, contract_id, version_id, version_hash):
    if not actor or not actor.is_authenticated:
        raise PermissionDenied("Khong co quyen phan hoi hop dong.")
    if actor.is_staff or actor.is_superuser:
        raise Http404
    contract = HopDong.objects.select_for_update().select_related(
        "dat_phong__nguoi_thue", "phien_ban_hien_tai"
    ).get(pk=contract_id)
    if contract.dat_phong.nguoi_thue.tai_khoan_id != actor.id:
        raise Http404
    if (contract.trang_thai != "cho_nguoi_thue_xac_nhan" or not contract.phien_ban_hien_tai_id
            or contract.phien_ban_hien_tai_id != version_id
            or contract.phien_ban_hien_tai.ma_bam_sha256 != version_hash):
        raise ValidationError("Phien ban hop dong khong con hop le de phan hoi.")
    version = PhienBanHopDong.objects.select_for_update().get(pk=version_id, hop_dong=contract)
    if PhanHoiHopDong.objects.select_for_update().filter(phien_ban=version).exists():
        raise ValidationError("Phien ban nay da co phan hoi.")
    return contract, version


@transaction.atomic
def respond_to_contract_review(*, actor, contract_id, version_id, version_hash, action, password="", reason="", ip_address=None):
    """Persist exactly one tenant decision for the current frozen version."""
    contract, version = _tenant_review_contract(
        actor=actor, contract_id=contract_id, version_id=version_id, version_hash=version_hash
    )
    if action == "chap_thuan":
        if not password or not actor.check_password(password):
            raise ValidationError("Thong tin xac nhan khong hop le.")
        next_status, method, reason = "cho_kich_hoat", "xac_nhan_dien_tu_he_thong", ""
    elif action == "yeu_cau_chinh_sua":
        reason = reason.strip()
        if not reason or len(reason) > 2000:
            raise ValidationError("Ly do chinh sua khong hop le.")
        next_status, method = "yeu_cau_chinh_sua", "yeu_cau_chinh_sua_he_thong"
    else:
        raise ValidationError("Hanh dong phan hoi khong hop le.")
    try:
        # The one-to-one constraint remains the final arbiter on databases where
        # row locking cannot serialize concurrent requests.
        with transaction.atomic():
            response = PhanHoiHopDong.objects.create(
                phien_ban=version, nguoi_phan_hoi=actor, hanh_dong=action, ly_do=reason,
                ma_bam_phien_ban=version.ma_bam_sha256, phuong_thuc_xac_nhan=method, dia_chi_ip=ip_address,
            )
    except IntegrityError as error:
        raise ValidationError("Phien ban nay da co phan hoi.") from error
    contract.trang_thai, contract.nguoi_cap_nhat = next_status, actor
    contract.save(update_fields=["trang_thai", "nguoi_cap_nhat", "ngay_cap_nhat"])
    LichSuHopDong.objects.create(hop_dong=contract, hanh_dong="cap_nhat", trang_thai_cu="cho_nguoi_thue_xac_nhan",
        trang_thai_moi=next_status, noi_dung=f"Nguoi thue {action} phien ban {version.so_phien_ban}.", nguoi_thuc_hien=actor)
    NhatKyThaoTac.objects.create(nguoi_thuc_hien=actor, hanh_dong="cap_nhat", module="Hop dong", doi_tuong="HopDong",
        doi_tuong_id=contract.pk, tieu_de=f"Phan hoi hop dong {contract.so_hop_dong}", du_lieu_moi={"hanh_dong": action, "phien_ban": version.so_phien_ban})
    notify_admin_event(
        reference=f"CONTRACT:{contract.pk}:RESPONSE:{version.pk}",
        notification_type="hop_dong",
        title="Người thuê đã phản hồi hợp đồng",
        text=(
            f"{contract.so_hop_dong}: người thuê đã "
            f"{'chấp thuận' if action == 'chap_thuan' else 'yêu cầu chỉnh sửa'} "
            f"phiên bản {version.so_phien_ban}."
        ),
        url=f"/quan-ly-hop-dong/{contract.pk}/",
    )
    return response


@transaction.atomic
def reopen_contract_for_revision(*, actor, contract_id):
    require_admin(actor)
    contract = HopDong.objects.select_for_update().get(pk=contract_id)
    if contract.trang_thai != "yeu_cau_chinh_sua":
        raise ValidationError("Hop dong khong co yeu cau chinh sua dang cho.")
    contract.trang_thai, contract.nguoi_cap_nhat = "nhap", actor
    contract.save(update_fields=["trang_thai", "nguoi_cap_nhat", "ngay_cap_nhat"])
    LichSuHopDong.objects.create(hop_dong=contract, hanh_dong="cap_nhat", trang_thai_cu="yeu_cau_chinh_sua",
        trang_thai_moi="nhap", noi_dung="Admin mo lai hop dong de chinh sua.", nguoi_thuc_hien=actor)
    return contract


@transaction.atomic
def send_contract_for_tenant_confirmation(*, actor, contract_id):
    """Freeze one draft version and send it to its owning tenant."""
    require_admin(actor)
    contract = (HopDong.objects.select_for_update().select_related(
        "dat_phong__nguoi_thue", "dat_phong__phong__co_so", "phien_ban_hien_tai"
    ).get(pk=contract_id))
    if contract.trang_thai == "cho_nguoi_thue_xac_nhan" and contract.phien_ban_hien_tai_id:
        return contract.phien_ban_hien_tai, False
    if contract.trang_thai != "nhap":
        raise ValidationError("Chi hop dong nhap moi duoc gui nguoi thue xac nhan.")
    booking = DatPhong.objects.select_for_update().get(pk=contract.dat_phong_id)
    payment = ThanhToanCocDatPhong.objects.select_for_update().filter(
        dat_phong=booking, active_slot=1, trang_thai="da_xac_nhan"
    ).first()
    if not payment or payment.so_tien_thuc_nhan is None or payment.so_tien_thuc_nhan <= 0:
        raise ValidationError("Tien coc chua duoc xac nhan hop le.")
    if contract.tien_coc_thuc_nhan is None or contract.tien_coc_thuc_nhan <= 0:
        raise ValidationError("Hop dong thieu so tien coc thuc nhan hop le.")
    if not all((contract.ngay_bat_dau, contract.ngay_ket_thuc, contract.tien_thue_thang is not None)):
        raise ValidationError("Hop dong thieu du lieu bat buoc.")
    last = PhienBanHopDong.objects.select_for_update().filter(hop_dong=contract).order_by("-so_phien_ban").first()
    number, sent_at = (last.so_phien_ban if last else 0) + 1, timezone.now()
    payload = du_lieu_phien_ban_review(contract, so_phien_ban=number, thoi_diem_tao=sent_at)
    version = PhienBanHopDong.objects.create(
        hop_dong=contract, so_phien_ban=number, du_lieu=payload,
        ma_bam_sha256=hash_canonical_json(payload), nguoi_gui=actor, thoi_diem_gui=sent_at,
    )
    contract.phien_ban_hien_tai, contract.trang_thai, contract.nguoi_cap_nhat = version, "cho_nguoi_thue_xac_nhan", actor
    contract.save(update_fields=["phien_ban_hien_tai", "trang_thai", "nguoi_cap_nhat", "ngay_cap_nhat"])
    LichSuHopDong.objects.create(hop_dong=contract, hanh_dong="cap_nhat", trang_thai_cu="nhap",
        trang_thai_moi=contract.trang_thai, noi_dung=f"Gui phien ban review {number} cho nguoi thue.", nguoi_thuc_hien=actor)
    ThongBao.objects.get_or_create(nguoi_thue=booking.nguoi_thue,
        ma_tham_chieu=f"CONTRACT:{contract.pk}:REVIEW:{number}",
        defaults={"loai": "hop_dong", "muc_do": "quan_trong", "tieu_de": "Hop dong cho ban xac nhan",
                  "noi_dung": "Hop dong da duoc gui de ban kiem tra va xac nhan.", "url_lien_ket": f"/hop-dong-cua-toi/{contract.pk}/"})
    NhatKyThaoTac.objects.create(nguoi_thuc_hien=actor, hanh_dong="cap_nhat", module="Hop dong",
        doi_tuong="HopDong", doi_tuong_id=contract.pk, tieu_de=f"Gui phien ban review {contract.so_hop_dong}",
        du_lieu_moi={"phien_ban": number, "ma_bam_sha256": version.ma_bam_sha256})
    return version, True


@transaction.atomic
def confirm_deposit_and_create_contract(*, actor, booking_id):
    require_admin(actor)
    booking = (
        DatPhong.objects.select_for_update()
        .select_related("nguoi_thue", "nguoi_thue__tai_khoan", "phong", "phong__co_so")
        .get(pk=booking_id)
    )
    existing = HopDong.objects.select_for_update().filter(dat_phong=booking).first()
    if existing:
        return existing

    _validated_booking(booking)
    if not booking.ngay_tra_du_kien:
        booking.ngay_tra_du_kien = tinh_ngay_ket_thuc_theo_thang(booking.ngay_nhan_phong, int(booking.so_thang_thue))
    room = _assert_room_available_for_booking(booking)
    payment = _active_payment(booking)

    payment.trang_thai = "da_xac_nhan"
    payment.thoi_diem_admin_xac_nhan = timezone.now()
    payment.nguoi_xac_nhan = actor
    payment.save()
    evidence = ChungTuThanhToan.objects.select_for_update().filter(giao_dich_coc=payment).first()
    if evidence:
        mark_reviewed(evidence, accepted=True, reviewer=actor)

    booking.trang_thai = "da_duyet"
    booking.nguoi_xu_ly = actor
    booking.save(update_fields=["trang_thai", "nguoi_xu_ly", "ngay_tra_du_kien", "ngay_cap_nhat"])

    contract = HopDong.objects.create(
        dat_phong=booking,
        so_hop_dong=_next_contract_number(),
        ngay_bat_dau=booking.ngay_nhan_phong,
        ngay_ket_thuc=booking.ngay_tra_du_kien,
        tien_coc=booking.tien_coc_du_kien or Decimal("0"),
        tien_thue_thang=booking.gia_thue_thang_tai_thoi_diem_dat,
        phuong_thuc_thanh_toan=payment.phuong_thuc,
        so_nguoi_o=booking.so_nguoi_o,
        cho_phep_ghep=booking.dong_y_nhan_yeu_cau_ghep,
        dieu_khoan=booking.noi_dung_dieu_khoan_snapshot,
        ghi_chu=f"Tao tu yeu cau {booking.ma_yeu_cau}; coc {payment.ma_tham_chieu}.",
        trang_thai=_contract_status(booking.ngay_nhan_phong, booking.ngay_tra_du_kien),
        ngay_ky=timezone.now(),
        nguoi_tao=actor,
        nguoi_cap_nhat=actor,
    )

    KhaiBaoNguoiOCungDatPhong.objects.filter(
        dat_phong=booking, trang_thai_xac_minh="cho_xac_minh"
    ).update(trang_thai_xac_minh="da_xac_minh", ngay_cap_nhat=timezone.now())

    dam_bao_ban_chup_hop_dong(contract, actor=actor)
    snapshot_nguoi_o_cung_khi_ky(contract)

    LichSuHopDong.objects.create(
        hop_dong=contract,
        hanh_dong="tao",
        trang_thai_moi=contract.trang_thai,
        noi_dung=f"Admin xac nhan coc {payment.ma_tham_chieu} va tao hop dong tu {booking.ma_yeu_cau}.",
        nguoi_thuc_hien=actor,
    )
    marker = f"BOOKING:{booking.pk}:CONTRACT_CREATED"
    ThongBao.objects.get_or_create(
        nguoi_thue=booking.nguoi_thue,
        ma_tham_chieu=marker,
        defaults={
            "loai": "hop_dong",
            "muc_do": "quan_trong",
            "tieu_de": "Hop dong thue phong da duoc tao",
            "noi_dung": f"Hop dong {contract.so_hop_dong} cho phong {room.so_phong} da duoc tao.",
            "url_lien_ket": f"/hop-dong-cua-toi/{contract.pk}/",
        },
    )
    NhatKyThaoTac.objects.create(
        nguoi_thuc_hien=actor,
        hanh_dong="duyet",
        module="Dat phong",
        doi_tuong="DatPhong",
        doi_tuong_id=booking.pk,
        tieu_de=f"Xac nhan coc va tao hop dong {contract.so_hop_dong}",
        du_lieu_moi={"hop_dong_id": contract.pk, "payment_id": payment.pk, "trang_thai": booking.trang_thai},
    )
    notify_booking_event(
        booking=booking,
        event=f"CONTRACT_CREATED:{contract.pk}",
        title="Da xac nhan coc va tao hop dong",
        text=f"{booking.ma_yeu_cau}: hop dong {contract.so_hop_dong} da duoc tao.",
        url=f"/quan-ly-hop-dong/{contract.pk}/",
    )
    room.dong_bo_trang_thai()
    return contract


@transaction.atomic
def reject_deposit(*, actor, booking_id, reason):
    require_admin(actor)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Vui long nhap ly do tu choi giao dich coc.")
    booking = DatPhong.objects.select_for_update().select_related("nguoi_thue").get(pk=booking_id)
    payment = _active_payment(booking)
    payment.trang_thai = "tu_choi"
    payment.ly_do_tu_choi = reason
    payment.save()
    evidence = ChungTuThanhToan.objects.select_for_update().filter(giao_dich_coc=payment).first()
    if evidence:
        mark_reviewed(evidence, accepted=False, reviewer=actor, note=reason)
    ThongBao.objects.get_or_create(
        nguoi_thue=booking.nguoi_thue,
        ma_tham_chieu=f"BOOKING:{booking.pk}:DEPOSIT_REJECTED:{payment.pk}",
        defaults={
            "loai": "dat_phong",
            "muc_do": "quan_trong",
            "tieu_de": "Giao dich coc bi tu choi",
            "noi_dung": f"{booking.ma_yeu_cau}: {reason}",
            "url_lien_ket": f"/dat-phong-cua-toi/{booking.pk}/thanh-toan-coc/",
        },
    )
    NhatKyThaoTac.objects.create(nguoi_thuc_hien=actor, hanh_dong="tu_choi", module="Coc dat phong",
        doi_tuong="ThanhToanCocDatPhong", doi_tuong_id=payment.pk, tieu_de="Tu choi giao dich coc", noi_dung=reason)
    notify_booking_event(
        booking=booking,
        event=f"DEPOSIT_REJECTED:{payment.pk}",
        title="Giao dich coc da bi tu choi",
        text=f"{booking.ma_yeu_cau}: Admin tu choi giao dich coc. Ly do: {reason}",
        url=f"/quan-ly-dat-phong/{booking.pk}/",
    )
    return payment


@transaction.atomic
def reject_booking(*, actor, booking_id, reason):
    require_admin(actor)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Vui long nhap ly do tu choi yeu cau dat phong.")
    booking = DatPhong.objects.select_for_update().select_related("nguoi_thue", "phong").get(pk=booking_id)
    if HopDong.objects.filter(dat_phong=booking).exists():
        raise ValidationError("Yeu cau da co hop dong, khong the tu choi.")
    if booking.trang_thai not in ("cho_duyet", "da_duyet"):
        raise ValidationError("Yeu cau khong con o trang thai cho phep tu choi.")
    booking.trang_thai = "tu_choi"
    booking.ly_do_tu_choi = reason
    booking.nguoi_xu_ly = actor
    booking.save(update_fields=["trang_thai", "ly_do_tu_choi", "nguoi_xu_ly", "ngay_cap_nhat"])
    booking.giao_dich_coc.select_for_update().filter(trang_thai="chua_thanh_toan").update(trang_thai="da_huy", active_slot=None)
    booking.nguoi_di_cung_khai_bao.filter(trang_thai_xac_minh="cho_xac_minh").update(trang_thai_xac_minh="da_huy", ngay_cap_nhat=timezone.now())
    ThongBao.objects.get_or_create(
        nguoi_thue=booking.nguoi_thue,
        ma_tham_chieu=f"BOOKING:{booking.pk}:BOOKING_REJECTED",
        defaults={
            "loai": "dat_phong",
            "muc_do": "quan_trong",
            "tieu_de": "Yeu cau dat phong bi tu choi",
            "noi_dung": f"{booking.ma_yeu_cau}: {reason}",
            "url_lien_ket": f"/dat-phong-cua-toi/{booking.pk}/",
        },
    )
    NhatKyThaoTac.objects.create(nguoi_thuc_hien=actor, hanh_dong="tu_choi", module="Dat phong",
        doi_tuong="DatPhong", doi_tuong_id=booking.pk, tieu_de="Tu choi yeu cau dat phong", noi_dung=reason)
    notify_booking_event(
        booking=booking,
        event="BOOKING_REJECTED",
        title="Yeu cau dat phong da bi tu choi",
        text=f"{booking.ma_yeu_cau}: Admin tu choi yeu cau dat phong. Ly do: {reason}",
        url=f"/quan-ly-dat-phong/{booking.pk}/",
    )
    booking.phong.dong_bo_trang_thai()
    return booking
