"""Nghiep vu phong."""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from core.tien_ich import ghi_nhat_ky
from core.models import (
    CoSo,
    Phong,
    HinhAnhPhong,
    DatPhong,
    HopDong,

    # Smart Room — Phase 1
    FaceProfile,
    QuyenRaVao,

    # Nhật ký thao tác
)
from core.dich_vu.phan_quyen import la_admin
from core.dich_vu.luu_tru import cap_nhat_trang_thai_luu_tru
from core.dich_vu.trang_thai_phong import transition_room_maintenance
from django.core.exceptions import ValidationError


def quan_ly_phong(request):

    if not request.user.is_authenticated:

        return redirect(
            "dang_nhap"
        )

    if not la_admin(request):

        return redirect(
            "tai_khoan"
        )

    phong = (
        Phong.objects
        .select_related("co_so")
        .order_by(
            "co_so__ten_co_so",
            "so_phong"
        )
    )

    tu_khoa = request.GET.get(
        "q",
        ""
    ).strip()

    if tu_khoa:

        phong = phong.filter(
            Q(
                so_phong__icontains=tu_khoa
            )
            |
            Q(
                co_so__ten_co_so__icontains=tu_khoa
            )
            |
            Q(
                co_so__quan__icontains=tu_khoa
            )
        )

    trang_thai = request.GET.get(
        "trang_thai",
        ""
    ).strip()

    cac_trang_thai = [
        "trong",
        "da_dat",
        "dang_thue",
        "bao_tri",
    ]

    if trang_thai in cac_trang_thai:

        phong = phong.filter(
            trang_thai=trang_thai
        )

    else:

        trang_thai = ""

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

    context = {

        "phong": phong,

        "tong_phong": tong_phong,
        "phong_trong": phong_trong,
        "phong_da_dat": phong_da_dat,
        "phong_dang_thue": phong_dang_thue,
        "phong_bao_tri": phong_bao_tri,

        "tu_khoa": tu_khoa,
        "trang_thai": trang_thai,
    }

    return render(
        request,
        "core/quan_ly_phong.html",
        context
    )


def xoa_phong(request, id):

    # -----------------------------------------------------
    # KIỂM TRA ĐĂNG NHẬP
    # -----------------------------------------------------

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    # -----------------------------------------------------
    # CHỈ ADMIN ĐƯỢC XÓA
    # -----------------------------------------------------

    if not la_admin(request):
        return redirect("tai_khoan")

    # -----------------------------------------------------
    # CHỈ CHO PHÉP XÓA BẰNG POST
    # -----------------------------------------------------

    if request.method != "POST":
        messages.error(
            request,
            "Thao tác xóa phòng không hợp lệ."
        )

        return redirect("quan_ly_phong")

    # -----------------------------------------------------
    # LẤY PHÒNG
    # -----------------------------------------------------

    phong = get_object_or_404(
        Phong,
        id=id
    )

    so_phong = phong.so_phong

    # Lưu dữ liệu trước khi xóa để ghi nhật ký
    du_lieu_cu = {
        "id": phong.id,
        "so_phong": phong.so_phong,
        "co_so": (
            phong.co_so.ten_co_so
            if phong.co_so
            else ""
        ),
        "tang": phong.tang,
        "loai_phong": phong.loai_phong,
        "gia_thue": str(phong.gia_thue),
        "dien_tich": str(phong.dien_tich),
        "so_nguoi_toi_da": phong.so_nguoi_toi_da,
        "trang_thai": phong.trang_thai,
    }

    # -----------------------------------------------------
    # KHÔNG CHO XÓA PHÒNG ĐANG THUÊ
    # -----------------------------------------------------

    if phong.trang_thai == "dang_thue":

        messages.error(
            request,
            f"Không thể xóa phòng P{so_phong} vì phòng đang có người thuê."
        )

        return redirect("quan_ly_phong")

    # -----------------------------------------------------
    # KHÔNG CHO XÓA PHÒNG ĐANG ĐƯỢC ĐẶT
    # -----------------------------------------------------

    if phong.trang_thai == "da_dat":

        messages.error(
            request,
            f"Không thể xóa phòng P{so_phong} vì phòng đang được đặt."
        )

        return redirect("quan_ly_phong")

    # -----------------------------------------------------
    # KIỂM TRA HỢP ĐỒNG LIÊN QUAN
    # -----------------------------------------------------

    try:

        if HopDong.objects.filter(
            dat_phong__phong=phong
        ).exists():

            messages.error(
                request,
                f"Không thể xóa phòng P{so_phong} vì phòng đã có hợp đồng liên quan."
            )

            return redirect("quan_ly_phong")

    except Exception:
        pass

    # -----------------------------------------------------
    # KIỂM TRA ĐƠN ĐẶT PHÒNG LIÊN QUAN
    # -----------------------------------------------------

    try:

        if DatPhong.objects.filter(
            phong=phong
        ).exists():

            messages.error(
                request,
                f"Không thể xóa phòng P{so_phong} vì phòng đã có dữ liệu đặt phòng."
            )

            return redirect("quan_ly_phong")

    except Exception:
        pass

    # -----------------------------------------------------
    # XÓA PHÒNG
    # -----------------------------------------------------

    try:

        phong.delete()

        # -------------------------------------------------
        # GHI NHẬT KÝ THAO TÁC
        # -------------------------------------------------

        ghi_nhat_ky(
            request=request,
            hanh_dong="Xóa",
            module="Phòng",
            doi_tuong="Phong",
            doi_tuong_id=phong.id,
            tieu_de=f"Xóa phòng {so_phong}",
            noi_dung=(
                f"Admin {request.user.username} "
                f"đã xóa phòng {so_phong}."
            ),
            du_lieu_cu=du_lieu_cu,
            du_lieu_moi={},
        )

        messages.success(
            request,
            f"Đã xóa phòng P{so_phong} thành công."
        )

    except Exception as e:

        messages.error(
            request,
            f"Không thể xóa phòng P{so_phong}. "
            f"Phòng có thể đang được sử dụng bởi dữ liệu khác."
        )

    return redirect("quan_ly_phong")


