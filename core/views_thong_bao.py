from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import LichSuThongBao, NguoiThue, ThongBao


def _admin_guard(request):
    return request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


def _tenant_for(request):
    if not request.user.is_authenticated or request.user.is_staff or request.user.is_superuser:
        return None
    return NguoiThue.objects.filter(tai_khoan=request.user, dang_hoat_dong=True).first()


def _notice_payload(notice, detail_url):
    return {
        "id": notice.pk,
        "tieu_de": notice.tieu_de,
        "noi_dung": notice.noi_dung[:180],
        "loai": notice.loai,
        "muc_do": notice.muc_do,
        "thoi_gian": timezone.localtime(notice.ngay_tao).strftime("%d/%m/%Y %H:%M"),
        "detail_url": detail_url,
    }


@login_required(login_url="dang_nhap")
def thong_bao_admin(request):
    if not _admin_guard(request):
        return redirect("tai_khoan")
    notices = ThongBao.objects.filter(nguoi_nhan_user=request.user).order_by("da_doc", "-ngay_tao")
    page_obj = Paginator(notices, 20).get_page(request.GET.get("page"))
    return render(request, "core/thong_bao_admin.html", {"thong_bao": page_obj.object_list, "page_obj": page_obj})


@login_required(login_url="dang_nhap")
def chi_tiet_thong_bao_admin(request, id):
    if not _admin_guard(request):
        return redirect("tai_khoan")
    notice = get_object_or_404(ThongBao, pk=id, nguoi_nhan_user=request.user)
    return render(request, "core/chi_tiet_thong_bao_admin.html", {"thong_bao": notice})


@require_POST
@login_required(login_url="dang_nhap")
def doc_thong_bao_admin(request, id):
    if not _admin_guard(request):
        return redirect("tai_khoan")
    notice = get_object_or_404(ThongBao, pk=id, nguoi_nhan_user=request.user)
    if not notice.da_doc:
        notice.da_doc = True
        notice.ngay_doc = timezone.now()
        notice.save(update_fields=["da_doc", "ngay_doc", "ngay_cap_nhat"])
        LichSuThongBao.objects.create(thong_bao=notice, hanh_dong="doc", nguoi_thuc_hien=request.user)
    next_url = notice.url_lien_ket or reverse("chi_tiet_thong_bao_admin", args=[notice.pk])
    return redirect(next_url)


@require_POST
@login_required(login_url="dang_nhap")
def doc_tat_ca_thong_bao_admin(request):
    if not _admin_guard(request):
        return redirect("tai_khoan")
    now = timezone.now()
    ThongBao.objects.filter(nguoi_nhan_user=request.user, da_doc=False).update(da_doc=True, ngay_doc=now)
    messages.success(request, "Da danh dau tat ca thong bao admin la da doc.")
    return redirect("thong_bao_admin")


@require_GET
@login_required(login_url="dang_nhap")
def kiem_tra_thong_bao_admin_moi(request):
    if not _admin_guard(request):
        return JsonResponse({"so_chua_doc": 0, "items": []})
    qs = ThongBao.objects.filter(nguoi_nhan_user=request.user, da_doc=False).order_by("-ngay_tao")
    items = [_notice_payload(notice, reverse("chi_tiet_thong_bao_admin", args=[notice.pk])) for notice in qs[:5]]
    return JsonResponse({"so_chua_doc": qs.count(), "items": items})


@require_GET
@login_required(login_url="dang_nhap")
def kiem_tra_thong_bao_cua_toi_moi(request):
    tenant = _tenant_for(request)
    if not tenant:
        return JsonResponse({"so_chua_doc": 0, "items": []})
    qs = ThongBao.objects.filter(nguoi_thue=tenant, da_doc=False).order_by("-ngay_tao")
    items = [_notice_payload(notice, reverse("chi_tiet_thong_bao_cua_toi", args=[notice.pk])) for notice in qs[:5]]
    return JsonResponse({"so_chua_doc": qs.count(), "items": items})
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Exists, OuterRef
from django.db import transaction
from django.utils import timezone
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


