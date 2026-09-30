"""Nghiep vu hop dong."""
from decimal import Decimal, InvalidOperation
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Exists, OuterRef, Case, When, Value, IntegerField
from django.db import transaction
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
logger = logging.getLogger(__name__)
from core.tien_ich import ghi_nhat_ky
from core.templatetags.bo_loc import STATUS_LABELS
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
from core.dich_vu.ngay_thue import tinh_ngay_ket_thuc_theo_thang


def _status_label(value):
    return STATUS_LABELS.get(str(value), str(value).replace("_", " ").capitalize())


def cap_nhat_trang_thai_hop_dong(hop_dong):
    """
    Đồng bộ trạng thái hợp đồng theo ngày hiện tại và xử lý
    các dữ liệu phụ thuộc khi hợp đồng chuyển trạng thái.

    Quy tắc thời gian:
    - da_huy:
        Giữ nguyên, không tự thay đổi.
    - cho_hieu_luc:
        Hôm nay chưa đến ngày bắt đầu.
    - dang_hieu_luc:
        Hợp đồng đã bắt đầu và còn trên 30 ngày.
    - sap_het_han:
        Hợp đồng còn từ 0 đến 30 ngày, bao gồm đúng ngày kết thúc.
    - da_het_han:
        Chỉ hết hạn khi đã qua ngày kết thúc.

    Khi chuyển sang da_het_han:
    - Người ở cùng đang ở -> da_roi.
    - Ghi ngày rời phòng.
    - Quyền ra vào của chủ phòng/người ở cùng -> het_han.
    - Không xóa FaceProfile.
    - Ghi LichSuHopDong một lần.
    - Đồng bộ lại trạng thái phòng.

    Lưu ý:
    Hàm này không tạo ThongBao để tránh sinh thông báo trùng khi
    được gọi từ nhiều màn hình/view khác nhau.
    """

    # =====================================================
    # DỮ LIỆU CƠ BẢN
    # =====================================================

    hom_nay = timezone.localdate()
    trang_thai_cu = hop_dong.trang_thai

    # =====================================================
    # HỢP ĐỒNG ĐÃ HỦY
    # =====================================================

    if trang_thai_cu == "da_huy":

        # Dọn trạng thái người ở cùng theo hướng idempotent.
        hop_dong.nguoi_o_cung.filter(
            trang_thai="dang_o"
        ).update(
            trang_thai="da_roi",
            ngay_ra=hom_nay,
        )

        phong = hop_dong.dat_phong.phong
        nguoi_thue = hop_dong.dat_phong.nguoi_thue

        # Hủy hợp đồng là thu hồi quyền, không phải hết hạn tự nhiên.
        hop_dong.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown").filter(
            nguoi_thue=nguoi_thue,
        ).exclude(
            trang_thai="bi_thu_hoi",
        ).update(
            trang_thai="bi_thu_hoi",
            ngay_ket_thuc=hom_nay,
        )

        hop_dong.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown").filter(
            nguoi_o_cung__hop_dong=hop_dong,
        ).exclude(
            trang_thai="bi_thu_hoi",
        ).update(
            trang_thai="bi_thu_hoi",
            ngay_ket_thuc=hom_nay,
        )

        cap_nhat_trang_thai_phong_theo_hop_dong(
            hop_dong
        )

        return hop_dong

    # =====================================================
    # XÁC ĐỊNH TRẠNG THÁI ĐÚNG THEO NGÀY
    # =====================================================

    if hom_nay < hop_dong.ngay_bat_dau:

        trang_thai_moi = "cho_hieu_luc"

    elif hom_nay > hop_dong.ngay_ket_thuc:

        trang_thai_moi = "da_het_han"

    else:

        so_ngay_con_lai = (
            hop_dong.ngay_ket_thuc - hom_nay
        ).days

        if 0 <= so_ngay_con_lai <= 30:

            trang_thai_moi = "sap_het_han"

        else:

            trang_thai_moi = "dang_hieu_luc"

    # =====================================================
    # NẾU KHÔNG ĐỔI TRẠNG THÁI
    # VẪN ĐỒNG BỘ PHÒNG RỒI KẾT THÚC
    # =====================================================

    if trang_thai_cu == trang_thai_moi:

        cap_nhat_trang_thai_phong_theo_hop_dong(
            hop_dong
        )

        return hop_dong

    # =====================================================
    # LƯU TRẠNG THÁI HỢP ĐỒNG
    # =====================================================

    hop_dong.trang_thai = trang_thai_moi

    hop_dong.save(
        update_fields=[
            "trang_thai",
            "ngay_cap_nhat",
        ]
    )

    # =====================================================
    # GHI LỊCH SỬ CHUYỂN TRẠNG THÁI
    # =====================================================

    hanh_dong_lich_su = None
    noi_dung_lich_su = ""

    if trang_thai_moi == "sap_het_han":

        hanh_dong_lich_su = "sap_het_han"
        noi_dung_lich_su = (
            f"Hợp đồng {hop_dong.so_hop_dong} chuyển sang "
            f"trạng thái sắp hết hạn. "
            f"Ngày kết thúc: "
            f"{hop_dong.ngay_ket_thuc.strftime('%d/%m/%Y')}."
        )

    elif trang_thai_moi == "da_het_han":

        hanh_dong_lich_su = "het_han"
        noi_dung_lich_su = (
            f"Hợp đồng {hop_dong.so_hop_dong} đã hết hạn "
            f"sau ngày "
            f"{hop_dong.ngay_ket_thuc.strftime('%d/%m/%Y')}."
        )

    elif trang_thai_moi in [
        "cho_hieu_luc",
        "dang_hieu_luc",
    ]:

        hanh_dong_lich_su = "cap_nhat"
        noi_dung_lich_su = (
            f"Hệ thống tự động cập nhật trạng thái hợp đồng "
            f"{hop_dong.so_hop_dong} từ "
            f"{trang_thai_cu} sang {trang_thai_moi}."
        )

    if hanh_dong_lich_su:

        LichSuHopDong.objects.create(
            hop_dong=hop_dong,
            hanh_dong=hanh_dong_lich_su,
            trang_thai_cu=trang_thai_cu,
            trang_thai_moi=trang_thai_moi,
            noi_dung=noi_dung_lich_su,
            nguoi_thuc_hien=None,
            dia_chi_ip=None,
        )

    # =====================================================
    # XỬ LÝ VÒNG ĐỜI KHI HỢP ĐỒNG HẾT HẠN
    # =====================================================

    if trang_thai_moi == "da_het_han":

        phong = hop_dong.dat_phong.phong
        nguoi_thue = hop_dong.dat_phong.nguoi_thue

        # -------------------------------------------------
        # 1. NGƯỜI Ở CÙNG RỜI PHÒNG
        # -------------------------------------------------

        hop_dong.nguoi_o_cung.filter(
            trang_thai="dang_o"
        ).update(
            trang_thai="da_roi",
            ngay_ra=hom_nay,
        )

        # -------------------------------------------------
        # 2. QUYỀN RA VÀO CỦA CHỦ PHÒNG -> HẾT HẠN
        # -------------------------------------------------

        hop_dong.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown").filter(
            nguoi_thue=nguoi_thue,
        ).exclude(
            trang_thai__in=[
                "het_han",
                "bi_thu_hoi",
            ]
        ).update(
            trang_thai="het_han",
            ngay_ket_thuc=hop_dong.ngay_ket_thuc,
        )

        # -------------------------------------------------
        # 3. QUYỀN RA VÀO NGƯỜI Ở CÙNG -> HẾT HẠN
        # -------------------------------------------------

        hop_dong.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown").filter(
            nguoi_o_cung__hop_dong=hop_dong,
        ).exclude(
            trang_thai__in=[
                "het_han",
                "bi_thu_hoi",
            ]
        ).update(
            trang_thai="het_han",
            ngay_ket_thuc=hop_dong.ngay_ket_thuc,
        )

        # -------------------------------------------------
        # 4. KHÔNG XÓA FACEPROFILE
        # -------------------------------------------------
        # FaceProfile được giữ nguyên để bảo toàn dữ liệu sinh trắc học,
        # lịch sử và khả năng tái sử dụng nếu người thuê ký hợp đồng mới.

    # =====================================================
    # ĐỒNG BỘ TRẠNG THÁI PHÒNG
    # =====================================================

    cap_nhat_trang_thai_phong_theo_hop_dong(
        hop_dong
    )

    return hop_dong


def cap_nhat_trang_thai_phong_theo_hop_dong(hop_dong):
    """
    Đồng bộ trạng thái phòng sau khi hợp đồng thay đổi.

    Toàn bộ logic trạng thái phòng được xử lý tập trung
    tại Phong.dong_bo_trang_thai().
    """

    phong = hop_dong.dat_phong.phong

    phong.dong_bo_trang_thai()


