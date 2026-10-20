"""Danh sach phong cong khai."""

from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.shortcuts import render
from django.utils import timezone

from core.dich_vu.gallery_phong import chuan_bi_gallery_hien_thi
from core.dich_vu.phong_cong_khai import (
    gan_trang_thai_cong_khai,
    queryset_phong_cong_khai,
    them_giu_cho_cong_khai,
)
from core.bieu_mau_dat_phong import RentalQuoteForm
from core.dich_vu.dat_phong import room_is_bookable_for_rental
from core.models import DatPhong, NguoiOCungPhong


def danh_sach_phong(request):
    thoi_diem_hien_tai = timezone.now()
    trang_thai_hop_dong_dang_thue = ["dang_hieu_luc", "sap_het_han"]
    dat_phong_dang_thue = DatPhong.objects.filter(
        trang_thai="da_duyet",
        hop_dong__trang_thai__in=trang_thai_hop_dong_dang_thue,
    ).select_related("hop_dong", "nguoi_thue").order_by("-id").prefetch_related(
        Prefetch(
            "hop_dong__nguoi_o_cung",
            queryset=NguoiOCungPhong.objects.filter(trang_thai="dang_o"),
        )
    )
    phong = them_giu_cho_cong_khai(
        queryset_phong_cong_khai(), thoi_diem_hien_tai
    ).prefetch_related(
        Prefetch("dat_phong", queryset=dat_phong_dang_thue, to_attr="dat_phong_dang_thue")
    )

    tu_khoa = request.GET.get("q", "").strip()
    if tu_khoa:
        phong = phong.filter(
            Q(so_phong__icontains=tu_khoa)
            | Q(co_so__ten_co_so__icontains=tu_khoa)
            | Q(co_so__quan__icontains=tu_khoa)
            | Q(co_so__dia_chi__icontains=tu_khoa)
        )

    gia_max = request.GET.get("gia_max", "").strip()
    if gia_max:
        try:
            gia_max_value = Decimal(gia_max)
            if gia_max_value >= 0:
                phong = phong.filter(gia_thue__lte=gia_max_value)
        except (InvalidOperation, ValueError, TypeError):
            pass

    has_availability_query = (
        'ngay_nhan_phong' in request.GET or 'so_thang_thue' in request.GET
    )
    availability_form = RentalQuoteForm(request.GET if has_availability_query else None)
    availability_period = None
    availability_errors = None
    if has_availability_query:
        if availability_form.is_valid():
            availability_period = availability_form.cleaned_data
            phong = [
                room for room in phong
                if room_is_bookable_for_rental(
                    room,
                    availability_period['ngay_nhan_phong'],
                    availability_period['so_thang_thue'],
                )
            ]
        else:
            availability_errors = availability_form.errors

    paginator = Paginator(phong, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    phong = page_obj.object_list
    chuan_bi_gallery_hien_thi(phong)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    pagination_query = query_params.urlencode()

    for item in phong:
        dat_phong_hien_tai = next(iter(item.dat_phong_dang_thue), None)
        hop_dong_hien_tai = (
            dat_phong_hien_tai.hop_dong if dat_phong_hien_tai else None
        )
        trang_thai_cong_khai = gan_trang_thai_cong_khai(
            item,
            hop_dong_hien_tai=hop_dong_hien_tai,
            co_giu_cho_hop_le=item.co_giu_cho_hop_le,
        )

        suc_chua = item.so_nguoi_toi_da if item.so_nguoi_toi_da else 0
        suc_chua_da_cau_hinh = suc_chua > 0
        if hop_dong_hien_tai:
            so_nguoi_hien_tai = 1 + len(hop_dong_hien_tai.nguoi_o_cung.all())
        else:
            so_nguoi_hien_tai = 0

        if trang_thai_cong_khai == "da_dat":
            so_nguoi_hien_tai = 0

        if suc_chua_da_cau_hinh:
            cho_con_lai = max(suc_chua - so_nguoi_hien_tai, 0)
            ty_le_su_dung = min(round((so_nguoi_hien_tai / suc_chua) * 100), 100)
        else:
            cho_con_lai = 0
            ty_le_su_dung = 0

        cho_phep_ghep_hien_tai = bool(
            hop_dong_hien_tai
            and suc_chua_da_cau_hinh
            and hop_dong_hien_tai.cho_phep_ghep
            and cho_con_lai > 0
        )
        item.hop_dong_hien_tai = hop_dong_hien_tai
        item.suc_chua_hien_thi = suc_chua
        item.suc_chua_da_cau_hinh = suc_chua_da_cau_hinh
        item.so_nguoi_hien_tai = so_nguoi_hien_tai
        item.cho_con_lai = cho_con_lai
        item.phan_tram_su_dung = ty_le_su_dung
        item.cho_phep_ghep_hien_tai = cho_phep_ghep_hien_tai
        item.available_for_period = availability_period is not None

    return render(
        request,
        "core/danh_sach_phong.html",
        {
            "phong": phong,
            "page_obj": page_obj,
            "tong_phong": paginator.count,
            "pagination_query": pagination_query,
            "tu_khoa": tu_khoa,
            "gia_max": gia_max,
            "availability_form": availability_form,
            "availability_errors": availability_errors,
            "availability_period": availability_period,
        },
    )
