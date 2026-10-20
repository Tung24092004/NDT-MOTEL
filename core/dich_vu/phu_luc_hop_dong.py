"""Snapshot bat bien va phu luc hop dong."""
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import (
    BanChupHopDong,
    BanChupNguoiOCungHopDong,
    PhuLucHopDong,
)


def du_lieu_hop_dong_goc(hop_dong):
    booking = hop_dong.dat_phong
    tenant = booking.nguoi_thue
    room = booking.phong
    return {
        "so_hop_dong": hop_dong.so_hop_dong,
        "ngay_bat_dau": hop_dong.ngay_bat_dau.isoformat(),
        "ngay_ket_thuc_goc": hop_dong.ngay_ket_thuc.isoformat(),
        "ngay_ky": hop_dong.ngay_ky.isoformat() if hop_dong.ngay_ky else None,
        "tien_coc": str(hop_dong.tien_coc),
        "tien_coc_thuc_nhan": (
            str(hop_dong.tien_coc_thuc_nhan)
            if hop_dong.tien_coc_thuc_nhan is not None else None
        ),
        "so_thang_thue": booking.so_thang_thue,
        "tien_thue_thang": str(hop_dong.tien_thue_thang),
        "ngay_thanh_toan_hang_thang": hop_dong.ngay_thanh_toan_hang_thang,
        "phuong_thuc_thanh_toan": hop_dong.phuong_thuc_thanh_toan,
        "so_nguoi_o": hop_dong.so_nguoi_o,
        "cho_phep_ghep": hop_dong.cho_phep_ghep,
        "tien_phat_tre_han": str(hop_dong.tien_phat_tre_han),
        "dieu_khoan": hop_dong.dieu_khoan,
        "ghi_chu": hop_dong.ghi_chu,
        "nguoi_thue": {
            "ho_ten": tenant.ho_ten,
            "cccd": tenant.cccd,
            "so_dien_thoai": tenant.so_dien_thoai,
            "email": tenant.email,
        },
        "phong": {
            "so_phong": room.so_phong,
            "co_so": room.co_so.ten_co_so,
            "dia_chi": room.co_so.dia_chi,
        },
    }


def dam_bao_ban_chup_hop_dong(hop_dong, *, actor=None, legacy=False, source=None):
    return BanChupHopDong.objects.get_or_create(
        hop_dong=hop_dong,
        defaults={
            "du_lieu": du_lieu_hop_dong_goc(hop_dong),
            "ngay_chot": hop_dong.ngay_ky or timezone.now(),
            "nguoi_chot": actor,
            "nguon": source or ("legacy_migration" if legacy else "tao_hop_dong"),
            "la_du_lieu_legacy": legacy,
        },
    )


def snapshot_nguoi_o_cung_khi_ky(hop_dong):
    created = 0
    declarations = hop_dong.dat_phong.nguoi_di_cung_khai_bao.filter(
        trang_thai_xac_minh="da_xac_minh"
    ).order_by("id")
    for person in declarations:
        _, was_created = BanChupNguoiOCungHopDong.objects.get_or_create(
            hop_dong=hop_dong,
            khai_bao_dat_phong=person,
            loai_su_kien="co_mat_khi_ky",
            defaults={
                "ho_ten": person.ho_ten,
                "ngay_sinh": person.ngay_sinh,
                "gioi_tinh": person.gioi_tinh,
                "cccd": person.cccd,
                "so_dien_thoai": person.so_dien_thoai,
                "quan_he": person.quan_he,
                "trang_thai_xac_minh": person.trang_thai_xac_minh,
                "ngay_hieu_luc": hop_dong.ngay_bat_dau,
                "nguon": "khai_bao_dat_phong",
                "ghi_chu": "Snapshot tu khai bao dat phong tai thoi diem tao hop dong.",
            },
        )
        created += int(was_created)
    return created