def tao_phong(request):

    # =====================================================
    # KIỂM TRA QUYỀN
    # =====================================================

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):

        messages.error(
            request,
            "Bạn không có quyền thực hiện chức năng này."
        )

        return redirect("tai_khoan")

    # =====================================================
    # DANH SÁCH CƠ SỞ ĐANG HOẠT ĐỘNG
    # =====================================================

    co_so_list = (
        CoSo.objects
        .filter(trang_thai="hoat_dong")
        .order_by("ten_co_so")
    )

    # =====================================================
    # HÀM RENDER FORM
    # =====================================================

    def render_form():

        return render(
            request,
            "core/tao_phong.html",
            {
                "co_so_list": co_so_list,
                "loai_phong_choices": Phong.LOAI_PHONG,
            }
        )

    # =====================================================
    # GET
    # =====================================================

    if request.method != "POST":
        return render_form()

    # =====================================================
    # LẤY DỮ LIỆU POST
    # =====================================================

    co_so_id = request.POST.get(
        "co_so",
        ""
    ).strip()

    so_phong = request.POST.get(
        "so_phong",
        ""
    ).strip()

    tang_raw = request.POST.get(
        "tang",
        ""
    ).strip()

    loai_phong = request.POST.get(
        "loai_phong",
        ""
    ).strip()

    gia_thue_raw = request.POST.get(
        "gia_thue",
        ""
    ).strip()

    dien_tich_raw = request.POST.get(
        "dien_tich",
        ""
    ).strip()

    so_nguoi_toi_da_raw = request.POST.get(
        "so_nguoi_toi_da",
        ""
    ).strip()

    tien_coc_mac_dinh_raw = request.POST.get(
        "tien_coc_mac_dinh",
        ""
    ).strip()

    tien_dien_moi_so_raw = request.POST.get(
        "tien_dien_moi_so",
        ""
    ).strip()

    tien_nuoc_moi_khoi_raw = request.POST.get(
        "tien_nuoc_moi_khoi",
        ""
    ).strip()

    phi_dich_vu_raw = request.POST.get(
        "phi_dich_vu",
        ""
    ).strip()

    trang_thai = request.POST.get(
        "trang_thai",
        "trong"
    ).strip()

    tien_ich = request.POST.get(
        "tien_ich",
        ""
    ).strip()

    mo_ta = request.POST.get(
        "mo_ta",
        ""
    ).strip()

    hinh_anh_upload = request.FILES.getlist(
        "hinh_anh"
    )

    # =====================================================
    # KIỂM TRA CƠ SỞ
    # =====================================================

    if not co_so_id:

        messages.error(
            request,
            "Vui lòng chọn cơ sở."
        )

        return render_form()

    try:

        co_so = CoSo.objects.get(
            id=co_so_id,
            trang_thai="hoat_dong"
        )

    except (
        CoSo.DoesNotExist,
        ValueError,
    ):

        messages.error(
            request,
            "Cơ sở không hợp lệ hoặc đã ngừng hoạt động."
        )

        return render_form()

    # =====================================================
    # KIỂM TRA SỐ PHÒNG
    # =====================================================

    if not so_phong:

        messages.error(
            request,
            "Vui lòng nhập số phòng."
        )

        return render_form()

    phong_trung = (
        Phong.objects
        .filter(
            co_so=co_so,
            so_phong__iexact=so_phong
        )
        .exists()
    )

    if phong_trung:

        messages.error(
            request,
            (
                f"Phòng {so_phong} đã tồn tại "
                f"tại {co_so.ten_co_so}."
            )
        )

        return render_form()

    # =====================================================
    # KIỂM TRA LOẠI PHÒNG
    # =====================================================

    cac_loai_phong_hop_le = [
        value
        for value, label
        in Phong.LOAI_PHONG
    ]

    if loai_phong not in cac_loai_phong_hop_le:

        messages.error(
            request,
            "Vui lòng chọn loại phòng hợp lệ."
        )

        return render_form()

    # =====================================================
    # KIỂM TRA TRƯỜNG BẮT BUỘC
    # =====================================================

    if not tang_raw:

        messages.error(
            request,
            "Vui lòng nhập tầng."
        )

        return render_form()

    if not gia_thue_raw:

        messages.error(
            request,
            "Vui lòng nhập giá thuê."
        )

        return render_form()

    if not dien_tich_raw:

        messages.error(
            request,
            "Vui lòng nhập diện tích."
        )

        return render_form()

    if not so_nguoi_toi_da_raw:

        messages.error(
            request,
            "Vui lòng nhập số người tối đa."
        )

        return render_form()

    # =====================================================
    # CHUYỂN KIỂU DỮ LIỆU
    # =====================================================

    try:

        tang = int(
            tang_raw
        )

        gia_thue = Decimal(
            gia_thue_raw
        )

        dien_tich = Decimal(
            dien_tich_raw
        )

        so_nguoi_toi_da = int(
            so_nguoi_toi_da_raw
        )

        tien_coc_mac_dinh = Decimal(
            tien_coc_mac_dinh_raw or 0
        )

        tien_dien_moi_so = Decimal(
            tien_dien_moi_so_raw or 0
        )

        tien_nuoc_moi_khoi = Decimal(
            tien_nuoc_moi_khoi_raw or 0
        )

        phi_dich_vu = Decimal(
            phi_dich_vu_raw or 0
        )

    except (
        ValueError,
        InvalidOperation,
    ):

        messages.error(
            request,
            "Dữ liệu số không hợp lệ. Vui lòng kiểm tra lại."
        )

        return render_form()

    # =====================================================
    # KIỂM TRA GIÁ TRỊ
    # =====================================================

    if tang < 1:

        messages.error(
            request,
            "Tầng phải lớn hơn hoặc bằng 1."
        )

        return render_form()

    if gia_thue <= 0:

        messages.error(
            request,
            "Giá thuê phải lớn hơn 0."
        )

        return render_form()

    if dien_tich <= 0:

        messages.error(
            request,
            "Diện tích phải lớn hơn 0."
        )

        return render_form()

    if so_nguoi_toi_da < 1:

        messages.error(
            request,
            "Số người tối đa phải lớn hơn hoặc bằng 1."
        )

        return render_form()

    if (
        tien_coc_mac_dinh < 0
        or tien_dien_moi_so < 0
        or tien_nuoc_moi_khoi < 0
        or phi_dich_vu < 0
    ):

        messages.error(
            request,
            "Các khoản tiền và chi phí không được âm."
        )

        return render_form()

    # =====================================================
    # KIỂM TRA TRẠNG THÁI BAN ĐẦU
    # =====================================================

    # Phòng mới chỉ được:
    # - Trống
    # - Bảo trì
    #
    # Đã đặt / Đang thuê phải phát sinh từ nghiệp vụ thật.

    if trang_thai not in [
        "trong",
        "bao_tri",
    ]:

        messages.error(
            request,
            "Trạng thái ban đầu của phòng không hợp lệ."
        )

        return render_form()

    # =====================================================
    # TẠO PHÒNG
    # =====================================================

    with transaction.atomic():

        phong = Phong.objects.create(
            co_so=co_so,
            so_phong=so_phong,
            tang=tang,
            loai_phong=loai_phong,
            gia_thue=gia_thue,
            dien_tich=dien_tich,
            so_nguoi_toi_da=so_nguoi_toi_da,
            tien_coc_mac_dinh=tien_coc_mac_dinh,
            tien_dien_moi_so=tien_dien_moi_so,
            tien_nuoc_moi_khoi=tien_nuoc_moi_khoi,
            phi_dich_vu=phi_dich_vu,
            tien_ich=tien_ich,
            mo_ta=mo_ta,
            trang_thai=trang_thai,
        )

        # =================================================
        # HÌNH ẢNH PHÒNG
        # =================================================

        for thu_tu, tep_anh in enumerate(
            hinh_anh_upload
        ):
            HinhAnhPhong.objects.create(
                phong=phong,
                anh=tep_anh,
                mo_ta=(
                    f"Phòng {phong.so_phong}"
                ),
                la_anh_dai_dien=(
                    thu_tu == 0
                ),
                thu_tu=thu_tu,
            )

        # =================================================
        # NHẬT KÝ
        # =================================================

        ghi_nhat_ky(
            request=request,
            hanh_dong="Tạo mới",
            module="Phòng",
            doi_tuong="Phong",
            doi_tuong_id=phong.id,
            tieu_de=(
                f"Tạo phòng {phong.so_phong}"
            ),
            noi_dung=(
                f"Admin {request.user.username} "
                f"đã tạo phòng {phong.so_phong} "
                f"tại {co_so.ten_co_so}."
            ),
            du_lieu_cu={},
            du_lieu_moi={
                "id": phong.id,
                "co_so": co_so.ten_co_so,
                "so_phong": phong.so_phong,
                "tang": phong.tang,
                "loai_phong": phong.loai_phong,
                "gia_thue": str(
                    phong.gia_thue
                ),
                "dien_tich": str(
                    phong.dien_tich
                ),
                "so_nguoi_toi_da":
                    phong.so_nguoi_toi_da,
                "tien_coc_mac_dinh": str(
                    phong.tien_coc_mac_dinh
                ),
                "tien_dien_moi_so": str(
                    phong.tien_dien_moi_so
                ),
                "tien_nuoc_moi_khoi": str(
                    phong.tien_nuoc_moi_khoi
                ),
                "phi_dich_vu": str(
                    phong.phi_dich_vu
                ),
                "tien_ich":
                    phong.tien_ich,
                "trang_thai":
                    phong.trang_thai,
                "mo_ta":
                    phong.mo_ta,
            },
        )

    messages.success(
        request,
        (
            f"Đã tạo phòng {phong.so_phong} "
            f"tại {co_so.ten_co_so} thành công."
        )
    )

    return redirect(
        "quan_ly_phong"
    )


