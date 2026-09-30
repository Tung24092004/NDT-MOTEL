"""Nghiep vu thanh toan."""
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from core.tien_ich import ghi_nhat_ky
from core.dich_vu.thong_bao_quan_tri import notify_admin_event
from core.models import (
    CoSo,
    Phong,
    HinhAnhPhong,
    NguoiThue,
    DatPhong,
    HopDong,
    LichSuHopDong,
    YeuCauGiaHanHopDong,
    HoaDon,
    YeuCauSuaChua,
    ChinhSachHoTro,
    ThongBao,
    YeuCauGhepNguoi,
    LichSuThanhToan,

    # Smart Room — Phase 1
    NguoiOCungPhong,
    FaceProfile,
    QuyenRaVao,
    LichSuRaVao,

    # Nhật ký thao tác
    NhatKyThaoTac,
)
from core.dich_vu.phan_quyen import la_admin


def thanh_toan_hoa_don_cua_toi(request, id):

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard_admin")

    nguoi_thue = (
        NguoiThue.objects
        .filter(
            tai_khoan=request.user,
            dang_hoat_dong=True,
        )
        .first()
    )

    if not nguoi_thue:
        messages.error(
            request,
            "Tài khoản chưa được liên kết với thông tin "
            "người thuê đang hoạt động."
        )
        return redirect("tai_khoan")

    hoa_don = get_object_or_404(
        HoaDon.objects.select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__nguoi_thue",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
        ),
        id=id,
        hop_dong__dat_phong__nguoi_thue=nguoi_thue,
    )

    if hoa_don.trang_thai == "da_thanh_toan":
        messages.info(
            request,
            "Hóa đơn này đã được xác nhận thanh toán."
        )
        return redirect(
            "chi_tiet_hoa_don_cua_toi",
            id=hoa_don.id
        )

    if hoa_don.trang_thai == "huy":
        messages.error(
            request,
            "Hóa đơn đã hủy nên không thể thanh toán."
        )
        return redirect(
            "chi_tiet_hoa_don_cua_toi",
            id=hoa_don.id
        )

    if hoa_don.trang_thai == "cho_xac_nhan":
        messages.info(
            request,
            "Hóa đơn đã gửi yêu cầu xác nhận thanh toán. "
            "Vui lòng chờ quản trị viên kiểm tra."
        )
        return redirect(
            "chi_tiet_hoa_don_cua_toi",
            id=hoa_don.id
        )

    if hoa_don.trang_thai not in [
        "chua_thanh_toan",
        "qua_han",
    ]:
        messages.error(
            request,
            "Trạng thái hóa đơn hiện tại không cho phép thanh toán."
        )
        return redirect(
            "chi_tiet_hoa_don_cua_toi",
            id=hoa_don.id
        )

    hop_dong = hoa_don.hop_dong
    phong = hop_dong.dat_phong.phong

    tong_tien = hoa_don.tong_tien

    tong_tien_hien_thi = (
        f"{tong_tien:,.0f}".replace(",", ".")
    )

    # =====================================================
    # THÔNG TIN VIETQR
    # =====================================================

    ngan_hang = "Techcombank"
    ma_ngan_hang = "TCB"
    so_tai_khoan = "19075135295011"
    chu_tai_khoan = "NGHIEM DINH TUNG"

    noi_dung_chuyen_khoan = (
        f"NDTMOTEL HD{hoa_don.id}"
    )

    from urllib.parse import urlencode

    tham_so_qr = urlencode(
        {
            "amount": int(tong_tien),
            "addInfo": noi_dung_chuyen_khoan,
            "accountName": chu_tai_khoan,
        }
    )

    qr_url = (
        f"https://img.vietqr.io/image/"
        f"{ma_ngan_hang}-"
        f"{so_tai_khoan}-compact2.png?"
        f"{tham_so_qr}"
    )

    context_chung = {
        "hoa_don": hoa_don,
        "nguoi_thue": nguoi_thue,
        "hop_dong": hop_dong,
        "phong": phong,

        "tong_tien": tong_tien_hien_thi,
        "tong_tien_goc": tong_tien,

        "ngan_hang": ngan_hang,
        "so_tai_khoan": so_tai_khoan,
        "chu_tai_khoan": chu_tai_khoan,
        "noi_dung_chuyen_khoan":
            noi_dung_chuyen_khoan,
        "qr_url": qr_url,
    }

    # =====================================================
    # GET — CHỌN PHƯƠNG THỨC
    # =====================================================

    if request.method == "GET":

        context_chung["buoc_thanh_toan"] = "chon"

        return render(
            request,
            "core/thanh_toan_hoa_don_cua_toi.html",
            context_chung
        )

    if request.method != "POST":
        return redirect(
            "thanh_toan_hoa_don_cua_toi",
            id=hoa_don.id
        )

    buoc = request.POST.get(
        "buoc",
        ""
    ).strip()

    phuong_thuc = request.POST.get(
        "phuong_thuc",
        ""
    ).strip()

    if phuong_thuc not in [
        "tien_mat",
        "chuyen_khoan",
    ]:
        messages.error(
            request,
            "Vui lòng chọn phương thức thanh toán."
        )
        return redirect(
            "thanh_toan_hoa_don_cua_toi",
            id=hoa_don.id
        )

    # =====================================================
    # BƯỚC 1 → REVIEW
    # =====================================================

    if buoc == "xac_nhan":

        context_chung.update(
            {
                "phuong_thuc": phuong_thuc,
                "buoc_thanh_toan": "xac_thuc",
            }
        )

        return render(
            request,
            "core/thanh_toan_hoa_don_cua_toi.html",
            context_chung
        )

    # =====================================================
    # BƯỚC 2 → GỬI YÊU CẦU ADMIN
    # =====================================================

    if buoc != "xac_thuc":
        messages.error(
            request,
            "Yêu cầu thanh toán không hợp lệ."
        )
        return redirect(
            "thanh_toan_hoa_don_cua_toi",
            id=hoa_don.id
        )

    xac_nhan = request.POST.get(
        "xac_nhan",
        ""
    ).strip()

    if xac_nhan != "dong_y":
        messages.error(
            request,
            "Vui lòng xác nhận thông tin trước khi gửi yêu cầu."
        )

        context_chung.update(
            {
                "phuong_thuc": phuong_thuc,
                "buoc_thanh_toan": "xac_thuc",
            }
        )

        return render(
            request,
            "core/thanh_toan_hoa_don_cua_toi.html",
            context_chung
        )

    # =====================================================
    # LOCK HÓA ĐƠN — CHỐNG GỬI TRÙNG
    # =====================================================

    with transaction.atomic():

        hoa_don_khoa = get_object_or_404(
            HoaDon.objects
            .select_for_update()
            .select_related(
                "hop_dong",
                "hop_dong__dat_phong",
                "hop_dong__dat_phong__nguoi_thue",
                "hop_dong__dat_phong__phong",
            ),
            id=id,
            hop_dong__dat_phong__nguoi_thue=nguoi_thue,
        )

        if hoa_don_khoa.trang_thai == "cho_xac_nhan":
            messages.info(
                request,
                "Yêu cầu xác nhận thanh toán đã được gửi trước đó."
            )
            return redirect(
                "chi_tiet_hoa_don_cua_toi",
                id=hoa_don_khoa.id
            )

        if hoa_don_khoa.trang_thai == "da_thanh_toan":
            messages.info(
                request,
                "Hóa đơn đã được xác nhận thanh toán."
            )
            return redirect(
                "chi_tiet_hoa_don_cua_toi",
                id=hoa_don_khoa.id
            )

        if hoa_don_khoa.trang_thai == "huy":
            messages.error(
                request,
                "Hóa đơn đã hủy nên không thể gửi yêu cầu."
            )
            return redirect(
                "chi_tiet_hoa_don_cua_toi",
                id=hoa_don_khoa.id
            )

        if hoa_don_khoa.trang_thai not in [
            "chua_thanh_toan",
            "qua_han",
        ]:
            messages.error(
                request,
                "Trạng thái hóa đơn đã thay đổi. "
                "Vui lòng tải lại trang."
            )
            return redirect(
                "chi_tiet_hoa_don_cua_toi",
                id=hoa_don_khoa.id
            )

        trang_thai_cu = hoa_don_khoa.trang_thai
        phuong_thuc_cu = hoa_don_khoa.phuong_thuc

        # QUAN TRỌNG:
        # Khách chỉ gửi yêu cầu.
        # Không ghi ngày thanh toán.
        # Không sinh mã giao dịch.
        # Không ghi người xác nhận.
        # Không tạo LichSuThanhToan.

        hoa_don_khoa.trang_thai = "cho_xac_nhan"
        hoa_don_khoa.phuong_thuc = phuong_thuc
        hoa_don_khoa.ngay_thanh_toan = None
        hoa_don_khoa.ma_giao_dich = ""
        hoa_don_khoa.nguoi_xac_nhan = None

        hoa_don_khoa.save(
            update_fields=[
                "trang_thai",
                "phuong_thuc",
                "ngay_thanh_toan",
                "ma_giao_dich",
                "nguoi_xac_nhan",
                "ngay_cap_nhat",
            ]
        )

        thong_bao_moi = ThongBao.objects.create(
            nguoi_thue=nguoi_thue,
            ma_tham_chieu=f"INVOICE:{hoa_don_khoa.pk}:PAYMENT_REPORTED:USER",
            tieu_de="Đã gửi yêu cầu xác nhận thanh toán",
            noi_dung=(
                f"Yêu cầu xác nhận thanh toán hóa đơn "
                f"{hoa_don_khoa.thang}/{hoa_don_khoa.nam} "
                f"phòng {hoa_don_khoa.hop_dong.dat_phong.phong.so_phong} "
                f"đã được gửi. Phương thức: "
                f"{hoa_don_khoa.get_phuong_thuc_display()}. "
                f"Quản trị viên sẽ kiểm tra trước khi "
                f"ghi nhận hóa đơn đã thanh toán."
            ),
            loai="thanh_toan",
            muc_do="binh_thuong",
            url_lien_ket=f"/hoa-don-cua-toi/{hoa_don_khoa.pk}/",
        )

        notify_admin_event(
            reference=f"INVOICE:{hoa_don_khoa.pk}:PAYMENT_REPORTED",
            notification_type="thanh_toan",
            title="Hóa đơn chờ xác nhận thanh toán",
            text=(
                f"{nguoi_thue.ho_ten} đã báo thanh toán hóa đơn "
                f"{hoa_don_khoa.thang}/{hoa_don_khoa.nam}, phòng "
                f"{hoa_don_khoa.hop_dong.dat_phong.phong.so_phong}, "
                f"số tiền {hoa_don_khoa.tong_tien:,.0f} đồng."
            ),
            url=f"/quan-ly-hoa-don/{hoa_don_khoa.pk}/",
        )

        ghi_nhat_ky(
            request=request,
            hanh_dong="Gửi yêu cầu",
            module="Hóa đơn",
            doi_tuong="HoaDon",
            doi_tuong_id=hoa_don_khoa.id,
            tieu_de=(
                f"Gửi yêu cầu xác nhận thanh toán "
                f"{hoa_don_khoa.thang}/{hoa_don_khoa.nam}"
            ),
            noi_dung=(
                f"Người thuê {request.user.username} "
                f"gửi yêu cầu xác nhận thanh toán hóa đơn "
                f"{hoa_don_khoa.thang}/{hoa_don_khoa.nam} "
                f"bằng {hoa_don_khoa.get_phuong_thuc_display()}."
            ),
            du_lieu_cu={
                "trang_thai": trang_thai_cu,
                "phuong_thuc": phuong_thuc_cu,
            },
            du_lieu_moi={
                "trang_thai": "cho_xac_nhan",
                "phuong_thuc": phuong_thuc,
                "so_tien": str(hoa_don_khoa.tong_tien),
                "thong_bao_id": thong_bao_moi.id,
            },
        )

        ghi_nhat_ky(
            request=request,
            hanh_dong="Tạo",
            module="Thông báo",
            doi_tuong="ThongBao",
            doi_tuong_id=thong_bao_moi.id,
            tieu_de="Thông báo yêu cầu xác nhận thanh toán",
            noi_dung=(
                f"Tạo thông báo yêu cầu xác nhận thanh toán "
                f"cho {nguoi_thue.ho_ten}."
            ),
            du_lieu_cu={},
            du_lieu_moi={
                "thong_bao_id": thong_bao_moi.id,
                "hoa_don_id": hoa_don_khoa.id,
                "loai": thong_bao_moi.loai,
            },
        )

    messages.success(
        request,
        "Đã gửi yêu cầu xác nhận thanh toán. "
        "Hóa đơn đang chờ quản trị viên kiểm tra."
    )

    return redirect(
        "chi_tiet_hoa_don_cua_toi",
        id=id
    )