def quan_ly_thong_bao(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    thong_bao_qs = (
        ThongBao.objects
        .select_related("nguoi_thue")
        .order_by("-ngay_tao")
    )

    tu_khoa = request.GET.get("q", "").strip()
    loai = request.GET.get("loai", "").strip()
    muc_do = request.GET.get("muc_do", "").strip()
    trang_thai_doc = request.GET.get("da_doc", "").strip()

    if tu_khoa:
        thong_bao_qs = thong_bao_qs.filter(
            Q(tieu_de__icontains=tu_khoa)
            | Q(noi_dung__icontains=tu_khoa)
            | Q(nguoi_thue__ho_ten__icontains=tu_khoa)
        )

    if loai:
        thong_bao_qs = thong_bao_qs.filter(loai=loai)

    if muc_do:
        thong_bao_qs = thong_bao_qs.filter(muc_do=muc_do)

    if trang_thai_doc == "da_doc":
        thong_bao_qs = thong_bao_qs.filter(da_doc=True)
    elif trang_thai_doc == "chua_doc":
        thong_bao_qs = thong_bao_qs.filter(da_doc=False)

    tong_thong_bao = ThongBao.objects.count()
    tong_da_doc = ThongBao.objects.filter(da_doc=True).count()
    tong_chua_doc = ThongBao.objects.filter(da_doc=False).count()

    return render(
        request,
        "core/quan_ly_thong_bao.html",
        {
            "thong_bao": thong_bao_qs,
            "tu_khoa": tu_khoa,
            "loai": loai,
            "muc_do": muc_do,
            "trang_thai_doc": trang_thai_doc,
            "tong_thong_bao": tong_thong_bao,
            "tong_da_doc": tong_da_doc,
            "tong_chua_doc": tong_chua_doc,
        }
    )


def chi_tiet_thong_bao(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    thong_bao = get_object_or_404(
        ThongBao.objects.select_related("nguoi_thue"),
        id=id
    )

    return render(
        request,
        "core/chi_tiet_thong_bao.html",
        {
            "thong_bao": thong_bao,
        }
    )


def thong_bao_cua_toi(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if la_admin(request):
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

    thong_bao_qs = (
        ThongBao.objects
        .filter(nguoi_thue=nguoi_thue)
        .order_by("-ngay_tao")
    )

    tu_khoa = request.GET.get("q", "").strip()
    loai = request.GET.get("loai", "").strip()
    muc_do = request.GET.get("muc_do", "").strip()
    trang_thai_doc = request.GET.get("da_doc", "").strip()

    if tu_khoa:
        thong_bao_qs = thong_bao_qs.filter(
            Q(tieu_de__icontains=tu_khoa)
            | Q(noi_dung__icontains=tu_khoa)
        )

    if loai:
        thong_bao_qs = thong_bao_qs.filter(loai=loai)

    if muc_do:
        thong_bao_qs = thong_bao_qs.filter(muc_do=muc_do)

    if trang_thai_doc == "da_doc":
        thong_bao_qs = thong_bao_qs.filter(da_doc=True)
    elif trang_thai_doc == "chua_doc":
        thong_bao_qs = thong_bao_qs.filter(da_doc=False)

    tong_thong_bao = ThongBao.objects.filter(
        nguoi_thue=nguoi_thue
    ).count()

    tong_da_doc = ThongBao.objects.filter(
        nguoi_thue=nguoi_thue,
        da_doc=True
    ).count()

    tong_chua_doc = ThongBao.objects.filter(
        nguoi_thue=nguoi_thue,
        da_doc=False
    ).count()

    return render(
        request,
        "core/thong_bao_cua_toi.html",
        {
            "thong_bao": thong_bao_qs,
            "nguoi_thue": nguoi_thue,
            "tu_khoa": tu_khoa,
            "loai": loai,
            "muc_do": muc_do,
            "trang_thai_doc": trang_thai_doc,
            "tong_thong_bao": tong_thong_bao,
            "tong_da_doc": tong_da_doc,
            "tong_chua_doc": tong_chua_doc,
        }
    )


def chi_tiet_thong_bao_cua_toi(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if la_admin(request):
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

    thong_bao = get_object_or_404(
        ThongBao,
        id=id,
        nguoi_thue=nguoi_thue
    )

    if not thong_bao.da_doc:
        thong_bao.da_doc = True

        # Giữ tương thích với model hiện tại:
        # nếu có field ngay_doc thì lưu thời điểm đọc.
        update_fields = ["da_doc"]

        if hasattr(thong_bao, "ngay_doc"):
            thong_bao.ngay_doc = timezone.now()
            update_fields.append("ngay_doc")

        thong_bao.save(
            update_fields=update_fields
        )

    return render(
        request,
        "core/chi_tiet_thong_bao_cua_toi.html",
        {
            "thong_bao": thong_bao,
            "nguoi_thue": nguoi_thue,
        }
    )


def tao_thong_bao(request):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        return redirect("tai_khoan")

    if request.method == "POST":
        nguoi_thue_id = request.POST.get(
            "nguoi_thue",
            ""
        ).strip()

        tieu_de = request.POST.get(
            "tieu_de",
            ""
        ).strip()

        noi_dung = request.POST.get(
            "noi_dung",
            ""
        ).strip()

        loai = request.POST.get(
            "loai",
            "he_thong"
        ).strip()

        muc_do = request.POST.get(
            "muc_do",
            "binh_thuong"
        ).strip()

        if not nguoi_thue_id:
            messages.error(
                request,
                "Vui lòng chọn người nhận thông báo."
            )
        elif not tieu_de:
            messages.error(
                request,
                "Vui lòng nhập tiêu đề thông báo."
            )
        elif not noi_dung:
            messages.error(
                request,
                "Vui lòng nhập nội dung thông báo."
            )
        else:
            nguoi_thue = get_object_or_404(
                NguoiThue,
                id=nguoi_thue_id,
                dang_hoat_dong=True
            )

            loai_hop_le = {
                value
                for value, _ in ThongBao._meta.get_field("loai").choices
            }

            muc_do_hop_le = {
                value
                for value, _ in ThongBao._meta.get_field("muc_do").choices
            }

            if loai not in loai_hop_le:
                messages.error(
                    request,
                    "Loại thông báo không hợp lệ."
                )
            elif muc_do not in muc_do_hop_le:
                messages.error(
                    request,
                    "Mức độ thông báo không hợp lệ."
                )
            else:
                with transaction.atomic():
                    thong_bao_moi = ThongBao.objects.create(
                        nguoi_thue=nguoi_thue,
                        tieu_de=tieu_de,
                        noi_dung=noi_dung,
                        loai=loai,
                        muc_do=muc_do,
                    )

                    ghi_nhat_ky(
                        request=request,
                        hanh_dong="Tạo",
                        module="Thông báo",
                        doi_tuong="ThongBao",
                        doi_tuong_id=thong_bao_moi.id,
                        tieu_de=(
                            f"Tạo thông báo #{thong_bao_moi.id}"
                        ),
                        noi_dung=(
                            f"Admin {request.user.username} tạo thông báo "
                            f"cho người thuê {nguoi_thue.ho_ten}: "
                            f"{tieu_de}."
                        ),
                        du_lieu_cu={},
                        du_lieu_moi={
                            "nguoi_thue": nguoi_thue.ho_ten,
                            "tieu_de": tieu_de,
                            "noi_dung": noi_dung,
                            "loai": loai,
                            "muc_do": muc_do,
                            "da_doc": False,
                        },
                    )

                messages.success(
                    request,
                    "Tạo thông báo thành công."
                )

                return redirect("quan_ly_thong_bao")

    nguoi_thue = (
        NguoiThue.objects
        .filter(dang_hoat_dong=True)
        .order_by("ho_ten")
    )

    return render(
        request,
        "core/tao_thong_bao.html",
        {
            "nguoi_thue": nguoi_thue,
        }
    )


def xu_ly_thong_bao(request, id):
    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):
        messages.error(
            request,
            "Bạn không có quyền thực hiện thao tác này."
        )
        return redirect("tai_khoan")

    thong_bao = get_object_or_404(
        ThongBao.objects.select_related("nguoi_thue"),
        id=id
    )

    if request.method != "POST":
        return redirect(
            "chi_tiet_thong_bao",
            id=thong_bao.id
        )

    hanh_dong = request.POST.get(
        "hanh_dong",
        ""
    ).strip()

    if hanh_dong == "xoa":
        thong_bao_id = thong_bao.id

        du_lieu_cu = {
            "nguoi_thue": (
                thong_bao.nguoi_thue.ho_ten
                if thong_bao.nguoi_thue
                else ""
            ),
            "tieu_de": thong_bao.tieu_de,
            "noi_dung": thong_bao.noi_dung,
            "loai": thong_bao.loai,
            "muc_do": thong_bao.muc_do,
            "da_doc": thong_bao.da_doc,
        }

        with transaction.atomic():
            ghi_nhat_ky(
                request=request,
                hanh_dong="Xóa",
                module="Thông báo",
                doi_tuong="ThongBao",
                doi_tuong_id=thong_bao_id,
                tieu_de=f"Xóa thông báo #{thong_bao_id}",
                noi_dung=(
                    f"Admin {request.user.username} "
                    f"xóa thông báo: {thong_bao.tieu_de}."
                ),
                du_lieu_cu=du_lieu_cu,
                du_lieu_moi={},
            )

            thong_bao.delete()

        messages.success(
            request,
            "Đã xóa thông báo."
        )
        return redirect("quan_ly_thong_bao")

    if hanh_dong == "da_doc":
        thong_bao.da_doc = True
        update_fields = ["da_doc"]

        if hasattr(thong_bao, "ngay_doc"):
            thong_bao.ngay_doc = timezone.now()
            update_fields.append("ngay_doc")

        thong_bao.save(
            update_fields=update_fields
        )

        messages.success(
            request,
            "Đã đánh dấu thông báo là đã đọc."
        )

    elif hanh_dong == "chua_doc":
        thong_bao.da_doc = False
        update_fields = ["da_doc"]

        if hasattr(thong_bao, "ngay_doc"):
            thong_bao.ngay_doc = None
            update_fields.append("ngay_doc")

        thong_bao.save(
            update_fields=update_fields
        )

        messages.success(
            request,
            "Đã đánh dấu thông báo là chưa đọc."
        )

    elif hanh_dong == "cap_nhat":
        tieu_de = request.POST.get(
            "tieu_de",
            ""
        ).strip()

        noi_dung = request.POST.get(
            "noi_dung",
            ""
        ).strip()

        loai = request.POST.get(
            "loai",
            ""
        ).strip()

        muc_do = request.POST.get(
            "muc_do",
            ""
        ).strip()

        if not tieu_de:
            messages.error(
                request,
                "Tiêu đề thông báo không được để trống."
            )
            return redirect(
                "chi_tiet_thong_bao",
                id=thong_bao.id
            )

        if not noi_dung:
            messages.error(
                request,
                "Nội dung thông báo không được để trống."
            )
            return redirect(
                "chi_tiet_thong_bao",
                id=thong_bao.id
            )

        loai_hop_le = {
            value
            for value, _ in ThongBao._meta.get_field("loai").choices
        }

        muc_do_hop_le = {
            value
            for value, _ in ThongBao._meta.get_field("muc_do").choices
        }

        if loai not in loai_hop_le:
            messages.error(
                request,
                "Loại thông báo không hợp lệ."
            )
            return redirect(
                "chi_tiet_thong_bao",
                id=thong_bao.id
            )

        if muc_do not in muc_do_hop_le:
            messages.error(
                request,
                "Mức độ thông báo không hợp lệ."
            )
            return redirect(
                "chi_tiet_thong_bao",
                id=thong_bao.id
            )

        du_lieu_cu = {
            "tieu_de": thong_bao.tieu_de,
            "noi_dung": thong_bao.noi_dung,
            "loai": thong_bao.loai,
            "muc_do": thong_bao.muc_do,
        }

        thong_bao.tieu_de = tieu_de
        thong_bao.noi_dung = noi_dung
        thong_bao.loai = loai
        thong_bao.muc_do = muc_do
        thong_bao.save(
            update_fields=[
                "tieu_de",
                "noi_dung",
                "loai",
                "muc_do",
            ]
        )

        ghi_nhat_ky(
            request=request,
            hanh_dong="Cập nhật",
            module="Thông báo",
            doi_tuong="ThongBao",
            doi_tuong_id=thong_bao.id,
            tieu_de=f"Cập nhật thông báo #{thong_bao.id}",
            noi_dung=(
                f"Admin {request.user.username} cập nhật "
                f"thông báo #{thong_bao.id}."
            ),
            du_lieu_cu=du_lieu_cu,
            du_lieu_moi={
                "tieu_de": thong_bao.tieu_de,
                "noi_dung": thong_bao.noi_dung,
                "loai": thong_bao.loai,
                "muc_do": thong_bao.muc_do,
            },
        )

        messages.success(
            request,
            "Đã cập nhật thông báo."
        )

    else:
        messages.error(
            request,
            "Thao tác thông báo không hợp lệ."
        )

    return redirect(
        "chi_tiet_thong_bao",
        id=thong_bao.id
    )
