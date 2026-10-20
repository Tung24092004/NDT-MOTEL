"""Xac dinh mot viec quan trong nhat cho tai khoan nguoi thue."""
from django.urls import reverse
from django.utils import timezone

from core.models import DatPhong, FaceProfile, HoaDon
from core.dich_vu.luu_tru import lay_hop_dong_luu_tru_hien_tai


def ho_so_du_dieu_kien_dat_phong(nguoi_thue):
    """Dong bo voi dieu kien danh tinh dang duoc dung khi dat phong."""
    cccd = (nguoi_thue.cccd or "").strip()
    so_dien_thoai = (nguoi_thue.so_dien_thoai or "").strip()
    return bool(
        (nguoi_thue.ho_ten or "").strip()
        and len(cccd) == 12
        and cccd.isascii()
        and cccd.isdigit()
        and so_dien_thoai.isdigit()
        and 9 <= len(so_dien_thoai) <= 11
    )


def _ket_qua(ma, tieu_de, mo_ta, *, nhan_nut="", duong_dan="", muc_do="info"):
    return {
        "ma": ma,
        "tieu_de": tieu_de,
        "mo_ta": mo_ta,
        "nhan_nut": nhan_nut,
        "duong_dan": duong_dan,
        "muc_do": muc_do,
    }


def _yeu_cau_coc(nguoi_thue):
    bookings = (
        DatPhong.objects.filter(nguoi_thue=nguoi_thue, trang_thai="cho_duyet")
        .prefetch_related("giao_dich_coc")
        .order_by("ngay_dat", "id")
    )
    cho_thanh_toan = None
    cho_xac_nhan = None

    for booking in bookings:
        attempts = list(booking.giao_dich_coc.all())
        active = next((item for item in attempts if item.active_slot == 1), None)
        latest = active or max(attempts, key=lambda item: item.pk, default=None)
        expired = bool(
            booking.han_thanh_toan_coc
            and booking.han_thanh_toan_coc <= timezone.now()
            and not (active and active.trang_thai in ("cho_xac_nhan", "da_xac_nhan"))
        )
        snapshot = bool(
            booking.da_dong_y_dieu_khoan
            and booking.gia_thue_thang_tai_thoi_diem_dat is not None
        )

        if active and active.trang_thai == "cho_xac_nhan":
            cho_xac_nhan = cho_xac_nhan or booking
            continue
        if snapshot and not expired and (
            latest is None or latest.trang_thai in ("chua_thanh_toan", "tu_choi")
        ):
            cho_thanh_toan = cho_thanh_toan or booking

    return cho_thanh_toan, cho_xac_nhan


def _hop_dong_luu_tru_hop_le(nguoi_thue):
    return lay_hop_dong_luu_tru_hien_tai(nguoi_thue=nguoi_thue)


def lay_viec_tiep_theo(nguoi_thue):
    """Tra ve dung mot muc theo thu tu uu tien cua hanh trinh thue phong."""
    if not ho_so_du_dieu_kien_dat_phong(nguoi_thue):
        return _ket_qua(
            "ho_so",
            "Hoàn thiện hồ sơ",
            "Bổ sung họ tên, CCCD và số điện thoại hợp lệ trước khi gửi yêu cầu đặt phòng.",
            nhan_nut="Hoàn thiện hồ sơ",
            duong_dan=reverse("cap_nhat_thong_tin"),
            muc_do="warning",
        )

    cho_thanh_toan, cho_xac_nhan = _yeu_cau_coc(nguoi_thue)
    if cho_thanh_toan:
        return _ket_qua(
            "thanh_toan_coc",
            "Thanh toán tiền cọc",
            f"Yêu cầu {cho_thanh_toan.ma_yeu_cau} đang chờ bạn hoàn tất tiền cọc.",
            nhan_nut="Thanh toán tiền cọc",
            duong_dan=reverse("thanh_toan_coc_cua_toi", args=[cho_thanh_toan.pk]),
            muc_do="warning",
        )
    if cho_xac_nhan:
        return _ket_qua(
            "cho_xac_nhan_coc",
            "Đang chờ xác nhận tiền cọc",
            f"Bạn đã báo thanh toán cho yêu cầu {cho_xac_nhan.ma_yeu_cau}. Không cần thanh toán lại.",
            nhan_nut="Xem yêu cầu",
            duong_dan=reverse("chi_tiet_dat_phong_cua_toi", args=[cho_xac_nhan.pk]),
        )

    hop_dong = _hop_dong_luu_tru_hop_le(nguoi_thue)
    if hop_dong and not FaceProfile.objects.filter(
        nguoi_thue=nguoi_thue,
        trang_thai="da_xac_thuc",
        dong_y_du_lieu_khuon_mat=True,
    ).exists():
        return _ket_qua(
            "face_id",
            "Đăng ký Face ID",
            f"Hợp đồng {hop_dong.so_hop_dong} đang hiệu lực nhưng hồ sơ Face ID chưa hợp lệ.",
            nhan_nut="Đăng ký Face ID",
            duong_dan=reverse("nhan_dien_su_dung_phong"),
        )

    hoa_don = (
        HoaDon.objects.filter(
            hop_dong__dat_phong__nguoi_thue=nguoi_thue,
            trang_thai__in=("chua_thanh_toan", "qua_han"),
        )
        .order_by("han_thanh_toan", "id")
        .first()
    )
    if hoa_don:
        return _ket_qua(
            "hoa_don",
            "Xem và thanh toán hóa đơn",
            f"Hóa đơn tháng {hoa_don.thang}/{hoa_don.nam} có hạn thanh toán {hoa_don.han_thanh_toan:%d/%m/%Y}.",
            nhan_nut="Xem hóa đơn",
            duong_dan=reverse("chi_tiet_hoa_don_cua_toi", args=[hoa_don.pk]),
            muc_do="warning" if hoa_don.trang_thai == "qua_han" else "info",
        )

    return _ket_qua(
        "on_dinh",
        "Bạn không có việc cần xử lý ngay",
        "Tài khoản đang ở trạng thái ổn định. Bạn có thể xem các phòng đang có.",
        nhan_nut="Xem phòng",
        duong_dan=reverse("danh_sach_phong"),
        muc_do="success",
    )
