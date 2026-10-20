"""Nghiep vu smart room."""
from datetime import datetime, time, timedelta

import cv2
import numpy as np
from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Exists, OuterRef
from django.db import transaction
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET
from django.core.exceptions import ValidationError
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
import base64
import json
import os
import mimetypes
import re
from uuid import uuid4
from django.conf import settings
FACE_YUNET_MODEL = os.path.join(
    settings.BASE_DIR,
    "models",
    "face_detection_yunet_2023mar.onnx"
)
FACE_SFACE_MODEL = os.path.join(
    settings.BASE_DIR,
    "models",
    "face_recognition_sface_2021dec.onnx"
)
from core.dich_vu.phan_quyen import la_admin
from core.dich_vu.luu_tru import (
    danh_gia_xac_minh_nguoi_o_cung,
    danh_gia_quyen_ra_vao,
    danh_gia_hop_dong,
    du_dieu_kien_dang_ky_face_id,
    ly_do_nguoi_o_cung_chua_du_dieu_kien,
    nguoi_o_cung_du_dieu_kien,
    nguoi_thue_duoc_xac_thuc_cua,
    quyen_ra_vao_con_hieu_luc,
    thu_hoi_quyen_nguoi_o_cung,
    trang_thai_xac_minh_nguoi_o_cung,
)
from core.dich_vu.phu_luc_hop_dong import ghi_nhan_thay_doi_cu_tru
from core.dich_vu.yeu_cau_nguoi_o_cung import (
    direct_admit, leave_residency, return_as_new_residency,
)
from core.dich_vu.quyen_ra_vao import grant_access, revoke_access
from core.dich_vu.dong_y_sinh_trac_hoc import has_effective_consent


def smart_room_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    hom_nay = timezone.localdate()

    # =====================================================
    # THỐNG KÊ SMART ROOM
    # =====================================================

    tong_nguoi_o_cung = (
        NguoiOCungPhong.objects
        .filter(
            trang_thai="dang_o"
        )
        .count()
    )

    tong_face_profile = (
        FaceProfile.objects
        .count()
    )

    face_co_anh = (
        FaceProfile.objects
        .filter(
            trang_thai__in=[
                "co_anh",
                "da_xac_thuc",
            ]
        )
        .count()
    )

    face_da_xac_thuc = (
        FaceProfile.objects
        .filter(
            trang_thai="da_xac_thuc"
        )
        .count()
    )

    face_chua_san_sang = (
        FaceProfile.objects
        .exclude(
            trang_thai="da_xac_thuc"
        )
        .count()
    )

    # =====================================================
    # QUYỀN RA VÀO THỰC SỰ CÒN HIỆU LỰC HÔM NAY
    # =====================================================

    quyen_hoat_dong = (
        QuyenRaVao.objects
        .filter(
            trang_thai="hoat_dong",
            ngay_bat_dau__lte=hom_nay,
        )
        .filter(
            Q(ngay_ket_thuc__isnull=True)
            | Q(ngay_ket_thuc__gte=hom_nay)
        )
        .count()
    )

    # =====================================================
    # DANH SÁCH PHÒNG + SỨC CHỨA
    # =====================================================

    cac_phong = (
        Phong.objects
        .select_related("co_so")
        .order_by(
            "co_so__ten_co_so",
            "tang",
            "so_phong",
        )
    )

    danh_sach_phong = []

    tong_phong = 0
    phong_dang_o = 0
    phong_day = 0
    phong_chua_cau_hinh_suc_chua = 0

    tong_suc_chua = 0
    tong_nguoi_dang_o = 0
    tong_cho_con_lai = 0

    for phong in cac_phong:

        so_nguoi = phong.so_nguoi_dang_o
        suc_chua = phong.so_nguoi_toi_da
        cho_con_lai = phong.so_cho_con_lai

        # =================================================
        # ĐẢM BẢO SỐ LIỆU KHÔNG ÂM
        # =================================================

        so_nguoi = max(
            so_nguoi or 0,
            0
        )

        suc_chua = max(
            suc_chua or 0,
            0
        )

        cho_con_lai = max(
            cho_con_lai or 0,
            0
        )

        # =================================================
        # TỔNG SỐ LIỆU
        # =================================================

        tong_phong += 1

        tong_suc_chua += suc_chua
        tong_nguoi_dang_o += so_nguoi
        tong_cho_con_lai += cho_con_lai

        if so_nguoi > 0:
            phong_dang_o += 1

        # =================================================
        # TÍNH PHẦN TRĂM SỬ DỤNG SỨC CHỨA
        # =================================================

        if suc_chua > 0:
            ty_le_suc_chua = int(
                (so_nguoi / suc_chua) * 100
            )
        else:
            ty_le_suc_chua = 0

        ty_le_suc_chua = min(
            max(
                ty_le_suc_chua,
                0
            ),
            100
        )

        # =================================================
        # TRẠNG THÁI SỨC CHỨA
        # =================================================

        if suc_chua <= 0:
            trang_thai_suc_chua = "chua_cau_hinh"
            nhan_suc_chua = "Chưa cấu hình sức chứa"

            phong_chua_cau_hinh_suc_chua += 1

        elif so_nguoi >= suc_chua:
            trang_thai_suc_chua = "day"
            nhan_suc_chua = "Đã đầy"

            phong_day += 1

        elif so_nguoi > 0:
            trang_thai_suc_chua = "dang_o"
            nhan_suc_chua = (
                f"Còn {cho_con_lai} chỗ"
            )

        else:
            trang_thai_suc_chua = "trong"
            nhan_suc_chua = (
                f"Còn {cho_con_lai} chỗ"
            )

        # =================================================
        # ĐƯA PHÒNG VÀO DANH SÁCH DASHBOARD
        # =================================================

        danh_sach_phong.append(
            {
                "phong": phong,

                "so_nguoi": so_nguoi,
                "suc_chua": suc_chua,
                "cho_con_lai": cho_con_lai,

                "ty_le_suc_chua": ty_le_suc_chua,

                "trang_thai_suc_chua": (
                    trang_thai_suc_chua
                ),

                "nhan_suc_chua": (
                    nhan_suc_chua
                ),
            }
        )

    # =====================================================
    # 10 SỰ KIỆN RA / VÀO GẦN NHẤT
    # =====================================================

    lich_su_gan_day = (
        LichSuRaVao.objects
        .select_related(
            "phong__co_so",
            "nguoi_thue",
            "nguoi_o_cung",
            "quyen_ra_vao",
        )
        .order_by(
            "-thoi_diem"
        )[:10]
    )

    # =====================================================
    # THỐNG KÊ LƯỢT FACE ID GẦN ĐÂY
    # =====================================================

    face_id_cho_phep_gan_day = (
        LichSuRaVao.objects
        .filter(
            nguon="camera",
            ket_qua="cho_phep",
        )
        .count()
    )

    face_id_tu_choi_gan_day = (
        LichSuRaVao.objects
        .filter(
            nguon="camera",
            ket_qua="tu_choi",
        )
        .count()
    )

    # =====================================================
    # CONTEXT DASHBOARD
    # =====================================================

    context = {
        # Smart Room
        "tong_nguoi_o_cung": tong_nguoi_o_cung,

        "tong_face_profile": tong_face_profile,
        "face_co_anh": face_co_anh,
        "face_da_xac_thuc": face_da_xac_thuc,
        "face_chua_san_sang": face_chua_san_sang,

        "quyen_hoat_dong": quyen_hoat_dong,

        # Phòng
        "tong_phong": tong_phong,
        "phong_dang_o": phong_dang_o,
        "phong_day": phong_day,

        "phong_chua_cau_hinh_suc_chua": (
            phong_chua_cau_hinh_suc_chua
        ),

        "tong_suc_chua": tong_suc_chua,
        "tong_nguoi_dang_o": tong_nguoi_dang_o,
        "tong_cho_con_lai": tong_cho_con_lai,

        # Danh sách phòng
        "danh_sach_phong": danh_sach_phong,

        # Lịch sử
        "lich_su_gan_day": lich_su_gan_day,

        # Face ID
        "face_id_cho_phep_gan_day": (
            face_id_cho_phep_gan_day
        ),

        "face_id_tu_choi_gan_day": (
            face_id_tu_choi_gan_day
        ),
    }

    return render(
        request,
        "core/smart_room_dashboard.html",
        context
    )


