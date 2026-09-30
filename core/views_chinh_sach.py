"""Read-only tenant presentation; existing workflows remain unchanged."""
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_safe
from .models import ChinhSachHoTro


@require_safe
def chinh_sach_ho_tro(request):
    today = timezone.localdate()
    policies = ChinhSachHoTro.objects.filter(
        trang_thai=True, ngay_bat_dau__lte=today, ngay_ket_thuc__gte=today,
    ).order_by('-ngay_bat_dau', 'pk')
    return render(request, 'core/chinh_sach_ho_tro.html', {'policies': policies})
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Exists, OuterRef
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


def quan_ly_chinh_sach(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    chinh_sach = (
        ChinhSachHoTro.objects
        .all()
        .order_by("-ngay_tao")
    )

    tu_khoa = request.GET.get(
        "q",
        ""
    ).strip()

    if tu_khoa:
        chinh_sach = chinh_sach.filter(
            Q(ten_chinh_sach__icontains=tu_khoa)
            | Q(doi_tuong_khac__icontains=tu_khoa)
            | Q(mo_ta__icontains=tu_khoa)
        )

    return render(
        request,
        "core/quan_ly_chinh_sach.html",
        {
            "chinh_sach": chinh_sach,
            "tu_khoa": tu_khoa,
        }
    )


def chi_tiet_chinh_sach(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    chinh_sach = get_object_or_404(
        ChinhSachHoTro,
        id=id
    )

    return render(
        request,
        "core/chi_tiet_chinh_sach.html",
        {
            "chinh_sach": chinh_sach
        }
    )


def tao_chinh_sach(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method == "POST":
        ten_chinh_sach = request.POST.get("ten_chinh_sach", "").strip()
        doi_tuong = request.POST.get("doi_tuong", "sinh_vien").strip()
        doi_tuong_khac = request.POST.get("doi_tuong_khac", "").strip()
        loai_ho_tro = request.POST.get("loai_ho_tro", "phan_tram").strip()
        gia_tri_raw = request.POST.get("gia_tri_ho_tro", "").strip()
        ngan_sach_raw = request.POST.get("ngan_sach", "").strip()
        so_luong_raw = request.POST.get("so_luong_nguoi_duoc_ap_dung", "").strip()
        ngay_bat_dau_raw = request.POST.get("ngay_bat_dau", "").strip()
        ngay_ket_thuc_raw = request.POST.get("ngay_ket_thuc", "").strip()

        doi_tuong_hop_le = {
            value
            for value, _ in ChinhSachHoTro._meta.get_field("doi_tuong").choices
        }
        loai_ho_tro_hop_le = {
            value
            for value, _ in ChinhSachHoTro._meta.get_field("loai_ho_tro").choices
        }

        try:
            if not ten_chinh_sach:
                raise ValueError("Vui lòng nhập tên chính sách.")

            if doi_tuong not in doi_tuong_hop_le:
                raise ValueError("Đối tượng áp dụng không hợp lệ.")

            if loai_ho_tro not in loai_ho_tro_hop_le:
                raise ValueError("Loại hỗ trợ không hợp lệ.")

            gia_tri_ho_tro = Decimal(gia_tri_raw or "0")
            ngan_sach = Decimal(ngan_sach_raw or "0")
            so_luong = int(so_luong_raw or "0")

            if gia_tri_ho_tro < 0:
                raise ValueError("Giá trị hỗ trợ không hợp lệ.")

            if ngan_sach < 0:
                raise ValueError("Ngân sách không hợp lệ.")

            if so_luong < 0:
                raise ValueError("Số lượng người được áp dụng không hợp lệ.")

            ngay_bat_dau = parse_date(ngay_bat_dau_raw)
            ngay_ket_thuc = parse_date(ngay_ket_thuc_raw)

            if not ngay_bat_dau:
                raise ValueError("Ngày bắt đầu không hợp lệ.")

            if not ngay_ket_thuc:
                raise ValueError("Ngày kết thúc không hợp lệ.")

            if ngay_ket_thuc < ngay_bat_dau:
                raise ValueError("Ngày kết thúc không được trước ngày bắt đầu.")

            ChinhSachHoTro.objects.create(
                ten_chinh_sach=ten_chinh_sach,
                doi_tuong=doi_tuong,
                doi_tuong_khac=doi_tuong_khac,
                loai_ho_tro=loai_ho_tro,
                gia_tri_ho_tro=gia_tri_ho_tro,
                ngan_sach=ngan_sach,
                so_luong_nguoi_duoc_ap_dung=so_luong,
                ngay_bat_dau=ngay_bat_dau,
                ngay_ket_thuc=ngay_ket_thuc,
                dieu_kien=request.POST.get("dieu_kien", "").strip(),
                trang_thai=request.POST.get("trang_thai") == "on",
                mo_ta=request.POST.get("mo_ta", "").strip(),
            )

            messages.success(
                request,
                "Tạo chính sách hỗ trợ thành công."
            )
            return redirect("quan_ly_chinh_sach")

        except (ValueError, InvalidOperation) as exc:
            messages.error(
                request,
                str(exc) or "Dữ liệu nhập vào không hợp lệ."
            )

    return render(
        request,
        "core/tao_chinh_sach.html"
    )


def xu_ly_chinh_sach(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        messages.error(
            request,
            "Bạn không có quyền thực hiện thao tác này."
        )
        return redirect("tai_khoan")

    chinh_sach = get_object_or_404(
        ChinhSachHoTro,
        id=id
    )

    if request.method == "POST":

        hanh_dong = request.POST.get(
            "hanh_dong",
            ""
        ).strip()

        # =================================================
        # BẬT CHÍNH SÁCH
        # =================================================

        if hanh_dong == "bat":

            chinh_sach.trang_thai = True

            chinh_sach.save(
                update_fields=["trang_thai"]
            )

            messages.success(
                request,
                f'Đã kích hoạt chính sách "{chinh_sach.ten_chinh_sach}".'
            )

        # =================================================
        # TẮT CHÍNH SÁCH
        # =================================================

        elif hanh_dong == "tat":

            chinh_sach.trang_thai = False

            chinh_sach.save(
                update_fields=["trang_thai"]
            )

            messages.success(
                request,
                f'Đã tắt chính sách "{chinh_sach.ten_chinh_sach}".'
            )

        # =================================================
        # XÓA CHÍNH SÁCH
        # =================================================

        elif hanh_dong == "xoa":

            ten = chinh_sach.ten_chinh_sach

            chinh_sach.delete()

            messages.success(
                request,
                f'Đã xóa chính sách "{ten}".'
            )

            return redirect(
                "quan_ly_chinh_sach"
            )

        # =================================================
        # CẬP NHẬT THÔNG TIN CHÍNH SÁCH
        # =================================================

        elif hanh_dong == "cap_nhat":

            ten_chinh_sach = request.POST.get(
                "ten_chinh_sach",
                ""
            ).strip()

            doi_tuong = request.POST.get(
                "doi_tuong",
                ""
            ).strip()

            doi_tuong_khac = request.POST.get(
                "doi_tuong_khac",
                ""
            ).strip()

            loai_ho_tro = request.POST.get(
                "loai_ho_tro",
                ""
            ).strip()

            gia_tri = request.POST.get(
                "gia_tri_ho_tro",
                ""
            ).strip()

            ngan_sach = request.POST.get(
                "ngan_sach",
                ""
            ).strip()

            so_luong = request.POST.get(
                "so_luong_nguoi_duoc_ap_dung",
                ""
            ).strip()

            ngay_bat_dau = request.POST.get(
                "ngay_bat_dau",
                ""
            ).strip()

            ngay_ket_thuc = request.POST.get(
                "ngay_ket_thuc",
                ""
            ).strip()

            dieu_kien = request.POST.get(
                "dieu_kien",
                ""
            ).strip()

            mo_ta = request.POST.get(
                "mo_ta",
                ""
            ).strip()

            # ---------------------------------------------
            # Kiểm tra tên
            # ---------------------------------------------

            if not ten_chinh_sach:

                messages.error(
                    request,
                    "Vui lòng nhập tên chính sách."
                )

                return redirect(
                    "chi_tiet_chinh_sach",
                    id=chinh_sach.id
                )

            # ---------------------------------------------
            # Kiểm tra đối tượng
            # ---------------------------------------------

            doi_tuong_hop_le = [
                "sinh_vien",
                "nguoi_lao_dong",
                "ho_gia_dinh",
                "nguoi_cao_tuoi",
                "khach_thue_moi",
                "khach_thue_lau_dai",
                "khac",
            ]

            if doi_tuong not in doi_tuong_hop_le:

                messages.error(
                    request,
                    "Đối tượng áp dụng không hợp lệ."
                )

                return redirect(
                    "chi_tiet_chinh_sach",
                    id=chinh_sach.id
                )

            # ---------------------------------------------
            # Kiểm tra loại hỗ trợ
            # ---------------------------------------------

            loai_ho_tro_hop_le = [
                "phan_tram",
                "so_tien",
                "mien_phi",
            ]

            if loai_ho_tro not in loai_ho_tro_hop_le:

                messages.error(
                    request,
                    "Loại hỗ trợ không hợp lệ."
                )

                return redirect(
                    "chi_tiet_chinh_sach",
                    id=chinh_sach.id
                )

            # ---------------------------------------------
            # Giá trị hỗ trợ
            # ---------------------------------------------

            try:

                gia_tri_ho_tro = Decimal(
                    gia_tri or "0"
                )

                if gia_tri_ho_tro < 0:

                    raise InvalidOperation

            except (InvalidOperation, ValueError):

                messages.error(
                    request,
                    "Giá trị hỗ trợ không hợp lệ."
                )

                return redirect(
                    "chi_tiet_chinh_sach",
                    id=chinh_sach.id
                )

            # ---------------------------------------------
            # Ngân sách
            # ---------------------------------------------

            try:

                ngan_sach_value = Decimal(
                    ngan_sach or "0"
                )

                if ngan_sach_value < 0:

                    raise InvalidOperation

            except (InvalidOperation, ValueError):

                messages.error(
                    request,
                    "Ngân sách không hợp lệ."
                )

                return redirect(
                    "chi_tiet_chinh_sach",
                    id=chinh_sach.id
                )

            # ---------------------------------------------
            # Số lượng người được áp dụng
            # ---------------------------------------------

            try:

                so_luong_value = int(
                    so_luong or "0"
                )

                if so_luong_value < 0:

                    raise ValueError

            except ValueError:

                messages.error(
                    request,
                    "Số lượng người được áp dụng không hợp lệ."
                )

                return redirect(
                    "chi_tiet_chinh_sach",
                    id=chinh_sach.id
                )

            # ---------------------------------------------
            # Ngày bắt đầu
            # ---------------------------------------------

            ngay_bat_dau_value = None

            if ngay_bat_dau:

                ngay_bat_dau_value = parse_date(
                    ngay_bat_dau
                )

                if not ngay_bat_dau_value:

                    messages.error(
                        request,
                        "Ngày bắt đầu không hợp lệ."
                    )

                    return redirect(
                        "chi_tiet_chinh_sach",
                        id=chinh_sach.id
                    )

            # ---------------------------------------------
            # Ngày kết thúc
            # ---------------------------------------------

            ngay_ket_thuc_value = None

            if ngay_ket_thuc:

                ngay_ket_thuc_value = parse_date(
                    ngay_ket_thuc
                )

                if not ngay_ket_thuc_value:

                    messages.error(
                        request,
                        "Ngày kết thúc không hợp lệ."
                    )

                    return redirect(
                        "chi_tiet_chinh_sach",
                        id=chinh_sach.id
                    )

            # ---------------------------------------------
            # Kiểm tra khoảng thời gian
            # ---------------------------------------------

            if (
                ngay_bat_dau_value
                and ngay_ket_thuc_value
                and ngay_ket_thuc_value < ngay_bat_dau_value
            ):

                messages.error(
                    request,
                    "Ngày kết thúc không được trước ngày bắt đầu."
                )

                return redirect(
                    "chi_tiet_chinh_sach",
                    id=chinh_sach.id
                )

            # ---------------------------------------------
            # Cập nhật dữ liệu
            # ---------------------------------------------

            chinh_sach.ten_chinh_sach = ten_chinh_sach
            chinh_sach.doi_tuong = doi_tuong
            chinh_sach.doi_tuong_khac = doi_tuong_khac
            chinh_sach.loai_ho_tro = loai_ho_tro
            chinh_sach.gia_tri_ho_tro = gia_tri_ho_tro
            chinh_sach.ngan_sach = ngan_sach_value
            chinh_sach.so_luong_nguoi_duoc_ap_dung = so_luong_value
            chinh_sach.ngay_bat_dau = ngay_bat_dau_value
            chinh_sach.ngay_ket_thuc = ngay_ket_thuc_value
            chinh_sach.dieu_kien = dieu_kien
            chinh_sach.mo_ta = mo_ta

            # Checkbox trạng thái
            chinh_sach.trang_thai = (
                request.POST.get("trang_thai") == "on"
            )

            chinh_sach.save()

            messages.success(
                request,
                "Cập nhật chính sách hỗ trợ thành công."
            )

        # =================================================
        # THAO TÁC KHÔNG HỢP LỆ
        # =================================================

        else:

            messages.error(
                request,
                "Vui lòng chọn một thao tác hợp lệ."
            )

        return redirect(
            "chi_tiet_chinh_sach",
            id=chinh_sach.id
        )

    return redirect(
        "chi_tiet_chinh_sach",
        id=chinh_sach.id
    )
