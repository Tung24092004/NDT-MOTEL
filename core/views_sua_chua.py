"""Nghiep vu sua chua."""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Exists, OuterRef
from django.core.exceptions import ValidationError
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
from core.dich_vu.phan_quyen import la_admin
from core.dich_vu.sua_chua import create_repair_request, transition_repair_request
from core.views_tai_khoan import _lay_nguoi_thue_dang_dang_nhap


def _lay_trang_thai_sua_chua_hop_le():
    return [
        "moi",
        "dang_xu_ly",
        "cho_thay_the",
        "hoan_thanh",
        "tu_choi",
    ]


def _lay_loai_su_co_hop_le():
    return [
        "dien",
        "nuoc",
        "thiet_bi",
        "phong",
        "wifi",
        "ve_sinh",
        "khac",
    ]


def _lay_muc_do_hop_le():
    return [
        "thap",
        "trung_binh",
        "cao",
        "khan_cap",
    ]


def _lay_phong_dang_thue_cua_nguoi_thue(nguoi_thue):
    return (
        Phong.objects
        .filter(
            dat_phong__nguoi_thue=nguoi_thue,
            dat_phong__trang_thai="da_duyet",
            dat_phong__hop_dong__trang_thai__in=[
                "dang_hieu_luc",
                "sap_het_han",
            ],
        )
        .distinct()
        .order_by("so_phong")
    )