def smart_access_control(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    phong_ds = (
        Phong.objects
        .select_related("co_so")
        .order_by(
            "co_so__ten_co_so",
            "tang",
            "so_phong"
        )
    )

    nguoi_thue_ds = (
        NguoiThue.objects
        .order_by("ho_ten")
    )

    nguoi_o_cung_ds = (
        NguoiOCungPhong.objects
        .filter(trang_thai="dang_o")
        .select_related("hop_dong__dat_phong__phong")
        .order_by("ho_ten")
    )

    ket_qua = None

    if request.method == "POST":

        phong_id = request.POST.get("phong", "").strip()
        chu_the = request.POST.get("chu_the", "").strip()
        nguoi_id = request.POST.get("nguoi_id", "").strip()

        phong = Phong.objects.filter(id=phong_id).first()

        if not phong:

            ket_qua = {
                "duoc_phep": False,
                "tieu_de": "ACCESS DENIED",
                "ly_do": "Không tìm thấy phòng cần kiểm tra.",
                "phong": None,
                "nguoi": None,
                "face": False,
                "quyen": False,
                "dung_phong": False,
            }

        elif not chu_the or not nguoi_id:

            ket_qua = {
                "duoc_phep": False,
                "tieu_de": "ACCESS DENIED",
                "ly_do": "Vui lòng chọn đầy đủ phòng và người cần kiểm tra.",
                "phong": phong,
                "nguoi": None,
                "face": False,
                "quyen": False,
                "dung_phong": False,
            }

        else:

            nguoi = None
            nguoi_thue = None
            nguoi_o_cung = None

            # =====================================================
            # NGƯỜI THUÊ CHÍNH
            # =====================================================

            if chu_the == "nguoi_thue":

                nguoi_thue = (
                    NguoiThue.objects
                    .filter(id=nguoi_id)
                    .first()
                )

                nguoi = nguoi_thue

            # =====================================================
            # NGƯỜI Ở CÙNG
            # =====================================================

            elif chu_the == "nguoi_o_cung":

                nguoi_o_cung = (
                    NguoiOCungPhong.objects
                    .select_related(
                        "hop_dong__dat_phong__phong"
                    )
                    .filter(
                        id=nguoi_id,
                        trang_thai="dang_o"
                    )
                    .first()
                )

                nguoi = nguoi_o_cung

            # =====================================================
            # KHÔNG TÌM THẤY NGƯỜI
            # =====================================================

            if not nguoi:

                ket_qua = {
                    "duoc_phep": False,
                    "tieu_de": "ACCESS DENIED",
                    "ly_do": (
                        "Người được chọn không tồn tại "
                        "hoặc không còn ở trong phòng."
                    ),
                    "phong": phong,
                    "nguoi": None,
                    "face": False,
                    "quyen": False,
                    "dung_phong": False,
                }

            else:

                # =================================================
                # 1. KIỂM TRA FACE PROFILE
                # =================================================

                if nguoi_thue:

                    face_profile = (
                        FaceProfile.objects
                        .filter(
                            nguoi_thue=nguoi_thue
                        )
                        .first()
                    )

                else:

                    face_profile = (
                        FaceProfile.objects
                        .filter(
                            nguoi_o_cung=nguoi_o_cung
                        )
                        .first()
                    )

                face_hop_le = bool(
                    face_profile
                    and face_profile.trang_thai == "da_xac_thuc"
                    and face_profile.anh_dai_dien
                )

                # =================================================
                # 2. KIỂM TRA QUYỀN RA VÀO
                # =================================================

                if nguoi_thue:

                    quyen = (
                        eligible_permissions(QuyenRaVao.objects.all())
                        .filter(
                            phong=phong,
                            nguoi_thue=nguoi_thue
                        )
                        .order_by("-ngay_tao")
                        .first()
                    )

                else:

                    quyen = (
                        eligible_permissions(QuyenRaVao.objects.all())
                        .filter(
                            phong=phong,
                            nguoi_o_cung=nguoi_o_cung
                        )
                        .order_by("-ngay_tao")
                        .first()
                    )

                hom_nay = timezone.localdate()

                quyen_hop_le = False
                ly_do_quyen = ""

                if not quyen:

                    ly_do_quyen = (
                        "Người này chưa được cấp "
                        "quyền ra vào phòng."
                    )

                elif quyen.trang_thai != "hoat_dong":

                    ly_do_quyen = (
                        "Quyền ra vào hiện đang ở trạng thái: "
                        f"{quyen.get_trang_thai_display()}."
                    )

                elif quyen.ngay_bat_dau > hom_nay:

                    ly_do_quyen = (
                        "Quyền ra vào chưa bắt đầu "
                        "có hiệu lực."
                    )

                elif (
                    quyen.ngay_ket_thuc
                    and quyen.ngay_ket_thuc < hom_nay
                ):

                    ly_do_quyen = (
                        "Quyền ra vào đã hết thời hạn."
                    )

                else:

                    quyen_hop_le = True

                # =================================================
                # 3. KIỂM TRA NGƯỜI CÓ THUỘC ĐÚNG PHÒNG
                # =================================================

                dung_phong = False

                if nguoi_thue:

                    # HopDong không có nguoi_thue trực tiếp.
                    # Quan hệ đúng:
                    # HopDong -> dat_phong -> nguoi_thue

                    hop_dong = (
                        HopDong.objects
                        .filter(
                            dat_phong__phong=phong,
                            dat_phong__nguoi_thue=nguoi_thue,
                            trang_thai__in=[
                                "dang_hieu_luc",
                                "sap_het_han",
                            ],
                        )
                        .first()
                    )

                    dung_phong = bool(hop_dong)

                elif nguoi_o_cung:

                    hop_dong = nguoi_o_cung.hop_dong

                    if hop_dong:

                        dat_phong = getattr(
                            hop_dong,
                            "dat_phong",
                            None
                        )

                        if dat_phong:

                            dung_phong = (
                                dat_phong.phong_id
                                == phong.id
                            )

                # =================================================
                # 4. QUYẾT ĐỊNH ACCESS
                # =================================================

                dung_phong = dung_phong and bool(quyen) and _quyen_co_hop_dong_hien_tai(quyen)
                duoc_phep = (
                    face_hop_le
                    and quyen_hop_le
                    and dung_phong
                )

                # =================================================
                # ACCESS GRANTED
                # =================================================

                if duoc_phep:

                    tieu_de = "ACCESS GRANTED"

                    ly_do = (
                        "Nhận diện khuôn mặt hợp lệ, "
                        "quyền ra vào đang hoạt động "
                        "và người dùng thuộc đúng phòng."
                    )

                    ghi_chu = (
                        "Mô phỏng camera: "
                        "Nhận diện thành công. "
                        "Đủ điều kiện mở cửa."
                    )

                # =================================================
                # ACCESS DENIED
                # =================================================

                else:

                    tieu_de = "ACCESS DENIED"

                    if not face_hop_le:

                        ly_do = (
                            "Face Profile chưa được xác thực "
                            "hoặc chưa có ảnh hợp lệ."
                        )

                    elif not quyen_hop_le:

                        ly_do = ly_do_quyen

                    elif not dung_phong:

                        ly_do = (
                            "Người này không thuộc "
                            "phòng được kiểm tra."
                        )

                    else:

                        ly_do = (
                            "Không đủ điều kiện truy cập."
                        )

                    ghi_chu = (
                        "Mô phỏng camera: "
                        "Truy cập bị từ chối."
                    )

                # =================================================
                # 5. GHI LỊCH SỬ RA VÀO
                # =================================================

                LichSuRaVao.objects.create(
                    quyen_ra_vao=quyen,
                    phong=phong,
                    nguoi_thue=nguoi_thue,
                    nguoi_o_cung=nguoi_o_cung,
                    ten_nguoi=nguoi.ho_ten,
                    loai_su_kien="vao",
                    nguon="camera",
                    ket_qua=("cho_phep" if duoc_phep else "tu_choi"),
                    thoi_diem=timezone.now(),
                    ghi_chu=ghi_chu,
                )

                # =================================================
                # 6. TRẢ KẾT QUẢ CHO TEMPLATE
                # =================================================

                ket_qua = {
                    "duoc_phep": duoc_phep,
                    "tieu_de": tieu_de,
                    "ly_do": ly_do,
                    "phong": phong,
                    "nguoi": nguoi,
                    "face": face_hop_le,
                    "quyen": quyen_hop_le,
                    "dung_phong": dung_phong,
                    "face_profile": face_profile,
                    "quyen_obj": quyen,
                }

    return render(
        request,
        "core/smart_access_control.html",
        {
            "phong_ds": phong_ds,
            "nguoi_thue_ds": nguoi_thue_ds,
            "nguoi_o_cung_ds": nguoi_o_cung_ds,
            "ket_qua": ket_qua,
        }
    )


def quan_ly_nguoi_o_cung(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    # =====================================================
    # DANH SÁCH NGƯỜI Ở CÙNG
    # =====================================================

    ds = (
        NguoiOCungPhong.objects
        .select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
        )
        .order_by("-ngay_tao")
    )

    # =====================================================
    # BỘ LỌC
    # =====================================================

    tu_khoa = request.GET.get("q", "").strip()
    phong_id = request.GET.get("phong", "").strip()
    trang_thai_filter = request.GET.get("trang_thai", "").strip()

    # Tìm kiếm
    if tu_khoa:
        ds = ds.filter(
            models.Q(ho_ten__icontains=tu_khoa)
            | models.Q(cccd__icontains=tu_khoa)
            | models.Q(so_dien_thoai__icontains=tu_khoa)
            | models.Q(quan_he__icontains=tu_khoa)
            | models.Q(
                hop_dong__dat_phong__phong__so_phong__icontains=tu_khoa
            )
        )

    # Lọc theo phòng
    if phong_id.isdigit():
        ds = ds.filter(
            hop_dong__dat_phong__phong_id=int(phong_id)
        )

    # Lọc theo trạng thái
    if trang_thai_filter in dict(NguoiOCungPhong.TRANG_THAI):
        ds = ds.filter(
            trang_thai=trang_thai_filter
        )

    # =====================================================
    # DANH SÁCH PHÒNG
    # =====================================================

    cac_phong = (
        Phong.objects
        .select_related("co_so")
        .order_by(
            "co_so__ten_co_so",
            "tang",
            "so_phong"
        )
    )

    # =====================================================
    # THỐNG KÊ TỔNG QUAN
    # =====================================================

    tong_nguoi = NguoiOCungPhong.objects.count()

    dang_o = NguoiOCungPhong.objects.filter(
        trang_thai="dang_o"
    ).count()

    da_roi = NguoiOCungPhong.objects.filter(
        trang_thai="da_roi"
    ).count()

    # =====================================================
    # THỐNG KÊ SỨC CHỨA
    # =====================================================

    tong_suc_chua = 0
    tong_dang_o = 0
    tong_cho_con_lai = 0

    for phong in cac_phong:
        tong_suc_chua += phong.so_nguoi_toi_da
        tong_dang_o += phong.so_nguoi_dang_o
        tong_cho_con_lai += phong.so_cho_con_lai

    # =====================================================
    # TRẢ VỀ TEMPLATE
    # =====================================================

    return render(
        request,
        "core/quan_ly_nguoi_o_cung.html",
        {
            # Template đang dùng biến "ds"
            "ds": ds,

            # Giữ thêm biến này nếu nơi khác đang sử dụng
            "nguoi_o_cung": ds,

            "cac_phong": cac_phong,

            "tu_khoa": tu_khoa,
            "phong_id": phong_id,

            # Template đang dùng "trang_thai_filter"
            "trang_thai_filter": trang_thai_filter,

            # Giữ thêm biến này cho tương thích
            "trang_thai": trang_thai_filter,

            "tong_nguoi": tong_nguoi,
            "dang_o": dang_o,
            "da_roi": da_roi,

            "tong_suc_chua": tong_suc_chua,
            "tong_dang_o": tong_dang_o,
            "tong_cho_con_lai": tong_cho_con_lai,
        }
    )


def chi_tiet_nguoi_o_cung(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    nguoi = get_object_or_404(
        NguoiOCungPhong.objects.select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__phong",
            "hop_dong__dat_phong__phong__co_so",
        ),
        id=id
    )

    phong = nguoi.hop_dong.dat_phong.phong

    # Các người đang ở cùng hợp đồng
    danh_sach_nguoi_o = (
        nguoi.hop_dong.nguoi_o_cung
        .filter(trang_thai="dang_o")
        .order_by("ho_ten")
    )

    face_profile = FaceProfile.objects.filter(nguoi_o_cung=nguoi).first()
    quyen_ra_vao = (
        QuyenRaVao.objects.filter(nguoi_o_cung=nguoi)
        .order_by("-id")
        .first()
    )
    dieu_kien_xac_minh = danh_gia_xac_minh_nguoi_o_cung(nguoi)

    return render(
        request,
        "core/chi_tiet_nguoi_o_cung.html",
        {
            "nguoi": nguoi,
            "phong": phong,
            "hop_dong": nguoi.hop_dong,
            "danh_sach_nguoi_o": danh_sach_nguoi_o,
            "trang_thai_xac_minh": trang_thai_xac_minh_nguoi_o_cung(nguoi),
            "dang_luu_tru": nguoi_o_cung_du_dieu_kien(nguoi),
            "ly_do_chua_du_dieu_kien": ly_do_nguoi_o_cung_chua_du_dieu_kien(nguoi),
            "face_profile": face_profile,
            "quyen_ra_vao": quyen_ra_vao,
            "quyen_con_hieu_luc": bool(quyen_ra_vao and quyen_ra_vao_con_hieu_luc(quyen_ra_vao)),
            "co_the_xac_minh": dieu_kien_xac_minh.du_dieu_kien,
            "ly_do_khong_the_xac_minh": dieu_kien_xac_minh.ly_do,

            # Thông tin sức chứa phòng
            "suc_chua": phong.so_nguoi_toi_da,
            "so_nguoi_dang_o": phong.so_nguoi_dang_o,
            "so_cho_con_lai": phong.so_cho_con_lai,
            "leave_idempotency_key": uuid4().hex,
            "return_idempotency_key": uuid4().hex,
        }
    )


def _tao_nguoi_o_cung_retired(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    # Lấy các hợp đồng còn hiệu lực
    cac_hop_dong = (
        HopDong.objects
        .select_related(
            "dat_phong",
            "dat_phong__phong",
            "dat_phong__phong__co_so",
            "dat_phong__nguoi_thue",
        )
        .filter(
            trang_thai__in=[
                "dang_hieu_luc",
                "sap_het_han",
            ],
            dat_phong__trang_thai="da_duyet",
        )
        .order_by(
            "dat_phong__phong__so_phong"
        )
    )

    if request.method == "POST":

        hop_dong_id = request.POST.get("hop_dong")

        ho_ten = request.POST.get(
            "ho_ten",
            ""
        ).strip()

        ngay_sinh_raw = request.POST.get(
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

        ngay_vao_raw = request.POST.get(
            "ngay_vao",
            ""
        ).strip()

        ghi_chu = request.POST.get(
            "ghi_chu",
            ""
        ).strip()

        # -------------------------------------------------
        # KIỂM TRA HỢP ĐỒNG
        # -------------------------------------------------

        if not hop_dong_id:
            messages.error(
                request,
                "Vui lòng chọn hợp đồng/phòng."
            )

            return render(
                request,
                "core/tao_nguoi_o_cung.html",
                {
                    "cac_hop_dong": cac_hop_dong
                }
            )

        hop_dong = get_object_or_404(
            HopDong.objects.select_related(
                "dat_phong",
                "dat_phong__phong",
                "dat_phong__nguoi_thue",
            ),
            id=hop_dong_id
        )

        phong = hop_dong.dat_phong.phong
        so_nguoi_dang_o = phong.so_nguoi_dang_o
        so_cho_con_lai = phong.so_cho_con_lai

        # -------------------------------------------------
        # KIỂM TRA HỢP ĐỒNG CÒN HIỆU LỰC
        # -------------------------------------------------

        if not contract_is_current(hop_dong):
            messages.error(
                request,
                "Hợp đồng này hiện không còn hiệu lực."
            )

            return render(
                request,
                "core/tao_nguoi_o_cung.html",
                {
                    "cac_hop_dong": cac_hop_dong
                }
            )

        # -------------------------------------------------
        # KIỂM TRA TÊN
        # -------------------------------------------------

        if not ho_ten:
            messages.error(
                request,
                "Vui lòng nhập họ tên người ở cùng."
            )

            return render(
                request,
                "core/tao_nguoi_o_cung.html",
                {
                    "cac_hop_dong": cac_hop_dong,
                    "phong": phong,
                }
            )

        # -------------------------------------------------
        # KIỂM TRA NGÀY VÀO
        # -------------------------------------------------

        ngay_vao = parse_date(ngay_vao_raw)

        if not ngay_vao:
            messages.error(
                request,
                "Ngày vào không hợp lệ."
            )

            return render(
                request,
                "core/tao_nguoi_o_cung.html",
                {
                    "cac_hop_dong": cac_hop_dong,
                    "phong": phong,
                }
            )
        if ngay_vao < hop_dong.ngay_bat_dau:
            messages.error(
                request,
                (
                    f"Ngày vào không được trước ngày bắt đầu hợp đồng "
                    f"({hop_dong.ngay_bat_dau.strftime('%d/%m/%Y')})."
                )
            )

            return render(
                request,
                "core/tao_nguoi_o_cung.html",
                {
                    "cac_hop_dong": cac_hop_dong,
                    "phong": phong,
                    "so_nguoi_dang_o": so_nguoi_dang_o,
                    "so_cho_con_lai": so_cho_con_lai,
                }
            )

        if ngay_vao > hop_dong.ngay_ket_thuc:
            messages.error(
                request,
                (
                    f"Ngày vào không được sau ngày kết thúc hợp đồng "
                    f"({hop_dong.ngay_ket_thuc.strftime('%d/%m/%Y')})."
                )
            )

            return render(
                request,
                "core/tao_nguoi_o_cung.html",
                {
                    "cac_hop_dong": cac_hop_dong,
                    "phong": phong,
                    "so_nguoi_dang_o": so_nguoi_dang_o,
                    "so_cho_con_lai": so_cho_con_lai,
                }
            )
        # -------------------------------------------------
        # KIỂM TRA SỨC CHỨA
        # -------------------------------------------------

        # Lấy lại phòng mới nhất từ database
        phong.refresh_from_db()

        so_nguoi_dang_o = phong.so_nguoi_dang_o
        so_cho_con_lai = phong.so_cho_con_lai

        if phong.so_nguoi_toi_da <= 0:
            messages.error(request, "Phòng chưa cấu hình sức chứa.")
            return render(request, "core/tao_nguoi_o_cung.html", {
                "cac_hop_dong": cac_hop_dong, "phong": phong,
                "so_nguoi_dang_o": so_nguoi_dang_o, "so_cho_con_lai": so_cho_con_lai,
            })

        if so_cho_con_lai <= 0:
            messages.error(
                request,
                (
                    f"Phòng {phong.so_phong} đã đủ người. "
                    f"Sức chứa tối đa: {phong.so_nguoi_toi_da} người."
                )
            )

            return render(
                request,
                "core/tao_nguoi_o_cung.html",
                {
                    "cac_hop_dong": cac_hop_dong,
                    "phong": phong,
                    "so_nguoi_dang_o": so_nguoi_dang_o,
                    "so_cho_con_lai": so_cho_con_lai,
                }
            )

        # -------------------------------------------------
        # KIỂM TRA CCCD
        # -------------------------------------------------

        if cccd and not re.fullmatch(r"(?:\d{9}|\d{12})", cccd):
            messages.error(request, "CCCD phải gồm 9 hoặc 12 chữ số.")
            return render(
                request,
                "core/tao_nguoi_o_cung.html",
                {
                    "cac_hop_dong": cac_hop_dong,
                    "phong": phong,
                    "so_nguoi_dang_o": so_nguoi_dang_o,
                    "so_cho_con_lai": so_cho_con_lai,
                },
            )

        if cccd:

            if NguoiThue.objects.filter(
                cccd=cccd
            ).exists():
                messages.error(
                    request,
                    "CCCD này đã thuộc một người thuê chính."
                )

                return render(
                    request,
                    "core/tao_nguoi_o_cung.html",
                    {
                        "cac_hop_dong": cac_hop_dong,
                        "phong": phong,
                        "so_nguoi_dang_o": so_nguoi_dang_o,
                        "so_cho_con_lai": so_cho_con_lai,
                    }
                )

            if NguoiOCungPhong.objects.filter(
                cccd=cccd
            ).exclude(
                cccd=""
            ).exists():
                messages.error(
                    request,
                    "CCCD này đã tồn tại trong danh sách người ở."
                )

                return render(
                    request,
                    "core/tao_nguoi_o_cung.html",
                    {
                        "cac_hop_dong": cac_hop_dong,
                        "phong": phong,
                        "so_nguoi_dang_o": so_nguoi_dang_o,
                        "so_cho_con_lai": so_cho_con_lai,
                    }
                )

        # -------------------------------------------------
        # KIỂM TRA NGÀY SINH
        # -------------------------------------------------

        ngay_sinh = None

        if ngay_sinh_raw:
            ngay_sinh = parse_date(ngay_sinh_raw)

            if not ngay_sinh:
                messages.error(
                    request,
                    "Ngày sinh không hợp lệ."
                )

                return render(
                    request,
                    "core/tao_nguoi_o_cung.html",
                    {
                        "cac_hop_dong": cac_hop_dong,
                        "phong": phong,
                        "so_nguoi_dang_o": so_nguoi_dang_o,
                        "so_cho_con_lai": so_cho_con_lai,
                    }
                )

        # -------------------------------------------------
        # TẠO NGƯỜI Ở CÙNG
        # -------------------------------------------------

        nguoi = NguoiOCungPhong.objects.create(
            hop_dong=hop_dong,
            ho_ten=ho_ten,
            ngay_sinh=ngay_sinh,
            gioi_tinh=gioi_tinh,
            cccd=cccd,
            so_dien_thoai=so_dien_thoai,
            quan_he=quan_he,
            # Có CCCD hợp lệ mới chỉ là đủ hồ sơ để Admin đối chiếu thủ công;
            # tuyệt đối không coi đó là xác minh chính thức hay đang lưu trú.
            trang_thai="cho_xac_minh" if cccd else "cho_bo_sung",
            ngay_vao=ngay_vao,
            ghi_chu=ghi_chu,
        )

        # -------------------------------------------------
        # TỰ ĐỘNG TẠO FACE PROFILE
        # -------------------------------------------------

        FaceProfile.objects.get_or_create(
            nguoi_o_cung=nguoi,
            defaults={
                "loai_chu_the": "nguoi_o_cung",
                "trang_thai": "chua_co_anh",
            }
        )

        # -------------------------------------------------
        # THÔNG BÁO THÀNH CÔNG
        # -------------------------------------------------

        # Tính lại số chỗ sau khi thêm người
        phong.refresh_from_db()

        messages.success(
            request,
            (
                f"Đã tạo hồ sơ {ho_ten} cho phòng {phong.so_phong}. "
                f"Hiện có {phong.so_nguoi_dang_o}/{phong.so_nguoi_toi_da} người. "
                f"Còn {phong.so_cho_con_lai} chỗ."
            )
        )

        return redirect(
            "chi_tiet_nguoi_o_cung",
            id=nguoi.id
        )

    return render(
        request,
        "core/tao_nguoi_o_cung.html",
        {
            "cac_hop_dong": cac_hop_dong
        }
    )


def tao_nguoi_o_cung(request):
    """Admin direct-admit form; residency writes live only in the domain service."""
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    cac_hop_dong = (
        HopDong.objects.select_related(
            "dat_phong", "dat_phong__phong", "dat_phong__phong__co_so",
            "dat_phong__nguoi_thue",
        ).filter(
            trang_thai__in=["dang_hieu_luc", "sap_het_han"],
            dat_phong__trang_thai="da_duyet",
        ).order_by("dat_phong__phong__so_phong")
    )
    if request.method == "POST":
        try:
            contract_id = int(request.POST.get("hop_dong", ""))
            ngay_vao = parse_date(request.POST.get("ngay_vao", "").strip())
            ngay_sinh_raw = request.POST.get("ngay_sinh", "").strip()
            ngay_sinh = parse_date(ngay_sinh_raw) if ngay_sinh_raw else None
            if ngay_sinh_raw and not ngay_sinh:
                raise ValidationError("Ngay sinh khong hop le.")
            resident, created = direct_admit(
                contract_id=contract_id, actor=request.user,
                idempotency_key=request.POST.get("idempotency_key", "").strip(),
                ho_ten=request.POST.get("ho_ten", ""),
                cccd=request.POST.get("cccd", ""), ngay_vao=ngay_vao,
                ngay_sinh=ngay_sinh,
                gioi_tinh=request.POST.get("gioi_tinh", "").strip(),
                so_dien_thoai=request.POST.get("so_dien_thoai", "").strip(),
                quan_he=request.POST.get("quan_he", "").strip(),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            messages.error(request, str(exc) or "Du lieu direct-admit khong hop le.")
        except Exception:
            messages.error(request, "Khong the ghi nhan nguoi o cung luc nay.")
        else:
            if created:
                messages.success(request, "Da ghi nhan nguoi o cung da xac minh.")
            else:
                messages.info(request, "Yeu cau direct-admit nay da duoc ghi nhan truoc do.")
            return redirect("chi_tiet_nguoi_o_cung", id=resident.pk)

    return render(
        request, "core/tao_nguoi_o_cung.html",
        {"cac_hop_dong": cac_hop_dong, "idempotency_key": request.POST.get("idempotency_key") or uuid4().hex},
    )


@transaction.atomic
def xu_ly_nguoi_o_cung(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    nguoi = get_object_or_404(
        NguoiOCungPhong.objects.select_related(
            "hop_dong",
            "hop_dong__dat_phong",
            "hop_dong__dat_phong__phong",
        ),
        id=id
    )

    if request.method != "POST":
        return redirect(
            "chi_tiet_nguoi_o_cung",
            id=nguoi.id
        )

    hanh_dong = request.POST.get(
        "hanh_dong",
        "cap_nhat"
    ).strip()

    # Residency lifecycle is canonicalized in the co-tenant domain service.
    # Legacy verification actions cannot activate or otherwise mutate a
    # residency now that direct-admit/request approval own that responsibility.
    if hanh_dong in ("xac_minh", "cho_bo_sung", "tu_choi"):
        messages.warning(request, "Thao tac legacy da duoc dong; hay dung quy trinh nguoi o cung moi.")
        return redirect("chi_tiet_nguoi_o_cung", id=nguoi.id)

    if hanh_dong == "roi_phong":
        try:
            resident, changed = leave_residency(
                residency_id=nguoi.pk, actor=request.user,
                idempotency_key=request.POST.get("idempotency_key") or f"leave:{nguoi.pk}",
            )
        except ValidationError as exc:
            messages.error(request, str(exc) or "Khong the ghi nhan roi phong.")
        except Exception:
            messages.error(request, "Khong the ghi nhan roi phong luc nay.")
        else:
            messages.success(request, "Da ghi nhan roi phong." if changed else "Residency nay da duoc ghi nhan roi phong.")
        return redirect("chi_tiet_nguoi_o_cung", id=resident.pk if 'resident' in locals() else nguoi.pk)

    if hanh_dong == "quay_lai":
        try:
            resident, changed = return_as_new_residency(
                residency_id=nguoi.pk, actor=request.user,
                idempotency_key=request.POST.get("idempotency_key") or f"return:{nguoi.pk}",
            )
        except ValidationError as exc:
            messages.error(request, str(exc) or "Khong the ghi nhan quay lai.")
        except Exception:
            messages.error(request, "Khong the ghi nhan quay lai luc nay.")
        else:
            messages.success(request, "Da tao dot luu tru moi." if changed else "Yeu cau quay lai nay da duoc ghi nhan truoc do.")
        return redirect("chi_tiet_nguoi_o_cung", id=resident.pk if 'resident' in locals() else nguoi.pk)

    if hanh_dong == "cap_nhat":
        submitted_cccd = request.POST.get("cccd", nguoi.cccd).strip()
        submitted_status = request.POST.get("trang_thai", nguoi.trang_thai).strip()
        submitted_leave = request.POST.get("ngay_ra", "").strip()
        existing_leave = nguoi.ngay_ra.isoformat() if nguoi.ngay_ra else ""
        if submitted_cccd != nguoi.cccd or submitted_status != nguoi.trang_thai or submitted_leave != existing_leave:
            messages.error(request, "CCCD va trang thai cu tru chi duoc thay doi qua quy trinh canonical.")
            return redirect("chi_tiet_nguoi_o_cung", id=nguoi.pk)
        ho_ten = request.POST.get("ho_ten", nguoi.ho_ten).strip()
        if not ho_ten:
            messages.error(request, "Ho ten khong duoc de trong.")
            return redirect("chi_tiet_nguoi_o_cung", id=nguoi.pk)
        ngay_sinh_raw = request.POST.get("ngay_sinh", "").strip()
        ngay_sinh = parse_date(ngay_sinh_raw) if ngay_sinh_raw else None
        if ngay_sinh_raw and not ngay_sinh:
            messages.error(request, "Ngay sinh khong hop le.")
            return redirect("chi_tiet_nguoi_o_cung", id=nguoi.pk)
        nguoi.ho_ten = ho_ten
        nguoi.ngay_sinh = ngay_sinh
        nguoi.gioi_tinh = request.POST.get("gioi_tinh", nguoi.gioi_tinh).strip()
        nguoi.so_dien_thoai = request.POST.get("so_dien_thoai", nguoi.so_dien_thoai).strip()
        nguoi.quan_he = request.POST.get("quan_he", nguoi.quan_he).strip()
        nguoi.ghi_chu = request.POST.get("ghi_chu", nguoi.ghi_chu).strip()
        nguoi.save(update_fields=["ho_ten", "ngay_sinh", "gioi_tinh", "so_dien_thoai", "quan_he", "ghi_chu", "ngay_cap_nhat"])
        messages.success(request, "Da cap nhat thong tin ho so.")
        return redirect("chi_tiet_nguoi_o_cung", id=nguoi.pk)

    if hanh_dong in ("xac_minh", "cho_bo_sung", "tu_choi"):
        trang_thai_cu = nguoi.trang_thai
        xac_minh_cu = nguoi.da_xac_minh_boi_admin
        so_quyen_thu_hoi = 0
        if hanh_dong == "xac_minh":
            dieu_kien = danh_gia_xac_minh_nguoi_o_cung(nguoi)
            if not dieu_kien.du_dieu_kien:
                messages.error(request, dieu_kien.ly_do)
                return redirect("chi_tiet_nguoi_o_cung", id=nguoi.id)
            nguoi.da_xac_minh_boi_admin = True
            if nguoi.trang_thai != "da_roi":
                nguoi.trang_thai = (
                    "dang_o" if nguoi.ngay_vao <= timezone.localdate() else "da_xac_minh"
                )
                nguoi.ngay_ra = None
            messages.success(request, "Đã xác minh thủ công hồ sơ người ở cùng.")
        elif hanh_dong == "cho_bo_sung":
            nguoi.da_xac_minh_boi_admin = False
            nguoi.trang_thai = "cho_bo_sung"
            so_quyen_thu_hoi = thu_hoi_quyen_nguoi_o_cung(
                nguoi, nguon="Admin", trang_thai="bi_thu_hoi"
            )
            messages.success(request, "Đã chuyển hồ sơ sang chờ bổ sung.")
        else:
            nguoi.da_xac_minh_boi_admin = False
            nguoi.trang_thai = "tu_choi"
            so_quyen_thu_hoi = thu_hoi_quyen_nguoi_o_cung(
                nguoi, nguon="Admin", trang_thai="bi_thu_hoi"
            )
            messages.success(request, "Đã từ chối hồ sơ người ở cùng.")
        nguoi.save(update_fields=[
            "trang_thai", "ngay_ra", "da_xac_minh_boi_admin", "ngay_cap_nhat"
        ])
        ghi_nhan_thay_doi_cu_tru(
            resident=nguoi,
            event={
                "xac_minh": "them_sau_ky",
                "cho_bo_sung": "yeu_cau_bo_sung",
                "tu_choi": "tu_choi",
            }[hanh_dong],
            actor=request.user,
            reason=f"Admin xu ly ho so: {hanh_dong}.",
        )
        ghi_nhat_ky(
            request=request,
            hanh_dong={
                "xac_minh": "duyet",
                "cho_bo_sung": "cap_nhat",
                "tu_choi": "tu_choi",
            }[hanh_dong],
            module="Smart Room",
            doi_tuong="NguoiOCungPhong",
            doi_tuong_id=nguoi.id,
            tieu_de=f"Xử lý hồ sơ người ở cùng #{nguoi.id}",
            noi_dung=(
                f"Admin xử lý '{hanh_dong}' hồ sơ #{nguoi.id}; "
                f"thu hồi {so_quyen_thu_hoi} quyền ra vào."
            ),
            du_lieu_cu={
                "trang_thai": trang_thai_cu,
                "da_xac_minh_boi_admin": xac_minh_cu,
            },
            du_lieu_moi={
                "trang_thai": nguoi.trang_thai,
                "da_xac_minh_boi_admin": nguoi.da_xac_minh_boi_admin,
            },
        )
        return redirect("chi_tiet_nguoi_o_cung", id=nguoi.id)

    # =====================================================
    # 1. ĐÁNH DẤU RỜI PHÒNG
    # =====================================================

    if (
        hanh_dong == "quay_lai"
        or (hanh_dong not in ("roi_phong", "xoa")
            and request.POST.get("trang_thai", "").strip() == "dang_o")
    ) and not contract_is_current(nguoi.hop_dong):
        messages.error(request, "Hợp đồng này hiện không còn hiệu lực.")
        return redirect("chi_tiet_nguoi_o_cung", id=nguoi.id)

    if hanh_dong == "quay_lai" and not nguoi.da_xac_minh_boi_admin:
        messages.error(request, "Cần Admin xác minh hồ sơ trước khi ghi nhận đang ở lại.")
        return redirect("chi_tiet_nguoi_o_cung", id=nguoi.id)

    if hanh_dong == "roi_phong":

        nguoi.trang_thai = "da_roi"
        nguoi.ngay_ra = timezone.localdate()

        nguoi.save(
            update_fields=[
                "trang_thai",
                "ngay_ra",
                "ngay_cap_nhat",
            ]
        )
        ghi_nhan_thay_doi_cu_tru(
            resident=nguoi,
            event="roi_sau_ky",
            actor=request.user,
            reason="Admin ghi nhan nguoi o cung roi phong.",
        )

        # Thu hồi toàn bộ quyền ra vào đang hoạt động
        thu_hoi_quyen_nguoi_o_cung(nguoi, nguon="Admin")

        messages.success(
            request,
            f"{nguoi.ho_ten} đã được ghi nhận rời phòng."
        )

        return redirect(
            "chi_tiet_nguoi_o_cung",
            id=nguoi.id
        )

    # =====================================================
    # 2. KHÔI PHỤC ĐANG Ở
    # =====================================================

    if hanh_dong == "quay_lai":

        phong = nguoi.hop_dong.dat_phong.phong

        phong.refresh_from_db()

        if phong.so_nguoi_toi_da <= 0:
            messages.error(request, "Phòng chưa cấu hình sức chứa.")
            return redirect("chi_tiet_nguoi_o_cung", id=nguoi.id)

        if phong.so_cho_con_lai <= 0:
            messages.error(
                request,
                (
                    f"Phòng {phong.so_phong} hiện đã đủ "
                    f"{phong.so_nguoi_toi_da} người."
                )
            )

            return redirect(
                "chi_tiet_nguoi_o_cung",
                id=nguoi.id
            )

        nguoi.trang_thai = "dang_o"
        nguoi.ngay_ra = None

        nguoi.save(
            update_fields=[
                "trang_thai",
                "ngay_ra",
                "ngay_cap_nhat",
            ]
        )
        ghi_nhan_thay_doi_cu_tru(
            resident=nguoi,
            event="them_sau_ky",
            actor=request.user,
            reason="Admin ghi nhan nguoi o cung quay lai.",
        )

        messages.success(
            request,
            f"Đã cập nhật {nguoi.ho_ten} đang ở lại phòng."
        )

        return redirect(
            "chi_tiet_nguoi_o_cung",
            id=nguoi.id
        )

    # =====================================================
    # 3. XÓA NGƯỜI Ở CÙNG
    # =====================================================

    if hanh_dong == "xoa":
        messages.error(
            request,
            "Hồ sơ residency được lưu lịch sử; hãy ghi nhận rời phòng thay vì xóa.",
        )
        return redirect("chi_tiet_nguoi_o_cung", id=nguoi.pk)

        if QuyenRaVao.objects.filter(nguoi_o_cung=nguoi).filter(
            Q(hop_dong__isnull=True) | Q(nguon_cap="legacy_unknown")
        ).exists():
            messages.error(request, "Không thể xóa người có quyền legacy cần giữ lịch sử.")
            return redirect("chi_tiet_nguoi_o_cung", id=nguoi.pk)

        # Xóa các quyền ra vào liên quan trước
        QuyenRaVao.objects.filter(hop_dong=nguoi.hop_dong, nguon_cap__in=KNOWN_PERMISSION_SOURCES,
            nguoi_o_cung=nguoi
        ).delete()

        # Xóa người ở cùng
        ten_nguoi = nguoi.ho_ten

        nguoi.delete()

        messages.success(
            request,
            f"Đã xóa người ở cùng {ten_nguoi}."
        )

        return redirect(
            "quan_ly_nguoi_o_cung"
        )

    # =====================================================
    # 4. CẬP NHẬT THÔNG TIN
    # =====================================================

    ho_ten = request.POST.get(
        "ho_ten",
        nguoi.ho_ten
    ).strip()

    so_dien_thoai = request.POST.get(
        "so_dien_thoai",
        nguoi.so_dien_thoai
    ).strip()

    gioi_tinh = request.POST.get(
        "gioi_tinh",
        nguoi.gioi_tinh
    ).strip()

    quan_he = request.POST.get(
        "quan_he",
        nguoi.quan_he
    ).strip()

    cccd = request.POST.get(
        "cccd",
        nguoi.cccd
    ).strip()

    ghi_chu = request.POST.get(
        "ghi_chu",
        nguoi.ghi_chu
    ).strip()

    ngay_sinh_raw = request.POST.get(
        "ngay_sinh",
        ""
    ).strip()

    ngay_ra_raw = request.POST.get(
        "ngay_ra",
        ""
    ).strip()

    trang_thai = request.POST.get(
        "trang_thai",
        nguoi.trang_thai
    ).strip()

    # =====================================================
    # 4.1. KIỂM TRA HỌ TÊN
    # =====================================================

    if not ho_ten:
        messages.error(
            request,
            "Họ tên không được để trống."
        )

        return redirect(
            "chi_tiet_nguoi_o_cung",
            id=nguoi.id
        )

    # =====================================================
    # 4.2. KIỂM TRA TRẠNG THÁI
    # =====================================================

    if trang_thai not in dict(NguoiOCungPhong.TRANG_THAI):
        messages.error(
            request,
            "Trạng thái không hợp lệ."
        )

        return redirect(
            "chi_tiet_nguoi_o_cung",
            id=nguoi.id
        )

    # =====================================================
    # 4.3. KIỂM TRA CCCD
    # =====================================================

    if cccd and not re.fullmatch(r"(?:\d{9}|\d{12})", cccd):
        messages.error(request, "CCCD phải gồm 9 hoặc 12 chữ số.")
        return redirect("chi_tiet_nguoi_o_cung", id=nguoi.id)

    if cccd:

        # Không cho trùng với người thuê chính
        if NguoiThue.objects.filter(
            cccd=cccd
        ).exists():

            messages.error(
                request,
                "CCCD này đã thuộc một người thuê chính."
            )

            return redirect(
                "chi_tiet_nguoi_o_cung",
                id=nguoi.id
            )

        # Không cho trùng người ở cùng khác
        if NguoiOCungPhong.objects.filter(
            cccd=cccd
        ).exclude(
            id=nguoi.id
        ).exclude(
            cccd=""
        ).exists():

            messages.error(
                request,
                "CCCD này đã tồn tại trong danh sách người ở cùng."
            )

            return redirect(
                "chi_tiet_nguoi_o_cung",
                id=nguoi.id
            )

    # =====================================================
    # 4.4. KIỂM TRA NGÀY SINH
    # =====================================================

    ngay_sinh = None

    if ngay_sinh_raw:

        ngay_sinh = parse_date(
            ngay_sinh_raw
        )

        if not ngay_sinh:

            messages.error(
                request,
                "Ngày sinh không hợp lệ."
            )

            return redirect(
                "chi_tiet_nguoi_o_cung",
                id=nguoi.id
            )

    # =====================================================
    # 4.5. KIỂM TRA NGÀY RỜI
    # =====================================================

    ngay_ra = None

    if ngay_ra_raw:

        ngay_ra = parse_date(
            ngay_ra_raw
        )

        if not ngay_ra:

            messages.error(
                request,
                "Ngày rời đi không hợp lệ."
            )

            return redirect(
                "chi_tiet_nguoi_o_cung",
                id=nguoi.id
            )

    # =====================================================
    # 4.6. KIỂM TRA LOGIC NGÀY
    # =====================================================

    if ngay_ra and ngay_ra < nguoi.ngay_vao:

        messages.error(
            request,
            "Ngày rời đi không được trước ngày vào."
        )

        return redirect(
            "chi_tiet_nguoi_o_cung",
            id=nguoi.id
        )

    # =====================================================
    # 4.7. NẾU CHUYỂN SANG ĐANG Ở
    #      PHẢI KIỂM TRA SỨC CHỨA
    # =====================================================

    if trang_thai == "dang_o" and nguoi.trang_thai == "da_roi":

        phong = nguoi.hop_dong.dat_phong.phong

        phong.refresh_from_db()

        if phong.so_nguoi_toi_da <= 0:
            messages.error(request, "Phòng chưa cấu hình sức chứa.")
            return redirect("chi_tiet_nguoi_o_cung", id=nguoi.id)

        if phong.so_cho_con_lai <= 0:

            messages.error(
                request,
                (
                    f"Phòng {phong.so_phong} hiện đã đủ "
                    f"{phong.so_nguoi_toi_da} người. "
                    f"Không thể chuyển {nguoi.ho_ten} về trạng thái đang ở."
                )
            )

            return redirect(
                "chi_tiet_nguoi_o_cung",
                id=nguoi.id
            )

    # =====================================================
    # 4.8. CẬP NHẬT DỮ LIỆU
    # =====================================================

    nguoi.ho_ten = ho_ten
    nguoi.so_dien_thoai = so_dien_thoai
    nguoi.gioi_tinh = gioi_tinh
    nguoi.quan_he = quan_he
    nguoi.cccd = cccd
    nguoi.ghi_chu = ghi_chu
    nguoi.ngay_sinh = ngay_sinh
    nguoi.trang_thai = trang_thai

    # Nếu đang ở thì không có ngày rời
    if trang_thai == "dang_o":

        nguoi.ngay_ra = None

    elif trang_thai == "da_roi":

        # Nếu chuyển sang đã rời mà chưa nhập ngày
        # thì tự lấy ngày hiện tại
        nguoi.ngay_ra = ngay_ra or timezone.localdate()

    else:
        nguoi.ngay_ra = None

    nguoi.save()

    # =====================================================
    # 4.9. NẾU CHUYỂN SANG ĐÃ RỜI
    #      THÌ THU HỒI QUYỀN RA VÀO
    # =====================================================

    if trang_thai == "da_roi":

        thu_hoi_quyen_nguoi_o_cung(
            nguoi,
            ngay_thu_hoi=nguoi.ngay_ra,
            nguon="Admin",
        )

    # =====================================================
    # 4.10. THÔNG BÁO
    # =====================================================

    if trang_thai == "da_roi":

        messages.success(
            request,
            (
                f"Đã cập nhật {nguoi.ho_ten} "
                f"thành trạng thái đã rời phòng."
            )
        )

    else:

        messages.success(
            request,
            f"Đã cập nhật thông tin {nguoi.ho_ten}."
        )

    return redirect(
        "chi_tiet_nguoi_o_cung",
        id=nguoi.id
    )


def _face_load_models():
    if not os.path.exists(FACE_YUNET_MODEL):
        raise FileNotFoundError(
            f"Không tìm thấy YuNet model: {FACE_YUNET_MODEL}"
        )

    if not os.path.exists(FACE_SFACE_MODEL):
        raise FileNotFoundError(
            f"Không tìm thấy SFace model: {FACE_SFACE_MODEL}"
        )

    detector = cv2.FaceDetectorYN.create(
        FACE_YUNET_MODEL,
        "",
        (320, 320),
        0.4,
        0.3,
        5000
    )

    recognizer = cv2.FaceRecognizerSF.create(
        FACE_SFACE_MODEL,
        ""
    )

    return detector, recognizer


def _face_image_from_base64(data):
    if not data:
        return None

    try:
        if "," in data:
            data = data.split(",", 1)[1]

        image_bytes = base64.b64decode(data)

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        return image

    except Exception:
        return None


def _face_detect(image, detector):
    if image is None:
        return None

    h, w = image.shape[:2]

    detector.setInputSize(
        (w, h)
    )

    _, faces = detector.detect(
        image
    )

    if faces is None or len(faces) == 0:
        return None

    if len(faces) > 1:
        raise ValueError(
            "Phát hiện nhiều khuôn mặt. "
            "Vui lòng chỉ để một người trước camera."
        )

    return faces[0]


def _face_feature(image, face, recognizer):
    aligned = recognizer.alignCrop(
        image,
        face
    )

    feature = recognizer.feature(
        aligned
    )

    return feature


def _face_feature_to_text(feature):
    vector = (
        feature
        .flatten()
        .astype(float)
        .tolist()
    )

    return json.dumps(vector)


def _face_feature_from_text(text):
    if not text:
        return None

    try:
        vector = np.array(
            json.loads(text),
            dtype=np.float32
        )

        return vector.reshape(
            1,
            -1
        )

    except Exception:
        return None


def _face_compare(
    feature_1,
    feature_2,
    recognizer
):
    if feature_1 is None or feature_2 is None:
        return 0.0

    score = recognizer.match(
        feature_1,
        feature_2,
        cv2.FaceRecognizerSF_FR_COSINE
    )

    return float(score)


def _smart_room_hop_dong_hop_le_cua_face_profile(fp):
    # Read-only, unique resolution. Never synchronize unrelated historical stays.
    if bool(fp.nguoi_thue_id) == bool(fp.danh_tinh_nguoi_o_cung_id):
        return None
    if fp.danh_tinh_nguoi_o_cung_id:
        resident = (
            fp.danh_tinh_nguoi_o_cung.lich_su_luu_tru
            .select_related("hop_dong__dat_phong__phong")
            .filter(trang_thai="dang_o")
            .order_by("-ngay_vao", "-pk")
            .first()
        )
        if not resident:
            return None
        hd = resident.hop_dong
        return hd if nguoi_o_cung_du_dieu_kien(resident) else None
    today = timezone.localdate()
    candidates = list(HopDong.objects.select_related("dat_phong__phong").filter(
        dat_phong__nguoi_thue_id=fp.nguoi_thue_id, dat_phong__trang_thai="da_duyet",
        trang_thai__in=("dang_hieu_luc", "sap_het_han"),
        ngay_bat_dau__lte=today, ngay_ket_thuc__gte=today,
    )[:2])
    if len(candidates) != 1:
        return None

    hop_dong = candidates[0]
    nguoi_thue = hop_dong.dat_phong.nguoi_thue

    if not nguoi_thue_duoc_xac_thuc_cua(
        nguoi_thue,
        hop_dong=hop_dong,
        today=today,
    ):
        return None

    return hop_dong


def _smart_room_hop_dong_cua_quyen(quyen):
    if not permission_binding_is_valid(quyen):
        return None
    return quyen.hop_dong if quyen_ra_vao_con_hieu_luc(quyen) else None


def _smart_room_user_co_quyen_voi_face_profile(request, fp):
    if la_admin(request):
        return True

    return bool(
        fp.nguoi_thue_id
        and fp.nguoi_thue
        and fp.nguoi_thue.tai_khoan_id == request.user.id
    )


def _face_profile_consent_from_post(request):
    return request.POST.get("dong_y_du_lieu_khuon_mat") in {
        "1",
        "true",
        "on",
        "yes",
    }


def _face_profile_apply_consent(fp):
    if not fp.dong_y_du_lieu_khuon_mat:
        fp.dong_y_du_lieu_khuon_mat = True
        fp.thoi_diem_dong_y_du_lieu_khuon_mat = timezone.now()


def _face_profile_has_consent(fp, request):
    if fp.dong_y_du_lieu_khuon_mat:
        return True

    if _face_profile_consent_from_post(request):
        _face_profile_apply_consent(fp)
        return True

    return False


def face_profile_image(request, id):
    if not request.user.is_authenticated:
        raise Http404("Không tìm thấy ảnh Face ID.")

    fp = get_object_or_404(
        FaceProfile.objects.select_related(
            "nguoi_thue",
            "nguoi_thue__tai_khoan",
            "nguoi_o_cung",
        ),
        id=id,
    )

    if not _smart_room_user_co_quyen_voi_face_profile(request, fp):
        raise Http404("Không tìm thấy ảnh Face ID.")

    if not fp.anh_dai_dien:
        raise Http404("Không tìm thấy ảnh Face ID.")

    content_type = (
        mimetypes.guess_type(fp.anh_dai_dien.name)[0]
        or "application/octet-stream"
    )

    try:
        image_file = fp.anh_dai_dien.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("Không tìm thấy ảnh Face ID.")

    response = FileResponse(image_file, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def face_profile_media(request, path):
    raise Http404("Không tìm thấy ảnh Face ID.")


def _smart_room_dong_bo_quyen_sau_dang_ky(fp, hop_dong, request):
    """Enrollment may reuse only permissions from this exact stay and auto source."""
    with transaction.atomic():
        Phong.objects.select_for_update().get(pk=hop_dong.dat_phong.phong_id)
        hop_dong = HopDong.objects.select_for_update().select_related("dat_phong").get(pk=hop_dong.pk)
        resolved = _smart_room_hop_dong_hop_le_cua_face_profile(fp)
        if not resolved or resolved.pk != hop_dong.pk or not contract_is_current(hop_dong):
            raise ValidationError("Không xác định duy nhất hợp đồng hợp lệ để cấp quyền.")
        resident = None
        if fp.danh_tinh_nguoi_o_cung_id:
            resident = (
                fp.danh_tinh_nguoi_o_cung.lich_su_luu_tru.select_for_update()
                .filter(hop_dong=hop_dong, trang_thai="dang_o").first()
            )
            if not resident:
                raise ValidationError("Danh tinh khong con cu tru hop le tai hop dong nay.")
        subject = dict(nguoi_thue_id=fp.nguoi_thue_id, nguoi_o_cung_id=resident.pk if resident else None)
        kind = "chu_phong" if fp.nguoi_thue_id else "nguoi_o_cung"
        existing = (QuyenRaVao.objects.select_for_update().filter(
            hop_dong=hop_dong, phong_id=hop_dong.dat_phong.phong_id,
            nguon_cap__in=KNOWN_PERMISSION_SOURCES, loai_quyen=kind, **subject,
        ).order_by("-id").first())
        if existing:
            # Enrollment cannot undo a deliberate lock/revocation/expiry or extend manual rights.
            if existing.nguon_cap in AUTO_PERMISSION_SOURCES and existing.trang_thai in ("hoat_dong", "tam_khoa"):
                existing.ngay_ket_thuc = hop_dong.ngay_ket_thuc
                existing.save(update_fields=["ngay_ket_thuc", "ngay_cap_nhat"])
            return existing, False
        if resident:
            # Co-tenant biometrics identify a person; they never create room access.
            raise ValidationError("Nguoi o cung chua co quyen ra vao hop le de dong bo Face ID.")
        return grant_access(
            contract_id=hop_dong.pk,
            tenant_id=fp.nguoi_thue_id,
            resident_id=None,
            source="face_id",
            actor=request.user,
            start_date=timezone.localdate(),
            end_date=hop_dong.ngay_ket_thuc,
        )


def nhan_dien_su_dung_phong(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if la_admin(request):
        return redirect("quan_ly_face_profile")

    nguoi_thue = get_object_or_404(
        NguoiThue,
        tai_khoan=request.user,
        dang_hoat_dong=True,
    )

    # Resolve uniquely without applying lifecycle changes to previous stays.
    hop_dong = _smart_room_hop_dong_hop_le_cua_face_profile(
        FaceProfile(nguoi_thue=nguoi_thue, loai_chu_the="nguoi_thue")
    )

    if not hop_dong:
        hop_dong_gan_nhat = (
            HopDong.objects.select_related("dat_phong")
            .filter(dat_phong__nguoi_thue=nguoi_thue)
            .order_by("-ngay_ket_thuc", "-id")
            .first()
        )
        ly_do = danh_gia_hop_dong(hop_dong_gan_nhat).ly_do
        if nguoi_thue.trang_thai_luu_tru == "da_tra_phong":
            ly_do = "Người thuê đã trả phòng, không còn đủ điều kiện Face ID."
        return render(
            request,
            "core/face_id_unavailable.html",
            {"nguoi_thue": nguoi_thue, "ly_do_khong_du_dieu_kien": ly_do},
        )

    with transaction.atomic():
        fp, _ = FaceProfile.objects.get_or_create(
            nguoi_thue=nguoi_thue,
            defaults={
                "nguoi_o_cung": None,
                "loai_chu_the": "nguoi_thue",
                "anh_dai_dien": None,
                "face_encoding": None,
                "trang_thai": "chua_co_anh",
                "ghi_chu": (
                    "Hồ sơ được tạo từ chức năng "
                    "Đăng ký nhận diện sử dụng phòng."
                ),
            },
        )

    return redirect(
        "chi_tiet_face_profile",
        id=fp.id
    )


def quan_ly_face_profile(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    ds = FaceProfile.objects.select_related(
        "nguoi_thue",
        "danh_tinh_nguoi_o_cung",
        "nguoi_o_cung__hop_dong__dat_phong__phong",
    ).order_by("-ngay_tao")

    trang_thai = request.GET.get("trang_thai", "")
    if trang_thai:
        ds = ds.filter(trang_thai=trang_thai)

    return render(request, "core/quan_ly_face_profile.html", {
        "ds": ds,
        "trang_thai_filter": trang_thai,
    })


def chi_tiet_face_profile(request, id):
    if not request.user.is_authenticated:
        raise Http404("Không tìm thấy hồ sơ Face ID.")

    fp = get_object_or_404(
        FaceProfile.objects.select_related(
            "nguoi_thue",
            "nguoi_thue__tai_khoan",
            "danh_tinh_nguoi_o_cung",
            "nguoi_o_cung",
            "nguoi_o_cung__hop_dong",
            "nguoi_o_cung__hop_dong__dat_phong",
            "nguoi_o_cung__hop_dong__dat_phong__phong",
            "nguoi_o_cung__hop_dong__dat_phong__phong__co_so",
        ),
        id=id
    )

    if not _smart_room_user_co_quyen_voi_face_profile(
        request,
        fp
    ):
        raise Http404("Không tìm thấy hồ sơ Face ID.")

    hop_dong = _smart_room_hop_dong_hop_le_cua_face_profile(fp)

    phong = (
        hop_dong.dat_phong.phong
        if hop_dong
        else None
    )

    quyen_ra_vao = None

    if phong:
        quyen_qs = (
            QuyenRaVao.objects
            .filter(phong=phong, hop_dong=hop_dong, nguon_cap__in=KNOWN_PERMISSION_SOURCES)
            .order_by("-id")
        )

        if fp.nguoi_thue_id:
            quyen_ra_vao = quyen_qs.filter(
                nguoi_thue_id=fp.nguoi_thue_id
            ).first()
        elif fp.danh_tinh_nguoi_o_cung_id:
            quyen_ra_vao = quyen_qs.filter(
                nguoi_o_cung__identity_id=fp.danh_tinh_nguoi_o_cung_id,
                nguoi_o_cung__trang_thai="dang_o",
            ).first()

    dieu_kien_face = du_dieu_kien_dang_ky_face_id(fp, hop_dong)
    chi_thieu_consent = bool(
        fp.nguoi_thue_id
        and hop_dong
        and dieu_kien_face.ly_do == "Chưa ghi nhận consent dữ liệu khuôn mặt."
    )

    context = {
        "fp": fp,
        "hop_dong": hop_dong,
        "phong": phong,
        "quyen_ra_vao": quyen_ra_vao,
        "la_admin_smart_room": la_admin(request),
        "la_chu_ho_so": bool(
            fp.nguoi_thue_id
            and fp.nguoi_thue
            and fp.nguoi_thue.tai_khoan_id == request.user.id
        ),
        "co_the_dang_ky_face": bool(dieu_kien_face.du_dieu_kien or chi_thieu_consent),
        "ly_do_khong_du_dieu_kien_face": dieu_kien_face.ly_do,
    }

    return render(
        request,
        "core/chi_tiet_face_profile.html",
        context
    )


def tao_face_profile(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method == "POST":
        nguoi_thue_id = request.POST.get("nguoi_thue", "").strip()
        nguoi_o_cung_id = request.POST.get("nguoi_o_cung", "").strip()
        loai_chu_the = request.POST.get("loai_chu_the", "").strip()
        ghi_chu = request.POST.get("ghi_chu", "").strip()
        dong_y_du_lieu_khuon_mat = _face_profile_consent_from_post(request)

        co_nguoi_thue = bool(nguoi_thue_id)
        co_nguoi_o_cung = bool(nguoi_o_cung_id)

        # =====================================================
        # KIỂM TRA CHỈ CHỌN 1 CHỦ THỂ
        # =====================================================

        if co_nguoi_thue and co_nguoi_o_cung:
            messages.error(
                request,
                "Chỉ được chọn một người: người thuê chính HOẶC người ở cùng, không cả hai."
            )

        elif not co_nguoi_thue and not co_nguoi_o_cung:
            messages.error(
                request,
                "Phải chọn người thuê chính hoặc người ở cùng."
            )

        elif loai_chu_the not in dict(FaceProfile.LOAI_CHU_THE):
            messages.error(
                request,
                "Loại chủ thể không hợp lệ."
            )

        else:
            # =================================================
            # LẤY ĐỐI TƯỢNG
            # =================================================

            nguoi_thue = (
                get_object_or_404(
                    NguoiThue,
                    id=nguoi_thue_id
                )
                if co_nguoi_thue
                else None
            )

            nguoi_o_cung = (
                get_object_or_404(
                    NguoiOCungPhong,
                    id=nguoi_o_cung_id
                )
                if co_nguoi_o_cung
                else None
            )

            # =================================================
            # KIỂM TRA LOẠI CHỦ THỂ KHỚP VỚI NGƯỜI ĐƯỢC CHỌN
            # =================================================

            if co_nguoi_thue and loai_chu_the != "nguoi_thue":
                messages.error(
                    request,
                    "Bạn đã chọn người thuê chính nên loại chủ thể phải là Người thuê chính."
                )

            elif co_nguoi_o_cung and loai_chu_the != "nguoi_o_cung":
                messages.error(
                    request,
                    "Bạn đã chọn người ở cùng nên loại chủ thể phải là Người ở cùng."
                )

            # =================================================
            # KIỂM TRA ĐÃ CÓ FACE PROFILE CHƯA
            # =================================================

            elif (
                nguoi_thue
                and FaceProfile.objects.filter(
                    nguoi_thue=nguoi_thue
                ).exists()
            ):
                messages.error(
                    request,
                    "Người thuê này đã có FaceProfile."
                )

            elif (
                nguoi_o_cung
                and FaceProfile.objects.filter(
                    danh_tinh_nguoi_o_cung=nguoi_o_cung.identity
                ).exists()
            ):
                messages.error(
                    request,
                    "Người ở cùng này đã có FaceProfile."
                )

            elif nguoi_o_cung:
                # A residency selector cannot supply another adult's personal
                # consent.  The later consent UI will create an identity-bound
                # profile; this legacy form must fail closed meanwhile.
                messages.error(request, "Nguoi o cung can dong y sinh trac hoc ca nhan do Admin ghi nhan.")

            else:
                # =================================================
                # TẠO PROFILE TRƯỚC
                #
                # Chưa có ảnh vì ảnh sẽ được lấy trực tiếp
                # từ webcam ở bước đăng ký Face ID.
                # =================================================

                if not dong_y_du_lieu_khuon_mat:
                    messages.error(
                        request,
                        "Cần ghi nhận đồng ý sử dụng dữ liệu khuôn mặt trước khi tạo FaceProfile."
                    )
                    return redirect("tao_face_profile")

                fp = FaceProfile.objects.create(
                    nguoi_thue=nguoi_thue,
                    danh_tinh_nguoi_o_cung=None,
                    nguoi_o_cung=None,
                    loai_chu_the=loai_chu_the,
                    anh_dai_dien=None,
                    face_encoding=None,
                    dong_y_du_lieu_khuon_mat=True,
                    thoi_diem_dong_y_du_lieu_khuon_mat=timezone.now(),
                    trang_thai="chua_co_anh",
                    ghi_chu=ghi_chu,
                )

                messages.success(
                    request,
                    "Đã tạo hồ sơ. Hãy đăng ký Face ID bằng camera."
                )

                # =================================================
                # CHUYỂN THẲNG SANG CHI TIẾT
                # ĐỂ ĐĂNG KÝ FACE ID BẰNG WEBCAM
                # =================================================

                return redirect(
                    "chi_tiet_face_profile",
                    id=fp.id
                )

    # =========================================================
    # DANH SÁCH NGƯỜI ĐỂ CHỌN
    # =========================================================

    nguoi_thue_ds = (
        NguoiThue.objects
        .filter(dang_hoat_dong=True)
        .order_by("ho_ten")
    )

    nguoi_o_cung_ds = (
        NguoiOCungPhong.objects
        .filter(trang_thai="dang_o")
        .select_related(
            "hop_dong__dat_phong__phong"
        )
        .order_by("ho_ten")
    )

    return render(
        request,
        "core/tao_face_profile.html",
        {
            "nguoi_thue_ds": nguoi_thue_ds,
            "nguoi_o_cung_ds": nguoi_o_cung_ds,
        }
    )


def face_id_dang_ky(request, id):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "success": False,
                "message": "Bạn chưa đăng nhập."
            },
            status=401
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Phương thức không hợp lệ."
            },
            status=405
        )

    try:
        with transaction.atomic():
            fp = get_object_or_404(
                FaceProfile.objects
                .select_for_update()
                .select_related(
                    "nguoi_thue",
                    "nguoi_thue__tai_khoan",
                    "nguoi_o_cung",
                    "nguoi_o_cung__hop_dong",
                    "nguoi_o_cung__hop_dong__dat_phong",
                    "nguoi_o_cung__hop_dong__dat_phong__phong",
                ),
                id=id
            )

            # -----------------------------------------------------
            # 1. CHỐNG IDOR / KIỂM TRA QUYỀN
            # -----------------------------------------------------

            if not _smart_room_user_co_quyen_voi_face_profile(
                request,
                fp
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Bạn không có quyền đăng ký "
                            "hồ sơ nhận diện này."
                        )
                    },
                    status=403
                )

            if fp.trang_thai == "bi_vo_hieu":
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Hồ sơ nhận diện đang bị vô hiệu. "
                            "Vui lòng liên hệ quản trị viên."
                        )
                    },
                    status=403
                )

            # -----------------------------------------------------
            # 2. KIỂM TRA HỢP ĐỒNG / PHÒNG
            # -----------------------------------------------------

            hop_dong = _smart_room_hop_dong_hop_le_cua_face_profile(
                fp
            )

            if not hop_dong:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Không xác định duy nhất hợp đồng đang hiệu lực. "
                            "Bạn chỉ có thể đăng ký Face ID khi "
                            "đang có quyền sử dụng phòng hợp lệ."
                        )
                    },
                    status=403
                )

            if not _face_profile_has_consent(fp, request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Cần xác nhận đồng ý sử dụng dữ liệu khuôn mặt "
                            "trước khi đăng ký Face ID."
                        )
                    },
                    status=400
                )

            dieu_kien_face = du_dieu_kien_dang_ky_face_id(fp, hop_dong)
            if not dieu_kien_face.du_dieu_kien:
                return JsonResponse(
                    {
                        "success": False,
                        "message": dieu_kien_face.ly_do,
                    },
                    status=403,
                )

            phong = hop_dong.dat_phong.phong

            # -----------------------------------------------------
            # 3. NHẬN VÀ ĐỌC FRAME
            # -----------------------------------------------------

            image_data = request.POST.get(
                "image",
                ""
            ).strip()

            if not image_data:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Không nhận được hình ảnh từ camera."
                        )
                    },
                    status=400
                )

            image = _face_image_from_base64(image_data)

            if image is None:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Không thể đọc hình ảnh từ camera."
                        )
                    },
                    status=400
                )

            if len(image.shape) < 2:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Khung hình camera không hợp lệ."
                    },
                    status=400
                )

            height, width = image.shape[:2]

            if width < 480 or height < 360:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Độ phân giải camera quá thấp. "
                            "Vui lòng dùng khung hình tối thiểu 480×360."
                        )
                    },
                    status=400
                )

            # -----------------------------------------------------
            # 4. KIỂM TRA ÁNH SÁNG
            # -----------------------------------------------------

            gray = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY
            )

            do_sang = float(gray.mean())

            if do_sang < 45:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Khuôn hình quá tối. "
                            "Vui lòng tăng ánh sáng phía trước khuôn mặt."
                        ),
                        "quality": {
                            "brightness": round(do_sang, 1)
                        },
                    },
                    status=400
                )

            if do_sang > 225:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Khuôn hình quá sáng. "
                            "Vui lòng tránh nguồn sáng chiếu trực tiếp "
                            "vào camera."
                        ),
                        "quality": {
                            "brightness": round(do_sang, 1)
                        },
                    },
                    status=400
                )

            # -----------------------------------------------------
            # 5. DETECT + FEATURE
            # -----------------------------------------------------

            detector, recognizer = _face_load_models()

            face = _face_detect(
                image,
                detector
            )

            if face is None:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Không phát hiện được khuôn mặt. "
                            "Hãy nhìn thẳng, giữ khuôn mặt ở giữa "
                            "khung và thử lại."
                        )
                    },
                    status=400
                )

            # YuNet trả bbox ở 4 phần tử đầu.
            try:
                face_w = float(face[2])
                face_h = float(face[3])
                ty_le_khuon_mat = (
                    (face_w * face_h)
                    / float(width * height)
                )
            except Exception:
                ty_le_khuon_mat = 0.0

            if ty_le_khuon_mat and ty_le_khuon_mat < 0.06:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Khuôn mặt đang quá xa camera. "
                            "Vui lòng tiến gần hơn một chút."
                        ),
                        "quality": {
                            "face_ratio": round(
                                ty_le_khuon_mat,
                                4
                            )
                        },
                    },
                    status=400
                )

            feature = _face_feature(
                image,
                face,
                recognizer
            )

            encoding_text = _face_feature_to_text(feature)

            # -----------------------------------------------------
            # 6. CHỐNG DÙNG CÙNG MỘT KHUÔN MẶT CHO HỒ SƠ KHÁC
            # -----------------------------------------------------

            FACE_THRESHOLD = 0.363

            profile_khac = (
                FaceProfile.objects
                .filter(trang_thai="da_xac_thuc")
                .exclude(id=fp.id)
                .only(
                    "id",
                    "face_encoding",
                )
            )

            for fp_khac in profile_khac:
                saved_feature = _face_feature_from_text(
                    fp_khac.face_encoding
                )

                if saved_feature is None:
                    continue

                score = _face_compare(
                    feature,
                    saved_feature,
                    recognizer
                )

                if score >= FACE_THRESHOLD:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": (
                                "Khuôn mặt này đã được đăng ký "
                                "cho một hồ sơ khác trong hệ thống."
                            )
                        },
                        status=409
                    )

            # -----------------------------------------------------
            # 7. LƯU ẢNH + ENCODING
            # -----------------------------------------------------

            trang_thai_cu = fp.trang_thai
            co_encoding_cu = bool(fp.face_encoding)

            ret, buffer = cv2.imencode(
                ".jpg",
                image
            )

            if not ret:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Không thể tạo ảnh đăng ký từ camera."
                        )
                    },
                    status=500
                )

            from django.core.files.base import ContentFile

            fp.face_encoding = encoding_text
            fp.trang_thai = "da_xac_thuc"

            fp.anh_dai_dien.save(
                f"face_id_{fp.id}.jpg",
                ContentFile(buffer.tobytes()),
                save=False
            )

            fp.save()

            # -----------------------------------------------------
            # 8. TỰ ĐỒNG BỘ QUYỀN ĐÚNG PHÒNG
            # -----------------------------------------------------

            quyen, quyen_moi = (
                _smart_room_dong_bo_quyen_sau_dang_ky(
                    fp,
                    hop_dong,
                    request
                )
            )

            # -----------------------------------------------------
            # 9. THÔNG BÁO CHO NGƯỜI THUÊ CHÍNH
            # -----------------------------------------------------

            thong_bao_moi = None

            if fp.nguoi_thue_id:
                thong_bao_moi = ThongBao.objects.create(
                    nguoi_thue=fp.nguoi_thue,
                    tieu_de="Đăng ký nhận diện sử dụng phòng thành công",
                    noi_dung=(
                        f"Face ID của bạn đã được đăng ký cho "
                        f"phòng {phong.so_phong}. "
                        f"Quyền ra vào hiện ở trạng thái "
                        f"{quyen.get_trang_thai_display()} và có hiệu lực "
                        f"đến {quyen.ngay_ket_thuc.strftime('%d/%m/%Y') if quyen.ngay_ket_thuc else 'không giới hạn'}."
                    ),
                    loai="he_thong",
                    muc_do="binh_thuong",
                )

            # -----------------------------------------------------
            # 10. AUDIT
            # -----------------------------------------------------

            ghi_nhat_ky(
                request=request,
                hanh_dong=(
                    "Đăng ký Face ID"
                    if not co_encoding_cu
                    else "Cập nhật Face ID"
                ),
                module="Smart Room",
                doi_tuong="FaceProfile",
                doi_tuong_id=fp.id,
                tieu_de=(
                    f"Đăng ký nhận diện phòng "
                    f"{phong.so_phong}"
                ),
                noi_dung=(
                    f"{request.user.username} đăng ký/cập nhật "
                    f"Face ID cho hồ sơ #{fp.id}; "
                    f"phòng {phong.so_phong}; "
                    f"hợp đồng {hop_dong.so_hop_dong}; "
                    f"quyền ra vào #{quyen.id}."
                ),
                du_lieu_cu={
                    "trang_thai": trang_thai_cu,
                    "co_face_encoding": co_encoding_cu,
                },
                du_lieu_moi={
                    "trang_thai": fp.trang_thai,
                    "phong": phong.so_phong,
                    "hop_dong": hop_dong.so_hop_dong,
                    "quyen_ra_vao_id": quyen.id,
                    "quyen_moi": quyen_moi,
                    "thong_bao_id": (
                        thong_bao_moi.id
                        if thong_bao_moi
                        else None
                    ),
                    "brightness": round(do_sang, 1),
                    "face_ratio": round(
                        ty_le_khuon_mat,
                        4
                    ),
                },
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": (
                        "Đăng ký Face ID thành công. "
                        "Quyền sử dụng phòng đã được đồng bộ."
                    ),
                    "face_profile_id": fp.id,
                    "status": fp.get_trang_thai_display(),
                    "phong": phong.so_phong,
                    "co_so": phong.co_so.ten_co_so,
                    "hop_dong": hop_dong.so_hop_dong,
                    "quyen_id": quyen.id,
                    "quyen_status": (
                        quyen.get_trang_thai_display()
                    ),
                    "quyen_moi": quyen_moi,
                    "quality": {
                        "brightness": round(do_sang, 1),
                        "face_ratio": round(
                            ty_le_khuon_mat,
                            4
                        ),
                    },
                }
            )

    except Http404:
        return JsonResponse(
            {
                "success": False,
                "message": "Không tìm thấy hồ sơ Face ID."
            },
            status=404
        )

    except ValueError as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": (
                    f"Lỗi xử lý Face ID: {str(e)}"
                )
            },
            status=500
        )


