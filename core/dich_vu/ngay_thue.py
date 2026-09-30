"""Nghiep vu dich vu/ngay thue."""
from datetime import timedelta
import calendar


def tinh_ngay_ket_thuc_theo_thang(ngay_bat_dau, so_thang):
    """
    Tính ngày kết thúc thời hạn thuê theo tháng lịch.

    Ví dụ:
        15/09/2026 + 6 tháng
        -> ngày kết thúc: 14/03/2027

    Trường hợp ngày bắt đầu nằm cuối tháng như 31/01,
    hệ thống tự xử lý theo ngày cuối cùng hợp lệ
    của tháng tương ứng.
    """

    if not ngay_bat_dau:
        raise ValueError("Ngày bắt đầu không hợp lệ.")

    if not isinstance(so_thang, int) or so_thang < 1:
        raise ValueError("Số tháng thuê không hợp lệ.")

    # -----------------------------------------------------
    # TÍNH THÁNG / NĂM ĐÍCH
    # -----------------------------------------------------

    tong_thang = (
        ngay_bat_dau.year * 12
        + (ngay_bat_dau.month - 1)
        + so_thang
    )

    nam_dich = tong_thang // 12
    thang_dich = tong_thang % 12 + 1

    # -----------------------------------------------------
    # NGÀY CUỐI CỦA THÁNG ĐÍCH
    # -----------------------------------------------------

    ngay_cuoi_thang_dich = calendar.monthrange(
        nam_dich,
        thang_dich
    )[1]

    # -----------------------------------------------------
    # NẾU NGÀY BAN ĐẦU TỒN TẠI Ở THÁNG ĐÍCH
    # -----------------------------------------------------

    if ngay_bat_dau.day <= ngay_cuoi_thang_dich:

        moc_cung_ngay = ngay_bat_dau.replace(
            year=nam_dich,
            month=thang_dich,
            day=ngay_bat_dau.day,
        )

        return moc_cung_ngay - timedelta(days=1)

    # -----------------------------------------------------
    # TRƯỜNG HỢP CUỐI THÁNG
    #
    # Ví dụ:
    # 31/01 + 1 tháng -> tháng 2 không có ngày 31.
    # Khi đó thời hạn kết thúc ở ngày cuối tháng 2.
    # -----------------------------------------------------

    return ngay_bat_dau.replace(
        year=nam_dich,
        month=thang_dich,
        day=ngay_cuoi_thang_dich,
    )