def quan_ly_sua_chua(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    yeu_cau = (
        YeuCauSuaChua.objects
        .select_related(
            "nguoi_thue",
            "phong",
            "phong__co_so",
        )
        .order_by("-ngay_tao")
    )

    tu_khoa = request.GET.get("q", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()

    if tu_khoa:
        yeu_cau = yeu_cau.filter(
            Q(tieu_de__icontains=tu_khoa)
            | Q(noi_dung__icontains=tu_khoa)
            | Q(nguoi_thue__ho_ten__icontains=tu_khoa)
            | Q(phong__so_phong__icontains=tu_khoa)
        )

    trang_thai_hop_le = _lay_trang_thai_sua_chua_hop_le()

    if trang_thai in trang_thai_hop_le:
        yeu_cau = yeu_cau.filter(trang_thai=trang_thai)
    else:
        trang_thai = ""

    tong_yeu_cau = yeu_cau.count()

    so_moi = yeu_cau.filter(
        trang_thai="moi"
    ).count()

    so_dang_xu_ly = yeu_cau.filter(
        trang_thai__in=["dang_xu_ly", "cho_thay_the"]
    ).count()

    so_hoan_thanh = yeu_cau.filter(
        trang_thai="hoan_thanh"
    ).count()

    for item in yeu_cau:
        item.chi_phi_hien_thi = item.chi_phi or 0

    return render(
        request,
        "core/quan_ly_sua_chua.html",
        {
            "yeu_cau": yeu_cau,
            "tu_khoa": tu_khoa,
            "trang_thai": trang_thai,
            "tong_yeu_cau": tong_yeu_cau,
            "so_moi": so_moi,
            "so_dang_xu_ly": so_dang_xu_ly,
            "so_hoan_thanh": so_hoan_thanh,
        }
    )


def chi_tiet_sua_chua(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    yeu_cau = get_object_or_404(
        YeuCauSuaChua.objects.select_related(
            "nguoi_thue",
            "phong",
            "phong__co_so",
        ),
        id=id
    )

    return render(
        request,
        "core/chi_tiet_sua_chua.html",
        {
            "yeu_cau": yeu_cau,
        }
    )


def xu_ly_sua_chua(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    yeu_cau = get_object_or_404(
        YeuCauSuaChua,
        id=id
    )

    if request.method != "POST":
        return redirect(
            "chi_tiet_sua_chua",
            id=yeu_cau.id
        )

    trang_thai = request.POST.get(
        "trang_thai",
        ""
    ).strip()

    nguoi_xu_ly = request.POST.get(
        "nguoi_xu_ly",
        ""
    ).strip()

    chi_tiet_chi_phi = request.POST.get(
        "chi_tiet_chi_phi",
        ""
    ).strip()

    ghi_chu_admin = request.POST.get(
        "ghi_chu_admin",
        ""
    ).strip()

    trang_thai_hop_le = _lay_trang_thai_sua_chua_hop_le()

    if trang_thai not in trang_thai_hop_le:
        messages.error(
            request,
            "Trạng thái sửa chữa không hợp lệ."
        )
        return redirect(
            "chi_tiet_sua_chua",
            id=yeu_cau.id
        )

    if trang_thai == "dang_xu_ly" and not nguoi_xu_ly:
        messages.error(
            request,
            "Khi chuyển sang Đang xử lý, vui lòng nhập người xử lý."
        )
        return redirect(
            "chi_tiet_sua_chua",
            id=yeu_cau.id
        )

    raw_chi_phi = request.POST.get(
        "chi_phi",
        "0"
    ).strip()

    try:
        chi_phi = Decimal(
            raw_chi_phi or "0"
        )
    except (InvalidOperation, ValueError):
        messages.error(
            request,
            "Chi phí không hợp lệ."
        )
        return redirect(
            "chi_tiet_sua_chua",
            id=yeu_cau.id
        )

    if chi_phi < 0:
        messages.error(
            request,
            "Chi phí không được âm."
        )
        return redirect(
            "chi_tiet_sua_chua",
            id=yeu_cau.id
        )

    # =========================================================
    # LƯU DỮ LIỆU CŨ ĐỂ GHI NHẬT KÝ
    # =========================================================

    du_lieu_cu = {
        "trang_thai": yeu_cau.trang_thai,
        "nguoi_xu_ly": yeu_cau.nguoi_xu_ly or "",
        "chi_phi": str(yeu_cau.chi_phi or 0),
        "chi_tiet_chi_phi": yeu_cau.chi_tiet_chi_phi or "",
        "ghi_chu_admin": yeu_cau.ghi_chu_admin or "",
        "ngay_bat_dau_xu_ly": (
            yeu_cau.ngay_bat_dau_xu_ly.isoformat()
            if yeu_cau.ngay_bat_dau_xu_ly
            else None
        ),
        "ngay_hoan_thanh": (
            yeu_cau.ngay_hoan_thanh.isoformat()
            if yeu_cau.ngay_hoan_thanh
            else None
        ),
    }

    # =========================================================
    # CẬP NHẬT YÊU CẦU SỬA CHỮA
    # =========================================================

    try:
        yeu_cau = transition_repair_request(
            actor=request.user, repair_id=yeu_cau.pk, target_status=trang_thai,
            handler=nguoi_xu_ly, cost=chi_phi, cost_detail=chi_tiet_chi_phi,
            admin_note=ghi_chu_admin,
        )
    except ValidationError as error:
        messages.error(request, str(error))
        return redirect("chi_tiet_sua_chua", id=yeu_cau.id)

    # =========================================================
    # DỮ LIỆU MỚI SAU KHI CẬP NHẬT
    # =========================================================

    du_lieu_moi = {
        "trang_thai": yeu_cau.trang_thai,
        "nguoi_xu_ly": yeu_cau.nguoi_xu_ly or "",
        "chi_phi": str(yeu_cau.chi_phi or 0),
        "chi_tiet_chi_phi": yeu_cau.chi_tiet_chi_phi or "",
        "ghi_chu_admin": yeu_cau.ghi_chu_admin or "",
        "ngay_bat_dau_xu_ly": (
            yeu_cau.ngay_bat_dau_xu_ly.isoformat()
            if yeu_cau.ngay_bat_dau_xu_ly
            else None
        ),
        "ngay_hoan_thanh": (
            yeu_cau.ngay_hoan_thanh.isoformat()
            if yeu_cau.ngay_hoan_thanh
            else None
        ),
    }

    # =========================================================
    # GHI NHẬT KÝ THAO TÁC
    # =========================================================

    ghi_nhat_ky(
        request=request,
        hanh_dong="Cập nhật",
        module="Sửa chữa",
        doi_tuong="YeuCauSuaChua",
        doi_tuong_id=yeu_cau.id,
        tieu_de=f"Cập nhật yêu cầu sửa chữa #{yeu_cau.id}",
        noi_dung=(
            f"Admin {request.user.username} cập nhật yêu cầu "
            f"sửa chữa #{yeu_cau.id} - {yeu_cau.tieu_de}. "
            f"Trạng thái: {du_lieu_cu['trang_thai']} → "
            f"{du_lieu_moi['trang_thai']}."
        ),
        du_lieu_cu=du_lieu_cu,
        du_lieu_moi=du_lieu_moi,
    )

    messages.success(
        request,
        "Đã cập nhật yêu cầu sửa chữa."
    )

    return redirect(
        "chi_tiet_sua_chua",
        id=yeu_cau.id
    )


def tao_sua_chua(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    repair_errors = {}
    submitted = {}

    if request.method == "POST":
        submitted = {
            "nguoi_thue": request.POST.get("nguoi_thue", "").strip(),
            "phong": request.POST.get("phong", "").strip(),
            "tieu_de": request.POST.get("tieu_de", "").strip(),
            "noi_dung": request.POST.get("noi_dung", "").strip(),
            "loai_su_co": request.POST.get("loai_su_co", "").strip(),
            "muc_do": request.POST.get("muc_do", "").strip(),
            "chi_phi": request.POST.get("chi_phi", "").strip(),
            "chi_tiet_chi_phi": request.POST.get("chi_tiet_chi_phi", "").strip(),
            "ghi_chu_admin": request.POST.get("ghi_chu_admin", "").strip(),
        }
        try:
            nguoi_thue_id = request.POST.get(
                "nguoi_thue",
                ""
            ).strip()

            phong_id = request.POST.get(
                "phong",
                ""
            ).strip()

            nguoi_thue = get_object_or_404(
                NguoiThue,
                id=nguoi_thue_id,
                dang_hoat_dong=True,
            )

            phong = get_object_or_404(
                Phong,
                id=phong_id
            )

            # Kiểm tra phòng phải thực sự thuộc người thuê
            # thông qua hợp đồng đang có hiệu lực.
            phong_hop_le = _lay_phong_dang_thue_cua_nguoi_thue(
                nguoi_thue
            ).filter(
                id=phong.id
            ).exists()

            if not phong_hop_le:
                messages.error(
                    request,
                    "Phòng được chọn không thuộc hợp đồng đang hiệu lực của người thuê."
                )
                return redirect("tao_sua_chua")

            tieu_de = request.POST.get(
                "tieu_de",
                ""
            ).strip()

            noi_dung = request.POST.get(
                "noi_dung",
                ""
            ).strip()

            loai_su_co = request.POST.get(
                "loai_su_co",
                ""
            ).strip()

            muc_do = request.POST.get(
                "muc_do",
                ""
            ).strip()

            if not tieu_de or not noi_dung:
                if not tieu_de:
                    repair_errors["tieu_de"] = "Nhập tiêu đề sự cố."
                if not noi_dung:
                    repair_errors["noi_dung"] = "Nhập mô tả chi tiết."
                messages.error(
                    request,
                    "Vui lòng nhập đầy đủ tiêu đề và nội dung."
                )

            elif loai_su_co not in _lay_loai_su_co_hop_le():
                repair_errors["loai_su_co"] = "Chọn loại sự cố hợp lệ."
                messages.error(
                    request,
                    "Loại sự cố không hợp lệ."
                )

            elif muc_do not in _lay_muc_do_hop_le():
                repair_errors["muc_do"] = "Chọn mức độ hợp lệ."
                messages.error(
                    request,
                    "Mức độ sự cố không hợp lệ."
                )

            else:
                raw_chi_phi = request.POST.get(
                    "chi_phi",
                    "0"
                ).strip()

                try:
                    chi_phi = Decimal(
                        raw_chi_phi or "0"
                    )
                except (InvalidOperation, ValueError):
                    messages.error(
                        request,
                        "Chi phí không hợp lệ."
                    )
                    chi_phi = None

                if chi_phi is not None:

                    if chi_phi < 0:
                        messages.error(
                            request,
                            "Chi phí không được âm."
                        )

                    else:
                        chi_tiet_chi_phi = request.POST.get(
                            "chi_tiet_chi_phi",
                            ""
                        ).strip()

                        ghi_chu_admin = request.POST.get(
                            "ghi_chu_admin",
                            ""
                        ).strip()

                        try:
                            yeu_cau_moi = create_repair_request(
                                actor=request.user, tenant_id=nguoi_thue.pk, room_id=phong.pk,
                                title=tieu_de, content=noi_dung, issue_type=loai_su_co,
                                priority=muc_do, image=request.FILES.get("hinh_anh"),
                                cost=chi_phi, cost_detail=chi_tiet_chi_phi,
                                admin_note=ghi_chu_admin,
                            )
                        except ValidationError as error:
                            messages.error(request, str(error))
                            return redirect("tao_sua_chua")

                        ghi_nhat_ky(
                            request=request,
                            hanh_dong="Tạo",
                            module="Sửa chữa",
                            doi_tuong="YeuCauSuaChua",
                            doi_tuong_id=yeu_cau_moi.id,
                            tieu_de=(
                                f"Tạo yêu cầu sửa chữa "
                                f"#{yeu_cau_moi.id}"
                            ),
                            noi_dung=(
                                f"Admin {request.user.username} "
                                f"tạo yêu cầu sửa chữa cho người thuê "
                                f"{nguoi_thue.ho_ten}, phòng "
                                f"{phong.so_phong}: {tieu_de}."
                            ),
                            du_lieu_cu={},
                            du_lieu_moi={
                                "nguoi_thue": nguoi_thue.ho_ten,
                                "phong": phong.so_phong,
                                "tieu_de": tieu_de,
                                "loai_su_co": loai_su_co,
                                "muc_do": muc_do,
                                "chi_phi": str(chi_phi),
                                "trang_thai": "moi",
                            },
                        )

                        messages.success(
                            request,
                            "Tạo yêu cầu sửa chữa thành công."
                        )

                        return redirect(
                            "quan_ly_sua_chua"
                        )

        except (ValueError, InvalidOperation):
            messages.error(
                request,
                "Dữ liệu yêu cầu sửa chữa không hợp lệ."
            )

    nguoi_thues = (
        NguoiThue.objects
        .filter(dang_hoat_dong=True)
        .order_by("ho_ten")
    )

    phongs = (
        Phong.objects
        .all()
        .select_related("co_so")
        .order_by("so_phong")
    )

    return render(
        request,
        "core/tao_sua_chua.html",
        {
            "nguoi_thues": nguoi_thues,
            "phongs": phongs,
            "loai_su_co": YeuCauSuaChua.LOAI_SU_CO,
            "muc_do": YeuCauSuaChua.MUC_DO,
            "repair_errors": repair_errors,
            "submitted": submitted,
        }
    )


def yeu_cau_sua_chua_cua_toi(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if la_admin(request):
        return redirect("quan_ly_sua_chua")

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    if not nguoi_thue:
        messages.error(
            request,
            "Không tìm thấy thông tin người thuê của tài khoản."
        )
        return redirect("tai_khoan")

    yeu_cau = (
        YeuCauSuaChua.objects
        .filter(nguoi_thue=nguoi_thue)
        .select_related(
            "phong",
            "phong__co_so",
        )
        .order_by("-ngay_tao")
    )

    trang_thai = request.GET.get(
        "trang_thai",
        ""
    ).strip()

    if trang_thai in _lay_trang_thai_sua_chua_hop_le():
        yeu_cau = yeu_cau.filter(
            trang_thai=trang_thai
        )
    else:
        trang_thai = ""

    return render(
        request,
        "core/yeu_cau_sua_chua_cua_toi.html",
        {
            "yeu_cau": yeu_cau,
            "trang_thai": trang_thai,
        }
    )


def tao_yeu_cau_sua_chua(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if la_admin(request):
        return redirect("tao_sua_chua")

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    if not nguoi_thue:
        messages.error(
            request,
            "Không tìm thấy thông tin người thuê của tài khoản."
        )
        return redirect("tai_khoan")

    phongs = _lay_phong_dang_thue_cua_nguoi_thue(
        nguoi_thue
    )

    repair_errors = {}
    submitted = {}

    if request.method == "POST":
        submitted = {
            "phong": request.POST.get("phong", "").strip(),
            "tieu_de": request.POST.get("tieu_de", "").strip(),
            "noi_dung": request.POST.get("noi_dung", "").strip(),
            "loai_su_co": request.POST.get("loai_su_co", "").strip(),
            "muc_do": request.POST.get("muc_do", "").strip(),
        }
        phong_id = request.POST.get(
            "phong",
            ""
        ).strip()

        phong = phongs.filter(
            id=phong_id
        ).first()

        if not phong:
            repair_errors["phong"] = "Chọn phòng đang thuê hợp lệ."
            messages.error(
                request,
                "Phòng không hợp lệ hoặc bạn không có quyền gửi yêu cầu cho phòng này."
            )
        else:
            tieu_de = request.POST.get(
                "tieu_de",
                ""
            ).strip()

            noi_dung = request.POST.get(
                "noi_dung",
                ""
            ).strip()

            loai_su_co = request.POST.get(
                "loai_su_co",
                ""
            ).strip()

            muc_do = request.POST.get(
                "muc_do",
                ""
            ).strip()

            if not tieu_de or not noi_dung:
                messages.error(
                    request,
                    "Vui lòng nhập tiêu đề và nội dung."
                )

            elif loai_su_co not in _lay_loai_su_co_hop_le():
                messages.error(
                    request,
                    "Loại sự cố không hợp lệ."
                )

            elif muc_do not in _lay_muc_do_hop_le():
                messages.error(
                    request,
                    "Mức độ sự cố không hợp lệ."
                )

            else:
                try:
                    create_repair_request(
                        actor=request.user, tenant_id=nguoi_thue.pk, room_id=phong.pk,
                        title=tieu_de, content=noi_dung, issue_type=loai_su_co,
                        priority=muc_do, image=request.FILES.get("hinh_anh"),
                    )
                except ValidationError as error:
                    repair_errors["phong"] = str(error)
                    messages.error(request, str(error))
                    return render(
                        request, "core/tao_yeu_cau_sua_chua.html",
                        {"phongs": phongs, "loai_su_co": YeuCauSuaChua.LOAI_SU_CO,
                         "muc_do": YeuCauSuaChua.MUC_DO, "repair_errors": repair_errors,
                         "submitted": submitted},
                    )

                messages.success(
                    request,
                    "Đã gửi yêu cầu sửa chữa. Vui lòng chờ quản lý xử lý."
                )

                return redirect(
                    "yeu_cau_sua_chua_cua_toi"
                )

    return render(
        request,
        "core/tao_yeu_cau_sua_chua.html",
        {
            "phongs": phongs,
            "loai_su_co": YeuCauSuaChua.LOAI_SU_CO,
            "muc_do": YeuCauSuaChua.MUC_DO,
        }
    )


def chi_tiet_yeu_cau_sua_chua_cua_toi(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if la_admin(request):
        return redirect(
            "chi_tiet_sua_chua",
            id=id
        )

    nguoi_thue = _lay_nguoi_thue_dang_dang_nhap(request)

    if not nguoi_thue:
        messages.error(
            request,
            "Không tìm thấy thông tin người thuê của tài khoản."
        )
        return redirect("tai_khoan")

    yeu_cau = get_object_or_404(
        YeuCauSuaChua.objects.select_related(
            "phong",
            "phong__co_so",
        ),
        id=id,
        nguoi_thue=nguoi_thue,
    )

    return render(
        request,
        "core/chi_tiet_yeu_cau_sua_chua_cua_toi.html",
        {
            "yeu_cau": yeu_cau,
        }
    )