def trang_xac_thuc_face_id(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    # Chỉ cần các phòng có ít nhất một quyền hoạt động/tạm khóa
    # vẫn hiển thị phòng theo hệ thống để Admin có thể vận hành terminal.
    phong_ds = (
        Phong.objects
        .select_related("co_so")
        .order_by(
            "co_so",
            "so_phong"
        )
    )

    return render(
        request,
        "core/xac_thuc_face_id.html",
        {
            "phong_ds": phong_ds,
        }
    )


def _quyen_co_hop_dong_hien_tai(quyen):
    return eligible_permissions(QuyenRaVao.objects.filter(pk=quyen.pk)).exists()


def face_id_xac_thuc(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "success": False,
                "message": "Bạn chưa đăng nhập."
            },
            status=401
        )

    if not la_admin(request):
        return JsonResponse(
            {
                "success": False,
                "message": (
                    "Bạn không có quyền vận hành "
                    "hệ thống xác thực ra vào."
                )
            },
            status=403
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Phương thức không hợp lệ."
            },
            status=405
        )

    def ghi_log_face_id(
        *,
        phong,
        loai_su_kien,
        ket_qua,
        ly_do,
        quyen=None,
        nguoi_thue=None,
        nguoi_o_cung=None,
        ten_nguoi="",
        score=None,
    ):
        """
        Ghi lịch sử cho cả lượt được phép và bị từ chối.

        Kết quả được lưu bằng field cấu trúc; nhãn trong ghi_chu chỉ còn
        phục vụ khả năng đọc và tương thích lịch sử. Không hard-delete log.
        """

        if ket_qua == "cho_phep":
            nhan = "[CHO PHÉP]"
        else:
            nhan = "[TỪ CHỐI]"

        chi_tiet = f"{nhan} Face ID - {ly_do}"

        if score is not None:
            chi_tiet += f" Độ tương đồng: {score:.4f}."

        return LichSuRaVao.objects.create(
            quyen_ra_vao=quyen,
            phong=phong,
            nguoi_thue=nguoi_thue,
            nguoi_o_cung=nguoi_o_cung,
            ten_nguoi=ten_nguoi or "",
            loai_su_kien=loai_su_kien,
            nguon="camera",
            ket_qua=ket_qua,
            thoi_diem=timezone.now(),
            ghi_chu=chi_tiet,
        )

    try:
        image_data = request.POST.get(
            "image",
            ""
        ).strip()

        phong_id = request.POST.get(
            "phong",
            ""
        ).strip()

        loai_su_kien = request.POST.get(
            "loai_su_kien",
            "vao"
        ).strip()

        if not image_data:
            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Không nhận được hình ảnh từ camera."
                    ),
                    "access": "denied",
                },
                status=400
            )

        if not phong_id:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Vui lòng chọn phòng.",
                    "access": "denied",
                },
                status=400
            )

        if loai_su_kien not in [
            "vao",
            "ra",
        ]:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Loại sự kiện không hợp lệ.",
                    "access": "denied",
                },
                status=400
            )

        phong = get_object_or_404(
            Phong.objects.select_related("co_so"),
            id=phong_id
        )

        image = _face_image_from_base64(image_data)

        if image is None:
            ghi_log_face_id(
                phong=phong,
                loai_su_kien=loai_su_kien,
                ket_qua="tu_choi",
                ly_do="Không thể đọc hình ảnh từ camera.",
            )

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Không thể đọc hình ảnh từ camera."
                    ),
                    "phong": phong.so_phong,
                    "access": "denied",
                },
                status=400
            )

        detector, recognizer = _face_load_models()

        face = _face_detect(
            image,
            detector
        )

        if face is None:
            ghi_log_face_id(
                phong=phong,
                loai_su_kien=loai_su_kien,
                ket_qua="tu_choi",
                ly_do=(
                    "Không phát hiện khuôn mặt trong khung hình."
                ),
            )

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Không phát hiện khuôn mặt. "
                        "Vui lòng đưa khuôn mặt vào giữa camera."
                    ),
                    "phong": phong.so_phong,
                    "access": "denied",
                },
                status=400
            )

        feature = _face_feature(
            image,
            face,
            recognizer
        )

        # =====================================================
        # CHỈ LẤY QUYỀN HỢP LỆ CỦA ĐÚNG PHÒNG
        # =====================================================

        ngay_hom_nay = timezone.localdate()

        quyen_hop_le = (
            eligible_permissions(QuyenRaVao.objects.all())
            .filter(
                phong=phong,
                trang_thai="hoat_dong",
                ngay_bat_dau__lte=ngay_hom_nay,
            )
            .filter(
                Q(ngay_ket_thuc__isnull=True)
                | Q(ngay_ket_thuc__gte=ngay_hom_nay)
            )
            .select_related(
                "nguoi_thue",
                "nguoi_o_cung",
            )
        )

        nguoi_thue_ids = list(
            quyen_hop_le
            .exclude(nguoi_thue_id__isnull=True)
            .values_list(
                "nguoi_thue_id",
                flat=True
            )
        )

        nguoi_o_cung_ids = list(
            quyen_hop_le
            .exclude(nguoi_o_cung_id__isnull=True)
            .values_list(
                "nguoi_o_cung_id",
                flat=True
            )
        )
        danh_tinh_nguoi_o_cung_ids = list(
            NguoiOCungPhong.objects.filter(pk__in=nguoi_o_cung_ids)
            .values_list("identity_id", flat=True)
        )

        # =====================================================
        # PHÒNG KHÔNG CÓ QUYỀN FACE ID ĐANG HOẠT ĐỘNG
        # =====================================================

        if (
            not nguoi_thue_ids
            and not nguoi_o_cung_ids
        ):
            ghi_log_face_id(
                phong=phong,
                loai_su_kien=loai_su_kien,
                ket_qua="tu_choi",
                ly_do=(
                    "Phòng không có quyền Face ID "
                    "đang hoạt động."
                ),
            )

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        f"Phòng {phong.so_phong} hiện không có "
                        "quyền ra vào Face ID nào đang hoạt động."
                    ),
                    "phong": phong.so_phong,
                    "access": "denied",
                },
                status=403
            )

        # =====================================================
        # CHỈ LẤY HỒ SƠ FACE ĐÃ XÁC THỰC
        # VÀ THỰC SỰ CÓ QUYỀN Ở PHÒNG ĐANG CHỌN
        # =====================================================

        face_profiles = (
            FaceProfile.objects
            .filter(trang_thai="da_xac_thuc")
            .filter(dong_y_du_lieu_khuon_mat=True)
            .filter(
                Q(nguoi_thue_id__in=nguoi_thue_ids)
                | Q(
                    danh_tinh_nguoi_o_cung_id__in=danh_tinh_nguoi_o_cung_ids
                )
            )
            .select_related(
                "nguoi_thue",
                "danh_tinh_nguoi_o_cung",
                "nguoi_o_cung",
            )
        )

        if not face_profiles.exists():
            ghi_log_face_id(
                phong=phong,
                loai_su_kien=loai_su_kien,
                ket_qua="tu_choi",
                ly_do=(
                    "Không có hồ sơ Face ID đã xác thực "
                    "được phép sử dụng phòng này."
                ),
            )

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Không có Face ID đã xác thực nào "
                        "đang được phép sử dụng phòng này."
                    ),
                    "phong": phong.so_phong,
                    "access": "denied",
                },
                status=403
            )

        best_profile = None
        best_score = -1.0

        for fp in face_profiles:
            if fp.danh_tinh_nguoi_o_cung_id and not has_effective_consent(
                fp.danh_tinh_nguoi_o_cung
            ):
                continue
            saved_feature = _face_feature_from_text(
                fp.face_encoding
            )

            if saved_feature is None:
                continue

            score = _face_compare(
                feature,
                saved_feature,
                recognizer
            )

            if score > best_score:
                best_score = score
                best_profile = fp

        FACE_THRESHOLD = 0.363

        # =====================================================
        # KHÔNG NHẬN DIỆN ĐƯỢC / KHÔNG ĐỦ NGƯỠNG
        # Không gán danh tính khi độ tin cậy chưa đạt ngưỡng.
        # =====================================================

        if (
            best_profile is None
            or best_score < FACE_THRESHOLD
        ):
            ghi_log_face_id(
                phong=phong,
                loai_su_kien=loai_su_kien,
                ket_qua="tu_choi",
                ly_do=(
                    "Không nhận diện được khuôn mặt "
                    "hoặc khuôn mặt không thuộc người "
                    "có quyền tại phòng."
                ),
                score=(
                    best_score
                    if best_score >= 0
                    else None
                ),
            )

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Không nhận diện được khuôn mặt "
                        "hoặc người này không có quyền "
                        f"sử dụng phòng {phong.so_phong}."
                    ),
                    "score": (
                        round(best_score, 4)
                        if best_score >= 0
                        else 0
                    ),
                    "phong": phong.so_phong,
                    "access": "denied",
                },
                status=403
            )

        # =====================================================
        # ĐÃ NHẬN DIỆN ĐƯỢC DANH TÍNH
        # =====================================================

        nguoi_thue = best_profile.nguoi_thue
        nguoi_o_cung = best_profile.nguoi_o_cung

        if nguoi_thue:
            quyen = (
                quyen_hop_le
                .filter(nguoi_thue=nguoi_thue)
                .order_by("-id")
                .first()
            )

            ten_nguoi = nguoi_thue.ho_ten

        else:
            quyen = (
                quyen_hop_le
                .filter(
                    nguoi_o_cung__identity_id=best_profile.danh_tinh_nguoi_o_cung_id,
                    nguoi_o_cung__trang_thai="dang_o",
                )
                .order_by("-id")
                .first()
            )
            nguoi_o_cung = quyen.nguoi_o_cung if quyen else None
            ten_nguoi = nguoi_o_cung.ho_ten if nguoi_o_cung else "Nguoi o cung"

        # =====================================================
        # TRƯỜNG HỢP QUYỀN BIẾN ĐỘNG TRONG LÚC XÁC THỰC
        # =====================================================

        if not quyen or not _quyen_co_hop_dong_hien_tai(quyen):
            ghi_log_face_id(
                phong=phong,
                loai_su_kien=loai_su_kien,
                ket_qua="tu_choi",
                ly_do=(
                    "Đã nhận diện đúng người nhưng "
                    "quyền ra vào không còn hợp lệ."
                ),
                nguoi_thue=nguoi_thue,
                nguoi_o_cung=nguoi_o_cung,
                ten_nguoi=ten_nguoi,
                score=best_score,
            )

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        f"Đã nhận diện {ten_nguoi} nhưng "
                        f"không còn quyền hợp lệ tại phòng "
                        f"{phong.so_phong}."
                    ),
                    "ten_nguoi": ten_nguoi,
                    "phong": phong.so_phong,
                    "score": round(best_score, 4),
                    "access": "denied",
                },
                status=403
            )

        # =====================================================
        # XÁC THỰC THÀNH CÔNG
        # GHI LỊCH SỬ CHO PHÉP
        # =====================================================

        ghi_log_face_id(
            phong=phong,
            loai_su_kien=loai_su_kien,
            ket_qua="cho_phep",
            ly_do=(
                "Khuôn mặt hợp lệ và quyền ra vào "
                "đang hoạt động."
            ),
            quyen=quyen,
            nguoi_thue=nguoi_thue,
            nguoi_o_cung=nguoi_o_cung,
            ten_nguoi=ten_nguoi,
            score=best_score,
        )

        hanh_dong = (
            "vào phòng"
            if loai_su_kien == "vao"
            else "ra khỏi phòng"
        )

        return JsonResponse(
            {
                "success": True,
                "message": (
                    f"{ten_nguoi} được phép {hanh_dong} "
                    f"{phong.so_phong}."
                ),
                "ten_nguoi": ten_nguoi,
                "phong": phong.so_phong,
                "co_so": phong.co_so.ten_co_so,
                "loai_quyen": quyen.get_loai_quyen_display(),
                "loai_su_kien": loai_su_kien,
                "score": round(best_score, 4),
                "access": "granted",
                "quyen_den_ngay": (
                    quyen.ngay_ket_thuc.strftime(
                        "%d/%m/%Y"
                    )
                    if quyen.ngay_ket_thuc
                    else ""
                ),
            }
        )

    except Http404:
        return JsonResponse(
            {
                "success": False,
                "message": "Không tìm thấy phòng cần xác thực.",
                "access": "error",
            },
            status=404
        )

    except ValueError as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e),
                "access": "denied",
            },
            status=400
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": (
                    f"Lỗi xử lý Face ID: {str(e)}"
                ),
                "access": "error",
            },
            status=500
        )


