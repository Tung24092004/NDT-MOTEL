"""Nguồn sự thật cho điều kiện lưu trú, Face ID và quyền ra vào."""
from dataclasses import dataclass
from datetime import datetime
import re

from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone


TRANG_THAI_DANG_O = "dang_o"
TRANG_THAI_TAM_VANG = "tam_vang"
TRANG_THAI_DA_TRA_PHONG = "da_tra_phong"

TRANG_THAI_LUU_TRU_HOP_LE = (
    TRANG_THAI_DANG_O,
    TRANG_THAI_TAM_VANG,
    TRANG_THAI_DA_TRA_PHONG,
)

NGUON_QUYEN_HOP_LE = ("thu_cong", "face_id", "duyet_ghep")


@dataclass(frozen=True)
class KetQuaDieuKien:
    du_dieu_kien: bool
    ly_do: str = ""
    hop_dong: object = None
    ma_trang_thai: str = ""
    so_ngay_con_lai: int | None = None
    muc_canh_bao: str = ""


def _ngay_dia_phuong(tai_thoi_diem=None):
    if tai_thoi_diem is None:
        return timezone.localdate()
    if isinstance(tai_thoi_diem, datetime):
        if timezone.is_aware(tai_thoi_diem):
            return timezone.localtime(tai_thoi_diem).date()
        return tai_thoi_diem.date()
    return tai_thoi_diem


def danh_gia_hop_dong(hop_dong, tai_thoi_diem=None):
    """Ngày kết thúc còn hiệu lực hết ngày; ngày kế tiếp mới hết hạn."""
    if not hop_dong:
        return KetQuaDieuKien(False, "Chưa có hợp đồng lưu trú.", ma_trang_thai="khong_co")

    hom_nay = _ngay_dia_phuong(tai_thoi_diem)
    if hop_dong.trang_thai == "da_huy":
        return KetQuaDieuKien(False, "Hợp đồng đã bị hủy.", hop_dong, "da_huy")
    if hop_dong.ngay_bat_dau > hom_nay:
        return KetQuaDieuKien(False, "Hợp đồng chưa đến ngày bắt đầu.", hop_dong, "chua_hieu_luc")
    if hop_dong.ngay_ket_thuc < hom_nay:
        return KetQuaDieuKien(False, "Hợp đồng đã hết hạn.", hop_dong, "da_het_han")
    if hop_dong.dat_phong.trang_thai != "da_duyet":
        return KetQuaDieuKien(False, "Đặt phòng chưa được duyệt/nhận phòng.", hop_dong, "chua_nhan_phong")
    if hop_dong.trang_thai not in ("dang_hieu_luc", "sap_het_han"):
        return KetQuaDieuKien(False, "Hợp đồng chưa ở trạng thái có hiệu lực.", hop_dong, "chua_hieu_luc")

    con_lai = (hop_dong.ngay_ket_thuc - hom_nay).days
    muc = "cao" if con_lai <= 2 else ("canh_bao" if con_lai <= 5 else "")
    ma = "sap_het_han" if con_lai <= 5 else "dang_hieu_luc"
    return KetQuaDieuKien(True, "", hop_dong, ma, con_lai, muc)


def hop_dong_dang_hieu_luc(hop_dong, tai_thoi_diem=None):
    return danh_gia_hop_dong(hop_dong, tai_thoi_diem).du_dieu_kien


def hop_dong_dang_luu_tru(hop_dong, today=None):
    return hop_dong_dang_hieu_luc(hop_dong, today)


def queryset_hop_dong_luu_tru_hien_tai(*, nguoi_thue=None, phong=None, today=None):
    """The single read model for a current primary tenancy.

    A room status, an approved booking, or a contract's persisted status on
    its own is not sufficient.  The contract lifecycle, booking, date window
    and primary tenant's residency state must agree.  The returned queryset is
    deliberately read-only so callers can safely use it for UI and access
    decisions without advancing lifecycle state during a GET.
    """
    from core.models import HopDong

    if today is None:
        today = timezone.localdate()

    qs = HopDong.objects.filter(
        dat_phong__trang_thai="da_duyet",
        dat_phong__nguoi_thue__dang_hoat_dong=True,
        dat_phong__nguoi_thue__trang_thai_luu_tru__in=(
            TRANG_THAI_DANG_O,
            TRANG_THAI_TAM_VANG,
        ),
        trang_thai__in=("dang_hieu_luc", "sap_het_han"),
        ngay_bat_dau__lte=today,
        ngay_ket_thuc__gte=today,
    )
    if nguoi_thue is not None:
        qs = qs.filter(dat_phong__nguoi_thue=nguoi_thue)
    if phong is not None:
        qs = qs.filter(dat_phong__phong=phong)
    return qs