def quan_ly_hop_dong(request):

    if not request.user.is_authenticated:

        return redirect(
            "dang_nhap"
        )

    if not la_admin(request):

        return redirect(
            "tai_khoan"
        )

    # -----------------------------------------------------
    # CẬP NHẬT TRẠNG THÁI HỢP ĐỒNG
    # -----------------------------------------------------

    cac_hop_dong = (
        HopDong.objects
        .exclude(
            trang_thai="da_huy"
        )
        .select_related(
            "dat_phong",
            "dat_phong__nguoi_thue",
            "dat_phong__phong",
            "dat_phong__phong__co_so"
        )
    )

    for hop_dong in cac_hop_dong:

        cap_nhat_trang_thai_hop_dong(
            hop_dong
        )

    # -----------------------------------------------------
    # LẤY LẠI DANH SÁCH
    # -----------------------------------------------------

    danh_sach_hop_dong = (
        HopDong.objects
        .select_related(
            "dat_phong",
            "dat_phong__nguoi_thue",
            "dat_phong__phong",
            "dat_phong__phong__co_so"
        )
        .order_by("-ngay_tao")
    )

    # -----------------------------------------------------
    # ĐỒNG BỘ PHÒNG
    # -----------------------------------------------------

    for hop_dong in danh_sach_hop_dong:

        cap_nhat_trang_thai_phong_theo_hop_dong(
            hop_dong
        )

    # -----------------------------------------------------
    # TÌM KIẾM
    # -----------------------------------------------------

    tu_khoa = request.GET.get(
        "q",
        ""
    ).strip()

    if tu_khoa:

        danh_sach_hop_dong = (
            danh_sach_hop_dong.filter(
                Q(
                    so_hop_dong__icontains=tu_khoa
                )
                |
                Q(
                    dat_phong__nguoi_thue__ho_ten__icontains=tu_khoa
                )
                |
                Q(
                    dat_phong__nguoi_thue__cccd__icontains=tu_khoa
                )
                |
                Q(
                    dat_phong__phong__so_phong__icontains=tu_khoa
                )
                |
                Q(
                    dat_phong__phong__co_so__ten_co_so__icontains=tu_khoa
                )
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
        "cho_hieu_luc",
        "dang_hieu_luc",
        "sap_het_han",
        "da_het_han",
        "da_huy",
    ]

    if trang_thai in cac_trang_thai:

        danh_sach_hop_dong = (
            danh_sach_hop_dong.filter(
                trang_thai=trang_thai
            )
        )

    else:

        trang_thai = ""

    # -----------------------------------------------------
    # THỐNG KÊ
    # -----------------------------------------------------

    tong_hop_dong = HopDong.objects.count()

    cho_hieu_luc = HopDong.objects.filter(
        trang_thai="cho_hieu_luc"
    ).count()

    dang_hieu_luc = HopDong.objects.filter(
        trang_thai="dang_hieu_luc"
    ).count()

    sap_het_han = HopDong.objects.filter(
        trang_thai="sap_het_han"
    ).count()

    da_het_han = HopDong.objects.filter(
        trang_thai="da_het_han"
    ).count()

    da_huy = HopDong.objects.filter(
        trang_thai="da_huy"
    ).count()

    # -----------------------------------------------------
    # ĐƠN ĐÃ DUYỆT NHƯNG CHƯA CÓ HỢP ĐỒNG
    # -----------------------------------------------------

    co_hop_dong = HopDong.objects.filter(
        dat_phong=OuterRef("pk")
    )

    don_chua_co_hop_dong = (
        DatPhong.objects
        .filter(
            trang_thai="da_duyet"
        )
        .annotate(
            da_co_hop_dong=Exists(
                co_hop_dong
            )
        )
        .filter(
            da_co_hop_dong=False
        )
        .select_related(
            "nguoi_thue",
            "phong",
            "phong__co_so"
        )
        .order_by("-ngay_dat")
    )

    context = {

    "hop_dong": danh_sach_hop_dong,
    "hop_dongs": danh_sach_hop_dong,

    "tong_hop_dong": tong_hop_dong,
        "cho_hieu_luc": cho_hieu_luc,
        "dang_hieu_luc": dang_hieu_luc,
        "sap_het_han": sap_het_han,
        "da_het_han": da_het_han,
        "da_huy": da_huy,

        "don_chua_co_hop_dong": don_chua_co_hop_dong,

        "tu_khoa": tu_khoa,
        "trang_thai": trang_thai,
    }

    return render(
        request,
        "core/quan_ly_hop_dong.html",
        context
    )


def chi_tiet_hop_dong(request, id):

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    hop_dong = get_object_or_404(
        HopDong.objects.select_related(
            "dat_phong",
            "dat_phong__nguoi_thue",
            "dat_phong__phong",
            "dat_phong__phong__co_so",
        ).prefetch_related("dat_phong__nguoi_di_cung_khai_bao"),
        id=id,
    )

    # Cập nhật trạng thái mới nhất của hợp đồng.
    cap_nhat_trang_thai_hop_dong(hop_dong)

    # Đồng bộ trạng thái phòng theo hợp đồng.
    cap_nhat_trang_thai_phong_theo_hop_dong(
        hop_dong
    )

    hop_dong.refresh_from_db()

    # -----------------------------------------------------
    # YÊU CẦU GIA HẠN
    # -----------------------------------------------------

    yeu_cau_gia_han_dang_cho = (
        YeuCauGiaHanHopDong.objects
        .filter(
            hop_dong=hop_dong,
            trang_thai="cho_duyet",
        )
        .select_related(
            "nguoi_yeu_cau",
            "nguoi_xu_ly",
        )
        .order_by("-ngay_tao")
        .first()
    )

    lich_su_gia_han = (
        YeuCauGiaHanHopDong.objects
        .filter(hop_dong=hop_dong)
        .select_related(
            "nguoi_yeu_cau",
            "nguoi_xu_ly",
        )
        .order_by("-ngay_tao")
    )

    nguoi_di_cung_khai_bao = (
        hop_dong.dat_phong.nguoi_di_cung_khai_bao
        .exclude(trang_thai_xac_minh="da_huy")
        .order_by("ho_ten", "id")
    )

    return render(
        request,
        "core/chi_tiet_hop_dong.html",
        {
            "hop_dong": hop_dong,
            "nguoi_di_cung_khai_bao": nguoi_di_cung_khai_bao,
            "yeu_cau_gia_han_dang_cho":
                yeu_cau_gia_han_dang_cho,
            "lich_su_gia_han": lich_su_gia_han,
        }
    )


def tao_hop_dong(request, dat_phong_id):

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    dat_phong = get_object_or_404(
        DatPhong.objects.select_related(
            "nguoi_thue",
            "phong",
            "phong__co_so",
        ),
        id=dat_phong_id,
    )

    if dat_phong.trang_thai != "da_duyet":
        messages.error(
            request,
            "Chỉ có thể tạo hợp đồng từ đơn đặt phòng đã được duyệt.",
        )
        return redirect("chi_tiet_dat_phong", id=dat_phong.id)

    hop_dong_cu = HopDong.objects.filter(dat_phong=dat_phong).first()
    if hop_dong_cu:
        messages.warning(
            request,
            f"Đơn này đã có hợp đồng {hop_dong_cu.so_hop_dong}.",
        )
        return redirect("chi_tiet_hop_dong", id=hop_dong_cu.id)

    # Đơn mới bắt buộc có thời hạn thuê.
    if not dat_phong.so_thang_thue:
        messages.error(
            request,
            "Đơn đặt phòng này chưa có thời hạn thuê. "
            "Không thể tự động tạo hợp đồng từ đơn cũ thiếu dữ liệu.",
        )
        return redirect("chi_tiet_dat_phong", id=dat_phong.id)

    ngay_bat_dau_mac_dinh = dat_phong.ngay_nhan_phong

    # Backend tự tính lại để không phụ thuộc dữ liệu ngày trả bị chỉnh thủ công.
    try:
        ngay_ket_thuc_mac_dinh = tinh_ngay_ket_thuc_theo_thang(
            ngay_bat_dau_mac_dinh,
            int(dat_phong.so_thang_thue),
        )
    except (ValueError, TypeError):
        messages.error(
            request,
            "Không thể xác định ngày kết thúc từ thời hạn thuê của đơn đặt phòng.",
        )
        return redirect("chi_tiet_dat_phong", id=dat_phong.id)

    # Tự sửa dữ liệu dự kiến nếu bản ghi đang lệch.
    if dat_phong.ngay_tra_du_kien != ngay_ket_thuc_mac_dinh:
        dat_phong.ngay_tra_du_kien = ngay_ket_thuc_mac_dinh
        dat_phong.save(update_fields=["ngay_tra_du_kien", "ngay_cap_nhat"])

    tien_coc_mac_dinh = (
        dat_phong.tien_coc_du_kien
        or dat_phong.phong.tien_coc_mac_dinh
        or Decimal("0")
    )
    tien_thue_mac_dinh = dat_phong.phong.gia_thue

    def sinh_so_hop_dong_hien_thi():
        nam = timezone.localdate().year
        hop_dong_cuoi = (
            HopDong.objects
            .filter(so_hop_dong__startswith=f"HD-{nam}-")
            .order_by("-so_hop_dong")
            .first()
        )
        so_tiep = 1
        if hop_dong_cuoi:
            try:
                so_tiep = int(hop_dong_cuoi.so_hop_dong.split("-")[-1]) + 1
            except (ValueError, IndexError):
                so_tiep = 1
        return f"HD-{nam}-{so_tiep:03d}"

    so_hop_dong_tu_dong = sinh_so_hop_dong_hien_thi()

    def render_form(message=None, level="error"):
        if message:
            if level == "warning":
                messages.warning(request, message)
            else:
                messages.error(request, message)

        return render(
            request,
            "core/tao_hop_dong.html",
            {
                "dat_phong": dat_phong,
                "ngay_bat_dau_mac_dinh": ngay_bat_dau_mac_dinh,
                "ngay_ket_thuc_mac_dinh": ngay_ket_thuc_mac_dinh,
                "tien_coc_mac_dinh": tien_coc_mac_dinh,
                "tien_thue_mac_dinh": tien_thue_mac_dinh,
                "so_hop_dong_tu_dong": so_hop_dong_tu_dong,
                "so_thang_thue": dat_phong.so_thang_thue,
            },
        )

    if request.method == "POST":

        tien_coc_raw = request.POST.get("tien_coc", "").strip()
        tien_thue_thang_raw = request.POST.get(
            "tien_thue_thang", ""
        ).strip()
        ngay_thanh_toan_raw = request.POST.get(
            "ngay_thanh_toan_hang_thang", "5"
        ).strip()
        phuong_thuc_thanh_toan = request.POST.get(
            "phuong_thuc_thanh_toan", "chuyen_khoan"
        ).strip()
        so_nguoi_o_raw = request.POST.get("so_nguoi_o", "1").strip()
        tien_phat_raw = request.POST.get(
            "tien_phat_tre_han", "0"
        ).strip()
        dieu_khoan = request.POST.get("dieu_khoan", "").strip()
        ghi_chu = request.POST.get("ghi_chu", "").strip()
        cho_phep_ghep = request.POST.get("cho_phep_ghep") == "on"

        # Ngày hợp đồng lấy từ đơn đặt phòng, không tin dữ liệu POST.
        ngay_bat_dau = dat_phong.ngay_nhan_phong
        try:
            ngay_ket_thuc = tinh_ngay_ket_thuc_theo_thang(
                ngay_bat_dau,
                int(dat_phong.so_thang_thue),
            )
        except (ValueError, TypeError):
            return render_form(
                "Không thể xác định thời hạn hợp đồng từ đơn đặt phòng."
            )

        try:
            tien_coc = (
                Decimal(tien_coc_raw)
                if tien_coc_raw
                else tien_coc_mac_dinh
            )
            if tien_coc < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            return render_form("Tiền cọc không hợp lệ.")

        try:
            tien_thue_thang = (
                Decimal(tien_thue_thang_raw)
                if tien_thue_thang_raw
                else tien_thue_mac_dinh
            )
            if tien_thue_thang < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            return render_form("Tiền thuê hàng tháng không hợp lệ.")

        try:
            ngay_thanh_toan_hang_thang = int(
                ngay_thanh_toan_raw or 5
            )
            if not 1 <= ngay_thanh_toan_hang_thang <= 28:
                raise ValueError
        except (ValueError, TypeError):
            return render_form(
                "Ngày thanh toán hàng tháng phải từ 1 đến 28."
            )

        if phuong_thuc_thanh_toan not in [
            "tien_mat",
            "chuyen_khoan",
        ]:
            return render_form("Phương thức thanh toán không hợp lệ.")

        try:
            so_nguoi_o = int(so_nguoi_o_raw or 1)
            if so_nguoi_o < 1:
                raise ValueError
            if so_nguoi_o > dat_phong.phong.so_nguoi_toi_da:
                return render_form(
                    f"Số người ở không được vượt quá "
                    f"{dat_phong.phong.so_nguoi_toi_da} người."
                )
        except (ValueError, TypeError):
            return render_form("Số người ở không hợp lệ.")

        try:
            tien_phat_tre_han = Decimal(tien_phat_raw or 0)
            if tien_phat_tre_han < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            return render_form("Tiền phạt trễ hạn không hợp lệ.")

        with transaction.atomic():

            dat_phong = (
                DatPhong.objects
                .select_for_update()
                .select_related(
                    "nguoi_thue",
                    "phong",
                    "phong__co_so",
                )
                .get(id=dat_phong_id)
            )

            if dat_phong.trang_thai != "da_duyet":
                messages.error(
                    request,
                    "Đơn đặt phòng không còn ở trạng thái được phép tạo hợp đồng.",
                )
                return redirect(
                    "chi_tiet_dat_phong",
                    id=dat_phong.id,
                )

            hop_dong_cu = HopDong.objects.filter(
                dat_phong=dat_phong
            ).first()
            if hop_dong_cu:
                messages.warning(
                    request,
                    f"Đơn này đã có hợp đồng {hop_dong_cu.so_hop_dong}.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=hop_dong_cu.id,
                )

            if not dat_phong.so_thang_thue:
                messages.error(
                    request,
                    "Đơn đặt phòng không có thời hạn thuê.",
                )
                return redirect(
                    "chi_tiet_dat_phong",
                    id=dat_phong.id,
                )

            ngay_bat_dau = dat_phong.ngay_nhan_phong
            ngay_ket_thuc = tinh_ngay_ket_thuc_theo_thang(
                ngay_bat_dau,
                int(dat_phong.so_thang_thue),
            )

            # Khóa phòng để tránh thay đổi nghiệp vụ đồng thời.
            phong = (
                Phong.objects
                .select_for_update()
                .get(pk=dat_phong.phong_id)
            )
            phong.dong_bo_trang_thai()
            phong.refresh_from_db()

            # Đơn đã duyệt này phải là đơn đang giữ chính phòng đó.
            if phong.trang_thai not in ["da_dat", "trong"]:
                messages.error(
                    request,
                    "Phòng không còn ở trạng thái phù hợp để tạo hợp đồng.",
                )
                return redirect(
                    "chi_tiet_dat_phong",
                    id=dat_phong.id,
                )

            nam_hien_tai = timezone.localdate().year
            hop_dong_nam = (
                HopDong.objects
                .select_for_update()
                .filter(
                    so_hop_dong__startswith=f"HD-{nam_hien_tai}-"
                )
                .order_by("-so_hop_dong")
            )
            hop_dong_cuoi = hop_dong_nam.first()

            so_thu_tu_tiep_theo = 1
            if hop_dong_cuoi:
                try:
                    so_thu_tu_tiep_theo = (
                        int(
                            hop_dong_cuoi.so_hop_dong.split("-")[-1]
                        )
                        + 1
                    )
                except (ValueError, IndexError):
                    so_thu_tu_tiep_theo = 1

            so_hop_dong = (
                f"HD-{nam_hien_tai}-{so_thu_tu_tiep_theo:03d}"
            )

            hop_dong = HopDong.objects.create(
                dat_phong=dat_phong,
                so_hop_dong=so_hop_dong,
                ngay_bat_dau=ngay_bat_dau,
                ngay_ket_thuc=ngay_ket_thuc,
                tien_coc=tien_coc,
                tien_thue_thang=tien_thue_thang,
                ngay_thanh_toan_hang_thang=(
                    ngay_thanh_toan_hang_thang
                ),
                phuong_thuc_thanh_toan=(
                    phuong_thuc_thanh_toan
                ),
                so_nguoi_o=so_nguoi_o,
                cho_phep_ghep=cho_phep_ghep,
                tien_phat_tre_han=tien_phat_tre_han,
                dieu_khoan=dieu_khoan,
                ghi_chu=ghi_chu,
                ngay_ky=timezone.now(),
                nguoi_tao=request.user,
                nguoi_cap_nhat=request.user,
            )

            cap_nhat_trang_thai_hop_dong(hop_dong)

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Hợp đồng",
                doi_tuong="HopDong",
                doi_tuong_id=hop_dong.id,
                tieu_de=f"Tạo hợp đồng {hop_dong.so_hop_dong}",
                noi_dung=(
                    f"Admin {request.user.username} tạo hợp đồng "
                    f"{hop_dong.so_hop_dong} cho "
                    f"{dat_phong.nguoi_thue.ho_ten}, phòng "
                    f"{dat_phong.phong.so_phong}, thời hạn "
                    f"{dat_phong.so_thang_thue} tháng "
                    f"({ngay_bat_dau.strftime('%d/%m/%Y')} - "
                    f"{ngay_ket_thuc.strftime('%d/%m/%Y')})."
                ),
                du_lieu_cu={},
                du_lieu_moi={
                    "hop_dong_id": hop_dong.id,
                    "so_hop_dong": hop_dong.so_hop_dong,
                    "nguoi_thue": dat_phong.nguoi_thue.ho_ten,
                    "phong": dat_phong.phong.so_phong,
                    "so_thang_thue": dat_phong.so_thang_thue,
                    "ngay_bat_dau": str(hop_dong.ngay_bat_dau),
                    "ngay_ket_thuc": str(hop_dong.ngay_ket_thuc),
                    "tien_coc": str(hop_dong.tien_coc),
                    "tien_thue_thang": str(
                        hop_dong.tien_thue_thang
                    ),
                    "ngay_thanh_toan_hang_thang": (
                        hop_dong.ngay_thanh_toan_hang_thang
                    ),
                    "phuong_thuc_thanh_toan": (
                        hop_dong.phuong_thuc_thanh_toan
                    ),
                    "so_nguoi_o": hop_dong.so_nguoi_o,
                    "cho_phep_ghep": hop_dong.cho_phep_ghep,
                    "tien_phat_tre_han": str(
                        hop_dong.tien_phat_tre_han
                    ),
                    "trang_thai": hop_dong.trang_thai,
                },
            )

            thong_bao_moi = ThongBao.objects.create(
                nguoi_thue=dat_phong.nguoi_thue,
                tieu_de="Hợp đồng thuê phòng đã được tạo",
                noi_dung=(
                    f"Hợp đồng {hop_dong.so_hop_dong} cho phòng "
                    f"{dat_phong.phong.so_phong} đã được tạo. "
                    f"Thời hạn thuê {dat_phong.so_thang_thue} tháng, "
                    f"từ {hop_dong.ngay_bat_dau.strftime('%d/%m/%Y')} "
                    f"đến {hop_dong.ngay_ket_thuc.strftime('%d/%m/%Y')}."
                ),
                loai="hop_dong",
                muc_do="quan_trong",
            )

            ghi_nhat_ky(
                request=request,
                hanh_dong="Tạo",
                module="Thông báo",
                doi_tuong="ThongBao",
                doi_tuong_id=thong_bao_moi.id,
                tieu_de=(
                    f"Tạo thông báo hợp đồng "
                    f"{hop_dong.so_hop_dong}"
                ),
                noi_dung=(
                    f"Tạo thông báo hợp đồng cho "
                    f"{dat_phong.nguoi_thue.ho_ten}."
                ),
                du_lieu_cu={},
                du_lieu_moi={
                    "thong_bao_id": thong_bao_moi.id,
                    "hop_dong_id": hop_dong.id,
                    "so_hop_dong": hop_dong.so_hop_dong,
                },
            )

        messages.success(
            request,
            f"Đã tạo hợp đồng {hop_dong.so_hop_dong} thành công.",
        )
        return redirect(
            "chi_tiet_hop_dong",
            id=hop_dong.id,
        )

    return render_form()


