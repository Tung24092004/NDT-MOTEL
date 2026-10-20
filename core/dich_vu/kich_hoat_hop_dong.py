"""Activation of a tenant-accepted contract.

This deliberately does not provision Smart Room resources or invoices.  It is
the narrow, auditable bridge between the immutable tenant acceptance and the
existing contract/room lifecycle.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.dich_vu.hop_dong import require_admin
from core.dich_vu.vong_doi_hop_dong import dong_bo_vong_doi_hop_dong
from core.models import (
    DatPhong,
    HopDong,
    LichSuHopDong,
    NhatKyThaoTac,
    PhanHoiHopDong,
    PhienBanHopDong,
    Phong,
    ThanhToanCocDatPhong,
    ThongBao,
)
from core.dich_vu.luu_tru import TRANG_THAI_DA_TRA_PHONG, TRANG_THAI_DANG_O


def _invalid(message):
    raise ValidationError(message)


@transaction.atomic
def activate_accepted_contract(*, actor, contract_id, ip_address=None):
    """Activate exactly one currently accepted review contract.

    The initial room-id lookup does not decide business truth.  It only lets
    every activation take the room lock first; all facts are reloaded under
    locks afterwards in the fixed order room -> booking -> contract -> review
    version -> response -> deposit.
    """
    require_admin(actor)
    try:
        room_id = HopDong.objects.values_list("dat_phong__phong_id", flat=True).get(pk=contract_id)
    except HopDong.DoesNotExist as error:
        raise ValidationError("Khong tim thay hop dong.") from error

    room = Phong.objects.select_for_update().select_related("co_so").get(pk=room_id)
    booking = DatPhong.objects.select_for_update().select_related("nguoi_thue").get(
        hop_dong__pk=contract_id
    )
    contract = HopDong.objects.select_for_update().select_related(
        "dat_phong__nguoi_thue", "dat_phong__phong__co_so"
    ).get(pk=contract_id)

    # A repeat of the successful POST is explicitly idempotent.  Do not make
    # old contracts without 02B proof look valid: only a contract that has
    # already crossed the activation boundary may use this branch.
    if contract.trang_thai in ("dang_hieu_luc", "sap_het_han") and contract.ngay_ky:
        return contract, False
    if contract.trang_thai != "cho_kich_hoat":
        _invalid("Hop dong khong o trang thai cho kich hoat.")
    if not contract.phien_ban_hien_tai_id:
        _invalid("Hop dong chua co phien ban hien tai.")

    version = PhienBanHopDong.objects.select_for_update().filter(
        pk=contract.phien_ban_hien_tai_id, hop_dong=contract
    ).first()
    if not version:
        _invalid("Phien ban hien tai khong thuoc hop dong.")
    response = PhanHoiHopDong.objects.select_for_update().filter(phien_ban=version).first()
    if not response:
        _invalid("Phien ban hien tai chua co phan hoi.")
    if response.hanh_dong != "chap_thuan":
        _invalid("Phan hoi hien tai khong phai chap thuan.")
    if response.ma_bam_phien_ban != version.ma_bam_sha256:
        _invalid("Hash phan hoi khong khop phien ban hien tai.")

    today = timezone.localdate()
    if not contract.ngay_bat_dau or not contract.ngay_ket_thuc or contract.ngay_bat_dau > contract.ngay_ket_thuc:
        _invalid("Thoi han hop dong khong hop le.")
    if today < contract.ngay_bat_dau:
        _invalid("Hop dong chua den ngay kich hoat. Ngay som nhat: %s." % contract.ngay_bat_dau.strftime("%d/%m/%Y"))
    if today > contract.ngay_ket_thuc:
        _invalid("Hop dong da qua ngay ket thuc, khong the kich hoat.")
    if booking.trang_thai not in ("cho_duyet", "da_duyet"):
        _invalid("Booking khong con o trang thai hop le de kich hoat.")
    if (
        booking.phong_id != room.pk
        or booking.ngay_nhan_phong != contract.ngay_bat_dau
        or booking.ngay_tra_du_kien != contract.ngay_ket_thuc
        or not booking.da_dong_y_dieu_khoan
        or not (booking.noi_dung_dieu_khoan_snapshot or "").strip()
    ):
        _invalid("Booking khong con khop du lieu hop dong da chap thuan.")
    if room.co_so.trang_thai != "hoat_dong" or room.trang_thai == "bao_tri":
        _invalid("Phong hoac co so khong con kha dung.")

    payment = ThanhToanCocDatPhong.objects.select_for_update().filter(
        dat_phong=booking, active_slot=1
    ).first()
    if not payment or payment.trang_thai != "da_xac_nhan" or payment.so_tien_thuc_nhan is None or payment.so_tien_thuc_nhan <= 0:
        _invalid("Tien coc chua duoc xac nhan hop le.")
    if payment.so_tien != booking.tien_coc_du_kien:
        _invalid("Tien coc khong khop snapshot booking.")
    if contract.tien_coc_thuc_nhan is None or contract.tien_coc_thuc_nhan <= 0:
        _invalid("Hop dong thieu so tien coc thuc nhan hop le.")

    conflict = HopDong.objects.select_for_update().filter(
        dat_phong__phong=room, trang_thai__in=("dang_hieu_luc", "sap_het_han")
    ).exclude(pk=contract.pk).exists()
    if conflict:
        _invalid("Phong dang co hop dong khac co hieu luc.")
    tenant_conflict = HopDong.objects.select_for_update().filter(
        dat_phong__nguoi_thue=booking.nguoi_thue,
        dat_phong__trang_thai="da_duyet",
        trang_thai__in=("dang_hieu_luc", "sap_het_han"),
        ngay_bat_dau__lte=today,
        ngay_ket_thuc__gte=today,
    ).exclude(pk=contract.pk).exists()
    if tenant_conflict:
        _invalid("Nguoi thue dang co hop dong luu tru hien tai khac.")

    old_status = contract.trang_thai
    if contract.ngay_ky is None:
        contract.ngay_ky = timezone.now()
    # The lifecycle deliberately preserves review states.  Move to its normal
    # date-driven entry state first, then let it calculate active/soon-expiring.
    contract.trang_thai = "cho_hieu_luc"
    contract.nguoi_cap_nhat = actor
    contract.save(update_fields=["ngay_ky", "trang_thai", "nguoi_cap_nhat", "ngay_cap_nhat"])
    contract = dong_bo_vong_doi_hop_dong(contract, actor=actor)
    contract.refresh_from_db()
    if contract.trang_thai not in ("dang_hieu_luc", "sap_het_han"):
        _invalid("Hop dong chua the chuyen sang trang thai co hieu luc.")

    if booking.trang_thai != "da_duyet":
        booking.trang_thai = "da_duyet"
        booking.nguoi_xu_ly = actor
        booking.save(update_fields=["trang_thai", "nguoi_xu_ly", "ngay_cap_nhat"])
    # A returning tenant may have been checked out by the previous contract.
    # Activation is the lifecycle boundary that restores their primary
    # residency; temporary absence remains untouched.
    if booking.nguoi_thue.trang_thai_luu_tru == TRANG_THAI_DA_TRA_PHONG:
        booking.nguoi_thue.trang_thai_luu_tru = TRANG_THAI_DANG_O
        booking.nguoi_thue.save(update_fields=["trang_thai_luu_tru", "ngay_cap_nhat"])
    room.dong_bo_trang_thai()
    room.refresh_from_db()
    if room.trang_thai != "dang_thue":
        _invalid("Khong the dong bo phong sang dang thue.")

    LichSuHopDong.objects.create(
        hop_dong=contract, hanh_dong="kich_hoat", trang_thai_cu=old_status,
        trang_thai_moi=contract.trang_thai,
        noi_dung="Admin kich hoat hop dong sau khi nguoi thue chap thuan phien ban %s." % version.so_phien_ban,
        nguoi_thuc_hien=actor, dia_chi_ip=ip_address,
    )
    NhatKyThaoTac.objects.create(
        nguoi_thuc_hien=actor, hanh_dong="kich_hoat", module="Hop dong",
        doi_tuong="HopDong", doi_tuong_id=contract.pk,
        tieu_de="Kich hoat hop dong %s" % contract.so_hop_dong,
        du_lieu_cu={"trang_thai": old_status},
        du_lieu_moi={"trang_thai": contract.trang_thai, "phien_ban": version.so_phien_ban},
    )
    ThongBao.objects.get_or_create(
        nguoi_thue=booking.nguoi_thue,
        ma_tham_chieu="CONTRACT:%s:ACTIVATED" % contract.pk,
        defaults={
            "loai": "hop_dong", "muc_do": "quan_trong",
            "tieu_de": "Hop dong da duoc kich hoat",
            "noi_dung": "Hop dong %s da co hieu luc tu %s den %s." % (
                contract.so_hop_dong, contract.ngay_bat_dau.strftime("%d/%m/%Y"),
                contract.ngay_ket_thuc.strftime("%d/%m/%Y"),
            ),
            "url_lien_ket": "/hop-dong-cua-toi/%s/" % contract.pk,
        },
    )
    return contract, True
