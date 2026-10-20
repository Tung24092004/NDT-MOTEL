"""Nghiep vu o ghep."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
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
from core.dich_vu.dieu_kien_o_ghep import dieu_kien_o_ghep
from core.views_tai_khoan import _lay_nguoi_thue_dang_dang_nhap


def quan_ly_yeu_cau_ghep_admin(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")
    return yeu_cau_ghep_cua_toi(request)


@login_required(login_url="dang_nhap")
def bat_tat_cho_phep_ghep(request, id):
    """
    Chủ phòng bật/tắt chức năng cho phép người khác đăng ký ở ghép.

    id = ID của hợp đồng.
    """
    if la_admin(request):
        return redirect("dashboard_admin")

    if request.method != "POST":
        return redirect("home")

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    if not nguoi_thue:
        messages.error(
            request,
            "Không tìm thấy thông tin người thuê."
        )
        return redirect("home")

    hop_dong = get_object_or_404(
        HopDong.objects.select_related(
            "dat_phong",
            "dat_phong__phong",
            "dat_phong__nguoi_thue",
        ),
        id=id,
    )

    phong_id = hop_dong.dat_phong.phong.id

    # -----------------------------------------------------
    # Chỉ chủ phòng mới được bật/tắt
    # -----------------------------------------------------

    if (
        hop_dong.dat_phong.nguoi_thue_id
        != nguoi_thue.id
    ):
        messages.error(
            request,
            "Bạn không có quyền thay đổi chức năng ở ghép của phòng này."
        )
        return redirect(
            "chi_tiet_phong",
            id=phong_id,
        )

    # -----------------------------------------------------
    # Hợp đồng phải đang hiệu lực
    # -----------------------------------------------------

    if hop_dong.trang_thai not in [
        "dang_hieu_luc",
        "sap_het_han",
    ]:
        messages.error(
            request,
            "Hợp đồng hiện không còn hiệu lực."
        )
        return redirect(
            "chi_tiet_phong",
            id=phong_id,
        )

    # -----------------------------------------------------
    # Khóa hợp đồng + phòng để tránh thay đổi đồng thời
    # -----------------------------------------------------

    with transaction.atomic():

        hop_dong = (
            HopDong.objects
            .select_for_update()
            .select_related(
                "dat_phong",
                "dat_phong__phong",
            )
            .get(id=id)
        )

        phong = (
            Phong.objects
            .select_for_update()
            .get(
                id=hop_dong.dat_phong.phong_id
            )
        )

        # -------------------------------------------------
        # ĐANG TẮT -> MUỐN BẬT
        # -------------------------------------------------

        if not hop_dong.cho_phep_ghep:

            so_nguoi_o_cung = (
                NguoiOCungPhong.objects
                .filter(
                    hop_dong=hop_dong,
                    trang_thai="dang_o",
                )
                .count()
            )

            # Chủ phòng luôn tính là 1 người
            so_nguoi_hien_tai = (
                1 + so_nguoi_o_cung
            )

            suc_chua = phong.so_nguoi_toi_da
            if suc_chua <= 0:
                messages.error(request, "Phòng chưa cấu hình sức chứa.")
                return redirect("chi_tiet_phong", id=phong.id)

            if so_nguoi_hien_tai >= suc_chua:
                messages.error(
                    request,
                    f"Phòng {phong.so_phong} đã đủ người. "
                    f"Đang có {so_nguoi_hien_tai}/{suc_chua} người."
                )
                return redirect(
                    "chi_tiet_phong",
                    id=phong.id,
                )

            hop_dong.cho_phep_ghep = True

            hop_dong.save(
                update_fields=[
                    "cho_phep_ghep"
                ]
            )

            messages.success(
                request,
                f"Đã bật cho phép ở ghép cho phòng {phong.so_phong}."
            )

        # -------------------------------------------------
        # ĐANG BẬT -> MUỐN TẮT
        # -------------------------------------------------

        else:

            hop_dong.cho_phep_ghep = False

            hop_dong.save(
                update_fields=[
                    "cho_phep_ghep"
                ]
            )

            messages.success(
                request,
                f"Đã tắt cho phép ở ghép cho phòng {phong.so_phong}."
            )

    return redirect(
        "chi_tiet_phong",
        id=phong.id,
    )


@login_required(login_url="dang_nhap")
def dang_ky_ghep_phong(request, id):
    """
    Người thuê đăng ký xin ở ghép vào một phòng đang có người thuê.

    id = ID phòng.

    Quy trình:
        Người thuê gửi yêu cầu
        -> Chủ phòng/Admin duyệt
        -> Tạo NguoiOCungPhong
        -> Cập nhật số người trong hợp đồng.
    """
    if la_admin(request):
        return redirect("dashboard_admin")

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    if not nguoi_thue:
        messages.error(
            request,
            "Không tìm thấy thông tin người thuê."
        )
        return redirect("home")

    phong = get_object_or_404(
        Phong.objects.select_related("co_so"),
        id=id,
    )
    dieu_kien = dieu_kien_o_ghep(phong)
    if not dieu_kien["phong_co_the_ghep"]:
        messages.error(request, dieu_kien["ly_do_khong_the_ghep"])
        return redirect("chi_tiet_phong", id=phong.id)

    # -----------------------------------------------------
    # Tìm hợp đồng đang hiệu lực của phòng
    # -----------------------------------------------------

    hop_dong = dieu_kien["hop_dong"]

    if not hop_dong:
        messages.error(
            request,
            "Phòng này hiện chưa có hợp đồng đang hiệu lực."
        )
        return redirect(
            "chi_tiet_phong",
            id=phong.id,
        )

    # -----------------------------------------------------
    # Chủ phòng không được tự đăng ký ghép vào phòng mình
    # -----------------------------------------------------

    if (
        hop_dong.dat_phong.nguoi_thue_id
        == nguoi_thue.id
    ):
        messages.error(
            request,
            "Bạn đang là chủ phòng, không thể đăng ký ở ghép vào chính phòng của mình."
        )
        return redirect(
            "chi_tiet_phong",
            id=phong.id,
        )

    # -----------------------------------------------------
    # Phòng phải cho phép ở ghép
    # -----------------------------------------------------

    if not hop_dong.cho_phep_ghep:
        messages.error(
            request,
            "Phòng này hiện không cho phép đăng ký ở ghép."
        )
        return redirect(
            "chi_tiet_phong",
            id=phong.id,
        )

    # -----------------------------------------------------
    # Kiểm tra sức chứa
    # -----------------------------------------------------

    so_nguoi_o_cung = (
        NguoiOCungPhong.objects
        .filter(
            hop_dong=hop_dong,
            trang_thai="dang_o",
        )
        .count()
    )

    # Chủ phòng = 1 người
    so_nguoi_hien_tai = (
        1 + so_nguoi_o_cung
    )

    suc_chua = phong.so_nguoi_toi_da
    if suc_chua <= 0:
        messages.error(request, "Phòng chưa cấu hình sức chứa.")
        return redirect("chi_tiet_phong", id=phong.id)

    if so_nguoi_hien_tai >= suc_chua:
        messages.error(
            request,
            f"Phòng {phong.so_phong} đã đủ người. "
            f"Đang có {so_nguoi_hien_tai}/{suc_chua} người."
        )
        return redirect(
            "chi_tiet_phong",
            id=phong.id,
        )

    # -----------------------------------------------------
    # Không cho cùng một tài khoản có nhiều yêu cầu
    # đang chờ trong cùng hợp đồng
    # -----------------------------------------------------

    yeu_cau_dang_cho = (
        YeuCauGhepNguoi.objects
        .filter(
            hop_dong=hop_dong,
            nguoi_dang_ky=nguoi_thue,
            trang_thai="cho_duyet",
        )
        .exists()
    )

    if yeu_cau_dang_cho:
        messages.warning(
            request,
            "Bạn đã có một yêu cầu ở ghép đang chờ duyệt."
        )
        return redirect(
            "yeu_cau_ghep_cua_toi"
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        ho_ten = request.POST.get(
            "ho_ten",
            ""
        ).strip()

        ngay_sinh = request.POST.get(
            "ngay_sinh",
            ""
        ).strip()

        gioi_tinh = request.POST.get(
            "gioi_tinh",
            ""
        ).strip()

        cccd = request.POST.get(
            "cccd",
            ""
        ).strip()

        so_dien_thoai = request.POST.get(
            "so_dien_thoai",
            ""
        ).strip()

        quan_he = request.POST.get(
            "quan_he",
            ""
        ).strip()

        ngay_du_kien_vao = request.POST.get(
            "ngay_du_kien_vao",
            ""
        ).strip()

        ly_do = request.POST.get(
            "ly_do",
            ""
        ).strip()

        # -------------------------------------------------
        # Kiểm tra họ tên
        # -------------------------------------------------

        if not ho_ten:
            messages.error(
                request,
                "Vui lòng nhập họ tên."
            )
            return render(
                request,
                "core/dang_ky_ghep_phong.html",
                {
                    "phong": phong,
                    "hop_dong": hop_dong,
                    "nguoi_thue": nguoi_thue,
                }
            )

        # -------------------------------------------------
        # Kiểm tra ngày dự kiến vào
        # -------------------------------------------------

        if not ngay_du_kien_vao:
            messages.error(
                request,
                "Vui lòng chọn ngày dự kiến vào ở."
            )
            return render(
                request,
                "core/dang_ky_ghep_phong.html",
                {
                    "phong": phong,
                    "hop_dong": hop_dong,
                    "nguoi_thue": nguoi_thue,
                }
            )

        ngay_vao = parse_date(
            ngay_du_kien_vao
        )

        if not ngay_vao:
            messages.error(
                request,
                "Ngày dự kiến vào ở không hợp lệ."
            )
            return render(
                request,
                "core/dang_ky_ghep_phong.html",
                {
                    "phong": phong,
                    "hop_dong": hop_dong,
                    "nguoi_thue": nguoi_thue,
                }
            )

        if ngay_vao < timezone.localdate():
            messages.error(
                request,
                "Ngày dự kiến vào ở không được ở quá khứ."
            )
            return render(
                request,
                "core/dang_ky_ghep_phong.html",
                {
                    "phong": phong,
                    "hop_dong": hop_dong,
                    "nguoi_thue": nguoi_thue,
                }
            )

        # -------------------------------------------------
        # Nếu bỏ trống CCCD -> lấy CCCD tài khoản
        # -------------------------------------------------

        if not cccd:
            cccd = nguoi_thue.cccd or ""

        # -------------------------------------------------
        # Kiểm tra CCCD trùng người đang ở cùng
        # -------------------------------------------------

        if cccd:

            trung_cccd = (
                NguoiOCungPhong.objects
                .filter(
                    hop_dong=hop_dong,
                    cccd=cccd,
                    trang_thai="dang_o",
                )
                .exists()
            )

            if trung_cccd:
                messages.error(
                    request,
                    "CCCD này đã có người đang ở trong phòng."
                )
                return render(
                    request,
                    "core/dang_ky_ghep_phong.html",
                    {
                        "phong": phong,
                        "hop_dong": hop_dong,
                        "nguoi_thue": nguoi_thue,
                    }
                )

            # CCCD không được trùng chủ phòng
            cccd_chu_phong = (
                hop_dong.dat_phong.nguoi_thue.cccd
                or ""
            )

            if (
                cccd_chu_phong
                and cccd == cccd_chu_phong
            ):
                messages.error(
                    request,
                    "CCCD này thuộc về chủ phòng."
                )
                return render(
                    request,
                    "core/dang_ky_ghep_phong.html",
                    {
                        "phong": phong,
                        "hop_dong": hop_dong,
                        "nguoi_thue": nguoi_thue,
                    }
                )

        # -------------------------------------------------
        # Tạo yêu cầu ở ghép
        # -------------------------------------------------

        YeuCauGhepNguoi.objects.create(
            hop_dong=hop_dong,
            nguoi_dang_ky=nguoi_thue,
            ho_ten=ho_ten,
            ngay_sinh=(
                parse_date(ngay_sinh)
                if ngay_sinh
                else None
            ),
            gioi_tinh=gioi_tinh,
            cccd=cccd,
            so_dien_thoai=so_dien_thoai,
            quan_he=quan_he,
            ngay_du_kien_vao=ngay_vao,
            ly_do=ly_do,
            trang_thai="cho_duyet",
        )

        messages.success(
            request,
            "Đã gửi yêu cầu ở ghép. "
            "Vui lòng chờ chủ phòng hoặc quản trị viên duyệt."
        )

        return redirect(
            "yeu_cau_ghep_cua_toi"
        )

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    return render(
        request,
        "core/dang_ky_ghep_phong.html",
        {
            "phong": phong,
            "hop_dong": hop_dong,
            "nguoi_thue": nguoi_thue,
        }
    )


@login_required(login_url="dang_nhap")
def yeu_cau_ghep_cua_toi(request):
    """
    Trang quản lý yêu cầu ở ghép.

    - Chủ phòng: xem các yêu cầu đang chờ duyệt vào phòng của mình.
    - Admin: xem tất cả yêu cầu đang chờ duyệt.
    - Người đăng ký: xem các yêu cầu do chính mình gửi.
    """

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    # =========================================================
    # KHÔNG PHẢI NGƯỜI THUÊ
    # =========================================================

    if not nguoi_thue and not la_admin(request):
        messages.error(
            request,
            "Không tìm thấy thông tin người thuê của tài khoản này."
        )

        return redirect("home")


    # =========================================================
    # QUERY CHUNG
    # =========================================================

    tat_ca_yeu_cau = (
        YeuCauGhepNguoi.objects
        .select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__nguoi_thue",
            "hop_dong__dat_phong__nguoi_thue__tai_khoan",
            "nguoi_dang_ky",
            "nguoi_dang_ky__tai_khoan",
        )
        .order_by("-ngay_tao")
    )


    # =========================================================
    # 1. YÊU CẦU CẦN TÔI XỬ LÝ
    # =========================================================

    if la_admin(request):

        # Admin được xem tất cả yêu cầu đang chờ duyệt

        yeu_cau_can_duyet = (
            tat_ca_yeu_cau
            .filter(trang_thai="cho_duyet")
        )

    else:

        # Chủ phòng chỉ thấy yêu cầu gửi vào đúng phòng
        # mà mình đang đứng tên hợp đồng.

        yeu_cau_can_duyet = (
            tat_ca_yeu_cau
            .filter(
                trang_thai="cho_duyet",
                hop_dong__dat_phong__nguoi_thue=nguoi_thue,
            )
        )


    # =========================================================
    # 2. YÊU CẦU DO CHÍNH TÔI GỬI
    # =========================================================

    if nguoi_thue:

        yeu_cau_da_gui = (
            tat_ca_yeu_cau
            .filter(
                nguoi_dang_ky=nguoi_thue
            )
        )

    else:

        yeu_cau_da_gui = YeuCauGhepNguoi.objects.none()


    # =========================================================
    # 3. RENDER
    # =========================================================
# =========================================================
# ĐẾM YÊU CẦU ĐANG CHỜ CỦA CHÍNH TÔI
# =========================================================

    so_yeu_cau_dang_cho = yeu_cau_da_gui.filter(
        trang_thai="cho_duyet"
    ).count()

    return render(
        request,
        "core/yeu_cau_ghep_cua_toi.html",
        {
        "admin_mode": la_admin(request),
        "yeu_cau_can_duyet": yeu_cau_can_duyet,
        "yeu_cau_da_gui": yeu_cau_da_gui,

        "so_yeu_cau_dang_cho": so_yeu_cau_dang_cho,

    }
    )


@login_required(login_url="dang_nhap")
def chi_tiet_yeu_cau_ghep(request, id):
    """
    Xem chi tiết một yêu cầu ở ghép.

    Quyền xem:
    - Người gửi yêu cầu
    - Chủ phòng của hợp đồng
    - Admin
    """

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    # =====================================================
    # LẤY YÊU CẦU
    # =====================================================

    yeu_cau = get_object_or_404(
        YeuCauGhepNguoi.objects.select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
            "hop_dong__dat_phong__nguoi_thue",
            "hop_dong__dat_phong__nguoi_thue__tai_khoan",
            "nguoi_dang_ky",
            "nguoi_dang_ky__tai_khoan",
            "nguoi_xu_ly",
        ),
        id=id,
    )

    hop_dong = yeu_cau.hop_dong
    phong = hop_dong.dat_phong.phong

    # =====================================================
    # XÁC ĐỊNH QUYỀN
    # =====================================================

    la_admin_user = la_admin(request)

    la_chu_phong = bool(
        nguoi_thue
        and hop_dong.dat_phong.nguoi_thue_id
        == nguoi_thue.id
    )

    la_nguoi_dang_ky = bool(
        nguoi_thue
        and yeu_cau.nguoi_dang_ky_id
        == nguoi_thue.id
    )

    # Người gửi + chủ phòng + admin đều được xem
    if not (
        la_admin_user
        or la_chu_phong
        or la_nguoi_dang_ky
    ):
        messages.error(
            request,
            "Bạn không có quyền xem yêu cầu ở ghép này."
        )

        return redirect(
            "yeu_cau_ghep_cua_toi"
        )

    # =====================================================
    # TÍNH SỨC CHỨA PHÒNG
    # =====================================================

    so_nguoi_o_cung = (
        NguoiOCungPhong.objects
        .filter(
            hop_dong=hop_dong,
            trang_thai="dang_o",
        )
        .count()
    )

    # Chủ phòng = 1 người
    so_nguoi_hien_tai = (
        1 + so_nguoi_o_cung
    )

    suc_chua = (
        phong.so_nguoi_toi_da or 1
    )

    so_cho_con_lai = max(
        suc_chua - so_nguoi_hien_tai,
        0
    )

    # =====================================================
    # QUYỀN DUYỆT / TỪ CHỐI
    # =====================================================

    co_quyen_duyet = bool(
        la_admin_user
        or la_chu_phong
    )

    # Chỉ cho phép xử lý khi yêu cầu còn chờ
    co_quyen_xu_ly = bool(
        co_quyen_duyet
        and yeu_cau.trang_thai == "cho_duyet"
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "core/chi_tiet_yeu_cau_ghep.html",
        {
            "yeu_cau": yeu_cau,

            "phong": phong,
            "hop_dong": hop_dong,

            "so_nguoi_hien_tai": so_nguoi_hien_tai,
            "so_cho_con_lai": so_cho_con_lai,
            "suc_chua": suc_chua,

            "co_quyen_duyet": co_quyen_duyet,
            "co_quyen_xu_ly": co_quyen_xu_ly,

            "is_requester": la_nguoi_dang_ky,
            "is_owner": la_chu_phong,
            "is_admin": la_admin_user,
        }
    )


@login_required(login_url="dang_nhap")
def xu_ly_yeu_cau_ghep(request, id):
    """
    Chủ phòng hoặc Admin duyệt/từ chối yêu cầu ở ghép.

    id = ID YeuCauGhepNguoi.
    """

    if request.method != "POST":
        return redirect(
            "yeu_cau_ghep_cua_toi"
        )

    # 0037 retired the pending legacy workflow.  Preserve every legacy row for
    # historical viewing, but fail closed: it cannot create residency, Face,
    # access, an appendix, or a replacement co-tenant request.
    messages.warning(
        request,
        "Luồng yêu cầu ở ghép cũ đã ngừng xử lý; người thuê chính cần gửi yêu cầu người ở cùng mới.",
    )
    return redirect("yeu_cau_ghep_cua_toi")

    # -----------------------------------------------------
    # Lấy yêu cầu ban đầu để kiểm tra quyền
    # -----------------------------------------------------

    yeu_cau = get_object_or_404(
        YeuCauGhepNguoi.objects.select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__nguoi_thue",
            "nguoi_dang_ky",
        ),
        id=id,
    )

    nguoi_thue = (
        _lay_nguoi_thue_dang_dang_nhap(request)
    )

    la_admin_user = la_admin(request)

    la_chu_phong = bool(
        nguoi_thue
        and yeu_cau.hop_dong.dat_phong.nguoi_thue_id
        == nguoi_thue.id
    )

    # -----------------------------------------------------
    # Kiểm tra quyền xử lý
    # -----------------------------------------------------

    if not la_admin_user and not la_chu_phong:
        messages.error(
            request,
            "Bạn không có quyền xử lý yêu cầu này."
        )
        return redirect(
            "yeu_cau_ghep_cua_toi"
        )

    hanh_dong = request.POST.get(
        "hanh_dong",
        ""
    ).strip()

    if hanh_dong not in [
        "duyet",
        "tu_choi",
    ]:
        messages.error(
            request,
            "Thao tác không hợp lệ."
        )
        return redirect(
            "yeu_cau_ghep_cua_toi"
        )

    ly_do_tu_choi = request.POST.get(
        "ly_do_tu_choi",
        ""
    ).strip()

    # =====================================================
    # TRANSACTION
    # =====================================================

    with transaction.atomic():

        # -------------------------------------------------
        # Khóa yêu cầu
        # -------------------------------------------------

        yeu_cau = (
            YeuCauGhepNguoi.objects
            .select_for_update()
            .select_related(
                "hop_dong",
                "hop_dong__dat_phong",
                "hop_dong__dat_phong__nguoi_thue",
                "nguoi_dang_ky",
            )
            .get(id=id)
        )

        # -------------------------------------------------
        # Không cho xử lý lần 2
        # -------------------------------------------------

        if yeu_cau.trang_thai != "cho_duyet":
            messages.warning(
                request,
                "Yêu cầu này đã được xử lý trước đó."
            )
            return redirect(
                "yeu_cau_ghep_cua_toi"
            )

        hop_dong_id = yeu_cau.hop_dong_id

        # -------------------------------------------------
        # Khóa hợp đồng
        # -------------------------------------------------

        hop_dong = (
            HopDong.objects
            .select_for_update()
            .select_related(
                "dat_phong",
                "dat_phong__nguoi_thue",
            )
            .get(id=hop_dong_id)
        )

        # -------------------------------------------------
        # Khóa phòng
        # -------------------------------------------------

        phong = (
            Phong.objects
            .select_for_update()
            .get(
                id=hop_dong.dat_phong.phong_id
            )
        )

        # =================================================
        # TỪ CHỐI
        # =================================================

        if hanh_dong == "tu_choi":

            yeu_cau.trang_thai = "tu_choi"
            yeu_cau.ly_do_tu_choi = (
                ly_do_tu_choi
            )
            yeu_cau.ngay_xu_ly = timezone.now()

            yeu_cau.save(
                update_fields=[
                    "trang_thai",
                    "ly_do_tu_choi",
                    "ngay_xu_ly",
                    "ngay_cap_nhat",
                ]
            )

            messages.success(
                request,
                "Đã từ chối yêu cầu ở ghép."
            )

            return redirect(
                "yeu_cau_ghep_cua_toi"
            )

        # =================================================
        # DUYỆT
        # =================================================

        # -------------------------------------------------
        # Hợp đồng còn hiệu lực
        # -------------------------------------------------

        if (hop_dong.trang_thai not in ["dang_hieu_luc", "sap_het_han"]
                or not hop_dong.ngay_bat_dau <= timezone.localdate() <= hop_dong.ngay_ket_thuc):
            messages.error(
                request,
                "Hợp đồng hiện không còn hiệu lực."
            )
            return redirect(
                "yeu_cau_ghep_cua_toi"
            )

        # -------------------------------------------------
        # Phải đang cho phép ghép
        # -------------------------------------------------

        if not hop_dong.cho_phep_ghep:
            messages.error(
                request,
                "Chủ phòng hiện không cho phép ở ghép."
            )
            return redirect(
                "yeu_cau_ghep_cua_toi"
            )

        # -------------------------------------------------
        # Tính số người thực tế
        #
        # Chủ phòng = 1
        # + người ở cùng đang ở
        # -------------------------------------------------

        so_nguoi_o_cung = (
            NguoiOCungPhong.objects
            .filter(
                hop_dong=hop_dong,
                trang_thai="dang_o",
            )
            .count()
        )

        so_nguoi_hien_tai = (
            1 + so_nguoi_o_cung
        )

        suc_chua = phong.so_nguoi_toi_da
        if suc_chua <= 0:
            messages.error(request, "Phòng chưa cấu hình sức chứa.")
            return redirect("yeu_cau_ghep_cua_toi")

        # -------------------------------------------------
        # Kiểm tra sức chứa ngay lúc duyệt
        # -------------------------------------------------

        if so_nguoi_hien_tai >= suc_chua:
            messages.error(
                request,
                f"Phòng {phong.so_phong} đã đủ người. "
                f"Đang có {so_nguoi_hien_tai}/{suc_chua} người."
            )
            return redirect(
                "yeu_cau_ghep_cua_toi"
            )

        # -------------------------------------------------
        # Kiểm tra CCCD của người ở cùng
        # -------------------------------------------------

        if yeu_cau.cccd:

            trung_cccd = (
                NguoiOCungPhong.objects
                .filter(
                    hop_dong=hop_dong,
                    cccd=yeu_cau.cccd,
                    trang_thai="dang_o",
                )
                .exists()
            )

            if trung_cccd:
                messages.error(
                    request,
                    "CCCD này đã có người đang ở trong phòng."
                )
                return redirect(
                    "yeu_cau_ghep_cua_toi"
                )

            # -------------------------------------------------
            # CCCD không được trùng chủ phòng
            # -------------------------------------------------

            cccd_chu_phong = (
                hop_dong.dat_phong.nguoi_thue.cccd
                or ""
            )

            if (
                cccd_chu_phong
                and yeu_cau.cccd == cccd_chu_phong
            ):
                messages.error(
                    request,
                    "CCCD này thuộc về chủ phòng."
                )
                return redirect(
                    "yeu_cau_ghep_cua_toi"
                )

        # -------------------------------------------------
        # Kiểm tra người này đã được duyệt trước đó chưa
        # -------------------------------------------------

        da_co_nguoi_cung = (
            NguoiOCungPhong.objects
            .filter(
                hop_dong=hop_dong,
                ho_ten=yeu_cau.ho_ten,
                trang_thai="dang_o",
            )
            .exists()
        )

        if da_co_nguoi_cung:
            messages.error(
                request,
                "Người này đã có trong danh sách người ở cùng phòng."
            )
            return redirect(
                "yeu_cau_ghep_cua_toi"
            )

        # -------------------------------------------------
        # Tạo người ở cùng
        # -------------------------------------------------

        trang_thai_nguoi_o_cung = "dang_o" if la_admin_user else "cho_xac_minh"
        nguoi_o_cung = NguoiOCungPhong.objects.create(
            hop_dong=hop_dong,
            ho_ten=yeu_cau.ho_ten,
            ngay_sinh=yeu_cau.ngay_sinh,
            gioi_tinh=yeu_cau.gioi_tinh,
            cccd=yeu_cau.cccd,
            so_dien_thoai=yeu_cau.so_dien_thoai,
            quan_he=yeu_cau.quan_he,
            ngay_vao=yeu_cau.ngay_du_kien_vao,
            trang_thai=trang_thai_nguoi_o_cung,
            ghi_chu=yeu_cau.ly_do,
        )

        # -------------------------------------------------
        # Tạo FaceProfile cho người ở cùng
        # -------------------------------------------------

        FaceProfile.objects.create(
            nguoi_o_cung=nguoi_o_cung,
            loai_chu_the="nguoi_o_cung",
        )

        # -------------------------------------------------
        # Tạo quyền ra vào cho người ở cùng
        # -------------------------------------------------

        if la_admin_user:
            QuyenRaVao.objects.create(
                hop_dong=hop_dong, nguon_cap="duyet_ghep",
                phong=phong,
                nguoi_o_cung=nguoi_o_cung,
                loai_quyen="nguoi_o_cung",
                trang_thai="hoat_dong",
                ngay_bat_dau=nguoi_o_cung.ngay_vao,
                ngay_ket_thuc=hop_dong.ngay_ket_thuc,
                nguoi_tao=request.user,
            )

        # -------------------------------------------------
        # Cập nhật yêu cầu
        # -------------------------------------------------

        yeu_cau.trang_thai = "da_duyet"
        yeu_cau.ngay_xu_ly = timezone.now()

        yeu_cau.save(
            update_fields=[
                "trang_thai",
                "ngay_xu_ly",
                "ngay_cap_nhat",
            ]
        )

        # -------------------------------------------------
        # Đếm lại sau khi tạo người ở cùng
        # -------------------------------------------------

        so_nguoi_o_cung_moi = (
            NguoiOCungPhong.objects
            .filter(
                hop_dong=hop_dong,
                trang_thai="dang_o",
            )
            .count()
        )

        # Chủ phòng + người ở cùng
        so_nguoi_moi = (
            1 + so_nguoi_o_cung_moi
        )

        # -------------------------------------------------
        # Đồng bộ HopDong.so_nguoi_o
        # -------------------------------------------------

        hop_dong.so_nguoi_o = so_nguoi_moi

        hop_dong.save(
            update_fields=[
                "so_nguoi_o"
            ]
        )

        # -------------------------------------------------
        # Nếu đủ sức chứa -> tự tắt ở ghép
        # -------------------------------------------------

        if so_nguoi_moi >= suc_chua:

            hop_dong.cho_phep_ghep = False

            hop_dong.save(
                update_fields=[
                    "cho_phep_ghep"
                ]
            )

    # =====================================================
    # THÔNG BÁO THÀNH CÔNG
    # =====================================================

    messages.success(
        request,
        f"Đã duyệt cho {yeu_cau.ho_ten} ở ghép "
        f"tại phòng {phong.so_phong}."
    )

    return redirect(
        "yeu_cau_ghep_cua_toi"
    )