def sua_hop_dong(request, id):

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    hop_dong = get_object_or_404(
        HopDong.objects.select_related(
            "dat_phong",
            "dat_phong__nguoi_thue",
            "dat_phong__phong",
            "dat_phong__phong__co_so",
        ).prefetch_related("dat_phong__nguoi_di_cung_khai_bao"),
        id=id,
    )

    dat_phong = hop_dong.dat_phong
    phong = dat_phong.phong
    nguoi_thue = dat_phong.nguoi_thue

    # -----------------------------------------------------
    # KHÔNG CHO SỬA HỢP ĐỒNG ĐÃ KẾT THÚC VÒNG ĐỜI
    # -----------------------------------------------------

    if hop_dong.trang_thai == "da_huy":
        messages.error(
            request,
            "Hợp đồng đã bị hủy, không thể chỉnh sửa.",
        )
        return redirect(
            "chi_tiet_hop_dong",
            id=id,
        )

    if hop_dong.trang_thai == "da_het_han":
        messages.error(
            request,
            "Hợp đồng đã hết hạn, không thể chỉnh sửa trực tiếp. "
            "Nếu tiếp tục thuê cần xử lý theo nghiệp vụ gia hạn.",
        )
        return redirect(
            "chi_tiet_hop_dong",
            id=id,
        )

    # -----------------------------------------------------
    # THỜI HẠN HỢP ĐỒNG
    #
    # Không nhận ngày bắt đầu / kết thúc từ form sửa.
    # Đây là dữ liệu vòng đời được xác lập khi tạo hợp đồng
    # từ đơn đặt phòng và chỉ thay đổi qua nghiệp vụ gia hạn.
    # -----------------------------------------------------

    so_thang_thue = dat_phong.so_thang_thue

    def render_form():
        return render(
            request,
            "core/sua_hop_dong.html",
            {
                "hop_dong": hop_dong,
                "phong": phong,
                "nguoi_thue": nguoi_thue,
                "so_thang_thue": so_thang_thue,
            },
        )

    # -----------------------------------------------------
    # XỬ LÝ FORM
    # -----------------------------------------------------

    if request.method == "POST":

        tien_coc_str = request.POST.get(
            "tien_coc",
            str(hop_dong.tien_coc),
        ).strip()

        tien_thue_thang_str = request.POST.get(
            "tien_thue_thang",
            str(hop_dong.tien_thue_thang),
        ).strip()

        ngay_thanh_toan_str = request.POST.get(
            "ngay_thanh_toan_hang_thang",
            str(hop_dong.ngay_thanh_toan_hang_thang),
        ).strip()

        phuong_thuc_thanh_toan = request.POST.get(
            "phuong_thuc_thanh_toan",
            hop_dong.phuong_thuc_thanh_toan,
        ).strip()

        so_nguoi_o_str = request.POST.get(
            "so_nguoi_o",
            str(hop_dong.so_nguoi_o),
        ).strip()

        tien_phat_tre_han_str = request.POST.get(
            "tien_phat_tre_han",
            str(hop_dong.tien_phat_tre_han),
        ).strip()

        dieu_khoan = request.POST.get(
            "dieu_khoan",
            "",
        ).strip()

        ghi_chu = request.POST.get(
            "ghi_chu",
            "",
        ).strip()

        # Checkbox không gửi giá trị khi bỏ chọn.
        cho_phep_ghep = (
            request.POST.get("cho_phep_ghep") == "on"
        )

        # -------------------------------------------------
        # PARSE SỐ
        # -------------------------------------------------

        try:
            tien_coc = Decimal(tien_coc_str)
            tien_thue_thang = Decimal(tien_thue_thang_str)
            tien_phat_tre_han = Decimal(tien_phat_tre_han_str)
            ngay_thanh_toan_hang_thang = int(
                ngay_thanh_toan_str
            )
            so_nguoi_o = int(so_nguoi_o_str)

        except (InvalidOperation, ValueError):
            messages.error(
                request,
                "Các giá trị số không hợp lệ.",
            )
            return render_form()

        # -------------------------------------------------
        # VALIDATE TIỀN
        # -------------------------------------------------

        if tien_coc < 0:
            messages.error(
                request,
                "Tiền cọc không được nhỏ hơn 0.",
            )
            return render_form()

        if tien_thue_thang < 0:
            messages.error(
                request,
                "Tiền thuê hàng tháng không được nhỏ hơn 0.",
            )
            return render_form()

        if tien_phat_tre_han < 0:
            messages.error(
                request,
                "Tiền phạt trễ hạn không được nhỏ hơn 0.",
            )
            return render_form()

        # -------------------------------------------------
        # VALIDATE NGÀY THANH TOÁN
        # -------------------------------------------------

        if not 1 <= ngay_thanh_toan_hang_thang <= 28:
            messages.error(
                request,
                "Ngày thanh toán hàng tháng phải từ 1 đến 28.",
            )
            return render_form()

        # -------------------------------------------------
        # VALIDATE PHƯƠNG THỨC THANH TOÁN
        # -------------------------------------------------

        if phuong_thuc_thanh_toan not in [
            "tien_mat",
            "chuyen_khoan",
        ]:
            messages.error(
                request,
                "Phương thức thanh toán không hợp lệ.",
            )
            return render_form()

        # -------------------------------------------------
        # VALIDATE SỐ NGƯỜI Ở
        # -------------------------------------------------

        if so_nguoi_o < 1:
            messages.error(
                request,
                "Số người ở phải ít nhất là 1.",
            )
            return render_form()

        if so_nguoi_o > phong.so_nguoi_toi_da:
            messages.error(
                request,
                f"Số người ở không được vượt quá "
                f"{phong.so_nguoi_toi_da} người.",
            )
            return render_form()

        # Không cho khai báo số người thấp hơn số người
        # thực tế đang được hệ thống ghi nhận trong phòng.
        so_nguoi_thuc_te = phong.so_nguoi_dang_o

        if (
            hop_dong.trang_thai
            in ["dang_hieu_luc", "sap_het_han"]
            and so_nguoi_o < so_nguoi_thuc_te
        ):
            messages.error(
                request,
                f"Phòng hiện đang ghi nhận "
                f"{so_nguoi_thuc_te} người ở. "
                f"Không thể đặt số người ở thấp hơn dữ liệu thực tế.",
            )
            return render_form()

        # -------------------------------------------------
        # KHÓA BẢN GHI VÀ LƯU
        # -------------------------------------------------

        with transaction.atomic():

            hop_dong_khoa = get_object_or_404(
                HopDong.objects
                .select_for_update()
                .select_related(
                    "dat_phong",
                    "dat_phong__nguoi_thue",
                    "dat_phong__phong",
                    "dat_phong__phong__co_so",
                ),
                id=hop_dong.id,
            )

            if hop_dong_khoa.trang_thai in [
                "da_huy",
                "da_het_han",
            ]:
                messages.error(
                    request,
                    "Trạng thái hợp đồng đã thay đổi. "
                    "Không thể tiếp tục chỉnh sửa.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=id,
                )

            phong_khoa = (
                Phong.objects
                .select_for_update()
                .get(id=hop_dong_khoa.dat_phong.phong_id)
            )

            if so_nguoi_o > phong_khoa.so_nguoi_toi_da:
                messages.error(
                    request,
                    f"Số người ở không được vượt quá "
                    f"{phong_khoa.so_nguoi_toi_da} người.",
                )
                return render_form()

            # ---------------------------------------------
            # DỮ LIỆU CŨ
            # ---------------------------------------------

            du_lieu_cu = {
                "ngay_bat_dau": (
                    hop_dong_khoa.ngay_bat_dau.isoformat()
                    if hop_dong_khoa.ngay_bat_dau
                    else None
                ),
                "ngay_ket_thuc": (
                    hop_dong_khoa.ngay_ket_thuc.isoformat()
                    if hop_dong_khoa.ngay_ket_thuc
                    else None
                ),
                "so_thang_thue": (
                    hop_dong_khoa.dat_phong.so_thang_thue
                ),
                "tien_coc": str(hop_dong_khoa.tien_coc),
                "tien_thue_thang": str(
                    hop_dong_khoa.tien_thue_thang
                ),
                "ngay_thanh_toan_hang_thang": (
                    hop_dong_khoa.ngay_thanh_toan_hang_thang
                ),
                "phuong_thuc_thanh_toan": (
                    hop_dong_khoa.phuong_thuc_thanh_toan
                ),
                "so_nguoi_o": hop_dong_khoa.so_nguoi_o,
                "cho_phep_ghep": hop_dong_khoa.cho_phep_ghep,
                "tien_phat_tre_han": str(
                    hop_dong_khoa.tien_phat_tre_han
                ),
                "dieu_khoan": hop_dong_khoa.dieu_khoan,
                "ghi_chu": hop_dong_khoa.ghi_chu,
                "trang_thai": hop_dong_khoa.trang_thai,
            }

            # ---------------------------------------------
            # CẬP NHẬT CÁC TRƯỜNG ĐƯỢC PHÉP SỬA
            # ---------------------------------------------

            hop_dong_khoa.tien_coc = tien_coc
            hop_dong_khoa.tien_thue_thang = tien_thue_thang
            hop_dong_khoa.ngay_thanh_toan_hang_thang = (
                ngay_thanh_toan_hang_thang
            )
            hop_dong_khoa.phuong_thuc_thanh_toan = (
                phuong_thuc_thanh_toan
            )
            hop_dong_khoa.so_nguoi_o = so_nguoi_o
            hop_dong_khoa.cho_phep_ghep = cho_phep_ghep
            hop_dong_khoa.tien_phat_tre_han = (
                tien_phat_tre_han
            )
            hop_dong_khoa.dieu_khoan = dieu_khoan
            hop_dong_khoa.ghi_chu = ghi_chu
            hop_dong_khoa.nguoi_cap_nhat = request.user

            # KHÔNG sửa:
            # - ngay_bat_dau
            # - ngay_ket_thuc
            # - trang_thai
            # - ngay_ky
            # - ngay_huy
            # - ly_do_huy
            # - nguoi_tao
            #
            # Thời hạn chỉ thay đổi qua nghiệp vụ gia hạn.

            hop_dong_khoa.save(
                update_fields=[
                    "tien_coc",
                    "tien_thue_thang",
                    "ngay_thanh_toan_hang_thang",
                    "phuong_thuc_thanh_toan",
                    "so_nguoi_o",
                    "cho_phep_ghep",
                    "tien_phat_tre_han",
                    "dieu_khoan",
                    "ghi_chu",
                    "nguoi_cap_nhat",
                    "ngay_cap_nhat",
                ]
            )

            # Đồng bộ trạng thái theo thời gian hiện tại,
            # nhưng không cho form sửa tự quyết định trạng thái.
            cap_nhat_trang_thai_hop_dong(
                hop_dong_khoa
            )

            hop_dong_khoa.refresh_from_db()
            phong_khoa.refresh_from_db()

            # ---------------------------------------------
            # DỮ LIỆU MỚI
            # ---------------------------------------------

            du_lieu_moi = {
                "ngay_bat_dau": (
                    hop_dong_khoa.ngay_bat_dau.isoformat()
                    if hop_dong_khoa.ngay_bat_dau
                    else None
                ),
                "ngay_ket_thuc": (
                    hop_dong_khoa.ngay_ket_thuc.isoformat()
                    if hop_dong_khoa.ngay_ket_thuc
                    else None
                ),
                "so_thang_thue": (
                    hop_dong_khoa.dat_phong.so_thang_thue
                ),
                "tien_coc": str(hop_dong_khoa.tien_coc),
                "tien_thue_thang": str(
                    hop_dong_khoa.tien_thue_thang
                ),
                "ngay_thanh_toan_hang_thang": (
                    hop_dong_khoa.ngay_thanh_toan_hang_thang
                ),
                "phuong_thuc_thanh_toan": (
                    hop_dong_khoa.phuong_thuc_thanh_toan
                ),
                "so_nguoi_o": hop_dong_khoa.so_nguoi_o,
                "cho_phep_ghep": hop_dong_khoa.cho_phep_ghep,
                "tien_phat_tre_han": str(
                    hop_dong_khoa.tien_phat_tre_han
                ),
                "dieu_khoan": hop_dong_khoa.dieu_khoan,
                "ghi_chu": hop_dong_khoa.ghi_chu,
                "trang_thai": hop_dong_khoa.trang_thai,
                "trang_thai_phong": phong_khoa.trang_thai,
            }

            ghi_nhat_ky(
                request=request,
                hanh_dong="Sửa",
                module="Hợp đồng",
                doi_tuong="HopDong",
                doi_tuong_id=hop_dong_khoa.id,
                tieu_de=(
                    f"Sửa hợp đồng "
                    f"{hop_dong_khoa.so_hop_dong}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} đã cập nhật "
                    f"thông tin hợp đồng "
                    f"{hop_dong_khoa.so_hop_dong} "
                    f"của phòng {phong_khoa.so_phong}. "
                    f"Thời hạn hợp đồng được giữ nguyên."
                ),
                du_lieu_cu=du_lieu_cu,
                du_lieu_moi=du_lieu_moi,
            )

        messages.success(
            request,
            f"Đã cập nhật hợp đồng "
            f"{hop_dong.so_hop_dong}. "
            f"Thời hạn hợp đồng được giữ nguyên.",
        )

        return redirect(
            "chi_tiet_hop_dong",
            id=hop_dong.id,
        )

    return render_form()