def xu_ly_face_profile(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method != "POST":
        return redirect(
            "chi_tiet_face_profile",
            id=id
        )

    with transaction.atomic():
        fp = get_object_or_404(
            FaceProfile.objects
            .select_for_update()
            .select_related(
                "nguoi_thue",
                "nguoi_o_cung",
            ),
            id=id
        )

        hanh_dong = request.POST.get(
            "hanh_dong",
            ""
        ).strip()

        trang_thai_cu = fp.trang_thai
        ghi_chu_cu = fp.ghi_chu

        if hanh_dong == "cap_nhat_anh":
            anh = request.FILES.get(
                "anh_dai_dien"
            )

            if not _face_profile_has_consent(fp, request):
                messages.error(
                    request,
                    "Cần ghi nhận đồng ý sử dụng dữ liệu khuôn mặt trước khi cập nhật ảnh FaceProfile."
                )
                return redirect(
                    "chi_tiet_face_profile",
                    id=fp.id
                )

            if not anh:
                messages.error(
                    request,
                    "Vui lòng chọn file ảnh."
                )
                return redirect(
                    "chi_tiet_face_profile",
                    id=fp.id
                )

            fp.anh_dai_dien = anh

            # Ảnh upload thủ công KHÔNG đồng nghĩa đã xác thực AI.
            if fp.trang_thai == "chua_co_anh":
                fp.trang_thai = "co_anh"

            fp.save()

            ghi_nhat_ky(
                request=request,
                hanh_dong="Cập nhật ảnh",
                module="Smart Room",
                doi_tuong="FaceProfile",
                doi_tuong_id=fp.id,
                tieu_de=f"Cập nhật ảnh FaceProfile #{fp.id}",
                noi_dung=(
                    f"Admin {request.user.username} "
                    f"cập nhật ảnh FaceProfile #{fp.id}."
                ),
                du_lieu_cu={
                    "trang_thai": trang_thai_cu,
                },
                du_lieu_moi={
                    "trang_thai": fp.trang_thai,
                    "co_anh": bool(fp.anh_dai_dien),
                },
            )

            messages.success(
                request,
                "Đã cập nhật ảnh hồ sơ khuôn mặt."
            )

        elif hanh_dong == "cap_nhat_trang_thai":
            trang_thai_moi = request.POST.get(
                "trang_thai",
                ""
            ).strip()

            ghi_chu_moi = request.POST.get(
                "ghi_chu",
                ""
            ).strip()

            if trang_thai_moi not in dict(
                FaceProfile.TRANG_THAI
            ):
                messages.error(
                    request,
                    "Trạng thái hồ sơ không hợp lệ."
                )

            elif (
                trang_thai_moi == "da_xac_thuc"
                and not fp.face_encoding
            ):
                messages.error(
                    request,
                    (
                        "Không thể chuyển sang Đã xác thực khi "
                        "hồ sơ chưa có dữ liệu Face ID. "
                        "Hãy đăng ký bằng camera."
                    )
                )

            elif (
                trang_thai_moi == "da_xac_thuc"
                and not _face_profile_has_consent(fp, request)
            ):
                messages.error(
                    request,
                    "Cần ghi nhận đồng ý sử dụng dữ liệu khuôn mặt trước khi xác thực FaceProfile."
                )

            else:
                fp.trang_thai = trang_thai_moi
                fp.ghi_chu = ghi_chu_moi
                update_fields = [
                    "trang_thai",
                    "ghi_chu",
                ]
                if fp.dong_y_du_lieu_khuon_mat:
                    update_fields.extend([
                        "dong_y_du_lieu_khuon_mat",
                        "thoi_diem_dong_y_du_lieu_khuon_mat",
                    ])
                fp.save(update_fields=update_fields)

                so_quyen_thu_hoi = 0

                if trang_thai_moi == "bi_vo_hieu":
                    quyen_qs = QuyenRaVao.objects.filter(hop_dong__isnull=False, nguon_cap__in=KNOWN_PERMISSION_SOURCES).exclude(
                        trang_thai="bi_thu_hoi"
                    )

                    if fp.nguoi_thue_id:
                        quyen_qs = quyen_qs.filter(
                            nguoi_thue_id=fp.nguoi_thue_id
                        )
                    else:
                        quyen_qs = quyen_qs.filter(
                            nguoi_o_cung_id=fp.nguoi_o_cung_id
                        )

                    so_quyen_thu_hoi = quyen_qs.update(
                        trang_thai="bi_thu_hoi",
                        ngay_ket_thuc=timezone.localdate(),
                    )

                ghi_nhat_ky(
                    request=request,
                    hanh_dong="Cập nhật trạng thái",
                    module="Smart Room",
                    doi_tuong="FaceProfile",
                    doi_tuong_id=fp.id,
                    tieu_de=(
                        f"Cập nhật FaceProfile #{fp.id}"
                    ),
                    noi_dung=(
                        f"Admin {request.user.username} cập nhật "
                        f"FaceProfile #{fp.id} từ "
                        f"{trang_thai_cu} sang "
                        f"{fp.trang_thai}. "
                        f"Thu hồi {so_quyen_thu_hoi} quyền."
                    ),
                    du_lieu_cu={
                        "trang_thai": trang_thai_cu,
                        "ghi_chu": ghi_chu_cu,
                    },
                    du_lieu_moi={
                        "trang_thai": fp.trang_thai,
                        "ghi_chu": fp.ghi_chu,
                        "so_quyen_thu_hoi": (
                            so_quyen_thu_hoi
                        ),
                    },
                )

                messages.success(
                    request,
                    "Đã cập nhật trạng thái hồ sơ."
                )

        elif hanh_dong == "xoa":
            # Không xóa dữ liệu sinh trắc học/lịch sử liên kết.
            fp.trang_thai = "bi_vo_hieu"

            ghi_chu_bo_sung = (
                f"Vô hiệu bởi Admin "
                f"{request.user.username} "
                f"lúc {timezone.localtime().strftime('%d/%m/%Y %H:%M')}."
            )

            fp.ghi_chu = (
                f"{fp.ghi_chu}\n{ghi_chu_bo_sung}".strip()
            )

            fp.save(
                update_fields=[
                    "trang_thai",
                    "ghi_chu",
                ]
            )

            quyen_qs = QuyenRaVao.objects.filter(hop_dong__isnull=False, nguon_cap__in=KNOWN_PERMISSION_SOURCES).exclude(
                trang_thai="bi_thu_hoi"
            )

            if fp.nguoi_thue_id:
                quyen_qs = quyen_qs.filter(
                    nguoi_thue_id=fp.nguoi_thue_id
                )
            else:
                quyen_qs = quyen_qs.filter(
                    nguoi_o_cung_id=fp.nguoi_o_cung_id
                )

            so_quyen_thu_hoi = quyen_qs.update(
                trang_thai="bi_thu_hoi",
                ngay_ket_thuc=timezone.localdate(),
            )

            ghi_nhat_ky(
                request=request,
                hanh_dong="Vô hiệu",
                module="Smart Room",
                doi_tuong="FaceProfile",
                doi_tuong_id=fp.id,
                tieu_de=(
                    f"Vô hiệu FaceProfile #{fp.id}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} vô hiệu "
                    f"FaceProfile #{fp.id}; thu hồi "
                    f"{so_quyen_thu_hoi} quyền ra vào."
                ),
                du_lieu_cu={
                    "trang_thai": trang_thai_cu,
                    "ghi_chu": ghi_chu_cu,
                },
                du_lieu_moi={
                    "trang_thai": fp.trang_thai,
                    "ghi_chu": fp.ghi_chu,
                    "so_quyen_thu_hoi": (
                        so_quyen_thu_hoi
                    ),
                },
            )

            messages.success(
                request,
                (
                    "Đã vô hiệu hồ sơ và thu hồi quyền ra vào. "
                    "Dữ liệu lịch sử được giữ nguyên."
                )
            )

        else:
            messages.error(
                request,
                "Hành động không hợp lệ."
            )

    return redirect(
        "chi_tiet_face_profile",
        id=fp.id
    )


@require_GET
def quyen_va_lich_su_ra_vao_cua_toi(request):
    """Read-only, owner-scoped access status and history for a principal tenant."""
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if la_admin(request):
        return redirect("dashboard_admin")

    nguoi_thue = get_object_or_404(NguoiThue, tai_khoan=request.user)

    quyen_goc = (
        QuyenRaVao.objects
        .filter(nguoi_thue=nguoi_thue)
        .select_related(
            "phong__co_so",
            "hop_dong__dat_phong__phong",
            "nguoi_thue",
        )
        .order_by("-ngay_tao", "-id")
    )
    lich_su_goc = (
        LichSuRaVao.objects
        .filter(nguoi_thue=nguoi_thue)
        .select_related("phong__co_so", "quyen_ra_vao")
        .order_by("-thoi_diem", "-id")
    )

    trang_thai = request.GET.get("trang_thai", "").strip()
    phong_id = request.GET.get("phong", "").strip()
    loai = request.GET.get("loai", "").strip()
    nguon = request.GET.get("nguon", "").strip()
    ket_qua = request.GET.get("ket_qua", "").strip()
    tu_ngay_raw = request.GET.get("tu_ngay", "").strip()
    den_ngay_raw = request.GET.get("den_ngay", "").strip()

    trang_thai_hop_le = {value for value, _label in QuyenRaVao.TRANG_THAI}
    loai_hop_le = {value for value, _label in LichSuRaVao.LOAI_SU_KIEN}
    nguon_hop_le = {value for value, _label in LichSuRaVao.NGUON_DU_LIEU}
    ket_qua_hop_le = {value for value, _label in LichSuRaVao.KET_QUA}

    quyen = quyen_goc
    lich_su = lich_su_goc
    if trang_thai in trang_thai_hop_le:
        quyen = quyen.filter(trang_thai=trang_thai)
    if phong_id.isdigit():
        quyen = quyen.filter(phong_id=phong_id)
        lich_su = lich_su.filter(phong_id=phong_id)
    if loai in loai_hop_le:
        lich_su = lich_su.filter(loai_su_kien=loai)
    if nguon in nguon_hop_le:
        lich_su = lich_su.filter(nguon=nguon)
    if ket_qua in ket_qua_hop_le:
        lich_su = lich_su.filter(ket_qua=ket_qua)

    tu_ngay = parse_date(tu_ngay_raw)
    den_ngay = parse_date(den_ngay_raw)
    mui_gio = timezone.get_current_timezone()
    if tu_ngay:
        bat_dau = timezone.make_aware(datetime.combine(tu_ngay, time.min), mui_gio)
        lich_su = lich_su.filter(thoi_diem__gte=bat_dau)
    if den_ngay:
        sau_ket_thuc = timezone.make_aware(
            datetime.combine(den_ngay + timedelta(days=1), time.min),
            mui_gio,
        )
        lich_su = lich_su.filter(thoi_diem__lt=sau_ket_thuc)

    danh_sach_quyen = list(quyen)
    for item in danh_sach_quyen:
        item.danh_gia_hieu_luc = danh_gia_quyen_ra_vao(item)

    page_obj = Paginator(lich_su, 20).get_page(request.GET.get("page"))
    query_string = request.GET.copy()
    query_string.pop("page", None)

    phong_ds = (
        Phong.objects
        .filter(
            Q(quyen_ra_vao__nguoi_thue=nguoi_thue)
            | Q(lich_su_ra_vao__nguoi_thue=nguoi_thue)
        )
        .select_related("co_so")
        .distinct()
        .order_by("co_so__ten_co_so", "so_phong")
    )

    return render(request, "core/quyen_va_lich_su_ra_vao_cua_toi.html", {
        "nguoi_thue": nguoi_thue,
        "danh_sach_quyen": danh_sach_quyen,
        "lich_su": page_obj.object_list,
        "page_obj": page_obj,
        "phong_ds": phong_ds,
        "tong_quyen": quyen_goc.count(),
        "quyen_hieu_luc": eligible_permissions(quyen_goc).count(),
        "tong_lich_su": lich_su_goc.count(),
        "trang_thai_filter": trang_thai if trang_thai in trang_thai_hop_le else "",
        "phong_filter": phong_id if phong_id.isdigit() else "",
        "loai_filter": loai if loai in loai_hop_le else "",
        "nguon_filter": nguon if nguon in nguon_hop_le else "",
        "ket_qua_filter": ket_qua if ket_qua in ket_qua_hop_le else "",
        "tu_ngay_filter": tu_ngay.isoformat() if tu_ngay else "",
        "den_ngay_filter": den_ngay.isoformat() if den_ngay else "",
        "query_string": query_string.urlencode(),
    })


def quan_ly_quyen_ra_vao(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    ds = QuyenRaVao.objects.select_related(
        "phong__co_so",
        "nguoi_thue",
        "nguoi_o_cung",
    ).order_by("-ngay_tao")

    trang_thai = request.GET.get("trang_thai", "")
    if trang_thai:
        ds = ds.filter(trang_thai=trang_thai)

    return render(request, "core/quan_ly_quyen_ra_vao.html", {
        "ds": ds,
        "trang_thai_filter": trang_thai,
    })


def chi_tiet_quyen_ra_vao(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    quyen = get_object_or_404(
        QuyenRaVao.objects.select_related(
            "phong__co_so",
            "nguoi_thue",
            "nguoi_o_cung__hop_dong__dat_phong__phong",
        ),
        id=id
    )
    lich_su = quyen.lich_su.select_related("phong").order_by("-thoi_diem")[:20]
    return render(request, "core/chi_tiet_quyen_ra_vao.html", {
        "quyen": quyen,
        "lich_su": lich_su,
    })


@transaction.atomic
def tao_quyen_ra_vao(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method == "POST":

        phong_id = request.POST.get("phong", "").strip()
        nguoi_thue_id = request.POST.get("nguoi_thue", "").strip()
        nguoi_o_cung_id = request.POST.get("nguoi_o_cung", "").strip()

        ngay_bat_dau_str = request.POST.get(
            "ngay_bat_dau", ""
        ).strip()

        ngay_ket_thuc_str = request.POST.get(
            "ngay_ket_thuc", ""
        ).strip()

        loai_quyen = request.POST.get(
            "loai_quyen",
            "chu_phong"
        ).strip()

        ma_the = request.POST.get(
            "ma_the",
            ""
        ).strip()

        ghi_chu = request.POST.get(
            "ghi_chu",
            ""
        ).strip()

        # =====================================================
        # 1. KIỂM TRA DỮ LIỆU CƠ BẢN
        # =====================================================

        if not phong_id or not ngay_bat_dau_str:

            messages.error(
                request,
                "Phòng và ngày bắt đầu là bắt buộc."
            )

        else:

            co_nguoi_thue = bool(nguoi_thue_id)
            co_nguoi_o_cung = bool(nguoi_o_cung_id)

            # Không được chọn cả hai
            if co_nguoi_thue and co_nguoi_o_cung:

                messages.error(
                    request,
                    "Chỉ được chọn một người: "
                    "người thuê HOẶC người ở cùng."
                )

            # Phải chọn ít nhất một người
            elif not co_nguoi_thue and not co_nguoi_o_cung:

                messages.error(
                    request,
                    "Phải chọn người thuê chính "
                    "hoặc người ở cùng."
                )

            # Kiểm tra loại quyền
            elif loai_quyen not in dict(
                QuyenRaVao.LOAI_QUYEN
            ):

                messages.error(
                    request,
                    "Loại quyền không hợp lệ."
                )

            else:

                phong = get_object_or_404(
                    Phong.objects.select_for_update(),
                    id=phong_id
                )

                nguoi_thue = (
                    get_object_or_404(
                        NguoiThue,
                        id=nguoi_thue_id
                    )
                    if co_nguoi_thue
                    else None
                )

                nguoi_o_cung = (
                    get_object_or_404(
                        NguoiOCungPhong.objects.select_related(
                            "hop_dong__dat_phong__phong"
                        ),
                        id=nguoi_o_cung_id
                    )
                    if co_nguoi_o_cung
                    else None
                )

                ngay_bat_dau = parse_date(
                    ngay_bat_dau_str
                )

                ngay_ket_thuc = (
                    parse_date(ngay_ket_thuc_str)
                    if ngay_ket_thuc_str
                    else None
                )

                # =================================================
                # 2. KIỂM TRA NGÀY
                # =================================================

                if not ngay_bat_dau:

                    messages.error(
                        request,
                        "Ngày bắt đầu không hợp lệ."
                    )

                elif (
                    ngay_ket_thuc
                    and ngay_ket_thuc < ngay_bat_dau
                ):

                    messages.error(
                        request,
                        "Ngày kết thúc không được "
                        "trước ngày bắt đầu."
                    )

                # =================================================
                # 3. NGƯỜI THUÊ CHÍNH
                # =================================================

                elif nguoi_thue:

                    today = timezone.localdate()
                    candidates = list(HopDong.objects.select_related("dat_phong").filter(
                        dat_phong__phong=phong, dat_phong__nguoi_thue=nguoi_thue,
                        dat_phong__trang_thai="da_duyet",
                        trang_thai__in=("dang_hieu_luc", "sap_het_han"),
                        ngay_bat_dau__lte=today, ngay_ket_thuc__gte=today,
                    )[:2])
                    hop_dong = candidates[0] if len(candidates) == 1 else None

                    if not hop_dong:

                        messages.error(
                            request,
                            "Không xác định duy nhất hợp đồng hiện tại của người thuê tại phòng đã chọn."
                        )

                    else:

                        # Cập nhật trạng thái hợp đồng
                        # Contract eligibility is checked without rewriting history.

                        # -----------------------------------------
                        # 3.1. KIỂM TRA HỢP ĐỒNG
                        # -----------------------------------------

                        if not contract_is_current(hop_dong):

                            messages.error(
                                request,
                                "Hợp đồng của người thuê "
                                "không còn hiệu lực."
                            )

                        elif ngay_bat_dau > hop_dong.ngay_ket_thuc:
                            messages.error(request, "Ngày bắt đầu quyền phải trong thời hạn hợp đồng.")
                        elif (
                            ngay_bat_dau
                            < hop_dong.ngay_bat_dau
                        ):

                            messages.error(
                                request,
                                "Ngày bắt đầu quyền ra vào "
                                "không được trước ngày bắt đầu "
                                "hợp đồng."
                            )

                        elif (
                            ngay_ket_thuc
                            and ngay_ket_thuc
                            > hop_dong.ngay_ket_thuc
                        ):

                            messages.error(
                                request,
                                "Ngày kết thúc quyền ra vào "
                                "không được sau ngày kết thúc "
                                "hợp đồng."
                            )

                        # -----------------------------------------
                        # 3.2. KIỂM TRA FACE ID
                        # -----------------------------------------

                        else:

                            face_profile = (
                                FaceProfile.objects
                                .filter(
                                    nguoi_thue=nguoi_thue,
                                    trang_thai="da_xac_thuc",
                                )
                                .first()
                            )

                            if not face_profile:

                                messages.error(
                                    request,
                                    "Người thuê này chưa có "
                                    "Face ID đã xác thực. "
                                    "Hãy đăng ký Face ID trước "
                                    "khi cấp quyền ra vào."
                                )

                            elif loai_quyen != "chu_phong":

                                messages.error(
                                    request,
                                    "Người thuê chính phải sử dụng "
                                    "loại quyền 'Chủ phòng'."
                                )

                            else:

                                # ---------------------------------
                                # 3.3. KIỂM TRA QUYỀN TRÙNG
                                # ---------------------------------

                                quyen_da_co = (
                                    QuyenRaVao.objects
                                    .filter(
                                        hop_dong=hop_dong, nguon_cap__in=KNOWN_PERMISSION_SOURCES,
                                        phong=phong,
                                        nguoi_thue=nguoi_thue,
                                        trang_thai__in=[
                                            "hoat_dong",
                                        ],
                                    )
                                    .exists()
                                )

                                if quyen_da_co:

                                    messages.error(
                                        request,
                                        "Người thuê này đã có "
                                        "quyền ra vào đang hoạt động "
                                        "tại phòng này."
                                    )

                                else:

                                    grant_access(
                                        contract_id=hop_dong.pk, tenant_id=nguoi_thue.pk,
                                        source="thu_cong", actor=request.user,
                                        start_date=ngay_bat_dau,
                                        end_date=ngay_ket_thuc or hop_dong.ngay_ket_thuc,
                                        card_code=ma_the, note=ghi_chu,
                                    )

                                    messages.success(
                                        request,
                                        "Đã cấp quyền ra vào "
                                        "cho người thuê thành công."
                                    )

                                    return redirect(
                                        "quan_ly_quyen_ra_vao"
                                    )

                # =================================================
                # 4. NGƯỜI Ở CÙNG
                # =================================================

                elif nguoi_o_cung and not nguoi_o_cung_du_dieu_kien(nguoi_o_cung):
                    messages.error(
                        request,
                        ly_do_nguoi_o_cung_chua_du_dieu_kien(nguoi_o_cung),
                    )

                elif nguoi_o_cung:

                    hop_dong = (
                        getattr(
                            nguoi_o_cung,
                            "hop_dong",
                            None
                        )
                    )

                    if not hop_dong:

                        messages.error(
                            request,
                            "Người ở cùng chưa có "
                            "hợp đồng liên kết."
                        )

                    else:

                        # Contract eligibility is checked without rewriting history.

                        phong_cua_nguoi_o_cung = (
                            hop_dong
                            .dat_phong
                            .phong
                        )

                        # -----------------------------------------
                        # 4.1. KIỂM TRA PHÒNG
                        # -----------------------------------------

                        if (
                            phong_cua_nguoi_o_cung.id
                            != phong.id
                        ):

                            messages.error(
                                request,
                                "Người ở cùng này không thuộc "
                                "phòng đã chọn."
                            )

                        # -----------------------------------------
                        # 4.2. KIỂM TRA HỢP ĐỒNG
                        # -----------------------------------------

                        elif not contract_is_current(hop_dong):

                            messages.error(
                                request,
                                "Hợp đồng của phòng này "
                                "không còn hiệu lực."
                            )

                        elif ngay_bat_dau > hop_dong.ngay_ket_thuc:
                            messages.error(request, "Ngày bắt đầu quyền phải trong thời hạn hợp đồng.")
                        elif (
                            ngay_bat_dau
                            < hop_dong.ngay_bat_dau
                        ):

                            messages.error(
                                request,
                                "Ngày bắt đầu quyền ra vào "
                                "không được trước ngày bắt đầu "
                                "hợp đồng."
                            )

                        elif (
                            ngay_ket_thuc
                            and ngay_ket_thuc
                            > hop_dong.ngay_ket_thuc
                        ):

                            messages.error(
                                request,
                                "Ngày kết thúc quyền ra vào "
                                "không được sau ngày kết thúc "
                                "hợp đồng."
                            )

                        # -----------------------------------------
                        # 4.3. KIỂM TRA FACE ID
                        # -----------------------------------------

                        else:

                            face_profile = (
                                FaceProfile.objects
                                .filter(
                                    nguoi_o_cung=nguoi_o_cung,
                                    trang_thai="da_xac_thuc",
                                )
                                .first()
                            )

                            if not face_profile:

                                messages.error(
                                    request,
                                    "Người ở cùng này chưa có "
                                    "Face ID đã xác thực. "
                                    "Hãy đăng ký Face ID trước "
                                    "khi cấp quyền ra vào."
                                )

                            elif loai_quyen != "nguoi_o_cung":

                                messages.error(
                                    request,
                                    "Người ở cùng phải sử dụng "
                                    "loại quyền 'Người ở cùng'."
                                )

                            else:

                                # ---------------------------------
                                # 4.4. KIỂM TRA QUYỀN TRÙNG
                                # ---------------------------------

                                quyen_da_co = (
                                    QuyenRaVao.objects
                                    .filter(
                                        hop_dong=hop_dong, nguon_cap__in=KNOWN_PERMISSION_SOURCES,
                                        phong=phong,
                                        nguoi_o_cung=nguoi_o_cung,
                                        trang_thai__in=[
                                            "hoat_dong",
                                        ],
                                    )
                                    .exists()
                                )

                                if quyen_da_co:

                                    messages.error(
                                        request,
                                        "Người ở cùng này đã có "
                                        "quyền ra vào đang hoạt động "
                                        "tại phòng này."
                                    )

                                else:

                                    grant_access(
                                        contract_id=hop_dong.pk, resident_id=nguoi_o_cung.pk,
                                        source="thu_cong", actor=request.user,
                                        start_date=ngay_bat_dau,
                                        end_date=ngay_ket_thuc or hop_dong.ngay_ket_thuc,
                                        card_code=ma_the, note=ghi_chu,
                                    )

                                    messages.success(
                                        request,
                                        "Đã cấp quyền ra vào "
                                        "cho người ở cùng thành công."
                                    )

                                    return redirect(
                                        "quan_ly_quyen_ra_vao"
                                    )

    # =========================================================
    # DANH SÁCH FORM
    # =========================================================

    phong_ds = (
        Phong.objects
        .select_related("co_so")
        .order_by("co_so", "so_phong")
    )

    nguoi_thue_ds = (
        NguoiThue.objects
        .filter(
            dang_hoat_dong=True
        )
        .order_by("ho_ten")
    )

    nguoi_o_cung_ds = (
        NguoiOCungPhong.objects
        .filter(
            trang_thai="dang_o"
        )
        .select_related(
            "hop_dong__dat_phong__phong"
        )
        .order_by("ho_ten")
    )

    return render(
        request,
        "core/tao_quyen_ra_vao.html",
        {
            "phong_ds": phong_ds,
            "nguoi_thue_ds": nguoi_thue_ds,
            "nguoi_o_cung_ds": nguoi_o_cung_ds,
        }
    )


def xu_ly_quyen_ra_vao(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method != "POST":
        return redirect(
            "chi_tiet_quyen_ra_vao",
            id=id
        )

    with transaction.atomic():
        quyen = get_object_or_404(
            QuyenRaVao.objects
            .select_for_update()
            .select_related(
                "phong",
                "phong__co_so",
                "nguoi_thue",
                "nguoi_o_cung",
            ),
            id=id
        )

        hanh_dong = request.POST.get(
            "hanh_dong",
            ""
        ).strip()

        if not quyen.hop_dong_id or quyen.nguon_cap == "legacy_unknown":
            messages.error(request, "Quyền legacy chưa có nguồn/hợp đồng; hãy cấp quyền mới sau kiểm tra.")
            return redirect("chi_tiet_quyen_ra_vao", id=quyen.pk)

        trang_thai_cu = quyen.trang_thai
        ngay_ket_thuc_cu = quyen.ngay_ket_thuc
        ma_the_cu = quyen.ma_the
        ghi_chu_cu = quyen.ghi_chu

        hop_dong = _smart_room_hop_dong_cua_quyen(quyen)

        if hanh_dong in [
            "hoat_dong",
            "tam_khoa",
            "het_han",
            "bi_thu_hoi",
        ]:
            if hanh_dong == "hoat_dong" and quyen.trang_thai != "hoat_dong":
                messages.error(
                    request,
                    "Khong kich hoat lai ban ghi cu. Hay cap quyen moi qua luong canonical.",
                )
                return redirect("chi_tiet_quyen_ra_vao", id=quyen.id)
            if hanh_dong in ("het_han", "bi_thu_hoi"):
                revoke_access(permission_id=quyen.pk, status=hanh_dong)
            if hanh_dong == "hoat_dong":
                if not hop_dong:
                    messages.error(
                        request,
                        (
                            "Không thể kích hoạt quyền vì "
                            "không còn hợp đồng hợp lệ."
                        )
                    )
                    return redirect(
                        "chi_tiet_quyen_ra_vao",
                        id=quyen.id
                    )

                if (
                    quyen.ngay_bat_dau
                    < hop_dong.ngay_bat_dau
                ):
                    quyen.ngay_bat_dau = (
                        hop_dong.ngay_bat_dau
                    )

                if (
                    quyen.ngay_ket_thuc is None
                    or quyen.ngay_ket_thuc
                    > hop_dong.ngay_ket_thuc
                ):
                    quyen.ngay_ket_thuc = (
                        hop_dong.ngay_ket_thuc
                    )

            quyen.trang_thai = hanh_dong

            if hanh_dong in [
                "het_han",
                "bi_thu_hoi",
            ]:
                quyen.active_access_key = None
                if (
                    not quyen.ngay_ket_thuc
                    or quyen.ngay_ket_thuc
                    > timezone.localdate()
                ):
                    quyen.ngay_ket_thuc = (
                        timezone.localdate()
                    )

            quyen.save()

            ghi_nhat_ky(
                request=request,
                hanh_dong="Cập nhật trạng thái",
                module="Smart Room",
                doi_tuong="QuyenRaVao",
                doi_tuong_id=quyen.id,
                tieu_de=(
                    f"Cập nhật quyền ra vào #{quyen.id}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} đổi "
                    f"quyền #{quyen.id} từ {trang_thai_cu} "
                    f"sang {quyen.trang_thai}."
                ),
                du_lieu_cu={
                    "trang_thai": trang_thai_cu,
                    "ngay_ket_thuc": (
                        ngay_ket_thuc_cu.isoformat()
                        if ngay_ket_thuc_cu
                        else None
                    ),
                },
                du_lieu_moi={
                    "trang_thai": quyen.trang_thai,
                    "ngay_ket_thuc": (
                        quyen.ngay_ket_thuc.isoformat()
                        if quyen.ngay_ket_thuc
                        else None
                    ),
                },
            )

            messages.success(
                request,
                "Đã cập nhật trạng thái quyền ra vào."
            )

        elif hanh_dong == "cap_nhat":
            if not hop_dong:
                messages.error(
                    request,
                    (
                        "Không thể cập nhật quyền vì "
                        "không còn hợp đồng hợp lệ."
                    )
                )
                return redirect(
                    "chi_tiet_quyen_ra_vao",
                    id=quyen.id
                )

            ngay_ket_thuc_str = request.POST.get(
                "ngay_ket_thuc",
                ""
            ).strip()

            ngay_ket_thuc_moi = (
                parse_date(ngay_ket_thuc_str)
                if ngay_ket_thuc_str
                else hop_dong.ngay_ket_thuc
            )

            if not ngay_ket_thuc_moi:
                messages.error(
                    request,
                    "Ngày kết thúc không hợp lệ."
                )

            elif ngay_ket_thuc_moi < quyen.ngay_bat_dau:
                messages.error(
                    request,
                    (
                        "Ngày kết thúc quyền không được "
                        "trước ngày bắt đầu."
                    )
                )

            elif ngay_ket_thuc_moi > hop_dong.ngay_ket_thuc:
                messages.error(
                    request,
                    (
                        "Ngày kết thúc quyền không được "
                        "sau ngày kết thúc hợp đồng."
                    )
                )

            else:
                quyen.ngay_ket_thuc = (
                    ngay_ket_thuc_moi
                )
                quyen.ma_the = request.POST.get(
                    "ma_the",
                    ""
                ).strip()
                quyen.ghi_chu = request.POST.get(
                    "ghi_chu",
                    ""
                ).strip()

                quyen.save()

                ghi_nhat_ky(
                    request=request,
                    hanh_dong="Cập nhật",
                    module="Smart Room",
                    doi_tuong="QuyenRaVao",
                    doi_tuong_id=quyen.id,
                    tieu_de=(
                        f"Cập nhật quyền ra vào #{quyen.id}"
                    ),
                    noi_dung=(
                        f"Admin {request.user.username} cập nhật "
                        f"quyền #{quyen.id} tại phòng "
                        f"{quyen.phong.so_phong}."
                    ),
                    du_lieu_cu={
                        "ngay_ket_thuc": (
                            ngay_ket_thuc_cu.isoformat()
                            if ngay_ket_thuc_cu
                            else None
                        ),
                        "ma_the": ma_the_cu,
                        "ghi_chu": ghi_chu_cu,
                    },
                    du_lieu_moi={
                        "ngay_ket_thuc": (
                            quyen.ngay_ket_thuc.isoformat()
                            if quyen.ngay_ket_thuc
                            else None
                        ),
                        "ma_the": quyen.ma_the,
                        "ghi_chu": quyen.ghi_chu,
                    },
                )

                messages.success(
                    request,
                    "Đã cập nhật quyền ra vào."
                )

        elif hanh_dong == "xoa":
            # Thay hard-delete bằng thu hồi để giữ lịch sử.
            revoke_access(permission_id=quyen.pk, status="bi_thu_hoi")
            quyen.trang_thai = "bi_thu_hoi"
            quyen.active_access_key = None

            if (
                not quyen.ngay_ket_thuc
                or quyen.ngay_ket_thuc
                > timezone.localdate()
            ):
                quyen.ngay_ket_thuc = (
                    timezone.localdate()
                )

            ghi_chu_bo_sung = (
                f"Thu hồi bởi Admin "
                f"{request.user.username} "
                f"lúc {timezone.localtime().strftime('%d/%m/%Y %H:%M')}."
            )

            quyen.ghi_chu = (
                f"{quyen.ghi_chu}\n"
                f"{ghi_chu_bo_sung}"
            ).strip()

            quyen.save()

            ghi_nhat_ky(
                request=request,
                hanh_dong="Thu hồi",
                module="Smart Room",
                doi_tuong="QuyenRaVao",
                doi_tuong_id=quyen.id,
                tieu_de=(
                    f"Thu hồi quyền ra vào #{quyen.id}"
                ),
                noi_dung=(
                    f"Admin {request.user.username} thu hồi "
                    f"quyền #{quyen.id} tại phòng "
                    f"{quyen.phong.so_phong}. "
                    "Bản ghi được giữ để bảo toàn lịch sử."
                ),
                du_lieu_cu={
                    "trang_thai": trang_thai_cu,
                    "ngay_ket_thuc": (
                        ngay_ket_thuc_cu.isoformat()
                        if ngay_ket_thuc_cu
                        else None
                    ),
                    "ghi_chu": ghi_chu_cu,
                },
                du_lieu_moi={
                    "trang_thai": quyen.trang_thai,
                    "ngay_ket_thuc": (
                        quyen.ngay_ket_thuc.isoformat()
                        if quyen.ngay_ket_thuc
                        else None
                    ),
                    "ghi_chu": quyen.ghi_chu,
                },
            )

            messages.success(
                request,
                (
                    "Đã thu hồi quyền ra vào. "
                    "Lịch sử được giữ nguyên."
                )
            )

        else:
            messages.error(
                request,
                "Hành động không hợp lệ."
            )

    return redirect(
        "chi_tiet_quyen_ra_vao",
        id=quyen.id
    )


def quan_ly_lich_su_ra_vao(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    ds = LichSuRaVao.objects.select_related(
        "phong__co_so",
        "nguoi_thue",
        "nguoi_o_cung",
    ).order_by("-thoi_diem")

    phong_id = request.GET.get("phong", "")
    loai = request.GET.get("loai", "")
    ket_qua = request.GET.get("ket_qua", "")
    if phong_id:
        ds = ds.filter(phong_id=phong_id)
    if loai:
        ds = ds.filter(loai_su_kien=loai)
    if ket_qua in {value for value, _label in LichSuRaVao.KET_QUA}:
        ds = ds.filter(ket_qua=ket_qua)

    phong_ds = Phong.objects.select_related("co_so").order_by("co_so", "so_phong")

    return render(request, "core/quan_ly_lich_su_ra_vao.html", {
        "ds": ds,
        "phong_ds": phong_ds,
        "phong_filter": phong_id,
        "loai_filter": loai,
        "ket_qua_filter": ket_qua,
    })


def chi_tiet_lich_su_ra_vao(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")
    if not la_admin(request):
        return redirect("tai_khoan")

    ls = get_object_or_404(
        LichSuRaVao.objects.select_related(
            "phong__co_so",
            "nguoi_thue",
            "nguoi_o_cung",
            "quyen_ra_vao",
        ),
        id=id
    )
    return render(request, "core/chi_tiet_lich_su_ra_vao.html", {"ls": ls})


def tao_lich_su_ra_vao(request):
    """
    Ghi nhận thủ công một lượt ra/vào.

    Nguyên tắc:
    - Chỉ Admin được sử dụng.
    - Nguồn luôn là "thu_cong"; không cho giả nguồn Camera/Face ID.
    - Bắt buộc chọn đúng 1 đối tượng: người thuê chính hoặc người ở cùng.
    - Đối tượng phải thực sự thuộc đúng phòng tại thời điểm sự kiện.
    - Nếu tìm được quyền ra vào phù hợp thì tự liên kết vào bản ghi.
    - Bản ghi thủ công được đánh dấu rõ trong ghi chú để phục vụ audit.
    """

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method == "POST":
        from django.utils.dateparse import parse_datetime

        phong_id = request.POST.get(
            "phong",
            ""
        ).strip()

        loai_su_kien = request.POST.get(
            "loai_su_kien",
            ""
        ).strip()

        thoi_diem_str = request.POST.get(
            "thoi_diem",
            ""
        ).strip()

        nguoi_thue_id = request.POST.get(
            "nguoi_thue",
            ""
        ).strip()

        nguoi_o_cung_id = request.POST.get(
            "nguoi_o_cung",
            ""
        ).strip()

        ten_nguoi_nhap = request.POST.get(
            "ten_nguoi",
            ""
        ).strip()

        ghi_chu_nhap = request.POST.get(
            "ghi_chu",
            ""
        ).strip()

        # =====================================================
        # 1. VALIDATE DỮ LIỆU BẮT BUỘC
        # =====================================================

        if (
            not phong_id
            or not loai_su_kien
            or not thoi_diem_str
        ):
            messages.error(
                request,
                (
                    "Phòng, loại sự kiện và thời điểm "
                    "là thông tin bắt buộc."
                )
            )

        elif loai_su_kien not in [
            "vao",
            "ra",
        ]:
            messages.error(
                request,
                "Loại sự kiện không hợp lệ."
            )

        elif bool(nguoi_thue_id) == bool(nguoi_o_cung_id):
            messages.error(
                request,
                (
                    "Vui lòng chọn đúng một đối tượng: "
                    "người thuê chính hoặc người ở cùng."
                )
            )

        else:
            phong = get_object_or_404(
                Phong.objects.select_related("co_so"),
                id=phong_id
            )

            thoi_diem = parse_datetime(
                thoi_diem_str
            )

            if not thoi_diem:
                messages.error(
                    request,
                    "Thời điểm sự kiện không hợp lệ."
                )

            else:
                # datetime-local thường không có timezone.
                if timezone.is_naive(thoi_diem):
                    thoi_diem = timezone.make_aware(
                        thoi_diem,
                        timezone.get_current_timezone()
                    )

                ngay_su_kien = timezone.localtime(
                    thoi_diem
                ).date()

                nguoi_thue = None
                nguoi_o_cung = None
                hop_dong = None
                quyen = None

                # =================================================
                # 2. NGƯỜI THUÊ CHÍNH
                # =================================================

                if nguoi_thue_id:
                    nguoi_thue = (
                        NguoiThue.objects
                        .filter(
                            id=nguoi_thue_id,
                            dang_hoat_dong=True,
                        )
                        .first()
                    )

                    if not nguoi_thue:
                        messages.error(
                            request,
                            (
                                "Người thuê được chọn không tồn tại "
                                "hoặc không còn hoạt động."
                            )
                        )

                    else:
                        candidates = list(
                            HopDong.objects
                            .filter(
                                dat_phong__nguoi_thue=nguoi_thue,
                                dat_phong__phong=phong,
                                dat_phong__trang_thai="da_duyet",
                                ngay_bat_dau__lte=ngay_su_kien,
                                ngay_ket_thuc__gte=ngay_su_kien,
                            )
                            .exclude(
                                trang_thai="da_huy"
                            )
                            .order_by("id")[:2]
                        )
                        hop_dong = candidates[0] if len(candidates) == 1 else None

                        if not hop_dong:
                            messages.error(
                                request,
                                (
                                    "Không xác định duy nhất hợp đồng hợp lệ tại phòng "
                                    f"{phong.so_phong} vào thời điểm này."
                                )
                            )

                # =================================================
                # 3. NGƯỜI Ở CÙNG
                # =================================================

                else:
                    nguoi_o_cung = (
                        NguoiOCungPhong.objects
                        .select_related(
                            "hop_dong__dat_phong__phong"
                        )
                        .filter(
                            id=nguoi_o_cung_id
                        )
                        .first()
                    )

                    if not nguoi_o_cung:
                        messages.error(
                            request,
                            "Người ở cùng được chọn không tồn tại."
                        )

                    else:
                        hop_dong = nguoi_o_cung.hop_dong

                        dung_phong = (
                            hop_dong
                            and hop_dong.dat_phong
                            and hop_dong.dat_phong.phong_id == phong.id
                        )

                        dung_thoi_gian = (
                            nguoi_o_cung.ngay_vao
                            and nguoi_o_cung.ngay_vao <= ngay_su_kien
                            and (
                                not nguoi_o_cung.ngay_ra
                                or nguoi_o_cung.ngay_ra >= ngay_su_kien
                            )
                        )

                        hop_dong_hop_le = (
                            hop_dong
                            and hop_dong.trang_thai != "da_huy"
                            and hop_dong.ngay_bat_dau <= ngay_su_kien
                            and hop_dong.ngay_ket_thuc >= ngay_su_kien
                        )

                        if not (
                            dung_phong
                            and dung_thoi_gian
                            and hop_dong_hop_le
                        ):
                            messages.error(
                                request,
                                (
                                    f"{nguoi_o_cung.ho_ten} không thuộc "
                                    f"phòng {phong.so_phong} tại thời điểm "
                                    "sự kiện được chọn."
                                )
                            )
                            hop_dong = None

                # =================================================
                # 4. TẠO LOG NẾU NGHIỆP VỤ HỢP LỆ
                # =================================================

                if hop_dong:
                    if nguoi_thue:
                        quyen = (
                            QuyenRaVao.objects.filter(hop_dong=hop_dong, nguon_cap__in=KNOWN_PERMISSION_SOURCES)
                            .filter(
                                phong=phong,
                                nguoi_thue=nguoi_thue, nguoi_o_cung__isnull=True, loai_quyen="chu_phong",
                                ngay_bat_dau__lte=ngay_su_kien,
                            )
                            .filter(
                                Q(ngay_ket_thuc__isnull=True)
                                | Q(ngay_ket_thuc__gte=ngay_su_kien)
                            )
                            .exclude(
                                trang_thai="bi_thu_hoi"
                            )
                            .order_by("-id")
                            .first()
                        )

                        ten_nguoi = (
                            ten_nguoi_nhap
                            or nguoi_thue.ho_ten
                        )

                    else:
                        quyen = (
                            QuyenRaVao.objects.filter(hop_dong=hop_dong, nguon_cap__in=KNOWN_PERMISSION_SOURCES)
                            .filter(
                                phong=phong,
                                nguoi_o_cung=nguoi_o_cung, nguoi_thue__isnull=True, loai_quyen="nguoi_o_cung",
                                ngay_bat_dau__lte=ngay_su_kien,
                            )
                            .filter(
                                Q(ngay_ket_thuc__isnull=True)
                                | Q(ngay_ket_thuc__gte=ngay_su_kien)
                            )
                            .exclude(
                                trang_thai="bi_thu_hoi"
                            )
                            .order_by("-id")
                            .first()
                        )

                        ten_nguoi = (
                            ten_nguoi_nhap
                            or nguoi_o_cung.ho_ten
                        )

                    ghi_chu = (
                        "[CHO PHÉP] [THỦ CÔNG] "
                        "Admin bổ sung bản ghi ra/vào thủ công."
                    )

                    if ghi_chu_nhap:
                        ghi_chu += (
                            f" Lý do/Ghi chú: {ghi_chu_nhap}"
                        )

                    LichSuRaVao.objects.create(
                        phong=phong,
                        nguoi_thue=nguoi_thue,
                        nguoi_o_cung=nguoi_o_cung,
                        quyen_ra_vao=quyen,
                        ten_nguoi=ten_nguoi,
                        loai_su_kien=loai_su_kien,
                        nguon="thu_cong",
                        ket_qua="cho_phep",
                        thoi_diem=thoi_diem,
                        ghi_chu=ghi_chu,
                    )

                    messages.success(
                        request,
                        (
                            "Đã ghi nhận sự kiện ra/vào thủ công "
                            "và lưu vào lịch sử."
                        )
                    )

                    return redirect(
                        "quan_ly_lich_su_ra_vao"
                    )

    phong_ds = (
        Phong.objects
        .select_related("co_so")
        .order_by(
            "co_so",
            "so_phong"
        )
    )

    nguoi_thue_ds = (
        NguoiThue.objects
        .filter(
            dang_hoat_dong=True
        )
        .order_by("ho_ten")
    )

    nguoi_o_cung_ds = (
        NguoiOCungPhong.objects
        .filter(
            trang_thai="dang_o"
        )
        .select_related(
            "hop_dong__dat_phong__phong"
        )
        .order_by("ho_ten")
    )

    return render(
        request,
        "core/tao_lich_su_ra_vao.html",
        {
            "phong_ds": phong_ds,
            "nguoi_thue_ds": nguoi_thue_ds,
            "nguoi_o_cung_ds": nguoi_o_cung_ds,
        }
    )


def xu_ly_lich_su_ra_vao(request, id):
    """
    Xử lý bản ghi lịch sử ra vào.

    Nguyên tắc:
    - Lịch sử ra vào là dữ liệu audit, không hard-delete.
    - Chỉ admin được truy cập.
    - Các yêu cầu "xóa" từ giao diện cũ sẽ bị từ chối an toàn.
    """

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    ls = get_object_or_404(
        LichSuRaVao.objects.select_related(
            "phong__co_so",
            "nguoi_thue",
            "nguoi_o_cung",
            "quyen_ra_vao",
        ),
        id=id
    )

    if request.method == "POST":
        hanh_dong = request.POST.get(
            "hanh_dong",
            ""
        ).strip()

        if hanh_dong == "xoa":
            messages.warning(
                request,
                (
                    "Lịch sử ra vào là dữ liệu kiểm tra hệ thống "
                    "nên không thể xóa. Bản ghi đã được giữ nguyên."
                )
            )

            return redirect(
                "chi_tiet_lich_su_ra_vao",
                id=ls.id
            )

        messages.warning(
            request,
            "Thao tác không hợp lệ."
        )

    return redirect(
        "chi_tiet_lich_su_ra_vao",
        id=ls.id
    )