def lay_hop_dong_luu_tru_hien_tai(*, nguoi_thue=None, phong=None, today=None):
    """Return one deterministic current tenancy contract, or ``None``."""
    return (
        queryset_hop_dong_luu_tru_hien_tai(
            nguoi_thue=nguoi_thue,
            phong=phong,
            today=today,
        )
        .select_related("dat_phong__nguoi_thue", "dat_phong__phong__co_so")
        .order_by("ngay_ket_thuc", "id")
        .first()
    )


def nguoi_thue_dang_luu_tru(nguoi_thue, hop_dong=None, tai_thoi_diem=None):
    if not nguoi_thue or not nguoi_thue.dang_hoat_dong:
        return False
    if nguoi_thue.trang_thai_luu_tru not in (TRANG_THAI_DANG_O, TRANG_THAI_TAM_VANG):
        return False
    return hop_dong is None or hop_dong_dang_hieu_luc(hop_dong, tai_thoi_diem)


def nguoi_o_cung_du_dieu_kien(nguoi_o_cung, tai_thoi_diem=None):
    if (
        not nguoi_o_cung
        or not nguoi_o_cung.da_xac_minh_boi_admin
        or nguoi_o_cung.trang_thai != "dang_o"
    ):
        return False
    hom_nay = _ngay_dia_phuong(tai_thoi_diem)
    if nguoi_o_cung.ngay_vao > hom_nay:
        return False
    if nguoi_o_cung.ngay_ra and nguoi_o_cung.ngay_ra < hom_nay:
        return False
    return hop_dong_dang_hieu_luc(nguoi_o_cung.hop_dong, hom_nay)


def trang_thai_xac_minh_nguoi_o_cung(nguoi_o_cung):
    if nguoi_o_cung.da_xac_minh_boi_admin:
        return "Đã được Admin xác minh"
    if nguoi_o_cung.trang_thai == "cho_bo_sung":
        return "Chờ bổ sung"
    if nguoi_o_cung.trang_thai == "cho_xac_minh":
        return "Chờ Admin xác minh"
    if nguoi_o_cung.trang_thai == "tu_choi":
        return "Từ chối"
    return "Chưa được Admin xác minh"


def ly_do_nguoi_o_cung_chua_du_dieu_kien(nguoi_o_cung, tai_thoi_diem=None):
    if nguoi_o_cung.trang_thai == "cho_bo_sung":
        return "Hồ sơ đang chờ bổ sung thông tin."
    if nguoi_o_cung.trang_thai == "cho_xac_minh":
        return "Hồ sơ đang chờ Admin xác minh."
    if nguoi_o_cung.trang_thai == "tu_choi":
        return "Hồ sơ đã bị từ chối."
    if nguoi_o_cung.trang_thai == "da_xac_minh":
        return "Hồ sơ đã xác minh nhưng chưa bắt đầu lưu trú."
    if nguoi_o_cung.trang_thai == "da_roi":
        return "Người ở cùng đã rời phòng."
    if not nguoi_o_cung.da_xac_minh_boi_admin:
        return "Hồ sơ chưa được Admin đối chiếu và xác minh thủ công."
    if not hop_dong_dang_hieu_luc(nguoi_o_cung.hop_dong, tai_thoi_diem):
        return danh_gia_hop_dong(nguoi_o_cung.hop_dong, tai_thoi_diem).ly_do
    if not nguoi_o_cung_du_dieu_kien(nguoi_o_cung, tai_thoi_diem):
        return "Người ở cùng chưa nằm trong thời hạn lưu trú."
    return ""