def sua_phong(request, id):

    # =====================================================
    # KIỂM TRA QUYỀN
    # =====================================================

    if not request.user.is_authenticated:
        return redirect("dang_nhap")

    if not la_admin(request):

        messages.error(
            request,
            "Bạn không có quyền thực hiện chức năng này."
        )

        return redirect("tai_khoan")

    # =====================================================
    # LẤY PHÒNG
    # =====================================================

    phong = get_object_or_404(
        Phong.objects.select_related("co_so"),
        id=id
    )

    # -----------------------------------------------------
    # ĐỒNG BỘ LẠI TRẠNG THÁI TRƯỚC KHI SỬA
    # -----------------------------------------------------

    phong.dong_bo_trang_thai()

    phong.refresh_from_db()

    # =====================================================
    # DANH SÁCH CƠ SỞ ĐANG HOẠT ĐỘNG
    # =====================================================

    cac_co_so = (
        CoSo.objects
        .filter(trang_thai="hoat_dong")
        .order_by("ten_co_so")
    )

    def lay_thong_tin_luu_tru():
        hom_nay = timezone.localdate()
        hop_dong = (
            HopDong.objects
            .filter(
                dat_phong__phong=phong,
                dat_phong__trang_thai="da_duyet",
                ngay_bat_dau__lte=hom_nay,
                ngay_ket_thuc__gte=hom_nay,
                trang_thai__in=[
                    "dang_hieu_luc",
                    "sap_het_han",
                ],
            )
            .select_related(
                "dat_phong",
                "dat_phong__nguoi_thue",
                "dat_phong__phong",
            )
            .order_by("-ngay_bat_dau", "-id")
            .first()
        )

        nguoi_thue = None
        face_profile = None
        quyen_ra_vao = None

        if hop_dong:
            nguoi_thue = hop_dong.dat_phong.nguoi_thue

            face_profile = (
                FaceProfile.objects
                .filter(nguoi_thue=nguoi_thue)
                .first()
            )

            quyen_ra_vao = (
                QuyenRaVao.objects
                .filter(
                    hop_dong=hop_dong,
                    phong=phong,
                    nguoi_thue=nguoi_thue,
                    nguoi_o_cung__isnull=True,
                )
                .order_by("-id")
                .first()
            )

        return {
            "hop_dong": hop_dong,
            "nguoi_thue": nguoi_thue,
            "face_profile": face_profile,
            "quyen_ra_vao": quyen_ra_vao,
        }

    # =====================================================
    # HÀM RENDER FORM
    # =====================================================

    def render_form():

        return render(
            request,
            "core/sua_phong.html",
            {
                "phong": phong,
                "cac_co_so": cac_co_so,
                "trang_thai_nghiep_vu":
                    phong.trang_thai_nghiep_vu(),
                "so_nguoi_dang_o":
                    phong.so_nguoi_dang_o,
                # Chuỗi số dùng riêng cho input HTML type=number.
                # Tránh Decimal bị localize thành dấu phẩy làm trình duyệt
                # coi value là không hợp lệ / gửi rỗng.
                "dien_tich_input": (
                    format(phong.dien_tich, "f")
                    .rstrip("0")
                    .rstrip(".")
                ),
                "hinh_anh_phong": (
                    phong.hinh_anh
                    .all()
                    .order_by("thu_tu", "id")
                ),
                "thong_tin_luu_tru": lay_thong_tin_luu_tru(),
            }
        )

    # =====================================================
    # GET
    # =====================================================

    if request.method != "POST":
        return render_form()

    if request.POST.get("hanh_dong") == "cap_nhat_luu_tru":
        thong_tin_luu_tru = lay_thong_tin_luu_tru()
        nguoi_thue = thong_tin_luu_tru["nguoi_thue"]

        if not nguoi_thue:
            messages.error(
                request,
                "Phòng hiện không có người thuê đang ở để cập nhật lưu trú."
            )
            return redirect("sua_phong", id=phong.id)

        trang_thai_moi = request.POST.get(
            "trang_thai_luu_tru",
            ""
        ).strip()

        try:
            so_quyen_thu_hoi = cap_nhat_trang_thai_luu_tru(
                nguoi_thue,
                trang_thai_moi,
                nguoi_thuc_hien=request.user,
            )
        except ValueError:
            messages.error(
                request,
                "Trạng thái lưu trú không hợp lệ."
            )
            return redirect("sua_phong", id=phong.id)

        if trang_thai_moi == "da_tra_phong":
            messages.success(
                request,
                (
                    "Đã đánh dấu người thuê là đã trả phòng và thu hồi "
                    f"{so_quyen_thu_hoi} quyền ra vào đang hiệu lực. "
                    "Tài khoản người thuê vẫn được giữ để đăng nhập."
                )
            )
        else:
            messages.success(
                request,
                "Đã cập nhật trạng thái lưu trú của người thuê."
            )

        return redirect("sua_phong", id=phong.id)

    # =====================================================
    # LẤY DỮ LIỆU POST
    # =====================================================

    co_so_id = request.POST.get(
        "co_so",
        ""
    ).strip()

    so_phong = request.POST.get(
        "so_phong",
        ""
    ).strip()

    tang_raw = request.POST.get(
        "tang",
        ""
    ).strip()

    loai_phong = request.POST.get(
        "loai_phong",
        ""
    ).strip()

    gia_thue_raw = request.POST.get(
        "gia_thue",
        ""
    ).strip()

    dien_tich_raw = request.POST.get(
        "dien_tich",
        ""
    ).strip()

    tien_ich = request.POST.get(
        "tien_ich",
        ""
    ).strip()

    so_nguoi_toi_da_raw = request.POST.get(
        "so_nguoi_toi_da",
        ""
    ).strip()

    tien_dien_moi_so_raw = request.POST.get(
        "tien_dien_moi_so",
        ""
    ).strip()

    tien_nuoc_moi_khoi_raw = request.POST.get(
        "tien_nuoc_moi_khoi",
        ""
    ).strip()

    phi_dich_vu_raw = request.POST.get(
        "phi_dich_vu",
        ""
    ).strip()

    tien_coc_mac_dinh_raw = request.POST.get(
        "tien_coc_mac_dinh",
        ""
    ).strip()

    trang_thai_yeu_cau = request.POST.get(
        "trang_thai",
        ""
    ).strip()

    mo_ta = request.POST.get(
        "mo_ta",
        ""
    ).strip()

    hinh_anh_upload = request.FILES.getlist(
        "hinh_anh"
    )

    anh_dai_dien_id = request.POST.get(
        "anh_dai_dien_id",
        ""
    ).strip()

    xoa_anh_ids = request.POST.getlist(
        "xoa_anh"
    )

    # =====================================================
    # KIỂM TRA CƠ SỞ
    # =====================================================

    if not co_so_id:

        messages.error(
            request,
            "Vui lòng chọn cơ sở."
        )

        return render_form()

    try:

        co_so = CoSo.objects.get(
            id=co_so_id,
            trang_thai="hoat_dong"
        )

    except (
        CoSo.DoesNotExist,
        ValueError,
    ):

        messages.error(
            request,
            "Cơ sở không hợp lệ hoặc đã ngừng hoạt động."
        )

        return render_form()

    # =====================================================
    # KIỂM TRA SỐ PHÒNG
    # =====================================================

    if not so_phong:

        messages.error(
            request,
            "Vui lòng nhập số phòng."
        )

        return render_form()

    # Không phân biệt chữ hoa / chữ thường.
    # Ví dụ P101 và p101 được xem là cùng một phòng.
    phong_trung = (
        Phong.objects
        .filter(
            co_so=co_so,
            so_phong__iexact=so_phong
        )
        .exclude(
            id=phong.id
        )
        .exists()
    )

    if phong_trung:

        messages.error(
            request,
            (
                f"Phòng {so_phong} đã tồn tại "
                f"tại {co_so.ten_co_so}."
            )
        )

        return render_form()

    # =====================================================
    # KIỂM TRA LOẠI PHÒNG
    # =====================================================

    if not loai_phong:

        messages.error(
            request,
            "Vui lòng chọn loại phòng."
        )

        return render_form()

    cac_loai_phong_hop_le = [
        value
        for value, label
        in Phong.LOAI_PHONG
    ]

    if loai_phong not in cac_loai_phong_hop_le:

        messages.error(
            request,
            "Loại phòng không hợp lệ."
        )

        return render_form()

    # =====================================================
    # KIỂM TRA CÁC TRƯỜNG BẮT BUỘC
    # =====================================================

    if not tang_raw:

        messages.error(
            request,
            "Vui lòng nhập tầng."
        )

        return render_form()

    if not gia_thue_raw:

        messages.error(
            request,
            "Vui lòng nhập giá thuê phòng."
        )

        return render_form()

    if not dien_tich_raw:

        messages.error(
            request,
            "Vui lòng nhập diện tích phòng."
        )

        return render_form()

    if not so_nguoi_toi_da_raw:

        messages.error(
            request,
            "Vui lòng nhập số người tối đa."
        )

        return render_form()

    # =====================================================
    # CHUYỂN KIỂU DỮ LIỆU
    # =====================================================

    try:

        tang = int(
            tang_raw
        )

        gia_thue = Decimal(
            gia_thue_raw
        )

        dien_tich = Decimal(
            dien_tich_raw
        )

        so_nguoi_toi_da = int(
            so_nguoi_toi_da_raw
        )

        tien_dien_moi_so = Decimal(
            tien_dien_moi_so_raw or 0
        )

        tien_nuoc_moi_khoi = Decimal(
            tien_nuoc_moi_khoi_raw or 0
        )

        phi_dich_vu = Decimal(
            phi_dich_vu_raw or 0
        )

        tien_coc_mac_dinh = Decimal(
            tien_coc_mac_dinh_raw or 0
        )

    except (
        ValueError,
        InvalidOperation,
    ):

        messages.error(
            request,
            (
                "Dữ liệu số không hợp lệ. "
                "Vui lòng kiểm tra tầng, giá thuê, diện tích, "
                "sức chứa và các khoản chi phí."
            )
        )

        return render_form()

    # =====================================================
    # KIỂM TRA GIÁ TRỊ
    # =====================================================

    if tang < 1:

        messages.error(
            request,
            "Tầng phải lớn hơn hoặc bằng 1."
        )

        return render_form()

    if gia_thue <= 0:

        messages.error(
            request,
            "Giá thuê phòng phải lớn hơn 0."
        )

        return render_form()

    if dien_tich <= 0:

        messages.error(
            request,
            "Diện tích phòng phải lớn hơn 0."
        )

        return render_form()

    if so_nguoi_toi_da < 0:

        messages.error(
            request,
            "Sức chứa không được âm; 0 là chưa cấu hình."
        )

        return render_form()

    if tien_dien_moi_so < 0:

        messages.error(
            request,
            "Tiền điện không được nhỏ hơn 0."
        )

        return render_form()

    if tien_nuoc_moi_khoi < 0:

        messages.error(
            request,
            "Tiền nước không được nhỏ hơn 0."
        )

        return render_form()

    if phi_dich_vu < 0:

        messages.error(
            request,
            "Phí dịch vụ không được nhỏ hơn 0."
        )

        return render_form()

    if tien_coc_mac_dinh < 0:

        messages.error(
            request,
            "Tiền cọc mặc định không được nhỏ hơn 0."
        )

        return render_form()

    # =====================================================
    # KIỂM TRA SỨC CHỨA
    # =====================================================

    so_nguoi_dang_o = (
        phong.so_nguoi_dang_o
    )

    if (
        so_nguoi_toi_da != phong.so_nguoi_toi_da
        and so_nguoi_toi_da < so_nguoi_dang_o
    ):

        messages.error(
            request,
            (
                f"Không thể giảm sức chứa xuống "
                f"{so_nguoi_toi_da} người vì phòng hiện "
                f"đang có {so_nguoi_dang_o} người ở."
            )
        )

        return render_form()

    # =====================================================
    # KIỂM TRA TRẠNG THÁI GỬI LÊN
    # =====================================================

    cac_trang_thai_hop_le = [
        value
        for value, label
        in Phong.TRANG_THAI
    ]

    if (
        trang_thai_yeu_cau
        not in cac_trang_thai_hop_le
    ):

        messages.error(
            request,
            "Trạng thái phòng không hợp lệ."
        )

        return render_form()

    # =====================================================
    # XÁC ĐỊNH TRẠNG THÁI ĐÚNG THEO NGHIỆP VỤ
    # =====================================================

    trang_thai_nghiep_vu = (
        phong.trang_thai_nghiep_vu()
    )

    maintenance_transition = (
        trang_thai_yeu_cau == "bao_tri"
        or phong.trang_thai == "bao_tri"
    )

    if maintenance_transition:
        # The service re-reads all facts under the room lock.  Do not trust this
        # pre-transaction state for either entering or leaving maintenance.
        trang_thai_luu = None
    else:

            # Không cho Admin tự sửa các trạng thái:
            #
            # trống
            # đã đặt
            # đang thuê
            #
            # Các trạng thái này phải được xác định
            # từ đơn đặt phòng và hợp đồng.

        if trang_thai_yeu_cau != trang_thai_nghiep_vu:

            ten_trang_thai = dict(Phong.TRANG_THAI).get(
                trang_thai_nghiep_vu, trang_thai_nghiep_vu
            )

            messages.error(
                request,
                (
                    "Trạng thái phòng được hệ thống xác định tự động theo đặt phòng "
                    f"và hợp đồng. Trạng thái đúng hiện tại là '{ten_trang_thai}'."
                )
            )

            return render_form()

        trang_thai_luu = trang_thai_nghiep_vu

    # =====================================================
    # LƯU DỮ LIỆU CŨ CHO NHẬT KÝ
    # =====================================================

    du_lieu_cu = {
        "id": phong.id,
        "co_so": (
            phong.co_so.ten_co_so
            if phong.co_so
            else ""
        ),
        "so_phong": phong.so_phong,
        "tang": phong.tang,
        "loai_phong": phong.loai_phong,
        "gia_thue": str(
            phong.gia_thue
        ),
        "dien_tich": str(
            phong.dien_tich
        ),
        "tien_ich": phong.tien_ich,
        "so_nguoi_toi_da":
            phong.so_nguoi_toi_da,
        "tien_dien_moi_so": str(
            phong.tien_dien_moi_so
        ),
        "tien_nuoc_moi_khoi": str(
            phong.tien_nuoc_moi_khoi
        ),
        "phi_dich_vu": str(
            phong.phi_dich_vu
        ),
        "tien_coc_mac_dinh": str(
            phong.tien_coc_mac_dinh
        ),
        "trang_thai":
            phong.trang_thai,
        "mo_ta":
            phong.mo_ta,
    }

    # =====================================================
    # CẬP NHẬT PHÒNG
    # =====================================================

    with transaction.atomic():

        if maintenance_transition:
            try:
                phong = transition_room_maintenance(
                    actor=request.user,
                    room_id=phong.pk,
                    entering=trang_thai_yeu_cau == "bao_tri",
                )
            except ValidationError as error:
                messages.error(request, str(error))
                return render_form()

        phong.co_so = co_so

        phong.so_phong = so_phong

        phong.tang = tang

        phong.loai_phong = loai_phong

        phong.gia_thue = gia_thue

        phong.dien_tich = dien_tich

        phong.tien_ich = tien_ich

        phong.so_nguoi_toi_da = (
            so_nguoi_toi_da
        )

        phong.tien_dien_moi_so = (
            tien_dien_moi_so
        )

        phong.tien_nuoc_moi_khoi = (
            tien_nuoc_moi_khoi
        )

        phong.phi_dich_vu = (
            phi_dich_vu
        )

        phong.tien_coc_mac_dinh = (
            tien_coc_mac_dinh
        )

        if not maintenance_transition:
            phong.trang_thai = trang_thai_luu

        phong.mo_ta = mo_ta

        phong.save()

        # =================================================
        # CẬP NHẬT HÌNH ẢNH PHÒNG
        # =================================================

        if xoa_anh_ids:
            (
                phong.hinh_anh
                .filter(id__in=xoa_anh_ids)
                .delete()
            )

        thu_tu_bat_dau = (
            phong.hinh_anh.count()
        )

        for vi_tri, tep_anh in enumerate(
            hinh_anh_upload
        ):
            HinhAnhPhong.objects.create(
                phong=phong,
                anh=tep_anh,
                mo_ta=(
                    f"Phòng {phong.so_phong}"
                ),
                la_anh_dai_dien=False,
                thu_tu=(
                    thu_tu_bat_dau
                    + vi_tri
                ),
            )

        if anh_dai_dien_id:
            anh_dai_dien = (
                phong.hinh_anh
                .filter(id=anh_dai_dien_id)
                .first()
            )

            if anh_dai_dien:
                anh_dai_dien.la_anh_dai_dien = True
                anh_dai_dien.save(
                    update_fields=[
                        "la_anh_dai_dien",
                        "ngay_cap_nhat",
                    ]
                )

        # Nếu sau các thao tác vẫn còn ảnh nhưng chưa có
        # ảnh đại diện, tự chọn ảnh đầu tiên.
        if (
            phong.hinh_anh.exists()
            and not phong.hinh_anh.filter(
                la_anh_dai_dien=True
            ).exists()
        ):
            anh_dau_tien = (
                phong.hinh_anh
                .order_by("thu_tu", "id")
                .first()
            )

            anh_dau_tien.la_anh_dai_dien = True
            anh_dau_tien.save(
                update_fields=[
                    "la_anh_dai_dien",
                    "ngay_cap_nhat",
                ]
            )

        # =================================================
        # ĐỒNG BỘ TRẠNG THÁI LẦN CUỐI
        # =================================================

        if not maintenance_transition and phong.trang_thai != "bao_tri":

            phong.dong_bo_trang_thai(
                giu_bao_tri=False
            )

        phong.refresh_from_db()

        # =================================================
        # DỮ LIỆU MỚI CHO NHẬT KÝ
        # =================================================

        du_lieu_moi = {
            "id": phong.id,
            "co_so": (
                phong.co_so.ten_co_so
                if phong.co_so
                else ""
            ),
            "so_phong": phong.so_phong,
            "tang": phong.tang,
            "loai_phong": phong.loai_phong,
            "gia_thue": str(
                phong.gia_thue
            ),
            "dien_tich": str(
                phong.dien_tich
            ),
            "tien_ich": phong.tien_ich,
            "so_nguoi_toi_da":
                phong.so_nguoi_toi_da,
            "tien_dien_moi_so": str(
                phong.tien_dien_moi_so
            ),
            "tien_nuoc_moi_khoi": str(
                phong.tien_nuoc_moi_khoi
            ),
            "phi_dich_vu": str(
                phong.phi_dich_vu
            ),
            "tien_coc_mac_dinh": str(
                phong.tien_coc_mac_dinh
            ),
            "trang_thai":
                phong.trang_thai,
            "mo_ta":
                phong.mo_ta,
        }

        # =================================================
        # NHẬT KÝ
        # =================================================

        ghi_nhat_ky(
            request=request,
            hanh_dong="Cập nhật",
            module="Phòng",
            doi_tuong="Phong",
            doi_tuong_id=phong.id,
            tieu_de=(
                f"Cập nhật phòng "
                f"{phong.so_phong}"
            ),
            noi_dung=(
                f"Admin {request.user.username} "
                f"đã cập nhật thông tin phòng "
                f"{phong.so_phong}."
            ),
            du_lieu_cu=du_lieu_cu,
            du_lieu_moi=du_lieu_moi,
        )

    messages.success(
        request,
        (
            f"Đã cập nhật phòng "
            f"{phong.so_phong} thành công."
        )
    )

    return redirect(
        "quan_ly_phong"
    )
