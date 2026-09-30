"""Nghiep vu quan tri."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Exists, OuterRef
from django.db import transaction
from django.core.paginator import Paginator
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
from core.dich_vu.gallery_phong import chuan_bi_gallery_hien_thi


def home(request):
    """
    Trang chủ PUBLIC hiển thị toàn bộ phòng.

    Khách chưa đăng nhập vẫn có thể:
    - Xem phòng
    - Xem cơ sở / vị trí
    - Xem giá
    - Xem trạng thái
    - Xem sức chứa
    - Xem số người đang ở
    - Xem số chỗ còn lại

    Dữ liệu sức chứa được giữ đồng bộ với Smart Room:
    - so_nguoi_toi_da > 0: đã cấu hình sức chứa
    - so_nguoi_toi_da <= 0: chưa cấu hình
    """

    phong = (
        Phong.objects
        .select_related("co_so")
        .prefetch_related("hinh_anh")
        .order_by(
            "co_so__ten_co_so",
            "so_phong",
        )
    )
    phong = chuan_bi_gallery_hien_thi(phong)

    for item in phong:

        # -------------------------------------------------
        # HỢP ĐỒNG HIỆN TẠI
        # -------------------------------------------------
        hop_dong_hien_tai = (
            HopDong.objects
            .filter(
                dat_phong__phong=item,
                trang_thai__in=[
                    "dang_hieu_luc",
                    "sap_het_han",
                ],
            )
            .select_related(
                "dat_phong",
                "dat_phong__nguoi_thue",
            )
            .order_by("-id")
            .first()
        )

        # -------------------------------------------------
        # SỨC CHỨA
        # -------------------------------------------------
        suc_chua = (
            item.so_nguoi_toi_da
            if item.so_nguoi_toi_da
            else 0
        )

        suc_chua_da_cau_hinh = (
            suc_chua > 0
        )

        # -------------------------------------------------
        # SỐ NGƯỜI ĐANG Ở
        # -------------------------------------------------
        if hop_dong_hien_tai:
            so_nguoi_hien_tai = (
                item.so_nguoi_dang_o
            )
        else:
            so_nguoi_hien_tai = 0

        # Phòng mới chỉ được đặt nhưng chưa có hợp đồng
        # thì chưa tính là đang có người ở.
        if (
            item.trang_thai == "da_dat"
            and not hop_dong_hien_tai
        ):
            so_nguoi_hien_tai = 0

        # -------------------------------------------------
        # CHỖ CÒN LẠI + TỶ LỆ SỬ DỤNG
        # -------------------------------------------------
        if suc_chua_da_cau_hinh:

            cho_con_lai = max(
                suc_chua - so_nguoi_hien_tai,
                0,
            )

            ty_le_su_dung = round(
                (
                    so_nguoi_hien_tai
                    / suc_chua
                )
                * 100
            )

            # Thanh tiến trình chỉ hiển thị tối đa 100%.
            ty_le_su_dung = min(
                ty_le_su_dung,
                100,
            )

        else:

            cho_con_lai = 0
            ty_le_su_dung = 0

        # -------------------------------------------------
        # Ở GHÉP
        # -------------------------------------------------
        cho_phep_ghep_hien_tai = bool(
            hop_dong_hien_tai
            and suc_chua_da_cau_hinh
            and hop_dong_hien_tai.cho_phep_ghep
            and cho_con_lai > 0
        )

        # -------------------------------------------------
        # DỮ LIỆU CHO TEMPLATE
        # -------------------------------------------------
        item.hop_dong_hien_tai = (
            hop_dong_hien_tai
        )

        item.suc_chua_hien_thi = (
            suc_chua
        )

        item.suc_chua_da_cau_hinh = (
            suc_chua_da_cau_hinh
        )

        item.so_nguoi_hien_tai = (
            so_nguoi_hien_tai
        )

        item.cho_con_lai = (
            cho_con_lai
        )

        item.phan_tram_su_dung = (
            ty_le_su_dung
        )

        item.cho_phep_ghep_hien_thi = (
            cho_phep_ghep_hien_tai
        )

        item.trang_thai_hien_thi = (
            item.get_trang_thai_display()
        )

    return render(
        request,
        "core/home.html",
        {
            "phong": phong,
            "tong_so_phong": len(phong),
        },
    )


def dashboard_admin(request):

    if not request.user.is_authenticated:

        return redirect(
            "dang_nhap"
        )

    if not la_admin(request):

        return redirect(
            "tai_khoan"
        )

    # -----------------------------------------------------
    # CẬP NHẬT HỢP ĐỒNG
    # -----------------------------------------------------

    cac_hop_dong = (
        HopDong.objects
        .exclude(
            trang_thai="da_huy"
        )
        .select_related(
            "dat_phong",
            "dat_phong__phong",
        )
    )

    for hop_dong in cac_hop_dong:

        cap_nhat_trang_thai_hop_dong(
            hop_dong
        )

    # -----------------------------------------------------
    # ĐỒNG BỘ PHÒNG
    # -----------------------------------------------------

    for hop_dong in cac_hop_dong:

        cap_nhat_trang_thai_phong_theo_hop_dong(
            hop_dong
        )

    # -----------------------------------------------------
    # THỐNG KÊ PHÒNG
    # -----------------------------------------------------

    tong_phong = Phong.objects.count()

    phong_trong = Phong.objects.filter(
        trang_thai="trong"
    ).count()

    phong_da_dat = Phong.objects.filter(
        trang_thai="da_dat"
    ).count()

    phong_dang_thue = Phong.objects.filter(
        trang_thai="dang_thue"
    ).count()

    phong_bao_tri = Phong.objects.filter(
        trang_thai="bao_tri"
    ).count()

    # -----------------------------------------------------
    # NGƯỜI THUÊ
    # -----------------------------------------------------

    tong_nguoi_thue = NguoiThue.objects.count()

    # -----------------------------------------------------
    # ĐẶT PHÒNG
    # -----------------------------------------------------

    tong_dat_phong = DatPhong.objects.count()

    dat_phong_cho_duyet = DatPhong.objects.filter(
        trang_thai="cho_duyet"
    ).count()

    dat_phong_da_duyet = DatPhong.objects.filter(
        trang_thai="da_duyet"
    ).count()

    dat_phong_tu_choi = DatPhong.objects.filter(
        trang_thai="tu_choi"
    ).count()

    dat_phong_da_huy = DatPhong.objects.filter(
        trang_thai="da_huy"
    ).count()

    # -----------------------------------------------------
    # HỢP ĐỒNG
    # -----------------------------------------------------

    tong_hop_dong = HopDong.objects.count()

    hop_dong_dang_hieu_luc = HopDong.objects.filter(
        trang_thai="dang_hieu_luc"
    ).count()

    hop_dong_sap_het_han = HopDong.objects.filter(
        trang_thai="sap_het_han"
    ).count()

    hop_dong_cho_hieu_luc = HopDong.objects.filter(
        trang_thai="cho_hieu_luc"
    ).count()

    hop_dong_da_het_han = HopDong.objects.filter(
        trang_thai="da_het_han"
    ).count()

    # -----------------------------------------------------
    # ĐƠN MỚI NHẤT
    # -----------------------------------------------------

    danh_sach_dat_phong = (
        DatPhong.objects
        .select_related(
            "nguoi_thue",
            "phong",
            "phong__co_so"
        )
        .order_by("-id")[:5]
    )

    context = {

        "tong_phong": tong_phong,
        "phong_trong": phong_trong,
        "phong_da_dat": phong_da_dat,
        "phong_dang_thue": phong_dang_thue,
        "phong_bao_tri": phong_bao_tri,

        "tong_nguoi_thue": tong_nguoi_thue,

        "tong_dat_phong": tong_dat_phong,
        "dat_phong_cho_duyet": dat_phong_cho_duyet,
        "dat_phong_da_duyet": dat_phong_da_duyet,
        "dat_phong_tu_choi": dat_phong_tu_choi,
        "dat_phong_da_huy": dat_phong_da_huy,

        "tong_hop_dong": tong_hop_dong,
        "hop_dong_dang_hieu_luc": hop_dong_dang_hieu_luc,
        "hop_dong_sap_het_han": hop_dong_sap_het_han,
        "hop_dong_cho_hieu_luc": hop_dong_cho_hieu_luc,
        "hop_dong_da_het_han": hop_dong_da_het_han,

        "danh_sach_dat_phong": danh_sach_dat_phong,
    }

    return render(
        request,
        "core/dashboard_admin.html",
        context
    )


def quan_ly_dat_phong(request):

    if not request.user.is_authenticated:

        return redirect(
            "dang_nhap"
        )

    if not la_admin(request):

        return redirect(
            "tai_khoan"
        )

    # -----------------------------------------------------
    # QUERY GỐC
    # -----------------------------------------------------

    dat_phong = (
        DatPhong.objects
        .select_related(
            "nguoi_thue",
            "nguoi_thue__tai_khoan",
            "nguoi_xu_ly",
            "phong",
            "phong__co_so",
        )
        .annotate(
            co_hop_dong=Exists(
                HopDong.objects.filter(
                    dat_phong_id=OuterRef("pk")
                )
            )
        )
        .order_by(
            "-ngay_dat",
            "-id",
        )
    )

    # -----------------------------------------------------
    # TÌM KIẾM
    # -----------------------------------------------------

    tu_khoa = request.GET.get(
        "q",
        ""
    ).strip()

    if tu_khoa:

        dat_phong = dat_phong.filter(

            Q(
                nguoi_thue__ho_ten__icontains=tu_khoa
            )

            |

            Q(
                nguoi_thue__cccd__icontains=tu_khoa
            )

            |

            Q(
                nguoi_thue__so_dien_thoai__icontains=tu_khoa
            )

            |

            Q(
                nguoi_thue__email__icontains=tu_khoa
            )

            |

            Q(
                phong__so_phong__icontains=tu_khoa
            )

            |

            Q(
                phong__co_so__ten_co_so__icontains=tu_khoa
            )

        )

    # -----------------------------------------------------
    # LỌC TRẠNG THÁI
    # -----------------------------------------------------

    trang_thai = request.GET.get(
        "trang_thai",
        ""
    ).strip()

    cac_trang_thai = [
        "cho_duyet",
        "da_duyet",
        "tu_choi",
        "da_huy",
    ]

    if trang_thai in cac_trang_thai:

        dat_phong = dat_phong.filter(
            trang_thai=trang_thai
        )

    else:

        trang_thai = ""

    # -----------------------------------------------------
    # LỌC THEO TÌNH TRẠNG HỢP ĐỒNG
    # -----------------------------------------------------

    hop_dong = request.GET.get(
        "hop_dong",
        ""
    ).strip()

    if hop_dong == "da_co":

        dat_phong = dat_phong.filter(
            co_hop_dong=True
        )

    elif hop_dong == "chua_co":

        dat_phong = dat_phong.filter(
            co_hop_dong=False
        )

    else:

        hop_dong = ""

    # -----------------------------------------------------
    # THỐNG KÊ TOÀN HỆ THỐNG
    # -----------------------------------------------------

    thong_ke = DatPhong.objects.values(
        "trang_thai"
    )

    tong_don = DatPhong.objects.count()

    cho_duyet = thong_ke.filter(
        trang_thai="cho_duyet"
    ).count()

    da_duyet = thong_ke.filter(
        trang_thai="da_duyet"
    ).count()

    tu_choi = thong_ke.filter(
        trang_thai="tu_choi"
    ).count()

    da_huy = thong_ke.filter(
        trang_thai="da_huy"
    ).count()

    # -----------------------------------------------------
    # SỐ KẾT QUẢ SAU KHI LỌC
    # -----------------------------------------------------

    tong_ket_qua = dat_phong.count()

    # -----------------------------------------------------
    # PHÂN TRANG
    # -----------------------------------------------------

    paginator = Paginator(
        dat_phong,
        10
    )

    so_trang = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        so_trang
    )

    # -----------------------------------------------------
    # CONTEXT
    # -----------------------------------------------------

    context = {

        "dat_phong": page_obj.object_list,
        "page_obj": page_obj,

        "tong_don": tong_don,
        "cho_duyet": cho_duyet,
        "da_duyet": da_duyet,
        "tu_choi": tu_choi,
        "da_huy": da_huy,

        "tong_ket_qua": tong_ket_qua,

        "tu_khoa": tu_khoa,
        "trang_thai": trang_thai,
        "hop_dong": hop_dong,
    }

    return render(
        request,
        "core/quan_ly_dat_phong.html",
        context
    )


def chi_tiet_dat_phong(request, id):

    if not request.user.is_authenticated:

        return redirect(
            "dang_nhap"
        )

    if not la_admin(request):

        return redirect(
            "tai_khoan"
        )

    dat_phong = get_object_or_404(
        DatPhong.objects.select_related(
            "nguoi_thue",
            "nguoi_xu_ly",
            "phong",
            "phong__co_so"
        ),
        id=id
    )

    # -----------------------------------------------------
    # HỢP ĐỒNG LIÊN QUAN
    # -----------------------------------------------------

    hop_dong = (
        HopDong.objects
        .filter(
            dat_phong=dat_phong
        )
        .first()
    )

    # -----------------------------------------------------
    # THÔNG TIN SỨC CHỨA
    # -----------------------------------------------------

    so_nguoi_dang_o = dat_phong.phong.so_nguoi_dang_o

    so_cho_con_lai = dat_phong.phong.so_cho_con_lai

    # -----------------------------------------------------
    # TRẠNG THÁI NGHIỆP VỤ
    # -----------------------------------------------------

    da_co_hop_dong = hop_dong is not None

    co_the_tao_hop_dong = (
        dat_phong.trang_thai == "da_duyet"
        and not da_co_hop_dong
    )

    # -----------------------------------------------------
    # TIẾN TRÌNH
    # -----------------------------------------------------

    tien_trinh = {
        "da_dat": True,
        "da_duyet": (
            dat_phong.trang_thai
            in [
                "da_duyet",
            ]
            or da_co_hop_dong
        ),
        "da_co_hop_dong": da_co_hop_dong,
        "dang_thue": (
            hop_dong is not None
            and hop_dong.trang_thai
            in [
                "dang_hieu_luc",
                "sap_het_han",
            ]
        ),
    }

    context = {
        "dat_phong": dat_phong,
        "hop_dong": hop_dong,

        "da_co_hop_dong": da_co_hop_dong,
        "co_the_tao_hop_dong": co_the_tao_hop_dong,

        "so_nguoi_dang_o": so_nguoi_dang_o,
        "so_cho_con_lai": so_cho_con_lai,

        "tien_trinh": tien_trinh,
    }

    return render(
        request,
        "core/chi_tiet_dat_phong.html",
        context
    )


def xu_ly_dat_phong(request, id):

    # =====================================================
    # KIỂM TRA ĐĂNG NHẬP / QUYỀN ADMIN
    # =====================================================

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    # =====================================================
    # CHỈ CHẤP NHẬN POST
    # =====================================================

    if request.method != "POST":

        return redirect(
            "chi_tiet_dat_phong",
            id=id
        )

    # =====================================================
    # DỮ LIỆU GỬI LÊN
    # =====================================================

    hanh_dong = request.POST.get(
        "hanh_dong",
        ""
    ).strip()

    ly_do_tu_choi = request.POST.get(
        "ly_do_tu_choi",
        ""
    ).strip()

    ly_do_huy = request.POST.get(
        "ly_do_huy",
        ""
    ).strip()

    # =====================================================
    # VALIDATE HÀNH ĐỘNG
    # =====================================================

    if hanh_dong not in {
        "duyet",
        "tu_choi",
        "huy",
    }:

        messages.error(
            request,
            "Thao tác xử lý đơn đặt phòng không hợp lệ."
        )

        return redirect(
            "chi_tiet_dat_phong",
            id=id
        )

    # =====================================================
    # TỪ CHỐI PHẢI CÓ LÝ DO
    # =====================================================

    if (
        hanh_dong == "tu_choi"
        and not ly_do_tu_choi
    ):

        messages.error(
            request,
            "Vui lòng nhập lý do từ chối đơn đặt phòng."
        )

        return redirect(
            "chi_tiet_dat_phong",
            id=id
        )

    # =====================================================
    # HỦY PHẢI CÓ LÝ DO
    # =====================================================

    if (
        hanh_dong == "huy"
        and not ly_do_huy
    ):

        messages.error(
            request,
            "Vui lòng nhập lý do hủy đơn đặt phòng."
        )

        return redirect(
            "chi_tiet_dat_phong",
            id=id
        )

    # =====================================================
    # TRANSACTION
    # =====================================================

    with transaction.atomic():

        room_id = get_object_or_404(
            DatPhong.objects.values("phong_id"), pk=id
        )["phong_id"]
        Phong.objects.select_for_update().get(pk=room_id)

        # -------------------------------------------------
        # KHÓA ĐƠN ĐẶT PHÒNG
        # -------------------------------------------------

        dat_phong = get_object_or_404(
            DatPhong.objects
            .select_for_update()
            .select_related(
                "nguoi_thue",
                "nguoi_thue__tai_khoan",
                "phong",
                "phong__co_so",
            ),
            id=id
        )

        # -------------------------------------------------
        # KHÓA PHÒNG
        # -------------------------------------------------

        phong = (
            Phong.objects
            .select_for_update()
            .select_related(
                "co_so"
            )
            .get(
                id=dat_phong.phong_id
            )
        )

        # =================================================
        # ĐỒNG BỘ TRẠNG THÁI PHÒNG TRƯỚC KHI XỬ LÝ
        # =================================================

        phong.dong_bo_trang_thai()

        phong.refresh_from_db()

        # =================================================
        # DUYỆT / TỪ CHỐI CHỈ ÁP DỤNG CHO ĐƠN CHỜ DUYỆT
        # =================================================

        if (
            hanh_dong in {
                "duyet",
                "tu_choi",
            }
            and dat_phong.trang_thai != "cho_duyet"
        ):

            messages.warning(
                request,
                "Đơn đặt phòng này đã được xử lý trước đó."
            )

            return redirect(
                "chi_tiet_dat_phong",
                id=id
            )

        # =================================================
        # DUYỆT ĐƠN
        # =================================================

        if hanh_dong == "duyet":

            if phong.so_nguoi_toi_da <= 0:
                messages.error(request, "Phòng chưa cấu hình sức chứa.")
                return redirect("chi_tiet_dat_phong", id=id)

            # ---------------------------------------------
            # PHÒNG BẢO TRÌ
            # ---------------------------------------------

            if phong.trang_thai == "bao_tri":

                messages.error(
                    request,
                    (
                        "Không thể duyệt đơn vì phòng "
                        "đang trong trạng thái bảo trì."
                    )
                )

                return redirect(
                    "chi_tiet_dat_phong",
                    id=id
                )

            # ---------------------------------------------
            # PHÒNG PHẢI THỰC SỰ TRỐNG
            # ---------------------------------------------

            if phong.trang_thai != "trong":

                messages.error(
                    request,
                    (
                        "Không thể duyệt đơn vì phòng "
                        "hiện không còn trống."
                    )
                )

                return redirect(
                    "chi_tiet_dat_phong",
                    id=id
                )

            # ---------------------------------------------
            # KIỂM TRA ĐƠN ĐÃ DUYỆT KHÁC
            # ---------------------------------------------

            co_don_da_duyet_khac = (
                DatPhong.objects
                .select_for_update()
                .filter(
                    phong=phong,
                    trang_thai="da_duyet"
                )
                .exclude(
                    pk=dat_phong.pk
                )
                .filter(
                    Q(
                        hop_dong__isnull=True
                    )
                    |
                    Q(
                        hop_dong__trang_thai__in=[
                            "cho_hieu_luc",
                            "dang_hieu_luc",
                            "sap_het_han",
                        ]
                    )
                )
                .exists()
            )

            if co_don_da_duyet_khac:

                messages.error(
                    request,
                    (
                        "Phòng này đã có một đơn đặt phòng "
                        "khác được duyệt và còn hiệu lực."
                    )
                )

                return redirect(
                    "chi_tiet_dat_phong",
                    id=id
                )

            # ---------------------------------------------
            # LƯU TRẠNG THÁI CŨ
            # ---------------------------------------------

            trang_thai_cu = dat_phong.trang_thai

            # ---------------------------------------------
            # CẬP NHẬT ĐƠN
            # ---------------------------------------------

            dat_phong.trang_thai = "da_duyet"

            dat_phong.nguoi_xu_ly = (
                request.user
            )

            dat_phong.ly_do_tu_choi = ""

            dat_phong.save(
                update_fields=[
                    "trang_thai",
                    "nguoi_xu_ly",
                    "ly_do_tu_choi",
                    "ngay_cap_nhat",
                ]
            )

            # ---------------------------------------------
            # DatPhong.save() sẽ đồng bộ trạng thái phòng
            # ---------------------------------------------

            phong.refresh_from_db()

            # ---------------------------------------------
            # THÔNG BÁO CHO NGƯỜI THUÊ
            # ---------------------------------------------

            thong_bao_moi = (
                ThongBao.objects.create(
                    nguoi_thue=dat_phong.nguoi_thue,

                    tieu_de=(
                        "Đặt phòng đã được duyệt"
                    ),

                    noi_dung=(
                        f"Yêu cầu đặt phòng "
                        f"{phong.so_phong} "
                        f"tại {phong.co_so.ten_co_so} "
                        f"đã được quản trị viên duyệt. "
                        f"Ngày nhận phòng dự kiến: "
                        f"{dat_phong.ngay_nhan_phong.strftime('%d/%m/%Y')}. "
                        f"Vui lòng theo dõi thông tin hợp đồng "
                        f"và các bước tiếp theo trên hệ thống."
                    ),

                    loai="dat_phong",

                    muc_do="binh_thuong",
                )
            )

            # ---------------------------------------------
            # NHẬT KÝ XỬ LÝ ĐƠN
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Duyệt",
                module="Đặt phòng",
                doi_tuong="DatPhong",
                doi_tuong_id=dat_phong.id,

                tieu_de=(
                    f"Duyệt đơn đặt phòng "
                    f"#{dat_phong.id}"
                ),

                noi_dung=(
                    f"Admin {request.user.username} "
                    f"đã duyệt đơn đặt phòng "
                    f"#{dat_phong.id} "
                    f"cho phòng {phong.so_phong}."
                ),

                du_lieu_cu={
                    "trang_thai":
                        trang_thai_cu,
                },

                du_lieu_moi={
                    "trang_thai":
                        dat_phong.trang_thai,

                    "nguoi_thue":
                        dat_phong.nguoi_thue.ho_ten,

                    "phong":
                        phong.so_phong,

                    "trang_thai_phong":
                        phong.trang_thai,

                    "nguoi_xu_ly":
                        request.user.username,

                    "thong_bao_id":
                        thong_bao_moi.id,
                },
            )

            # ---------------------------------------------
            # NHẬT KÝ THÔNG BÁO
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Thông báo",
                doi_tuong="ThongBao",
                doi_tuong_id=thong_bao_moi.id,

                tieu_de=(
                    f"Tạo thông báo duyệt đặt phòng "
                    f"#{dat_phong.id}"
                ),

                noi_dung=(
                    f"Tạo thông báo cho "
                    f"{dat_phong.nguoi_thue.ho_ten} "
                    f"sau khi Admin duyệt đơn đặt phòng "
                    f"{phong.so_phong}."
                ),

                du_lieu_cu={},

                du_lieu_moi={
                    "thong_bao_id":
                        thong_bao_moi.id,

                    "dat_phong_id":
                        dat_phong.id,

                    "nguoi_thue_id":
                        dat_phong.nguoi_thue_id,

                    "loai":
                        thong_bao_moi.loai,

                    "muc_do":
                        thong_bao_moi.muc_do,
                },
            )

            # ---------------------------------------------
            # THÔNG BÁO ADMIN
            # ---------------------------------------------

            messages.success(
                request,
                (
                    f"Đã duyệt đơn đặt phòng "
                    f"#{dat_phong.id}."
                )
            )

            return redirect(
                "chi_tiet_dat_phong",
                id=id
            )

        # =================================================
        # TỪ CHỐI ĐƠN
        # =================================================

        if hanh_dong == "tu_choi":

            # ---------------------------------------------
            # LƯU TRẠNG THÁI CŨ
            # ---------------------------------------------

            trang_thai_cu = dat_phong.trang_thai

            # ---------------------------------------------
            # CẬP NHẬT ĐƠN
            # ---------------------------------------------

            dat_phong.trang_thai = (
                "tu_choi"
            )

            dat_phong.nguoi_xu_ly = (
                request.user
            )

            dat_phong.ly_do_tu_choi = (
                ly_do_tu_choi
            )

            dat_phong.save(
                update_fields=[
                    "trang_thai",
                    "nguoi_xu_ly",
                    "ly_do_tu_choi",
                    "ngay_cap_nhat",
                ]
            )

            # ---------------------------------------------
            # DatPhong.save() sẽ đồng bộ trạng thái phòng
            # ---------------------------------------------

            phong.refresh_from_db()

            # ---------------------------------------------
            # NỘI DUNG THÔNG BÁO
            # ---------------------------------------------

            noi_dung_thong_bao = (
                f"Yêu cầu đặt phòng "
                f"{phong.so_phong} "
                f"tại {phong.co_so.ten_co_so} "
                f"đã bị quản trị viên từ chối. "
                f"Lý do: {ly_do_tu_choi}"
            )

            # ---------------------------------------------
            # THÔNG BÁO CHO NGƯỜI THUÊ
            # ---------------------------------------------

            thong_bao_moi = (
                ThongBao.objects.create(
                    nguoi_thue=dat_phong.nguoi_thue,

                    tieu_de=(
                        "Đặt phòng bị từ chối"
                    ),

                    noi_dung=noi_dung_thong_bao,

                    loai="dat_phong",

                    muc_do="canh_bao",
                )
            )

            # ---------------------------------------------
            # NHẬT KÝ XỬ LÝ ĐƠN
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Từ chối",
                module="Đặt phòng",
                doi_tuong="DatPhong",
                doi_tuong_id=dat_phong.id,

                tieu_de=(
                    f"Từ chối đơn đặt phòng "
                    f"#{dat_phong.id}"
                ),

                noi_dung=(
                    f"Admin {request.user.username} "
                    f"đã từ chối đơn đặt phòng "
                    f"#{dat_phong.id} "
                    f"cho phòng {phong.so_phong}. "
                    f"Lý do: {ly_do_tu_choi}"
                ),

                du_lieu_cu={
                    "trang_thai":
                        trang_thai_cu,
                },

                du_lieu_moi={
                    "trang_thai":
                        dat_phong.trang_thai,

                    "nguoi_thue":
                        dat_phong.nguoi_thue.ho_ten,

                    "phong":
                        phong.so_phong,

                    "trang_thai_phong":
                        phong.trang_thai,

                    "ly_do_tu_choi":
                        ly_do_tu_choi,

                    "nguoi_xu_ly":
                        request.user.username,

                    "thong_bao_id":
                        thong_bao_moi.id,
                },
            )

            # ---------------------------------------------
            # NHẬT KÝ THÔNG BÁO
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Thông báo",
                doi_tuong="ThongBao",
                doi_tuong_id=thong_bao_moi.id,

                tieu_de=(
                    f"Tạo thông báo từ chối đặt phòng "
                    f"#{dat_phong.id}"
                ),

                noi_dung=(
                    f"Tạo thông báo cho "
                    f"{dat_phong.nguoi_thue.ho_ten} "
                    f"sau khi Admin từ chối đơn đặt phòng "
                    f"{phong.so_phong}."
                ),

                du_lieu_cu={},

                du_lieu_moi={
                    "thong_bao_id":
                        thong_bao_moi.id,

                    "dat_phong_id":
                        dat_phong.id,

                    "nguoi_thue_id":
                        dat_phong.nguoi_thue_id,

                    "loai":
                        thong_bao_moi.loai,

                    "muc_do":
                        thong_bao_moi.muc_do,

                    "ly_do_tu_choi":
                        ly_do_tu_choi,
                },
            )

            # ---------------------------------------------
            # THÔNG BÁO ADMIN
            # ---------------------------------------------

            messages.success(
                request,
                (
                    f"Đã từ chối đơn đặt phòng "
                    f"#{dat_phong.id}."
                )
            )

            return redirect(
                "chi_tiet_dat_phong",
                id=id
            )

        # =================================================
        # HỦY ĐƠN
        # =================================================

        if hanh_dong == "huy":

            # ---------------------------------------------
            # CHỈ CHO HỦY ĐƠN CHỜ DUYỆT HOẶC ĐÃ DUYỆT
            # NHƯNG CHƯA CÓ HỢP ĐỒNG
            # ---------------------------------------------

            if dat_phong.trang_thai not in {
                "cho_duyet",
                "da_duyet",
            }:

                messages.warning(
                    request,
                    (
                        "Chỉ có thể hủy đơn đang chờ duyệt "
                        "hoặc đơn đã duyệt nhưng chưa lập hợp đồng."
                    )
                )

                return redirect(
                    "chi_tiet_dat_phong",
                    id=id
                )

            # ---------------------------------------------
            # NẾU ĐÃ CÓ HỢP ĐỒNG THÌ PHẢI HỦY HỢP ĐỒNG
            # ---------------------------------------------

            hop_dong_lien_quan = (
                HopDong.objects
                .select_for_update()
                .filter(
                    dat_phong=dat_phong
                )
                .first()
            )

            if hop_dong_lien_quan is not None:

                messages.error(
                    request,
                    (
                        "Đơn đặt phòng này đã có hợp đồng. "
                        "Không thể hủy trực tiếp đơn đặt phòng; "
                        "hãy xử lý hủy tại chức năng Hợp đồng "
                        "để hệ thống thu hồi quyền sử dụng phòng "
                        "và quyền Smart Room đúng nghiệp vụ."
                    )
                )

                return redirect(
                    "chi_tiet_dat_phong",
                    id=id
                )

            # ---------------------------------------------
            # LƯU TRẠNG THÁI CŨ
            # ---------------------------------------------

            trang_thai_cu = (
                dat_phong.trang_thai
            )

            trang_thai_phong_cu = (
                phong.trang_thai
            )

            # ---------------------------------------------
            # CẬP NHẬT ĐƠN
            # ---------------------------------------------

            dat_phong.trang_thai = (
                "da_huy"
            )

            dat_phong.nguoi_xu_ly = (
                request.user
            )

            # Model hiện tại chưa có trường ly_do_huy riêng.
            # Giữ lý do trong nhật ký + thông báo, không nhét
            # sai nghĩa vào ly_do_tu_choi.
            dat_phong.save(
                update_fields=[
                    "trang_thai",
                    "nguoi_xu_ly",
                    "ngay_cap_nhat",
                ]
            )

            # ---------------------------------------------
            # ĐỒNG BỘ LẠI TRẠNG THÁI PHÒNG
            # ---------------------------------------------

            phong.dong_bo_trang_thai()
            phong.refresh_from_db()

            # ---------------------------------------------
            # THÔNG BÁO CHO NGƯỜI THUÊ
            # ---------------------------------------------

            thong_bao_moi = (
                ThongBao.objects.create(
                    nguoi_thue=dat_phong.nguoi_thue,
                    tieu_de="Yêu cầu đặt phòng đã được hủy",
                    noi_dung=(
                        f"Yêu cầu đặt phòng "
                        f"{phong.so_phong} "
                        f"tại {phong.co_so.ten_co_so} "
                        f"đã được quản trị viên hủy. "
                        f"Lý do: {ly_do_huy}"
                    ),
                    loai="dat_phong",
                    muc_do="canh_bao",
                )
            )

            # ---------------------------------------------
            # NHẬT KÝ HỦY ĐƠN
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Hủy",
                module="Đặt phòng",
                doi_tuong="DatPhong",
                doi_tuong_id=dat_phong.id,
                tieu_de=(
                    f"Hủy đơn đặt phòng "
                    f"#{dat_phong.id}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} "
                    f"đã hủy đơn đặt phòng "
                    f"#{dat_phong.id} "
                    f"cho phòng {phong.so_phong}. "
                    f"Lý do: {ly_do_huy}"
                ),
                du_lieu_cu={
                    "trang_thai":
                        trang_thai_cu,
                    "trang_thai_phong":
                        trang_thai_phong_cu,
                },
                du_lieu_moi={
                    "trang_thai":
                        dat_phong.trang_thai,
                    "trang_thai_phong":
                        phong.trang_thai,
                    "nguoi_thue":
                        dat_phong.nguoi_thue.ho_ten,
                    "phong":
                        phong.so_phong,
                    "ly_do_huy":
                        ly_do_huy,
                    "nguoi_xu_ly":
                        request.user.username,
                    "thong_bao_id":
                        thong_bao_moi.id,
                },
            )

            # ---------------------------------------------
            # NHẬT KÝ THÔNG BÁO
            # ---------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Thông báo",
                doi_tuong="ThongBao",
                doi_tuong_id=thong_bao_moi.id,
                tieu_de=(
                    f"Tạo thông báo hủy đặt phòng "
                    f"#{dat_phong.id}"
                ),
                noi_dung=(
                    f"Tạo thông báo cho "
                    f"{dat_phong.nguoi_thue.ho_ten} "
                    f"sau khi Admin hủy đơn đặt phòng "
                    f"{phong.so_phong}."
                ),
                du_lieu_cu={},
                du_lieu_moi={
                    "thong_bao_id":
                        thong_bao_moi.id,
                    "dat_phong_id":
                        dat_phong.id,
                    "nguoi_thue_id":
                        dat_phong.nguoi_thue_id,
                    "loai":
                        thong_bao_moi.loai,
                    "muc_do":
                        thong_bao_moi.muc_do,
                    "ly_do_huy":
                        ly_do_huy,
                },
            )

            messages.success(
                request,
                (
                    f"Đã hủy đơn đặt phòng "
                    f"#{dat_phong.id}."
                )
            )

            return redirect(
                "chi_tiet_dat_phong",
                id=id
            )


def quan_ly_co_so(request):

    if not request.user.is_authenticated:

        return redirect(
            "dang_nhap"
        )

    if not la_admin(request):

        return redirect(
            "tai_khoan"
        )

    co_so = (
        CoSo.objects
        .all()
        .order_by("ten_co_so")
    )

    tu_khoa = request.GET.get(
        "q",
        ""
    ).strip()

    if tu_khoa:

        co_so = co_so.filter(
            Q(
                ten_co_so__icontains=tu_khoa
            )
            |
            Q(
                quan__icontains=tu_khoa
            )
        )

    # -----------------------------------------------------
    # THỐNG KÊ SỐ PHÒNG THEO CƠ SỞ
    # Dùng annotate để tránh N+1 query
    # -----------------------------------------------------

    co_so = co_so.annotate(
        so_luong_phong=Count("phong"),
        so_phong_trong=Count(
            "phong",
            filter=Q(phong__trang_thai="trong")
        ),
        so_phong_dang_thue=Count(
            "phong",
            filter=Q(phong__trang_thai="dang_thue")
        ),
        so_phong_bao_tri=Count(
            "phong",
            filter=Q(phong__trang_thai="bao_tri")
        ),
    )

    context = {

        "co_so": co_so,

        "tong_co_so": CoSo.objects.count(),

        "tu_khoa": tu_khoa,
    }

    return render(
        request,
        "core/quan_ly_co_so.html",
        context
    )


def chi_tiet_co_so(request, id):

    if not request.user.is_authenticated:

        return redirect(
            "dang_nhap"
        )

    if not la_admin(request):

        return redirect(
            "tai_khoan"
        )

    co_so = get_object_or_404(
        CoSo,
        id=id
    )

    phong = (
        Phong.objects
        .filter(
            co_so=co_so
        )
        .order_by("so_phong")
    )

    context = {

        "co_so": co_so,

        "phong": phong,

        "tong_phong": phong.count(),

        "phong_trong": phong.filter(
            trang_thai="trong"
        ).count(),

        "phong_da_dat": phong.filter(
            trang_thai="da_dat"
        ).count(),

        "phong_dang_thue": phong.filter(
            trang_thai="dang_thue"
        ).count(),

        "phong_bao_tri": phong.filter(
            trang_thai="bao_tri"
        ).count(),
    }

    return render(
        request,
        "core/chi_tiet_co_so.html",
        context
    )


def tao_co_so(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method == "POST":
        ten_co_so = request.POST.get("ten_co_so", "").strip()
        dia_chi = request.POST.get("dia_chi", "").strip()
        quan = request.POST.get("quan", "").strip()
        so_tang_raw = request.POST.get("so_tang", "").strip()
        so_phong_raw = request.POST.get("so_phong", "").strip()
        trang_thai = request.POST.get("trang_thai", "hoat_dong").strip()

        try:
            if not ten_co_so:
                raise ValueError("Vui lòng nhập tên cơ sở.")

            if not dia_chi:
                raise ValueError("Vui lòng nhập địa chỉ cơ sở.")

            if not quan:
                raise ValueError("Vui lòng nhập quận/khu vực.")

            so_tang = int(so_tang_raw or "1")
            so_phong = int(so_phong_raw or "0")

            if so_tang < 1:
                raise ValueError("Số tầng phải là số nguyên lớn hơn hoặc bằng 1.")

            if so_phong < 0:
                raise ValueError("Số phòng phải là số nguyên không âm.")

            trang_thai_hop_le = {
                value
                for value, _ in CoSo._meta.get_field("trang_thai").choices
            }

            if trang_thai not in trang_thai_hop_le:
                raise ValueError("Trạng thái cơ sở không hợp lệ.")

            CoSo.objects.create(
                ten_co_so=ten_co_so,
                dia_chi=dia_chi,
                quan=quan,
                so_dien_thoai=request.POST.get(
                    "so_dien_thoai",
                    ""
                ).strip(),
                email=request.POST.get(
                    "email",
                    ""
                ).strip(),
                nguoi_quan_ly=request.POST.get(
                    "nguoi_quan_ly",
                    ""
                ).strip(),
                sdt_quan_ly=request.POST.get(
                    "sdt_quan_ly",
                    ""
                ).strip(),
                so_tang=so_tang,
                so_phong=so_phong,
                tien_ich_chung=request.POST.get(
                    "tien_ich_chung",
                    ""
                ).strip(),
                mo_ta=request.POST.get(
                    "mo_ta",
                    ""
                ).strip(),
                trang_thai=trang_thai,
            )

            messages.success(
                request,
                "Tạo cơ sở thành công."
            )

            return redirect("quan_ly_co_so")

        except ValueError as exc:
            messages.error(
                request,
                str(exc) or "Dữ liệu cơ sở không hợp lệ."
            )

    return render(
        request,
        "core/tao_co_so.html"
    )


def xu_ly_co_so(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        messages.error(request, "Bạn không có quyền thực hiện thao tác này.")
        return redirect("tai_khoan")

    co_so = get_object_or_404(CoSo, id=id)

    if request.method == "POST":
        hanh_dong = request.POST.get("hanh_dong")

        # =========================
        # XÓA CƠ SỞ
        # =========================
        if hanh_dong == "xoa":
            ten_co_so = co_so.ten_co_so

            # Nếu cơ sở còn phòng thì không cho xóa
            if co_so.phong.exists():
                messages.error(
                    request,
                    "Không thể xóa cơ sở vì cơ sở này vẫn còn phòng."
                )
                return redirect(
                    "chi_tiet_co_so",
                    id=co_so.id
                )

            co_so.delete()

            messages.success(
                request,
                f'Đã xóa cơ sở "{ten_co_so}".'
            )

            return redirect("quan_ly_co_so")

        # =========================
        # BẬT HOẠT ĐỘNG
        # =========================
        elif hanh_dong == "hoat_dong":
            co_so.trang_thai = "hoat_dong"
            co_so.save(update_fields=["trang_thai"])

            messages.success(
                request,
                f'Đã chuyển "{co_so.ten_co_so}" sang trạng thái đang hoạt động.'
            )

        # =========================
        # TẠM NGƯNG
        # =========================
        elif hanh_dong == "tam_ngung":
            co_so.trang_thai = "tam_ngung"
            co_so.save(update_fields=["trang_thai"])

            messages.success(
                request,
                f'Đã tạm ngưng cơ sở "{co_so.ten_co_so}".'
            )

        # =========================
        # ĐÓNG CỬA
        # =========================
        elif hanh_dong == "dong_cua":
            co_so.trang_thai = "dong_cua"
            co_so.save(update_fields=["trang_thai"])

            messages.success(
                request,
                f'Đã đóng cửa cơ sở "{co_so.ten_co_so}".'
            )

        # =========================
        # CẬP NHẬT THÔNG TIN
        # =========================
        elif hanh_dong == "cap_nhat":

            ten_co_so = request.POST.get("ten_co_so", "").strip()
            dia_chi = request.POST.get("dia_chi", "").strip()
            quan = request.POST.get("quan", "").strip()
            so_dien_thoai = request.POST.get(
                "so_dien_thoai",
                ""
            ).strip()
            email = request.POST.get(
                "email",
                ""
            ).strip()
            nguoi_quan_ly = request.POST.get(
                "nguoi_quan_ly",
                ""
            ).strip()
            sdt_quan_ly = request.POST.get(
                "sdt_quan_ly",
                ""
            ).strip()
            tien_ich_chung = request.POST.get(
                "tien_ich_chung",
                ""
            ).strip()
            mo_ta = request.POST.get(
                "mo_ta",
                ""
            ).strip()

            so_tang = request.POST.get(
                "so_tang",
                ""
            ).strip()

            so_phong = request.POST.get(
                "so_phong",
                ""
            ).strip()

            if ten_co_so:
                co_so.ten_co_so = ten_co_so

            if dia_chi:
                co_so.dia_chi = dia_chi

            if quan:
                co_so.quan = quan

            co_so.so_dien_thoai = so_dien_thoai
            co_so.email = email
            co_so.nguoi_quan_ly = nguoi_quan_ly
            co_so.sdt_quan_ly = sdt_quan_ly
            co_so.tien_ich_chung = tien_ich_chung
            co_so.mo_ta = mo_ta

            if so_tang:
                try:
                    so_tang_int = int(so_tang)

                    if so_tang_int < 1:
                        raise ValueError

                    co_so.so_tang = so_tang_int

                except ValueError:
                    messages.error(
                        request,
                        "Số tầng phải là số nguyên lớn hơn hoặc bằng 1."
                    )

                    return redirect(
                        "chi_tiet_co_so",
                        id=co_so.id
                    )

            if so_phong:
                try:
                    so_phong_int = int(so_phong)

                    if so_phong_int < 0:
                        raise ValueError

                    co_so.so_phong = so_phong_int

                except ValueError:
                    messages.error(
                        request,
                        "Số phòng phải là số nguyên không âm."
                    )

                    return redirect(
                        "chi_tiet_co_so",
                        id=co_so.id
                    )

            co_so.save()

            messages.success(
                request,
                f'Đã cập nhật cơ sở "{co_so.ten_co_so}".'
            )

        return redirect(
            "chi_tiet_co_so",
            id=co_so.id
        )

    return redirect(
        "chi_tiet_co_so",
        id=co_so.id
    )