def danh_gia_xac_minh_nguoi_o_cung(nguoi_o_cung, tai_thoi_diem=None):
    """Kiểm tra dữ liệu trước khi Admin xác minh thủ công; không tự xác minh."""
    from core.booking_identifiers import normalize_companion_cccd
    from core.models import NguoiThue

    if not nguoi_o_cung:
        return KetQuaDieuKien(False, "Không tìm thấy hồ sơ người ở cùng.")
    try:
        cccd = normalize_companion_cccd(nguoi_o_cung.cccd)
    except ValidationError:
        cccd = None
    if not cccd:
        return KetQuaDieuKien(False, "CCCD phải gồm đúng 9 hoặc 12 chữ số.")
    if NguoiThue.objects.filter(cccd=cccd).exists():
        return KetQuaDieuKien(False, "CCCD đã thuộc một người thuê chính.")
    if (nguoi_o_cung.identity.lich_su_luu_tru.filter(trang_thai="dang_o")
            .exclude(pk=nguoi_o_cung.pk).exists()):
        return KetQuaDieuKien(False, "CCCD đã thuộc một hồ sơ người ở cùng khác.")
    hop_dong = danh_gia_hop_dong(nguoi_o_cung.hop_dong, tai_thoi_diem)
    if not hop_dong.du_dieu_kien:
        return KetQuaDieuKien(False, hop_dong.ly_do, nguoi_o_cung.hop_dong)
    return KetQuaDieuKien(True, "", nguoi_o_cung.hop_dong)


def nguoi_thue_duoc_xac_thuc_cua(nguoi_thue, hop_dong=None, today=None):
    return nguoi_thue_dang_luu_tru(nguoi_thue, hop_dong, today)


def du_dieu_kien_dang_ky_face_id(face_profile, hop_dong=None, tai_thoi_diem=None):
    if not face_profile:
        return KetQuaDieuKien(False, "Chưa có hồ sơ Face ID.")
    if face_profile.trang_thai == "bi_vo_hieu":
        return KetQuaDieuKien(False, "Hồ sơ Face ID đang bị vô hiệu.")
    if face_profile.danh_tinh_nguoi_o_cung_id:
        from core.dich_vu.dong_y_sinh_trac_hoc import has_effective_consent
        resident = face_profile.danh_tinh_nguoi_o_cung.lich_su_luu_tru.filter(
            trang_thai="dang_o"
        ).select_related("hop_dong").first()
        if not resident:
            return KetQuaDieuKien(False, "Danh tinh chua co dot cu tru dang hieu luc.", hop_dong)
        ly_do = ly_do_nguoi_o_cung_chua_du_dieu_kien(resident, tai_thoi_diem)
        if ly_do:
            return KetQuaDieuKien(False, ly_do, resident.hop_dong)
        if not has_effective_consent(face_profile.danh_tinh_nguoi_o_cung):
            return KetQuaDieuKien(False, "Chua co dong y sinh trac hoc ca nhan con hieu luc.", resident.hop_dong)
        return KetQuaDieuKien(True, "", resident.hop_dong)
    if not face_profile.nguoi_thue_id:
        return KetQuaDieuKien(False, "Hồ sơ Face ID chưa gắn đúng chủ thể.")
    if not hop_dong:
        return KetQuaDieuKien(False, "Không có hợp đồng lưu trú đang hiệu lực, duy nhất.")
    if not nguoi_thue_dang_luu_tru(face_profile.nguoi_thue, hop_dong, tai_thoi_diem):
        ly_do = danh_gia_hop_dong(hop_dong, tai_thoi_diem).ly_do if hop_dong else "Người thuê chưa ở trạng thái đang lưu trú."
        return KetQuaDieuKien(False, ly_do, hop_dong)
    if not face_profile.dong_y_du_lieu_khuon_mat:
        return KetQuaDieuKien(False, "Chưa ghi nhận consent dữ liệu khuôn mặt.", hop_dong)
    return KetQuaDieuKien(True, "", hop_dong)