def du_lieu_phien_ban_review(hop_dong, *, so_phien_ban, thoi_diem_tao):
    """Serialize only review terms a tenant needs to inspect."""
    booking, tenant, room = hop_dong.dat_phong, hop_dong.dat_phong.nguoi_thue, hop_dong.dat_phong.phong
    companions = hop_dong.ban_chup_nguoi_o_cung.filter(loai_su_kien="co_mat_khi_ky").order_by("ho_ten", "id")
    return {
        "so_phien_ban": so_phien_ban, "thoi_diem_tao_phien_ban": thoi_diem_tao.isoformat(),
        "so_hop_dong": hop_dong.so_hop_dong,
        "booking": {"id": booking.id, "ma_yeu_cau": booking.ma_yeu_cau},
        "nguoi_thue": {"ho_ten": tenant.ho_ten},
        "phong": {"so_phong": room.so_phong, "co_so": room.co_so.ten_co_so},
        "ngay_bat_dau": hop_dong.ngay_bat_dau.isoformat(), "ngay_ket_thuc": hop_dong.ngay_ket_thuc.isoformat(),
        "so_thang_thue": booking.so_thang_thue, "tien_thue_thang": str(hop_dong.tien_thue_thang),
        "tien_coc": str(hop_dong.tien_coc), "tien_coc_thuc_nhan": str(hop_dong.tien_coc_thuc_nhan),
        "ngay_thanh_toan_hang_thang": hop_dong.ngay_thanh_toan_hang_thang,
        "phuong_thuc_thanh_toan": hop_dong.phuong_thuc_thanh_toan,
        "so_nguoi_o": hop_dong.so_nguoi_o, "cho_phep_ghep": hop_dong.cho_phep_ghep,
        "tien_phat_tre_han": str(hop_dong.tien_phat_tre_han), "dieu_khoan": hop_dong.dieu_khoan,
        "trang_thai_khi_gui": "cho_nguoi_thue_xac_nhan",
        "nguoi_o_cung": [{"ho_ten": item.ho_ten, "quan_he": item.quan_he,
                            "trang_thai_xac_minh": item.trang_thai_xac_minh} for item in companions],
    }


@transaction.atomic
def tao_phu_luc_gia_han(*, request_obj, actor):
    old_end = request_obj.ngay_ket_thuc_cu
    new_end = request_obj.ngay_ket_thuc_de_xuat
    if not old_end or not new_end or new_end <= old_end:
        raise ValidationError("Ngay gia han khong hop le.")
    appendix, created = PhuLucHopDong.objects.get_or_create(
        yeu_cau_gia_han=request_obj,
        defaults={
            "hop_dong": request_obj.hop_dong,
            "loai": "gia_han",
            "ma_phu_luc": f"PL-GH-{request_obj.hop_dong_id}-{request_obj.pk}",
            "trang_thai": "da_duyet",
            "ngay_hieu_luc": old_end + timedelta(days=1),
            "noi_dung": f"Gia han hop dong them {request_obj.so_thang_gia_han} thang.",
            "ly_do": request_obj.ly_do,
            "ngay_ket_thuc_cu": old_end,
            "ngay_ket_thuc_moi": new_end,
            "du_lieu_snapshot": {
                "so_hop_dong": request_obj.hop_dong.so_hop_dong,
                "ngay_ket_thuc_cu": old_end.isoformat(),
                "ngay_ket_thuc_moi": new_end.isoformat(),
                "so_thang_gia_han": request_obj.so_thang_gia_han,
                "nguoi_duyet": actor.get_username() if actor else "",
            },
            "nguoi_tao": actor,
            "nguoi_duyet": actor,
            "ngay_duyet": timezone.now(),
        },
    )
    if appendix.hop_dong_id != request_obj.hop_dong_id:
        raise ValidationError("Phu luc khong khop hop dong cua yeu cau.")
    return appendix, created


@transaction.atomic
def ghi_nhan_thay_doi_cu_tru(
    *, resident, event, actor=None, reason="", ma_tham_chieu=None,
):
    allowed = {"them_sau_ky", "roi_sau_ky", "tu_choi", "yeu_cau_bo_sung"}
    if event not in allowed:
        raise ValidationError("Loai thay doi cu tru khong hop le.")
    today = timezone.localdate()
    code = ma_tham_chieu or f"PL-CT-{resident.hop_dong_id}-{resident.pk}-{event}-{today:%Y%m%d}"
    appendix, _ = PhuLucHopDong.objects.get_or_create(
        ma_phu_luc=code,
        defaults={
            "hop_dong": resident.hop_dong,
            "loai": "thay_doi_cu_tru",
            "trang_thai": "da_duyet",
            "ngay_hieu_luc": today,
            "noi_dung": reason or event,
            "ly_do": reason,
            "du_lieu_snapshot": {"resident_id": resident.pk, "event": event},
            "nguoi_tao": actor,
            "nguoi_duyet": actor,
            "ngay_duyet": timezone.now(),
        },
    )
    snapshot, created = BanChupNguoiOCungHopDong.objects.get_or_create(
        phu_luc=appendix,
        nguoi_o_cung=resident,
        loai_su_kien=event,
        defaults={
            "hop_dong": resident.hop_dong,
            "ho_ten": resident.ho_ten,
            "ngay_sinh": resident.ngay_sinh,
            "gioi_tinh": resident.gioi_tinh,
            "cccd": resident.cccd,
            "so_dien_thoai": resident.so_dien_thoai,
            "quan_he": resident.quan_he,
            "trang_thai_xac_minh": (
                "admin_xac_minh" if resident.da_xac_minh_boi_admin else resident.trang_thai
            ),
            "ngay_hieu_luc": today,
            "nguon": "ho_so_nguoi_o_cung",
            "ghi_chu": reason,
        },
    )
    return appendix, snapshot, created
