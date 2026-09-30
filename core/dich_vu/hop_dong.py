"""Admin booking confirmation and contract creation service."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import (
    DatPhong,
    HopDong,
    KhaiBaoNguoiOCungDatPhong,
    LichSuHopDong,
    NhatKyThaoTac,
    Phong,
    ThanhToanCocDatPhong,
    ThongBao,
)
from core.dich_vu.thong_bao_quan_tri import notify_booking_event
from core.dich_vu.ngay_thue import tinh_ngay_ket_thuc_theo_thang


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


def _assert_room_available_for_booking(booking):
    room = Phong.objects.select_for_update().get(pk=booking.phong_id)
    if room.co_so.trang_thai != "hoat_dong" or room.trang_thai == "bao_tri":
        raise ValidationError("Phong khong con kha dung.")
    conflict = (
        HopDong.objects.select_for_update()
        .filter(dat_phong__phong=room)
        .exclude(dat_phong=booking)
        .exclude(trang_thai__in=("da_huy", "da_het_han"))
        .filter(ngay_bat_dau__lte=booking.ngay_tra_du_kien, ngay_ket_thuc__gte=booking.ngay_nhan_phong)
        .exists()
    )
    if conflict:
        raise ValidationError("Phong da co hop dong trung thoi gian.")
    return room


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
