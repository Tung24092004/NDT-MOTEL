"""Nghiep vu gia han."""
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from core.quy_tac_nghiep_vu import (
    contract_is_current, permission_binding_is_valid, eligible_permissions,
    KNOWN_PERMISSION_SOURCES, AUTO_PERMISSION_SOURCES,
)
from core.tien_ich import ghi_nhat_ky
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
from core.views_hop_dong import cap_nhat_trang_thai_hop_dong, cap_nhat_trang_thai_phong_theo_hop_dong
from core.dich_vu.phan_quyen import la_admin
from core.views_tai_khoan import _lay_nguoi_thue_dang_dang_nhap
from core.dich_vu.ngay_thue import tinh_ngay_ket_thuc_theo_thang


def xu_ly_yeu_cau_gia_han(request, id):

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method != "POST":
        yeu_cau = get_object_or_404(
            YeuCauGiaHanHopDong,
            id=id,
        )
        return redirect(
            "chi_tiet_hop_dong",
            id=yeu_cau.hop_dong_id,
        )

    hanh_dong = request.POST.get(
        "hanh_dong",
        "",
    ).strip()

    ghi_chu_admin = request.POST.get(
        "ghi_chu_admin",
        "",
    ).strip()

    with transaction.atomic():

        room_id = get_object_or_404(
            YeuCauGiaHanHopDong.objects.values("hop_dong__dat_phong__phong_id"), pk=id
        )["hop_dong__dat_phong__phong_id"]
        Phong.objects.select_for_update().get(pk=room_id)

        yeu_cau = get_object_or_404(
            YeuCauGiaHanHopDong.objects
            .select_for_update()
            .select_related(
                "nguoi_yeu_cau",
                "hop_dong",
                "hop_dong__dat_phong",
                "hop_dong__dat_phong__nguoi_thue",
                "hop_dong__dat_phong__phong",
                "hop_dong__dat_phong__phong__co_so",
            ),
            id=id,
        )

        hop_dong = (
            HopDong.objects
            .select_for_update()
            .select_related(
                "dat_phong",
                "dat_phong__nguoi_thue",
                "dat_phong__phong",
                "dat_phong__phong__co_so",
            )
            .get(id=yeu_cau.hop_dong_id)
        )

        phong = (
            Phong.objects
            .select_for_update()
            .select_related("co_so")
            .get(id=hop_dong.dat_phong.phong_id)
        )

        nguoi_thue = hop_dong.dat_phong.nguoi_thue
        hom_nay = timezone.localdate()

        # -------------------------------------------------
        # KIỂM TRA YÊU CẦU
        # -------------------------------------------------

        if yeu_cau.trang_thai != "cho_duyet":
            messages.warning(
                request,
                "Yêu cầu gia hạn này đã được xử lý trước đó.",
            )
            return redirect(
                "chi_tiet_hop_dong",
                id=hop_dong.id,
            )

        if yeu_cau.nguoi_yeu_cau_id != nguoi_thue.id:
            messages.error(
                request,
                "Yêu cầu gia hạn không khớp với người thuê của hợp đồng.",
            )
            return redirect(
                "chi_tiet_hop_dong",
                id=hop_dong.id,
            )

        # Luôn đồng bộ trạng thái trước khi quyết định.
        cap_nhat_trang_thai_hop_dong(hop_dong)
        hop_dong.refresh_from_db()

        # =================================================
        # DUYỆT GIA HẠN
        # =================================================

        if hanh_dong == "duyet":

            if hop_dong.trang_thai == "da_huy":
                messages.error(
                    request,
                    "Hợp đồng đã bị hủy nên không thể gia hạn.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=hop_dong.id,
                )

            if hom_nay > hop_dong.ngay_ket_thuc:
                messages.error(
                    request,
                    "Hợp đồng đã hết hạn nên không thể duyệt yêu cầu gia hạn này.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=hop_dong.id,
                )

            if hop_dong.trang_thai != "sap_het_han":
                messages.error(
                    request,
                    "Chỉ có thể duyệt gia hạn khi hợp đồng đang ở trạng thái "
                    "sắp hết hạn.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=hop_dong.id,
                )

            # Chống duyệt yêu cầu cũ sau khi thời hạn hợp đồng đã thay đổi.
            if yeu_cau.ngay_ket_thuc_cu != hop_dong.ngay_ket_thuc:
                messages.error(
                    request,
                    "Thời hạn hợp đồng hiện tại đã thay đổi so với lúc người thuê "
                    "gửi yêu cầu. Hãy từ chối yêu cầu cũ và yêu cầu người thuê gửi lại.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=hop_dong.id,
                )

            ngay_ket_thuc_cu = hop_dong.ngay_ket_thuc
            ngay_ket_thuc_moi = yeu_cau.ngay_ket_thuc_de_xuat
            trang_thai_cu = hop_dong.trang_thai

            if ngay_ket_thuc_moi <= ngay_ket_thuc_cu:
                messages.error(
                    request,
                    "Ngày kết thúc đề xuất không hợp lệ.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=hop_dong.id,
                )

            # ---------------------------------------------
            # CẬP NHẬT HỢP ĐỒNG
            # ---------------------------------------------

            hop_dong.ngay_ket_thuc = ngay_ket_thuc_moi
            hop_dong.nguoi_cap_nhat = request.user
            hop_dong.save(
                update_fields=[
                    "ngay_ket_thuc",
                    "nguoi_cap_nhat",
                    "ngay_cap_nhat",
                ]
            )

            # Tính lại trạng thái sau khi kéo dài thời hạn.
            cap_nhat_trang_thai_hop_dong(hop_dong)
            hop_dong.refresh_from_db()

            # ---------------------------------------------
            # GIA HẠN QUYỀN RA VÀO GẮN VỚI HỢP ĐỒNG
            #
            # Chỉ gia hạn:
            # - quyền chủ phòng của người thuê chính;
            # - quyền người ở cùng thuộc đúng hợp đồng;
            # - quyền đang hoạt động / tạm khóa;
            # - quyền có ngày kết thúc đúng bằng ngày kết
            #   thúc cũ của hợp đồng.
            #
            # Không đụng khách tạm thời và không khôi phục
            # quyền đã hết hạn / bị thu hồi.
            # ---------------------------------------------

            quyen_chu_phong_gia_han = (
                hop_dong.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown")
                .filter(
                    phong=phong,
                    nguoi_o_cung__isnull=True,
                    nguoi_thue=nguoi_thue,
                    loai_quyen="chu_phong",
                    trang_thai__in=[
                        "hoat_dong",
                        "tam_khoa",
                    ],
                    ngay_ket_thuc=ngay_ket_thuc_cu,
                    nguon_cap__in=AUTO_PERMISSION_SOURCES,
                )
                .update(
                    ngay_ket_thuc=ngay_ket_thuc_moi,
                )
            )

            quyen_nguoi_o_cung_gia_han = (
                hop_dong.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown")
                .filter(
                    phong=phong,
                    nguoi_thue__isnull=True,
                    nguoi_o_cung__hop_dong=hop_dong,
                    nguoi_o_cung__trang_thai="dang_o",
                    loai_quyen="nguoi_o_cung",
                    trang_thai__in=[
                        "hoat_dong",
                        "tam_khoa",
                    ],
                    ngay_ket_thuc=ngay_ket_thuc_cu,
                    nguon_cap__in=AUTO_PERMISSION_SOURCES,
                )
                .update(
                    ngay_ket_thuc=ngay_ket_thuc_moi,
                )
            )

            tong_quyen_gia_han = (
                quyen_chu_phong_gia_han
                + quyen_nguoi_o_cung_gia_han
            )

            # ---------------------------------------------
            # CẬP NHẬT YÊU CẦU
            # ---------------------------------------------

            yeu_cau.trang_thai = "da_duyet"
            yeu_cau.nguoi_xu_ly = request.user
            yeu_cau.ngay_xu_ly = timezone.now()
            yeu_cau.ghi_chu_admin = ghi_chu_admin
            yeu_cau.ly_do_tu_choi = ""

            yeu_cau.save(
                update_fields=[
                    "trang_thai",
                    "nguoi_xu_ly",
                    "ngay_xu_ly",
                    "ghi_chu_admin",
                    "ly_do_tu_choi",
                    "ngay_cap_nhat",
                ]
            )

            # ---------------------------------------------
            # LỊCH SỬ HỢP ĐỒNG
            # ---------------------------------------------

            LichSuHopDong.objects.create(
                hop_dong=hop_dong,
                hanh_dong="gia_han",
                trang_thai_cu=trang_thai_cu,
                trang_thai_moi=hop_dong.trang_thai,
                noi_dung=(
                    f"Gia hạn hợp đồng thêm "
                    f"{yeu_cau.so_thang_gia_han} tháng. "
                    f"Ngày kết thúc thay đổi từ "
                    f"{ngay_ket_thuc_cu.strftime('%d/%m/%Y')} "
                    f"thành "
                    f"{ngay_ket_thuc_moi.strftime('%d/%m/%Y')}."
                ),
                nguoi_thuc_hien=request.user,
                dia_chi_ip=request.META.get("REMOTE_ADDR"),
            )

            # ---------------------------------------------
            # ĐỒNG BỘ PHÒNG
            # ---------------------------------------------

            cap_nhat_trang_thai_phong_theo_hop_dong(
                hop_dong
            )

            phong.refresh_from_db()

            # ---------------------------------------------
            # THÔNG BÁO NGƯỜI THUÊ
            # ---------------------------------------------

            thong_bao_moi = ThongBao.objects.create(
                nguoi_thue=nguoi_thue,
                tieu_de="Yêu cầu gia hạn hợp đồng đã được duyệt",
                noi_dung=(
                    f"Yêu cầu gia hạn hợp đồng "
                    f"{hop_dong.so_hop_dong} thêm "
                    f"{yeu_cau.so_thang_gia_han} tháng đã được duyệt. "
                    f"Thời hạn mới của hợp đồng là đến ngày "
                    f"{ngay_ket_thuc_moi.strftime('%d/%m/%Y')}."
                ),
                loai="hop_dong",
                muc_do="quan_trong",
            )

            # ---------------------------------------------
            # NHẬT KÝ THAO TÁC
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Duyệt gia hạn",
                module="Hợp đồng",
                doi_tuong="YeuCauGiaHanHopDong",
                doi_tuong_id=yeu_cau.id,
                tieu_de=(
                    f"Duyệt gia hạn hợp đồng "
                    f"{hop_dong.so_hop_dong}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} đã duyệt yêu cầu "
                    f"gia hạn hợp đồng {hop_dong.so_hop_dong} thêm "
                    f"{yeu_cau.so_thang_gia_han} tháng. "
                    f"Ngày kết thúc: "
                    f"{ngay_ket_thuc_cu.strftime('%d/%m/%Y')} → "
                    f"{ngay_ket_thuc_moi.strftime('%d/%m/%Y')}. "
                    f"Đã gia hạn {tong_quyen_gia_han} quyền ra vào "
                    f"gắn với hợp đồng."
                ),
                du_lieu_cu={
                    "trang_thai_hop_dong": trang_thai_cu,
                    "ngay_ket_thuc": str(ngay_ket_thuc_cu),
                    "trang_thai_yeu_cau": "cho_duyet",
                },
                du_lieu_moi={
                    "trang_thai_hop_dong": hop_dong.trang_thai,
                    "ngay_ket_thuc": str(ngay_ket_thuc_moi),
                    "trang_thai_yeu_cau": yeu_cau.trang_thai,
                    "so_thang_gia_han": yeu_cau.so_thang_gia_han,
                    "so_quyen_ra_vao_gia_han": tong_quyen_gia_han,
                    "thong_bao_id": thong_bao_moi.id,
                },
            )

            messages.success(
                request,
                f"Đã duyệt gia hạn hợp đồng {hop_dong.so_hop_dong} "
                f"đến ngày {ngay_ket_thuc_moi.strftime('%d/%m/%Y')}.",
            )

        # =================================================
        # TỪ CHỐI GIA HẠN
        # =================================================

        elif hanh_dong == "tu_choi":

            ly_do_tu_choi = request.POST.get(
                "ly_do_tu_choi",
                "",
            ).strip()

            if not ly_do_tu_choi:
                messages.error(
                    request,
                    "Vui lòng nhập lý do từ chối yêu cầu gia hạn.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=hop_dong.id,
                )

            yeu_cau.trang_thai = "tu_choi"
            yeu_cau.ly_do_tu_choi = ly_do_tu_choi
            yeu_cau.ghi_chu_admin = ghi_chu_admin
            yeu_cau.nguoi_xu_ly = request.user
            yeu_cau.ngay_xu_ly = timezone.now()

            yeu_cau.save(
                update_fields=[
                    "trang_thai",
                    "ly_do_tu_choi",
                    "ghi_chu_admin",
                    "nguoi_xu_ly",
                    "ngay_xu_ly",
                    "ngay_cap_nhat",
                ]
            )

            thong_bao_moi = ThongBao.objects.create(
                nguoi_thue=nguoi_thue,
                tieu_de="Yêu cầu gia hạn hợp đồng bị từ chối",
                noi_dung=(
                    f"Yêu cầu gia hạn hợp đồng "
                    f"{hop_dong.so_hop_dong} thêm "
                    f"{yeu_cau.so_thang_gia_han} tháng đã bị từ chối. "
                    f"Lý do: {ly_do_tu_choi}"
                ),
                loai="hop_dong",
                muc_do="quan_trong",
            )

            ghi_nhat_ky(
                request=request,
                hanh_dong="Từ chối gia hạn",
                module="Hợp đồng",
                doi_tuong="YeuCauGiaHanHopDong",
                doi_tuong_id=yeu_cau.id,
                tieu_de=(
                    f"Từ chối gia hạn hợp đồng "
                    f"{hop_dong.so_hop_dong}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} đã từ chối yêu cầu "
                    f"gia hạn hợp đồng {hop_dong.so_hop_dong}. "
                    f"Lý do: {ly_do_tu_choi}"
                ),
                du_lieu_cu={
                    "trang_thai_yeu_cau": "cho_duyet",
                    "ngay_ket_thuc_hop_dong": str(
                        hop_dong.ngay_ket_thuc
                    ),
                },
                du_lieu_moi={
                    "trang_thai_yeu_cau": yeu_cau.trang_thai,
                    "ly_do_tu_choi": ly_do_tu_choi,
                    "thong_bao_id": thong_bao_moi.id,
                },
            )

            messages.success(
                request,
                "Đã từ chối yêu cầu gia hạn và thông báo cho người thuê.",
            )

        # =================================================
        # THAO TÁC KHÔNG HỢP LỆ
        # =================================================

        else:
            messages.error(
                request,
                "Vui lòng chọn thao tác xử lý gia hạn hợp lệ.",
            )

    return redirect(
        "chi_tiet_hop_dong",
        id=hop_dong.id,
    )