def danh_gia_quyen_ra_vao(quyen, tai_thoi_diem=None):
    """Đánh giá read-only và trả lý do đủ chi tiết cho audit/command."""
    if not quyen:
        return KetQuaDieuKien(False, "Không tìm thấy quyền ra vào.", ma_trang_thai="khong_co")
    hom_nay = _ngay_dia_phuong(tai_thoi_diem)
    ly_do = []
    ma = []
    if quyen.trang_thai != "hoat_dong":
        ly_do.append("Quyền không ở trạng thái hoạt động")
        ma.append("khong_hoat_dong")
    if quyen.nguon_cap not in NGUON_QUYEN_HOP_LE:
        ly_do.append("nguồn cấp legacy/không có provenance được hỗ trợ")
        ma.append("nguon_khong_hop_le")
    if quyen.ngay_bat_dau > hom_nay:
        ly_do.append("quyền chưa đến ngày bắt đầu")
        ma.append("chua_bat_dau")
    if quyen.ngay_ket_thuc and quyen.ngay_ket_thuc < hom_nay:
        ly_do.append("quyền đã qua ngày kết thúc")
        ma.append("quyen_het_han")
    if not quyen.hop_dong_id:
        ly_do.append("thiếu hợp đồng provenance")
        ma.append("thieu_hop_dong")
    else:
        hop_dong = danh_gia_hop_dong(quyen.hop_dong, hom_nay)
        if not hop_dong.du_dieu_kien:
            ly_do.append(hop_dong.ly_do)
            ma.append("hop_dong_khong_hieu_luc")
        if quyen.phong_id != quyen.hop_dong.dat_phong.phong_id:
            ly_do.append("phòng không khớp hợp đồng")
            ma.append("sai_phong")

        if quyen.nguoi_thue_id:
            if quyen.nguoi_thue_id != quyen.hop_dong.dat_phong.nguoi_thue_id:
                ly_do.append("người thuê không phải chủ hợp đồng")
                ma.append("sai_nguoi_thue")
            elif not nguoi_thue_dang_luu_tru(quyen.nguoi_thue, quyen.hop_dong, hom_nay):
                ly_do.append("người thuê không còn đủ điều kiện lưu trú")
                ma.append("nguoi_thue_khong_du_dieu_kien")
        elif quyen.nguoi_o_cung_id:
            if quyen.nguoi_o_cung.hop_dong_id != quyen.hop_dong_id:
                ly_do.append("người ở cùng không thuộc hợp đồng")
                ma.append("sai_nguoi_o_cung")
            elif not nguoi_o_cung_du_dieu_kien(quyen.nguoi_o_cung, hom_nay):
                ly_do.append(ly_do_nguoi_o_cung_chua_du_dieu_kien(quyen.nguoi_o_cung, hom_nay))
                ma.append("nguoi_o_cung_khong_du_dieu_kien")
        else:
            ly_do.append("quyền chưa gắn chủ thể")
            ma.append("thieu_chu_the")

    if ly_do:
        return KetQuaDieuKien(False, "; ".join(ly_do), quyen.hop_dong if quyen.hop_dong_id else None, ",".join(ma))
    return KetQuaDieuKien(True, hop_dong=quyen.hop_dong, ma_trang_thai="hop_le")


def quyen_ra_vao_con_hieu_luc(quyen, tai_thoi_diem=None):
    return danh_gia_quyen_ra_vao(quyen, tai_thoi_diem).du_dieu_kien


@transaction.atomic
def thu_hoi_quyen_nguoi_o_cung(
    nguoi_o_cung,
    *,
    ngay_thu_hoi=None,
    nguon="He thong",
    trang_thai="het_han",
):
    """Idempotent: chỉ xử lý quyền đang hoạt động và giữ nguyên lịch sử."""
    if ngay_thu_hoi is None:
        ngay_thu_hoi = timezone.localdate()
    marker = f"[RESIDENCY_ELIGIBILITY:{nguon}]"
    qs = nguoi_o_cung.quyen_ra_vao.select_for_update().filter(trang_thai="hoat_dong")
    so_luong = 0
    for quyen in qs:
        quyen.trang_thai = trang_thai
        quyen.active_access_key = None
        if not quyen.ngay_ket_thuc or quyen.ngay_ket_thuc > ngay_thu_hoi:
            quyen.ngay_ket_thuc = ngay_thu_hoi
        if marker not in (quyen.ghi_chu or ""):
            quyen.ghi_chu = f"{quyen.ghi_chu or ''}\n{marker}".strip()
        quyen.save(update_fields=["trang_thai", "active_access_key", "ngay_ket_thuc", "ghi_chu", "ngay_cap_nhat"])
        so_luong += 1
    return so_luong


def danh_sach_quyen_dang_hieu_luc(queryset=None, today=None):
    from core.models import QuyenRaVao

    if queryset is None:
        queryset = QuyenRaVao.objects.all()

    if today is None:
        today = timezone.localdate()

    return queryset.filter(
        trang_thai="hoat_dong",
        ngay_bat_dau__lte=today,
    ).filter(
        Q(ngay_ket_thuc__isnull=True)
        | Q(ngay_ket_thuc__gte=today)
    )


def nguoi_thue_con_hop_dong_luu_tru_hieu_luc(
    nguoi_thue,
    *,
    exclude_contract_id=None,
    today=None,
):
    if today is None:
        today = timezone.localdate()

    qs = queryset_hop_dong_luu_tru_hien_tai(nguoi_thue=nguoi_thue, today=today)
    if exclude_contract_id:
        qs = qs.exclude(pk=exclude_contract_id)
    return qs.exists()


