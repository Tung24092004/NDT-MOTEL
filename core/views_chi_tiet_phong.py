"""Chi tiet phong cong khai va quan tri."""

from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, render

from core.bieu_mau_dat_phong import RentalQuoteForm
from core.dich_vu.dat_phong import room_is_bookable_for_rental
from core.dich_vu.dieu_kien_o_ghep import dieu_kien_o_ghep
from core.dich_vu.gallery_phong import chuan_bi_gallery_hien_thi
from core.dich_vu.phan_quyen import la_admin
from core.dich_vu.phong_cong_khai import (
    gan_trang_thai_cong_khai,
    queryset_phong_cong_khai,
    them_giu_cho_cong_khai,
)
from core.models import NguoiThue, Phong, YeuCauGhepNguoi


def chi_tiet_phong(request, id):
    la_quan_tri = la_admin(request)
    if la_quan_tri:
        phong_queryset = Phong.objects.select_related("co_so").prefetch_related("hinh_anh")
    else:
        phong_queryset = them_giu_cho_cong_khai(queryset_phong_cong_khai())
    phong = get_object_or_404(phong_queryset, id=id)
    chuan_bi_gallery_hien_thi([phong])
    dieu_kien = dieu_kien_o_ghep(phong)

    hop_dong_hien_tai = dieu_kien["hop_dong"]
    if not la_quan_tri:
        gan_trang_thai_cong_khai(
            phong,
            hop_dong_hien_tai=hop_dong_hien_tai,
            co_giu_cho_hop_le=phong.co_giu_cho_hop_le,
        )

    nguoi_thue_hien_tai = None
    if request.user.is_authenticated:
        nguoi_thue_hien_tai = NguoiThue.objects.filter(
            tai_khoan=request.user,
            dang_hoat_dong=True,
        ).first()

    suc_chua = phong.so_nguoi_toi_da if phong.so_nguoi_toi_da else 0
    suc_chua_da_cau_hinh = suc_chua > 0
    so_nguoi_hien_tai = dieu_kien["so_nguoi_hien_tai"] if hop_dong_hien_tai else 0

    if suc_chua_da_cau_hinh:
        cho_con_lai = max(suc_chua - so_nguoi_hien_tai, 0)
        ty_le_su_dung = min(max(round((so_nguoi_hien_tai / suc_chua) * 100), 0), 100)
    else:
        cho_con_lai = 0
        ty_le_su_dung = 0

    la_chu_phong = bool(
        hop_dong_hien_tai
        and nguoi_thue_hien_tai
        and hop_dong_hien_tai.dat_phong.nguoi_thue_id == nguoi_thue_hien_tai.id
    )

    yeu_cau_ghep_dang_cho = None
    if hop_dong_hien_tai and nguoi_thue_hien_tai and not la_chu_phong:
        yeu_cau_ghep_dang_cho = YeuCauGhepNguoi.objects.filter(
            hop_dong=hop_dong_hien_tai,
            nguoi_dang_ky=nguoi_thue_hien_tai,
            trang_thai="cho_duyet",
        ).first()

    co_the_dang_ky_ghep = bool(
        dieu_kien["phong_co_the_ghep"]
        and suc_chua_da_cau_hinh
        and hop_dong_hien_tai.cho_phep_ghep
        and cho_con_lai > 0
        and nguoi_thue_hien_tai
        and not la_chu_phong
        and not yeu_cau_ghep_dang_cho
        and not la_admin(request)
    )

    availability_period = None
    availability_query = ''
    if not la_quan_tri and ('ngay_nhan_phong' in request.GET or 'so_thang_thue' in request.GET):
        availability_form = RentalQuoteForm(request.GET)
        if availability_form.is_valid():
            candidate_period = availability_form.cleaned_data
            if room_is_bookable_for_rental(
                phong,
                candidate_period['ngay_nhan_phong'],
                candidate_period['so_thang_thue'],
            ):
                availability_period = candidate_period
                availability_query = urlencode({
                    'ngay_nhan_phong': candidate_period['ngay_nhan_phong'].isoformat(),
                    'so_thang_thue': candidate_period['so_thang_thue'],
                })

    return render(
        request,
        "core/chi_tiet_phong.html",
        {
            **{key: value for key, value in dieu_kien.items() if key != "hop_dong"},
            "an_menu_ghep_phong": not dieu_kien["phong_co_the_ghep"],
            "phong": phong,
            "hinh_anh_phong": phong.gallery_hien_thi,
            "anh_dai_dien": phong.anh_dai_dien_hien_thi,
            "hop_dong_hien_tai": hop_dong_hien_tai,
            "suc_chua": suc_chua,
            "suc_chua_da_cau_hinh": suc_chua_da_cau_hinh,
            "so_nguoi_hien_tai": so_nguoi_hien_tai,
            "cho_con_lai": cho_con_lai,
            "ty_le_su_dung": ty_le_su_dung,
            "nguoi_thue_hien_tai": nguoi_thue_hien_tai,
            "la_chu_phong": la_chu_phong,
            "yeu_cau_ghep_dang_cho": yeu_cau_ghep_dang_cho,
            "co_the_dang_ky_ghep": co_the_dang_ky_ghep,
            "availability_period": availability_period,
            "availability_query": availability_query,
        },
    )