def xu_ly_hop_dong(request, id):

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method != "POST":
        return redirect(
            "chi_tiet_hop_dong",
            id=id,
        )

    hanh_dong = request.POST.get(
        "hanh_dong",
        "",
    ).strip()

    with transaction.atomic():

        room_id = get_object_or_404(
            HopDong.objects.values("dat_phong__phong_id"), pk=id
        )["dat_phong__phong_id"]
        Phong.objects.select_for_update().get(pk=room_id)

        hop_dong = get_object_or_404(
            HopDong.objects
            .select_for_update()
            .select_related(
                "dat_phong",
                "dat_phong__nguoi_thue",
                "dat_phong__phong",
                "dat_phong__phong__co_so",
            ),
            id=id,
        )

        phong = (
            Phong.objects
            .select_for_update()
            .select_related("co_so")
            .get(id=hop_dong.dat_phong.phong_id)
        )

        dat_phong = hop_dong.dat_phong
        nguoi_thue = dat_phong.nguoi_thue

        # =====================================================
        # KÍCH HOẠT HỢP ĐỒNG
        # =====================================================

        if hanh_dong == "kich_hoat":

            if hop_dong.trang_thai == "da_huy":
                messages.error(
                    request,
                    "Hợp đồng đã bị hủy, không thể kích hoạt lại.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=id,
                )

            hom_nay = timezone.localdate()

            if hom_nay > hop_dong.ngay_ket_thuc:
                cap_nhat_trang_thai_hop_dong(hop_dong)

                messages.error(
                    request,
                    "Hợp đồng đã quá ngày kết thúc, không thể kích hoạt.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=id,
                )

            if hom_nay < hop_dong.ngay_bat_dau:
                cap_nhat_trang_thai_hop_dong(hop_dong)

                messages.warning(
                    request,
                    "Hợp đồng chưa đến ngày bắt đầu nên vẫn ở trạng thái "
                    "chờ hiệu lực. Hệ thống không thay đổi thời hạn hợp đồng.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=id,
                )

            # Không cho một phòng có nhiều hợp đồng cùng hiệu lực.
            phong_dang_thue_khac = (
                HopDong.objects
                .filter(
                    dat_phong__phong=phong,
                    trang_thai__in=[
                        "dang_hieu_luc",
                        "sap_het_han",
                    ],
                )
                .exclude(id=hop_dong.id)
                .exists()
            )

            if phong_dang_thue_khac:
                messages.error(
                    request,
                    f"Phòng {phong.so_phong} đang có hợp đồng khác "
                    f"có hiệu lực.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=id,
                )

            if hop_dong.trang_thai in ["dang_hieu_luc", "sap_het_han"] and hop_dong.ngay_ky:
                cap_nhat_trang_thai_hop_dong(hop_dong)
                messages.info(request, "Hợp đồng đã được kích hoạt.")
                return redirect("chi_tiet_hop_dong", id=id)

            trang_thai_cu = hop_dong.trang_thai

            # Không tự đổi ngày bắt đầu / ngày kết thúc.
            # Hai ngày này phải giữ đúng thời hạn đã tạo từ đơn đặt phòng.
            hop_dong.nguoi_cap_nhat = request.user

            update_fields = [
                "nguoi_cap_nhat",
                "ngay_cap_nhat",
            ]

            if not hop_dong.ngay_ky:
                hop_dong.ngay_ky = timezone.now()
                update_fields.append("ngay_ky")

            hop_dong.save(
                update_fields=update_fields,
            )

            # Tính trạng thái đúng theo ngày hiện tại và đồng bộ phòng.
            cap_nhat_trang_thai_hop_dong(hop_dong)

            hop_dong.refresh_from_db()

            if hop_dong.trang_thai not in [
                "dang_hieu_luc",
                "sap_het_han",
            ]:
                messages.warning(
                    request,
                    "Hợp đồng chưa thể chuyển sang trạng thái có hiệu lực.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=id,
                )

            if dat_phong.trang_thai != "da_duyet":
                dat_phong.trang_thai = "da_duyet"
                dat_phong.nguoi_xu_ly = request.user
                dat_phong.save(
                    update_fields=[
                        "trang_thai",
                        "nguoi_xu_ly",
                        "ngay_cap_nhat",
                    ]
                )

            thong_bao_moi = ThongBao.objects.create(
                nguoi_thue=nguoi_thue,
                tieu_de="Hợp đồng đã có hiệu lực",
                noi_dung=(
                    f"Hợp đồng {hop_dong.so_hop_dong} cho phòng "
                    f"{phong.so_phong} đang có hiệu lực. "
                    f"Thời hạn từ "
                    f"{hop_dong.ngay_bat_dau.strftime('%d/%m/%Y')} "
                    f"đến "
                    f"{hop_dong.ngay_ket_thuc.strftime('%d/%m/%Y')}."
                ),
                loai="hop_dong",
                muc_do="binh_thuong",
            )

            ghi_nhat_ky(
                request=request,
                hanh_dong="Kích hoạt",
                module="Hợp đồng",
                doi_tuong="HopDong",
                doi_tuong_id=hop_dong.id,
                tieu_de=(
                    f"Kích hoạt hợp đồng {hop_dong.so_hop_dong}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} xác nhận hợp đồng "
                    f"{hop_dong.so_hop_dong} của phòng "
                    f"{phong.so_phong} có hiệu lực."
                ),
                du_lieu_cu={
                    "trang_thai": trang_thai_cu,
                    "ngay_bat_dau": str(hop_dong.ngay_bat_dau),
                    "ngay_ket_thuc": str(hop_dong.ngay_ket_thuc),
                },
                du_lieu_moi={
                    "trang_thai": hop_dong.trang_thai,
                    "so_hop_dong": hop_dong.so_hop_dong,
                    "phong": phong.so_phong,
                    "nguoi_thue": nguoi_thue.ho_ten,
                    "thong_bao_id": thong_bao_moi.id,
                },
            )

            messages.success(
                request,
                f"Hợp đồng {hop_dong.so_hop_dong} đang có hiệu lực.",
            )

        # =====================================================
        # HỦY HỢP ĐỒNG
        # =====================================================

        elif hanh_dong == "huy":

            if hop_dong.trang_thai == "da_huy":
                messages.warning(
                    request,
                    "Hợp đồng này đã được hủy trước đó.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=id,
                )

            trang_thai_cu = hop_dong.trang_thai

            ly_do_huy = request.POST.get(
                "ly_do_huy",
                "",
            ).strip()

            if not ly_do_huy:
                ly_do_huy = "Hủy bởi quản trị viên."

            thoi_diem_huy = timezone.now()
            ngay_hom_nay = timezone.localdate()

            # Cập nhật đầy đủ thông tin hủy.
            hop_dong.trang_thai = "da_huy"
            hop_dong.ngay_huy = thoi_diem_huy
            hop_dong.ly_do_huy = ly_do_huy
            hop_dong.nguoi_cap_nhat = request.user

            hop_dong.save(
                update_fields=[
                    "trang_thai",
                    "ngay_huy",
                    "ly_do_huy",
                    "nguoi_cap_nhat",
                    "ngay_cap_nhat",
                ]
            )

            # -------------------------------------------------
            # THU HỒI QUYỀN RA VÀO SMART ROOM
            #
            # Không xóa FaceProfile để giữ hồ sơ/lịch sử.
            # Chỉ thu hồi quyền vào đúng phòng của hợp đồng.
            # -------------------------------------------------

            quyen_chu_phong_thu_hoi = (
                hop_dong.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown")
                .filter(nguoi_thue=nguoi_thue)
                .exclude(trang_thai="bi_thu_hoi")
                .update(
                    trang_thai="bi_thu_hoi",
                    ngay_ket_thuc=ngay_hom_nay,
                )
            )

            quyen_nguoi_o_cung_thu_hoi = (
                hop_dong.quyen_ra_vao_theo_hop_dong.exclude(nguon_cap="legacy_unknown")
                .filter(nguoi_o_cung__hop_dong=hop_dong)
                .exclude(trang_thai="bi_thu_hoi")
                .update(
                    trang_thai="bi_thu_hoi",
                    ngay_ket_thuc=ngay_hom_nay,
                )
            )

            tong_quyen_thu_hoi = (
                quyen_chu_phong_thu_hoi
                + quyen_nguoi_o_cung_thu_hoi
            )

            # Không xóa đơn đặt phòng cũ và không đổi da_duyet thành da_huy.
            # Đơn là lịch sử của giao dịch đã được duyệt; hợp đồng da_huy
            # sẽ không còn giữ phòng theo logic trạng thái nghiệp vụ.

            NguoiOCungPhong.objects.filter(
                hop_dong=hop_dong, trang_thai="dang_o",
            ).update(trang_thai="da_roi", ngay_ra=ngay_hom_nay)

            # Đồng bộ lại phòng từ nguồn sự thật nghiệp vụ.
            cap_nhat_trang_thai_phong_theo_hop_dong(
                hop_dong
            )

            phong.refresh_from_db()

            thong_bao_moi = ThongBao.objects.create(
                nguoi_thue=nguoi_thue,
                tieu_de="Hợp đồng đã bị hủy",
                noi_dung=(
                    f"Hợp đồng {hop_dong.so_hop_dong} của phòng "
                    f"{phong.so_phong} đã được quản trị viên hủy. "
                    f"Lý do: {ly_do_huy} "
                    f"Quyền ra vào phòng theo hợp đồng đã được thu hồi."
                ),
                loai="hop_dong",
                muc_do="canh_bao",
            )

            ghi_nhat_ky(
                request=request,
                hanh_dong="Hủy",
                module="Hợp đồng",
                doi_tuong="HopDong",
                doi_tuong_id=hop_dong.id,
                tieu_de=f"Hủy hợp đồng {hop_dong.so_hop_dong}",
                noi_dung=(
                    f"Admin {request.user.username} đã hủy hợp đồng "
                    f"{hop_dong.so_hop_dong} của phòng "
                    f"{phong.so_phong}. "
                    f"Lý do: {ly_do_huy}. "
                    f"Đã thu hồi {tong_quyen_thu_hoi} quyền ra vào."
                ),
                du_lieu_cu={
                    "trang_thai": trang_thai_cu,
                    "so_hop_dong": hop_dong.so_hop_dong,
                    "phong": phong.so_phong,
                },
                du_lieu_moi={
                    "trang_thai": hop_dong.trang_thai,
                    "ngay_huy": thoi_diem_huy.isoformat(),
                    "ly_do_huy": ly_do_huy,
                    "so_hop_dong": hop_dong.so_hop_dong,
                    "phong": phong.so_phong,
                    "nguoi_thue": nguoi_thue.ho_ten,
                    "trang_thai_phong": phong.trang_thai,
                    "so_quyen_ra_vao_thu_hoi": tong_quyen_thu_hoi,
                    "thong_bao_id": thong_bao_moi.id,
                },
            )

            messages.success(
                request,
                f"Đã hủy hợp đồng {hop_dong.so_hop_dong}, "
                f"đồng bộ lại phòng và thu hồi quyền ra vào.",
            )

        # =====================================================
        # CẬP NHẬT TRẠNG THÁI
        # =====================================================

        elif hanh_dong == "cap_nhat_trang_thai":

            if hop_dong.trang_thai == "da_huy":
                messages.warning(
                    request,
                    "Hợp đồng đã hủy không thể cập nhật trạng thái.",
                )
                return redirect(
                    "chi_tiet_hop_dong",
                    id=id,
                )

            trang_thai_cu = hop_dong.trang_thai

            cap_nhat_trang_thai_hop_dong(
                hop_dong
            )

            hop_dong.refresh_from_db()
            phong.refresh_from_db()

            if trang_thai_cu != hop_dong.trang_thai:
                hop_dong.nguoi_cap_nhat = request.user
                hop_dong.save(
                    update_fields=[
                        "nguoi_cap_nhat",
                        "ngay_cap_nhat",
                    ]
                )

                ghi_nhat_ky(
                    request=request,
                    hanh_dong="Cập nhật",
                    module="Hợp đồng",
                    doi_tuong="HopDong",
                    doi_tuong_id=hop_dong.id,
                    tieu_de=(
                        f"Cập nhật trạng thái hợp đồng "
                        f"{hop_dong.so_hop_dong}"
                    ),
                    noi_dung=(
                        f"Trạng thái hợp đồng {hop_dong.so_hop_dong} "
                        f"được cập nhật từ {trang_thai_cu} "
                        f"sang {hop_dong.trang_thai}."
                    ),
                    du_lieu_cu={
                        "trang_thai": trang_thai_cu,
                    },
                    du_lieu_moi={
                        "trang_thai": hop_dong.trang_thai,
                        "trang_thai_phong": phong.trang_thai,
                    },
                )

            if hop_dong.trang_thai in [
                "dang_hieu_luc",
                "sap_het_han",
            ]:
                messages.success(
                    request,
                    "Hợp đồng đang có hiệu lực.",
                )

            elif hop_dong.trang_thai == "da_het_han":
                messages.warning(
                    request,
                    "Hợp đồng đã hết hạn.",
                )

            elif hop_dong.trang_thai == "cho_hieu_luc":
                messages.success(
                    request,
                    "Hợp đồng vẫn đang ở trạng thái chờ hiệu lực.",
                )

            else:
                messages.success(
                    request,
                    "Đã cập nhật trạng thái hợp đồng.",
                )

        # =====================================================
        # THAO TÁC KHÔNG HỢP LỆ
        # =====================================================

        else:
            messages.error(
                request,
                "Vui lòng chọn một thao tác hợp lệ.",
            )

    return redirect(
        "chi_tiet_hop_dong",
        id=id,
    )