@transaction.atomic
def thu_hoi_quyen_luu_tru(
    nguoi_thue,
    *,
    ngay_thu_hoi=None,
    ly_do="",
    hop_dong=None,
):
    """Revoke active tenant rights, optionally only for one contract."""
    if ngay_thu_hoi is None:
        ngay_thu_hoi = timezone.localdate()

    qs = nguoi_thue.quyen_ra_vao.select_for_update()
    if hop_dong is not None:
        qs = qs.filter(
            hop_dong=hop_dong,
            phong_id=hop_dong.dat_phong.phong_id,
            nguoi_o_cung__isnull=True,
            loai_quyen="chu_phong",
        )
    qs = danh_sach_quyen_dang_hieu_luc(qs)

    ly_do = (ly_do or "Thu hoi theo vong doi luu tru.").strip()
    so_luong = 0

    for quyen in qs:
        ghi_chu = quyen.ghi_chu or ""
        quyen.trang_thai = "bi_thu_hoi"
        quyen.active_access_key = None
        quyen.ngay_ket_thuc = ngay_thu_hoi
        quyen.ghi_chu = f"{ghi_chu}\n{ly_do}".strip()
        quyen.save(
            update_fields=[
                "trang_thai",
                "active_access_key",
                "ngay_ket_thuc",
                "ghi_chu",
                "ngay_cap_nhat",
            ]
        )
        so_luong += 1

    return so_luong


@transaction.atomic
def cap_nhat_trang_thai_luu_tru(
    nguoi_thue,
    trang_thai_moi,
    *,
    nguoi_thuc_hien=None,
    ly_do="",
    hop_dong=None,
):
    if trang_thai_moi not in TRANG_THAI_LUU_TRU_HOP_LE:
        raise ValueError("Trang thai luu tru khong hop le.")

    contracts_to_close = []
    if trang_thai_moi == TRANG_THAI_DA_TRA_PHONG:
        from core.models import HopDong
        contract_qs = HopDong.objects.filter(
            dat_phong__nguoi_thue=nguoi_thue,
            dat_phong__trang_thai="da_duyet",
            trang_thai__in=("dang_hieu_luc", "sap_het_han"),
            ngay_bat_dau__lte=timezone.localdate(),
            ngay_ket_thuc__gte=timezone.localdate(),
        )
        if hop_dong is not None:
            contract_qs = contract_qs.filter(pk=hop_dong.pk)
        contracts_to_close = list(contract_qs.values_list("pk", flat=True))

    if trang_thai_moi == TRANG_THAI_DA_TRA_PHONG and hop_dong is not None:
        if nguoi_thue_con_hop_dong_luu_tru_hieu_luc(
            nguoi_thue,
            exclude_contract_id=getattr(hop_dong, "id", None),
        ):
            return 0

    nguoi_thue.trang_thai_luu_tru = trang_thai_moi
    nguoi_thue.save(update_fields=["trang_thai_luu_tru", "ngay_cap_nhat"])

    if trang_thai_moi == TRANG_THAI_DA_TRA_PHONG:
        # Checkout is the parent tenancy event.  It closes co-tenant stays
        # without fabricating voluntary-leave appendices or notifications.
        from core.models import HopDong
        from core.dich_vu.yeu_cau_nguoi_o_cung import close_active_residencies_for_contract
        for contract_id in contracts_to_close:
            stub = HopDong.objects.select_related("dat_phong__phong").get(pk=contract_id)
            stub.dat_phong.phong.__class__.objects.select_for_update().get(pk=stub.dat_phong.phong_id)
            locked_contract = HopDong.objects.select_for_update().select_related(
                "dat_phong__phong"
            ).get(pk=contract_id)
            close_active_residencies_for_contract(
                contract=locked_contract, leave_date=timezone.localdate(),
                access_status="bi_thu_hoi", access_source="Primary tenant checkout",
            )
        ten_nguoi = nguoi_thuc_hien.username if nguoi_thuc_hien else "He thong"
        return thu_hoi_quyen_luu_tru(
            nguoi_thue,
            ly_do=ly_do or f"Nguoi thue duoc danh dau da tra phong boi {ten_nguoi}.",
            hop_dong=hop_dong,
        )

    return 0