def gui_yeu_cau_gia_han(request, id):

    # -----------------------------------------------------
    # KIỂM TRA ĐĂNG NHẬP
    # -----------------------------------------------------

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    # Admin không sử dụng nghiệp vụ người thuê này.
    if la_admin(request):
        return redirect("dashboard_admin")

    # -----------------------------------------------------
    # LẤY NGƯỜI THUÊ
    # -----------------------------------------------------

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    if not nguoi_thue:
        messages.error(
            request,
            "Không tìm thấy thông tin người thuê đang hoạt động."
        )
        return redirect("tai_khoan")

    # -----------------------------------------------------
    # LẤY HỢP ĐỒNG CỦA CHÍNH NGƯỜI THUÊ
    # -----------------------------------------------------

    hop_dong = get_object_or_404(
        HopDong.objects.select_related(
            "dat_phong",
            "dat_phong__nguoi_thue",
            "dat_phong__phong",
            "dat_phong__phong__co_so",
        ),
        id=id,
        dat_phong__nguoi_thue=nguoi_thue,
    )

    # Đồng bộ trạng thái trước khi kiểm tra nghiệp vụ.
    cap_nhat_trang_thai_hop_dong(hop_dong)

    # -----------------------------------------------------
    # KIỂM TRA TRẠNG THÁI HỢP ĐỒNG
    # -----------------------------------------------------

    if hop_dong.trang_thai == "da_huy":
        messages.error(
            request,
            "Hợp đồng đã bị hủy nên không thể yêu cầu gia hạn."
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    if hop_dong.trang_thai == "da_het_han":
        messages.error(
            request,
            "Hợp đồng đã hết hạn. "
            "Vui lòng liên hệ quản trị viên để được hỗ trợ."
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    if hop_dong.trang_thai == "cho_hieu_luc":
        messages.warning(
            request,
            "Hợp đồng chưa bắt đầu nên chưa thể yêu cầu gia hạn."
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    # Chỉ mở nghiệp vụ gia hạn khi hợp đồng đã vào giai đoạn
    # sắp hết hạn (0 - 30 ngày còn lại).
    if hop_dong.trang_thai != "sap_het_han":
        messages.warning(
            request,
            "Hợp đồng chưa đến thời gian được phép yêu cầu gia hạn. "
            "Bạn có thể gửi yêu cầu khi hợp đồng còn tối đa 30 ngày."
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    # -----------------------------------------------------
    # KHÔNG CHO TỒN TẠI NHIỀU YÊU CẦU CHỜ DUYỆT
    # -----------------------------------------------------

    yeu_cau_dang_cho = (
        YeuCauGiaHanHopDong.objects
        .filter(
            hop_dong=hop_dong,
            nguoi_yeu_cau=nguoi_thue,
            trang_thai="cho_duyet",
        )
        .order_by("-ngay_tao")
        .first()
    )

    if yeu_cau_dang_cho:
        messages.warning(
            request,
            "Bạn đã có một yêu cầu gia hạn đang chờ quản trị viên xử lý."
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    # -----------------------------------------------------
    # CHỈ NHẬN POST
    # -----------------------------------------------------

    if request.method != "POST":
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    # -----------------------------------------------------
    # ĐỌC DỮ LIỆU FORM
    # -----------------------------------------------------

    so_thang_raw = request.POST.get(
        "so_thang_gia_han",
        "",
    ).strip()

    ly_do = request.POST.get(
        "ly_do",
        "",
    ).strip()

    try:
        so_thang_gia_han = int(so_thang_raw)
    except (TypeError, ValueError):
        messages.error(
            request,
            "Số tháng gia hạn không hợp lệ."
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    if so_thang_gia_han < 1 or so_thang_gia_han > 36:
        messages.error(
            request,
            "Thời gian gia hạn phải từ 1 đến 36 tháng."
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    # -----------------------------------------------------
    # TÍNH NGÀY KẾT THÚC MỚI
    #
    # Ví dụ:
    # Hợp đồng cũ kết thúc 14/03/2027
    # Gia hạn bắt đầu từ 15/03/2027.
    # -----------------------------------------------------

    ngay_ket_thuc_cu = hop_dong.ngay_ket_thuc

    ngay_bat_dau_gia_han = (
        ngay_ket_thuc_cu
        + timedelta(days=1)
    )

    try:
        ngay_ket_thuc_de_xuat = (
            tinh_ngay_ket_thuc_theo_thang(
                ngay_bat_dau_gia_han,
                so_thang_gia_han,
            )
        )
    except ValueError as exc:
        messages.error(
            request,
            str(exc)
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    # -----------------------------------------------------
    # TẠO YÊU CẦU TRONG TRANSACTION
    # -----------------------------------------------------

    try:
        with transaction.atomic():

            # Khóa hợp đồng để tránh dữ liệu bị thay đổi đồng thời.
            hop_dong_khoa = (
                HopDong.objects
                .select_for_update()
                .select_related(
                    "dat_phong",
                    "dat_phong__nguoi_thue",
                    "dat_phong__phong",
                )
                .get(
                    id=hop_dong.id,
                    dat_phong__nguoi_thue=nguoi_thue,
                )
            )

            # Kiểm tra lại lần cuối vì dữ liệu có thể đã thay đổi
            # từ lúc mở trang đến lúc gửi form.
            cap_nhat_trang_thai_hop_dong(
                hop_dong_khoa
            )

            if hop_dong_khoa.trang_thai != "sap_het_han":
                messages.warning(
                    request,
                    "Trạng thái hợp đồng đã thay đổi. "
                    "Yêu cầu gia hạn không được tạo."
                )
                return redirect(
                    "chi_tiet_hop_dong_cua_toi",
                    id=hop_dong_khoa.id,
                )

            da_co_yeu_cau = (
                YeuCauGiaHanHopDong.objects
                .select_for_update()
                .filter(
                    hop_dong=hop_dong_khoa,
                    nguoi_yeu_cau=nguoi_thue,
                    trang_thai="cho_duyet",
                )
                .exists()
            )

            if da_co_yeu_cau:
                messages.warning(
                    request,
                    "Bạn đã có yêu cầu gia hạn đang chờ xử lý."
                )
                return redirect(
                    "chi_tiet_hop_dong_cua_toi",
                    id=hop_dong_khoa.id,
                )

            # Lấy lại ngày kết thúc trong transaction để đảm bảo
            # yêu cầu luôn dựa trên dữ liệu mới nhất.
            ngay_ket_thuc_cu = (
                hop_dong_khoa.ngay_ket_thuc
            )

            ngay_bat_dau_gia_han = (
                ngay_ket_thuc_cu
                + timedelta(days=1)
            )

            ngay_ket_thuc_de_xuat = (
                tinh_ngay_ket_thuc_theo_thang(
                    ngay_bat_dau_gia_han,
                    so_thang_gia_han,
                )
            )

            yeu_cau = (
                YeuCauGiaHanHopDong.objects.create(
                    hop_dong=hop_dong_khoa,
                    nguoi_yeu_cau=nguoi_thue,
                    so_thang_gia_han=so_thang_gia_han,
                    ngay_ket_thuc_cu=ngay_ket_thuc_cu,
                    ngay_ket_thuc_de_xuat=ngay_ket_thuc_de_xuat,
                    ly_do=ly_do,
                    trang_thai="cho_duyet",
                )
            )

            # -------------------------------------------------
            # THÔNG BÁO XÁC NHẬN CHO NGƯỜI THUÊ
            # -------------------------------------------------

            ThongBao.objects.create(
                nguoi_thue=nguoi_thue,
                tieu_de="Đã gửi yêu cầu gia hạn hợp đồng",
                noi_dung=(
                    f"Yêu cầu gia hạn hợp đồng "
                    f"{hop_dong_khoa.so_hop_dong} thêm "
                    f"{so_thang_gia_han} tháng đã được gửi. "
                    f"Ngày kết thúc đề xuất: "
                    f"{ngay_ket_thuc_de_xuat.strftime('%d/%m/%Y')}. "
                    f"Vui lòng chờ quản trị viên xử lý."
                ),
                loai="hop_dong",
                muc_do="binh_thuong",
                ma_tham_chieu=(
                    f"GH_{yeu_cau.id}_GUI"
                ),
            )

            # -------------------------------------------------
            # NHẬT KÝ THAO TÁC
            # -------------------------------------------------

            ghi_nhat_ky(
                request,
                hanh_dong="gia_han",
                module="hop_dong",
                doi_tuong="YeuCauGiaHanHopDong",
                doi_tuong_id=yeu_cau.id,
                tieu_de="Gửi yêu cầu gia hạn hợp đồng",
                noi_dung=(
                    f"Người thuê {nguoi_thue.ho_ten} "
                    f"gửi yêu cầu gia hạn hợp đồng "
                    f"{hop_dong_khoa.so_hop_dong} "
                    f"thêm {so_thang_gia_han} tháng."
                ),
                du_lieu_moi={
                    "hop_dong_id": hop_dong_khoa.id,
                    "so_hop_dong": hop_dong_khoa.so_hop_dong,
                    "so_thang_gia_han": so_thang_gia_han,
                    "ngay_ket_thuc_cu": (
                        ngay_ket_thuc_cu.isoformat()
                    ),
                    "ngay_ket_thuc_de_xuat": (
                        ngay_ket_thuc_de_xuat.isoformat()
                    ),
                    "trang_thai": "cho_duyet",
                },
            )

    except Exception as exc:
        messages.error(
            request,
            f"Không thể gửi yêu cầu gia hạn: {exc}"
        )
        return redirect(
            "chi_tiet_hop_dong_cua_toi",
            id=hop_dong.id,
        )

    messages.success(
        request,
        "Đã gửi yêu cầu gia hạn hợp đồng thành công."
    )

    return redirect(
        "chi_tiet_hop_dong_cua_toi",
        id=hop_dong.id,
    )


def huy_yeu_cau_gia_han(request, id):

    # -----------------------------------------------------
    # KIỂM TRA ĐĂNG NHẬP
    # -----------------------------------------------------

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if la_admin(request):
        return redirect("dashboard_admin")

    if request.method != "POST":
        return redirect("hop_dong_cua_toi")

    # -----------------------------------------------------
    # LẤY NGƯỜI THUÊ
    # -----------------------------------------------------

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    if not nguoi_thue:
        messages.error(
            request,
            "Không tìm thấy thông tin người thuê đang hoạt động."
        )
        return redirect("tai_khoan")

    # -----------------------------------------------------
    # HỦY YÊU CẦU TRONG TRANSACTION
    # -----------------------------------------------------

    try:
        with transaction.atomic():

            yeu_cau = get_object_or_404(
                YeuCauGiaHanHopDong.objects
                .select_for_update()
                .select_related(
                    "hop_dong",
                    "hop_dong__dat_phong",
                    "hop_dong__dat_phong__nguoi_thue",
                ),
                id=id,
                nguoi_yeu_cau=nguoi_thue,
            )

            hop_dong = yeu_cau.hop_dong

            # Chỉ được hủy khi Admin chưa xử lý.
            if yeu_cau.trang_thai != "cho_duyet":
                messages.warning(
                    request,
                    "Yêu cầu này đã được xử lý nên không thể hủy."
                )
                return redirect(
                    "chi_tiet_hop_dong_cua_toi",
                    id=hop_dong.id,
                )

            yeu_cau.trang_thai = "da_huy"

            yeu_cau.save(
                update_fields=[
                    "trang_thai",
                    "ngay_cap_nhat",
                ]
            )

            # -------------------------------------------------
            # THÔNG BÁO
            # -------------------------------------------------

            ThongBao.objects.create(
                nguoi_thue=nguoi_thue,
                tieu_de="Đã hủy yêu cầu gia hạn hợp đồng",
                noi_dung=(
                    f"Bạn đã hủy yêu cầu gia hạn hợp đồng "
                    f"{hop_dong.so_hop_dong}."
                ),
                loai="hop_dong",
                muc_do="binh_thuong",
                ma_tham_chieu=(
                    f"GH_{yeu_cau.id}_HUY"
                ),
            )

            # -------------------------------------------------
            # NHẬT KÝ
            # -------------------------------------------------

            ghi_nhat_ky(
                request,
                hanh_dong="huy",
                module="hop_dong",
                doi_tuong="YeuCauGiaHanHopDong",
                doi_tuong_id=yeu_cau.id,
                tieu_de="Hủy yêu cầu gia hạn hợp đồng",
                noi_dung=(
                    f"Người thuê {nguoi_thue.ho_ten} "
                    f"hủy yêu cầu gia hạn hợp đồng "
                    f"{hop_dong.so_hop_dong}."
                ),
                du_lieu_cu={
                    "trang_thai": "cho_duyet",
                },
                du_lieu_moi={
                    "trang_thai": "da_huy",
                },
            )

    except Exception as exc:
        messages.error(
            request,
            f"Không thể hủy yêu cầu gia hạn: {exc}"
        )
        return redirect("hop_dong_cua_toi")

    messages.success(
        request,
        "Đã hủy yêu cầu gia hạn hợp đồng."
    )

    return redirect(
        "chi_tiet_hop_dong_cua_toi",
        id=hop_dong.id,
    )