def hop_dong_cua_toi(request):

    # -----------------------------------------------------
    # KIỂM TRA ĐĂNG NHẬP
    # -----------------------------------------------------

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    # -----------------------------------------------------
    # ADMIN KHÔNG DÙNG TRANG NÀY
    # -----------------------------------------------------

    if request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard_admin")

    # -----------------------------------------------------
    # LẤY THÔNG TIN NGƯỜI THUÊ
    # -----------------------------------------------------

    try:

        nguoi_thue = NguoiThue.objects.get(
            tai_khoan=request.user
        )

    except NguoiThue.DoesNotExist:

        messages.error(
            request,
            "Tài khoản chưa được liên kết với thông tin người thuê."
        )

        return redirect("tai_khoan")

    # -----------------------------------------------------
    # LẤY HỢP ĐỒNG CỦA NGƯỜI THUÊ
    # -----------------------------------------------------

    danh_sach_hop_dong = (
        HopDong.objects
        .filter(
            dat_phong__nguoi_thue=nguoi_thue
        )
        .annotate(
            thu_tu_nguoi_thue=Case(
                When(trang_thai="sap_het_han", then=Value(0)),
                When(trang_thai="dang_hieu_luc", then=Value(1)),
                When(trang_thai="cho_hieu_luc", then=Value(2)),
                When(trang_thai="da_het_han", then=Value(3)),
                When(trang_thai="da_huy", then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        )
        .select_related(
            "dat_phong",
            "dat_phong__phong",
            "dat_phong__phong__co_so",
        )
        .order_by("thu_tu_nguoi_thue", "ngay_ket_thuc", "-ngay_tao")
    )

    # -----------------------------------------------------
    # CẬP NHẬT TRẠNG THÁI MỚI NHẤT
    # -----------------------------------------------------

    for hop_dong in danh_sach_hop_dong:

        cap_nhat_trang_thai_hop_dong(
            hop_dong
        )

    # -----------------------------------------------------
    # THỐNG KÊ HỢP ĐỒNG
    # -----------------------------------------------------

    so_hop_dong_dang_thue = (
        HopDong.objects
        .filter(
            dat_phong__nguoi_thue=nguoi_thue,
            trang_thai__in=[
                "dang_hieu_luc",
                "sap_het_han",
            ],
        )
        .count()
    )

    so_hop_dong_sap_het_han = (
        HopDong.objects
        .filter(
            dat_phong__nguoi_thue=nguoi_thue,
            trang_thai="sap_het_han",
        )
        .count()
    )

    # -----------------------------------------------------
    # HIỂN THỊ
    # -----------------------------------------------------

    return render(
        request,
        "core/hop_dong_cua_toi.html",
        {
            "hop_dong": danh_sach_hop_dong,
            "hop_dongs": danh_sach_hop_dong,
            "nguoi_thue": nguoi_thue,

            "so_hop_dong_dang_thue": (
                so_hop_dong_dang_thue
            ),

            "so_hop_dong_sap_het_han": (
                so_hop_dong_sap_het_han
            ),
        }
    )


def chi_tiet_hop_dong_cua_toi(request, id):

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard_admin")

    try:
        nguoi_thue = NguoiThue.objects.get(
            tai_khoan=request.user
        )
    except NguoiThue.DoesNotExist:
        messages.error(
            request,
            "Tài khoản chưa được liên kết với thông tin người thuê."
        )
        return redirect("tai_khoan")

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

    cap_nhat_trang_thai_hop_dong(hop_dong)

    cap_nhat_trang_thai_phong_theo_hop_dong(
        hop_dong
    )

    hom_nay = timezone.localdate()

    so_ngay_con_lai = (
        hop_dong.ngay_ket_thuc - hom_nay
    ).days

    yeu_cau_gia_han_dang_cho = (
        YeuCauGiaHanHopDong.objects
        .filter(
            hop_dong=hop_dong,
            nguoi_yeu_cau=nguoi_thue,
            trang_thai="cho_duyet",
        )
        .order_by("-ngay_tao")
        .first()
    )

    lich_su_gia_han = (
        YeuCauGiaHanHopDong.objects
        .filter(
            hop_dong=hop_dong,
            nguoi_yeu_cau=nguoi_thue,
        )
        .order_by("-ngay_tao")
    )

    co_the_gia_han = (
        hop_dong.trang_thai == "sap_het_han"
        and hom_nay <= hop_dong.ngay_ket_thuc
        and yeu_cau_gia_han_dang_cho is None
    )

    context = {
        "hop_dong": hop_dong,
        "nguoi_thue": nguoi_thue,

        "hom_nay": hom_nay,
        "so_ngay_con_lai": so_ngay_con_lai,

        "co_the_gia_han": co_the_gia_han,
        "yeu_cau_gia_han_dang_cho":
            yeu_cau_gia_han_dang_cho,

        "lich_su_gia_han": lich_su_gia_han,
    }

    return render(
        request,
        "core/chi_tiet_hop_dong_cua_toi.html",
        context
    )


@login_required(login_url="dang_nhap")
def xuat_hop_dong_pdf(request, id):
    """
    Xuất hợp đồng thuê phòng ra PDF.

    Quyền:
    - Admin: được xuất mọi hợp đồng.
    - Người thuê: chỉ được xuất hợp đồng của chính mình.
    """

    # =====================================================
    # LẤY HỢP ĐỒNG + DỮ LIỆU LIÊN QUAN
    # =====================================================

    hop_dong = get_object_or_404(
        HopDong.objects.select_related(
            "dat_phong",
            "dat_phong__nguoi_thue",
            "dat_phong__phong",
            "dat_phong__phong__co_so",
        ),
        id=id,
    )

    dat_phong = hop_dong.dat_phong
    nguoi_thue = dat_phong.nguoi_thue
    phong = dat_phong.phong
    co_so = phong.co_so

    # =====================================================
    # KIỂM TRA QUYỀN
    # =====================================================

    if la_admin(request):
        duoc_phep = True
    else:
        duoc_phep = False
        try:
            if (
                nguoi_thue.tai_khoan
                and nguoi_thue.tai_khoan == request.user
            ):
                duoc_phep = True
        except Exception:
            duoc_phep = False

    if not duoc_phep:
        messages.error(
            request,
            "Bạn không có quyền xuất hợp đồng này.",
        )
        if la_admin(request):
            return redirect("quan_ly_hop_dong")
        return redirect("hop_dong_cua_toi")

    # =====================================================
    # HTTP RESPONSE
    # =====================================================

    response = HttpResponse(
        content_type="application/pdf"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="HopDong_{hop_dong.so_hop_dong}.pdf"'
    )

    # =====================================================
    # FONT
    # =====================================================

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"

    arial_path = r"C:\Windows\Fonts\arial.ttf"
    arial_bold_path = r"C:\Windows\Fonts\arialbd.ttf"

    try:
        pdfmetrics.registerFont(
            TTFont("ArialNDT", arial_path)
        )
        pdfmetrics.registerFont(
            TTFont("ArialNDT-Bold", arial_bold_path)
        )
        font_regular = "ArialNDT"
        font_bold = "ArialNDT-Bold"
    except Exception as exc:
        logger.warning("Khong the nap font Arial (%s).", type(exc).__name__)

    # =====================================================
    # MÀU SẮC
    # =====================================================

    mau_xanh = colors.HexColor("#2F7D5B")
    mau_xanh_dam = colors.HexColor("#215B42")
    mau_xanh_nhat = colors.HexColor("#E8F4EE")
    mau_vien = colors.HexColor("#D9E6DE")
    mau_text = colors.HexColor("#1F2933")
    mau_text_nhat = colors.HexColor("#5F6F66")
    mau_nen_nhat = colors.HexColor("#F7FAF8")

    # =====================================================
    # DOCUMENT
    # =====================================================

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=17 * mm,
        bottomMargin=20 * mm,
        title=f"Hợp đồng {hop_dong.so_hop_dong}",
        author="NDT MOTEL",
        subject="Hợp đồng thuê phòng",
    )

    # =====================================================
    # STYLE
    # =====================================================

    styles = getSampleStyleSheet()

    brand_style = ParagraphStyle(
        "NDTBrand",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
        textColor=mau_xanh_dam,
        spaceAfter=1.5 * mm,
    )

    title_style = ParagraphStyle(
        "NDTTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=17,
        leading=22,
        alignment=TA_CENTER,
        textColor=mau_text,
        spaceAfter=2 * mm,
    )

    contract_no_style = ParagraphStyle(
        "NDTContractNo",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=9.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=mau_text_nhat,
        spaceAfter=5 * mm,
    )

    section_style = ParagraphStyle(
        "NDTSection",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=10.5,
        leading=14,
        textColor=mau_xanh_dam,
        spaceBefore=4 * mm,
        spaceAfter=2.5 * mm,
    )

    normal_style = ParagraphStyle(
        "NDTNormal",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=9.3,
        leading=13.5,
        textColor=mau_text,
        spaceAfter=1.5 * mm,
    )

    bold_style = ParagraphStyle(
        "NDTBold",
        parent=normal_style,
        fontName=font_bold,
    )

    small_style = ParagraphStyle(
        "NDTSmall",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=7.8,
        leading=10.5,
        textColor=mau_text_nhat,
    )

    center_style = ParagraphStyle(
        "NDTCenter",
        parent=normal_style,
        alignment=TA_CENTER,
    )

    center_bold_style = ParagraphStyle(
        "NDTCenterBold",
        parent=bold_style,
        alignment=TA_CENTER,
    )

    # =====================================================
    # HÀM HỖ TRỢ
    # =====================================================

    def pdf_text(value):
        if value is None:
            return ""

        text = str(value)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def dinh_dang_tien(value):
        if value is None:
            return "0 VNĐ"

        try:
            amount = Decimal(value)
            return (
                f"{amount:,.0f}".replace(",", ".")
                + " VNĐ"
            )
        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ):
            return f"{value} VNĐ"

    def dinh_dang_ngay(value):
        if not value:
            return "—"

        try:
            return value.strftime("%d/%m/%Y")
        except Exception:
            return str(value)

    def tao_bang_thong_tin(rows, label_width=52 * mm):
        data = []

        for label, value in rows:
            data.append(
                [
                    Paragraph(
                        f"<b>{pdf_text(label)}</b>",
                        normal_style,
                    ),
                    Paragraph(
                        pdf_text(value),
                        normal_style,
                    ),
                ]
            )

        table = Table(
            data,
            colWidths=[
                label_width,
                176 * mm - label_width,
            ],
            hAlign="LEFT",
        )

        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (0, -1),
                        mau_nen_nhat,
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        mau_vien,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        6,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        6,
                    ),
                ]
            )
        )

        return table

    # =====================================================
    # DỮ LIỆU HIỂN THỊ
    # =====================================================

    so_hop_dong = (
        hop_dong.so_hop_dong
        or "Chưa có"
    )

    ho_ten = (
        nguoi_thue.ho_ten
        or "Chưa cập nhật"
    )

    cccd = (
        nguoi_thue.cccd
        or "Chưa cập nhật"
    )

    so_dien_thoai = (
        nguoi_thue.so_dien_thoai
        or "Chưa cập nhật"
    )

    email = (
        getattr(nguoi_thue, "email", "")
        or ""
    )

    if not email:
        try:
            if nguoi_thue.tai_khoan:
                email = (
                    nguoi_thue.tai_khoan.email
                    or "Chưa cập nhật"
                )
        except Exception:
            email = "Chưa cập nhật"

    if not email:
        email = "Chưa cập nhật"

    ten_phong = (
        phong.so_phong
        or "Chưa cập nhật"
    )

    ten_co_so = (
        co_so.ten_co_so
        or "Chưa cập nhật"
    )

    dia_chi_co_so = (
        getattr(co_so, "dia_chi", "")
        or "Chưa cập nhật"
    )

    phuong_thuc = (
        hop_dong.get_phuong_thuc_thanh_toan_display()
    )

    trang_thai = (
        hop_dong.get_trang_thai_display()
    )

    ngay_lap = (
        hop_dong.ngay_tao.date()
        if hop_dong.ngay_tao
        else timezone.localdate()
    )

    ngay_ky = (
        dinh_dang_ngay(
            hop_dong.ngay_ky.date()
        )
        if hop_dong.ngay_ky
        else "Chưa ký"
    )

    nguoi_di_cung_khai_bao = list(
        dat_phong.nguoi_di_cung_khai_bao
        .exclude(trang_thai_xac_minh="da_huy")
        .order_by("ho_ten", "id")
    )

    # =====================================================
    # STORY
    # =====================================================

    story = []

    # =====================================================
    # HEADER
    # =====================================================

    header_box = Table(
        [
            [
                Paragraph(
                    "NDT MOTEL",
                    brand_style,
                )
            ],
            [
                Paragraph(
                    "HỢP ĐỒNG THUÊ PHÒNG",
                    title_style,
                )
            ],
            [
                Paragraph(
                    (
                        "Số hợp đồng: "
                        f"<b>{pdf_text(so_hop_dong)}</b>"
                    ),
                    contract_no_style,
                )
            ],
        ],
        colWidths=[176 * mm],
    )

    header_box.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    mau_xanh_nhat,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.8,
                    mau_vien,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(header_box)
    story.append(Spacer(1, 4 * mm))

    story.append(
        Paragraph(
            (
                "Hợp đồng này ghi nhận thông tin thuê phòng giữa "
                "NDT MOTEL và người thuê theo dữ liệu đã được xác nhận "
                "trên hệ thống tại thời điểm xuất file."
            ),
            normal_style,
        )
    )

    # =====================================================
    # 1. THÔNG TIN HỢP ĐỒNG
    # =====================================================

    story.append(
        Paragraph(
            "1. THÔNG TIN HỢP ĐỒNG",
            section_style,
        )
    )

    story.append(
        tao_bang_thong_tin(
            [
                ("Số hợp đồng", so_hop_dong),
                (
                    "Thời hạn thuê",
                    (
                        f"{dinh_dang_ngay(hop_dong.ngay_bat_dau)} "
                        f"đến {dinh_dang_ngay(hop_dong.ngay_ket_thuc)}"
                    ),
                ),
                ("Trạng thái", trang_thai),
                (
                    "Ngày thanh toán hàng tháng",
                    f"Ngày {hop_dong.ngay_thanh_toan_hang_thang}",
                ),
                ("Phương thức thanh toán", phuong_thuc),
            ]
        )
    )

    # =====================================================
    # 2. THÔNG TIN NGƯỜI THUÊ
    # =====================================================

    story.append(
        Paragraph(
            "2. THÔNG TIN NGƯỜI THUÊ",
            section_style,
        )
    )

    story.append(
        tao_bang_thong_tin(
            [
                ("Họ và tên", ho_ten),
                ("CCCD", cccd),
                ("Số điện thoại", so_dien_thoai),
                ("Email", email),
            ]
        )
    )

    # =====================================================
    # 3. THÔNG TIN PHÒNG
    # =====================================================

    story.append(
        Paragraph(
            "3. THÔNG TIN PHÒNG THUÊ",
            section_style,
        )
    )

    story.append(
        tao_bang_thong_tin(
            [
                ("Cơ sở", ten_co_so),
                ("Địa chỉ", dia_chi_co_so),
                ("Phòng", ten_phong),
                (
                    "Số người ở theo hợp đồng",
                    f"{hop_dong.so_nguoi_o} người",
                ),
            ]
        )
    )

    if nguoi_di_cung_khai_bao:
        story.append(
            Paragraph(
                "DANH SÁCH NGƯỜI ĐI CÙNG ĐÃ KHAI BÁO",
                section_style,
            )
        )
        companion_rows = [[
            Paragraph("<b>Họ tên</b>", normal_style),
            Paragraph("<b>CCCD</b>", normal_style),
            Paragraph("<b>Quan hệ</b>", normal_style),
            Paragraph("<b>Trạng thái</b>", normal_style),
        ]]
        for companion in nguoi_di_cung_khai_bao:
            companion_rows.append([
                Paragraph(pdf_text(companion.ho_ten), normal_style),
                Paragraph(pdf_text(companion.cccd), normal_style),
                Paragraph(pdf_text(companion.quan_he or "—"), normal_style),
                Paragraph(pdf_text(_status_label(companion.trang_thai_xac_minh)), normal_style),
            ])
        companion_table = Table(
            companion_rows,
            colWidths=[58 * mm, 36 * mm, 38 * mm, 44 * mm],
            hAlign="LEFT",
            repeatRows=1,
        )
        companion_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), mau_xanh_nhat),
                    ("GRID", (0, 0), (-1, -1), 0.5, mau_vien),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(companion_table)

    # =====================================================
    # 4. CHI PHÍ VÀ THANH TOÁN
    # =====================================================

    story.append(
        Paragraph(
            "4. CHI PHÍ VÀ THANH TOÁN",
            section_style,
        )
    )

    story.append(
        tao_bang_thong_tin(
            [
                (
                    "Tiền thuê phòng / tháng",
                    dinh_dang_tien(
                        hop_dong.tien_thue_thang
                    ),
                ),
                (
                    "Tiền cọc",
                    dinh_dang_tien(
                        hop_dong.tien_coc
                    ),
                ),
                (
                    "Tiền phạt trễ hạn",
                    dinh_dang_tien(
                        hop_dong.tien_phat_tre_han
                    ),
                ),
                (
                    "Phương thức thanh toán",
                    phuong_thuc,
                ),
                (
                    "Kỳ thanh toán",
                    (
                        "Thanh toán vào ngày "
                        f"{hop_dong.ngay_thanh_toan_hang_thang} "
                        "hàng tháng"
                    ),
                ),
            ],
            label_width=62 * mm,
        )
    )

    story.append(
        Paragraph(
            (
                "<b>Lưu ý:</b> Việc hợp đồng ghi nhận phương thức thanh toán "
                "không đồng nghĩa với hóa đơn đã được thanh toán. Trạng thái "
                "thanh toán được theo dõi riêng theo từng hóa đơn trên hệ thống."
            ),
            small_style,
        )
    )

    # =====================================================
    # 5. ĐIỀU KHOẢN HỢP ĐỒNG
    # =====================================================

    story.append(
        Paragraph(
            "5. ĐIỀU KHOẢN HỢP ĐỒNG",
            section_style,
        )
    )

    dieu_khoan = (
        hop_dong.dieu_khoan
        or "Không có điều khoản bổ sung."
    )

    for line in dieu_khoan.splitlines():
        line = line.strip()
        if line:
            story.append(
                Paragraph(
                    pdf_text(line),
                    normal_style,
                )
            )

    # =====================================================
    # 6. CAM KẾT CỦA CÁC BÊN
    # =====================================================

    story.append(
        Paragraph(
            "6. CAM KẾT CỦA CÁC BÊN",
            section_style,
        )
    )

    cam_ket = [
        (
            "Người thuê xác nhận các thông tin cá nhân và thông tin thuê "
            "phòng trong hợp đồng là chính xác."
        ),
        (
            "Người thuê có trách nhiệm thanh toán tiền thuê, các khoản phí "
            "phát sinh và nghĩa vụ tài chính đúng thời hạn."
        ),
        (
            "Người thuê có trách nhiệm sử dụng phòng đúng mục đích, bảo quản "
            "tài sản và tuân thủ nội quy của cơ sở."
        ),
        (
            "Số người thực tế cư trú không được vượt quá sức chứa của phòng "
            "và phải được cập nhật, quản lý theo quy định của hệ thống."
        ),
        (
            "Gia hạn, chấm dứt hoặc thay đổi hợp đồng chỉ có hiệu lực sau khi "
            "được xử lý và ghi nhận hợp lệ trên hệ thống NDT MOTEL."
        ),
    ]

    for index, noi_dung in enumerate(
        cam_ket,
        start=1,
    ):
        story.append(
            Paragraph(
                f"{index}. {pdf_text(noi_dung)}",
                normal_style,
            )
        )

    # =====================================================
    # 7. GHI CHÚ
    # =====================================================

    if hop_dong.ghi_chu:
        story.append(
            Paragraph(
                "7. GHI CHÚ",
                section_style,
            )
        )

        for line in hop_dong.ghi_chu.splitlines():
            line = line.strip()
            if line:
                story.append(
                    Paragraph(
                        pdf_text(line),
                        normal_style,
                    )
                )

    # =====================================================
    # THÔNG TIN LẬP / KÝ HỢP ĐỒNG
    # =====================================================

    story.append(Spacer(1, 5 * mm))

    meta_table = Table(
        [
            [
                Paragraph(
                    (
                        "<b>Ngày lập:</b> "
                        f"{dinh_dang_ngay(ngay_lap)}"
                    ),
                    small_style,
                ),
                Paragraph(
                    (
                        "<b>Ngày ký:</b> "
                        f"{pdf_text(ngay_ky)}"
                    ),
                    small_style,
                ),
            ]
        ],
        colWidths=[88 * mm, 88 * mm],
    )

    meta_table.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ALIGN",
                    (1, 0),
                    (1, 0),
                    "RIGHT",
                ),
            ]
        )
    )

    story.append(meta_table)
    story.append(Spacer(1, 7 * mm))

    # =====================================================
    # CHỮ KÝ
    # =====================================================

    chu_ky = [
        [
            Paragraph(
                "ĐẠI DIỆN NDT MOTEL",
                center_bold_style,
            ),
            Paragraph(
                "NGƯỜI THUÊ",
                center_bold_style,
            ),
        ],
        [
            Paragraph(
                "Ký và ghi rõ họ tên",
                small_style,
            ),
            Paragraph(
                "Ký và ghi rõ họ tên",
                small_style,
            ),
        ],
        [
            Spacer(1, 18 * mm),
            Spacer(1, 18 * mm),
        ],
        [
            Paragraph(
                "NDT MOTEL",
                center_style,
            ),
            Paragraph(
                pdf_text(ho_ten),
                center_style,
            ),
        ],
    ]

    table_chu_ky = Table(
        chu_ky,
        colWidths=[88 * mm, 88 * mm],
    )

    table_chu_ky.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER",
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
            ]
        )
    )

    story.append(table_chu_ky)

    # =====================================================
    # FOOTER
    # =====================================================

    def them_footer(canvas, document):
        canvas.saveState()

        canvas.setStrokeColor(mau_vien)
        canvas.setLineWidth(0.5)
        canvas.line(
            16 * mm,
            14 * mm,
            A4[0] - 16 * mm,
            14 * mm,
        )

        canvas.setFont(font_regular, 7)
        canvas.setFillColor(mau_text_nhat)

        canvas.drawString(
            16 * mm,
            9.5 * mm,
            f"NDT MOTEL • Hợp đồng {so_hop_dong}",
        )

        canvas.drawRightString(
            A4[0] - 16 * mm,
            9.5 * mm,
            f"Trang {document.page}",
        )

        canvas.restoreState()

    # =====================================================
    # BUILD PDF
    # =====================================================

    try:
        doc.build(
            story,
            onFirstPage=them_footer,
            onLaterPages=them_footer,
        )
    except Exception as exc:
        logger.error("Khong the xuat PDF hop dong (%s).", type(exc).__name__)
        return HttpResponse(
            (
                "Không thể xuất file PDF. "
                "Vui lòng kiểm tra lại dữ liệu hợp đồng."
            ),
            status=500,
            content_type="text/plain; charset=utf-8",
        )

    # =====================================================
    # NHẬT KÝ
    # =====================================================

    ghi_nhat_ky(
        request=request,
        hanh_dong="Xuất PDF",
        module="Hợp đồng",
        doi_tuong="HopDong",
        doi_tuong_id=hop_dong.id,
        tieu_de=(
            f"Xuất hợp đồng {hop_dong.so_hop_dong}"
        ),
        noi_dung=(
            f"Xuất file PDF hợp đồng "
            f"{hop_dong.so_hop_dong} thành công."
        ),
        du_lieu_cu={},
        du_lieu_moi={
            "id": hop_dong.id,
            "so_hop_dong": hop_dong.so_hop_dong,
        },
    )

    return response