def xu_ly_hoa_don(request, id):

    # =====================================================
    # KIỂM TRA ĐĂNG NHẬP / QUYỀN ADMIN
    # =====================================================

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method != "POST":
        return redirect(
            "chi_tiet_hoa_don",
            id=id
        )

    hanh_dong = request.POST.get(
        "hanh_dong",
        ""
    ).strip()

    if hanh_dong not in [
        "xac_nhan_thanh_toan",
        "huy_thanh_toan",
    ]:
        messages.error(
            request,
            "Thao tác xử lý hóa đơn không hợp lệ."
        )
        return redirect(
            "chi_tiet_hoa_don",
            id=id
        )

    # =====================================================
    # TRANSACTION
    # =====================================================

    with transaction.atomic():

        hoa_don = get_object_or_404(
            HoaDon.objects
            .select_for_update()
            .select_related(
                "hop_dong",
                "hop_dong__dat_phong",
                "hop_dong__dat_phong__nguoi_thue",
                "hop_dong__dat_phong__phong",
                "hop_dong__dat_phong__phong__co_so",
            ),
            id=id
        )

        hop_dong = hoa_don.hop_dong
        nguoi_thue = (
            hop_dong
            .dat_phong
            .nguoi_thue
        )
        phong = (
            hop_dong
            .dat_phong
            .phong
        )

        # =================================================
        # XÁC NHẬN THANH TOÁN
        # =================================================

        if hanh_dong == "xac_nhan_thanh_toan":

            # ---------------------------------------------
            # TRẠNG THÁI KHÔNG CHO XỬ LÝ
            # ---------------------------------------------

            if hoa_don.trang_thai == "huy":
                messages.error(
                    request,
                    "Hóa đơn đã hủy, không thể xác nhận thanh toán."
                )
                return redirect(
                    "chi_tiet_hoa_don",
                    id=hoa_don.id
                )

            if hoa_don.trang_thai == "da_thanh_toan":
                messages.info(
                    request,
                    "Hóa đơn này đã được thanh toán trước đó."
                )
                return redirect(
                    "chi_tiet_hoa_don",
                    id=hoa_don.id
                )

            if hoa_don.trang_thai != "cho_xac_nhan":
                messages.warning(
                    request,
                    "Chỉ có thể xác nhận hóa đơn đang chờ đối soát thanh toán."
                )
                return redirect(
                    "chi_tiet_hoa_don",
                    id=hoa_don.id
                )

            # ---------------------------------------------
            # PHƯƠNG THỨC THANH TOÁN
            # ---------------------------------------------

            phuong_thuc = request.POST.get(
                "phuong_thuc",
                hoa_don.phuong_thuc or ""
            ).strip()

            if phuong_thuc not in [
                "tien_mat",
                "chuyen_khoan",
            ]:
                messages.error(
                    request,
                    "Vui lòng chọn phương thức thanh toán hợp lệ."
                )
                return redirect(
                    "chi_tiet_hoa_don",
                    id=hoa_don.id
                )

            trang_thai_cu = (
                hoa_don.trang_thai
            )

            # ---------------------------------------------
            # TỰ SINH MÃ GIAO DỊCH
            # ---------------------------------------------

            ma_giao_dich = (
                "TT-"
                + timezone.localdate().strftime(
                    "%Y%m%d"
                )
                + "-"
                + uuid.uuid4().hex[:8].upper()
            )

            # ---------------------------------------------
            # CẬP NHẬT HÓA ĐƠN
            # ---------------------------------------------

            hoa_don.trang_thai = (
                "da_thanh_toan"
            )
            hoa_don.ngay_thanh_toan = (
                timezone.now()
            )
            hoa_don.phuong_thuc = (
                phuong_thuc
            )
            hoa_don.ma_giao_dich = (
                ma_giao_dich
            )
            hoa_don.nguoi_xac_nhan = (
                request.user
            )

            hoa_don.save(
                update_fields=[
                    "trang_thai",
                    "ngay_thanh_toan",
                    "phuong_thuc",
                    "ma_giao_dich",
                    "nguoi_xac_nhan",
                    "ngay_cap_nhat",
                ]
            )

            # ---------------------------------------------
            # LỊCH SỬ THANH TOÁN
            # ---------------------------------------------

            lich_su = (
                LichSuThanhToan.objects.create(
                    hoa_don=hoa_don,
                    so_tien=hoa_don.tong_tien,
                    phuong_thuc=phuong_thuc,
                    ma_giao_dich=ma_giao_dich,
                    noi_dung=(
                        f"Xác nhận thanh toán hóa đơn "
                        f"{hoa_don.thang}/{hoa_don.nam}."
                    ),
                    nguoi_thuc_hien=request.user,
                    dia_chi_ip=(
                        request.META
                        .get(
                            "HTTP_X_FORWARDED_FOR",
                            ""
                        )
                        .split(",")[0]
                        .strip()
                        or request.META.get(
                            "REMOTE_ADDR"
                        )
                    ),
                )
            )

            # ---------------------------------------------
            # THÔNG BÁO USER
            # ---------------------------------------------

            thong_bao_moi = (
                ThongBao.objects.create(
                    nguoi_thue=nguoi_thue,
                    tieu_de=(
                        "Thanh toán hóa đơn thành công"
                    ),
                    noi_dung=(
                        f"Hóa đơn tháng "
                        f"{hoa_don.thang}/{hoa_don.nam} "
                        f"của phòng {phong.so_phong} "
                        f"đã được xác nhận thanh toán. "
                        f"Số tiền: "
                        f"{hoa_don.tong_tien:,.0f} đồng. "
                        f"Mã giao dịch: {ma_giao_dich}."
                    ),
                    loai="thanh_toan",
                    muc_do="binh_thuong",
                )
            )

            # ---------------------------------------------
            # AUDIT HÓA ĐƠN
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Thanh toán",
                module="Hóa đơn",
                doi_tuong="HoaDon",
                doi_tuong_id=hoa_don.id,
                tieu_de=(
                    f"Xác nhận thanh toán hóa đơn "
                    f"{hoa_don.thang}/{hoa_don.nam}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} "
                    f"xác nhận thanh toán hóa đơn "
                    f"{hoa_don.thang}/{hoa_don.nam} "
                    f"của hợp đồng "
                    f"{hop_dong.so_hop_dong}."
                ),
                du_lieu_cu={
                    "trang_thai":
                        trang_thai_cu,
                },
                du_lieu_moi={
                    "trang_thai":
                        hoa_don.trang_thai,
                    "so_tien":
                        str(hoa_don.tong_tien),
                    "phuong_thuc":
                        phuong_thuc,
                    "ma_giao_dich":
                        ma_giao_dich,
                    "nguoi_xac_nhan":
                        request.user.username,
                    "lich_su_thanh_toan_id":
                        lich_su.id,
                    "thong_bao_id":
                        thong_bao_moi.id,
                },
            )

            # ---------------------------------------------
            # AUDIT THÔNG BÁO
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Thông báo",
                doi_tuong="ThongBao",
                doi_tuong_id=thong_bao_moi.id,
                tieu_de=(
                    f"Tạo thông báo thanh toán "
                    f"{hoa_don.thang}/{hoa_don.nam}"
                ),
                noi_dung=(
                    f"Tạo thông báo xác nhận thanh toán "
                    f"cho {nguoi_thue.ho_ten}."
                ),
                du_lieu_cu={},
                du_lieu_moi={
                    "thong_bao_id":
                        thong_bao_moi.id,
                    "hoa_don_id":
                        hoa_don.id,
                    "ma_giao_dich":
                        ma_giao_dich,
                    "loai":
                        thong_bao_moi.loai,
                    "muc_do":
                        thong_bao_moi.muc_do,
                },
            )

            messages.success(
                request,
                "Đã xác nhận thanh toán hóa đơn thành công."
            )

        # =================================================
        # HỦY / HOÀN TRẠNG THÁI THANH TOÁN
        # =================================================

        elif hanh_dong == "huy_thanh_toan":

            # ---------------------------------------------
            # CHỈ HỦY KHI ĐANG ĐÃ THANH TOÁN
            # ---------------------------------------------

            if hoa_don.trang_thai != "da_thanh_toan":
                messages.warning(
                    request,
                    "Hóa đơn này hiện không ở trạng thái đã thanh toán."
                )
                return redirect(
                    "chi_tiet_hoa_don",
                    id=hoa_don.id
                )

            trang_thai_cu = (
                hoa_don.trang_thai
            )

            ngay_thanh_toan_cu = (
                hoa_don.ngay_thanh_toan
            )

            phuong_thuc_cu = (
                hoa_don.phuong_thuc
            )

            ma_giao_dich_cu = (
                hoa_don.ma_giao_dich
            )

            # ---------------------------------------------
            # TÍNH LẠI TRẠNG THÁI ĐÚNG THEO HẠN
            # ---------------------------------------------

            if (
                hoa_don.han_thanh_toan
                and
                hoa_don.han_thanh_toan
                < timezone.localdate()
            ):
                trang_thai_moi = "qua_han"
            else:
                trang_thai_moi = (
                    "chua_thanh_toan"
                )

            hoa_don.trang_thai = (
                trang_thai_moi
            )
            hoa_don.ngay_thanh_toan = None
            hoa_don.phuong_thuc = ""
            hoa_don.ma_giao_dich = ""
            hoa_don.nguoi_xac_nhan = None

            hoa_don.save(
                update_fields=[
                    "trang_thai",
                    "ngay_thanh_toan",
                    "phuong_thuc",
                    "ma_giao_dich",
                    "nguoi_xac_nhan",
                    "ngay_cap_nhat",
                ]
            )

            # ---------------------------------------------
            # THÔNG BÁO USER
            # ---------------------------------------------

            thong_bao_moi = (
                ThongBao.objects.create(
                    nguoi_thue=nguoi_thue,
                    tieu_de=(
                        "Điều chỉnh trạng thái thanh toán"
                    ),
                    noi_dung=(
                        f"Xác nhận thanh toán hóa đơn "
                        f"{hoa_don.thang}/{hoa_don.nam} "
                        f"của phòng {phong.so_phong} "
                        f"đã được quản trị viên hủy. "
                        f"Hóa đơn hiện ở trạng thái "
                        f"{hoa_don.get_trang_thai_display()}."
                    ),
                    loai="thanh_toan",
                    muc_do="canh_bao",
                )
            )

            # ---------------------------------------------
            # AUDIT HÓA ĐƠN
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Hủy thanh toán",
                module="Hóa đơn",
                doi_tuong="HoaDon",
                doi_tuong_id=hoa_don.id,
                tieu_de=(
                    f"Hủy thanh toán hóa đơn "
                    f"{hoa_don.thang}/{hoa_don.nam}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} "
                    f"hủy xác nhận thanh toán hóa đơn "
                    f"{hoa_don.thang}/{hoa_don.nam} "
                    f"của hợp đồng "
                    f"{hop_dong.so_hop_dong}."
                ),
                du_lieu_cu={
                    "trang_thai":
                        trang_thai_cu,
                    "ngay_thanh_toan": (
                        ngay_thanh_toan_cu.isoformat()
                        if ngay_thanh_toan_cu
                        else None
                    ),
                    "phuong_thuc":
                        phuong_thuc_cu,
                    "ma_giao_dich":
                        ma_giao_dich_cu,
                },
                du_lieu_moi={
                    "trang_thai":
                        hoa_don.trang_thai,
                    "ngay_thanh_toan":
                        None,
                    "phuong_thuc":
                        "",
                    "ma_giao_dich":
                        "",
                    "thong_bao_id":
                        thong_bao_moi.id,
                },
            )

            # ---------------------------------------------
            # AUDIT THÔNG BÁO
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Thông báo",
                doi_tuong="ThongBao",
                doi_tuong_id=thong_bao_moi.id,
                tieu_de=(
                    f"Tạo thông báo điều chỉnh thanh toán "
                    f"{hoa_don.thang}/{hoa_don.nam}"
                ),
                noi_dung=(
                    f"Tạo thông báo điều chỉnh thanh toán "
                    f"cho {nguoi_thue.ho_ten}."
                ),
                du_lieu_cu={},
                du_lieu_moi={
                    "thong_bao_id":
                        thong_bao_moi.id,
                    "hoa_don_id":
                        hoa_don.id,
                    "loai":
                        thong_bao_moi.loai,
                    "muc_do":
                        thong_bao_moi.muc_do,
                },
            )

            messages.success(
                request,
                "Đã hủy xác nhận thanh toán và cập nhật lại trạng thái hóa đơn."
            )

    return redirect(
        "chi_tiet_hoa_don",
        id=id
    )
