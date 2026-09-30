from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from core.views_chinh_sach import chinh_sach_ho_tro
from core.views_dat_phong import dat_phong_cua_toi, chi_tiet_dat_phong_cua_toi, thanh_toan_coc_cua_toi
from core.views_quan_tri_dat_phong import (
    quan_ly_dat_phong as admin_quan_ly_dat_phong,
    chi_tiet_dat_phong as admin_chi_tiet_dat_phong,
    xac_nhan_dat_phong_va_tao_hop_dong,
    tu_choi_thanh_toan_coc,
    tu_choi_yeu_cau_dat_phong,
)
from core.views_thong_bao import (
    thong_bao_admin,
    chi_tiet_thong_bao_admin,
    doc_thong_bao_admin,
    doc_tat_ca_thong_bao_admin,
    kiem_tra_thong_bao_admin_moi,
    kiem_tra_thong_bao_cua_toi_moi,
)
from django.conf import settings
from django.conf.urls.static import static

# Nghiep vu: quan tri
from core.views_quan_tri import (
    home,
    dashboard_admin,
    quan_ly_dat_phong,
    chi_tiet_dat_phong,
    xu_ly_dat_phong,
    quan_ly_co_so,
    chi_tiet_co_so,
    tao_co_so,
    xu_ly_co_so,
)

# Nghiep vu: phong
from core.views_phong import (
    danh_sach_phong,
    chi_tiet_phong,
    quan_ly_phong,
    tao_phong,
    sua_phong,
    xoa_phong,
)

# Nghiep vu: dat phong
from core.views_dat_phong import (
    dat_phong,
    huy_dat_phong_cua_toi,
)

# Nghiep vu: thong bao
from core.views_thong_bao import (
    thong_bao_cua_toi,
    chi_tiet_thong_bao_cua_toi,
    quan_ly_thong_bao,
    chi_tiet_thong_bao,
    tao_thong_bao,
    xu_ly_thong_bao,
)

# Nghiep vu: tai khoan
from core.views_tai_khoan import (
    doi_mat_khau,
    cap_nhat_thong_tin,
    tai_khoan,
)

# Nghiep vu: dang nhap
from core.views_dang_nhap import (
    dang_ky,
    dang_nhap,
    dang_xuat,
)

# Nghiep vu: nhat ky
from core.views_nhat_ky import (
    nhat_ky_thao_tac,
    chi_tiet_nhat_ky_thao_tac,
)

# Nghiep vu: hop dong
from core.views_hop_dong import (
    tao_hop_dong,
    quan_ly_hop_dong,
    chi_tiet_hop_dong,
    xu_ly_hop_dong,
    sua_hop_dong,
    hop_dong_cua_toi,
    chi_tiet_hop_dong_cua_toi,
    xuat_hop_dong_pdf,
)

# Nghiep vu: gia han
from core.views_gia_han import (
    xu_ly_yeu_cau_gia_han,
    gui_yeu_cau_gia_han,
    huy_yeu_cau_gia_han,
)

# Nghiep vu: hoa don
from core.views_hoa_don import (
    hoa_don_cua_toi,
    chi_tiet_hoa_don_cua_toi,
    quan_ly_hoa_don,
    chi_tiet_hoa_don,
    tao_hoa_don,
)

# Nghiep vu: thanh toan
from core.views_thanh_toan import (
    thanh_toan_hoa_don_cua_toi,
    xu_ly_hoa_don,
)

# Nghiep vu: nguoi thue
from core.views_nguoi_thue import (
    quan_ly_nguoi_thue,
    chi_tiet_nguoi_thue,
)

# Nghiep vu: o ghep
from core.views_o_ghep import (
    quan_ly_yeu_cau_ghep_admin,
    dang_ky_ghep_phong,
    bat_tat_cho_phep_ghep,
    yeu_cau_ghep_cua_toi,
    chi_tiet_yeu_cau_ghep,
    xu_ly_yeu_cau_ghep,
)

# Nghiep vu: sua chua
from core.views_sua_chua import (
    quan_ly_sua_chua,
    chi_tiet_sua_chua,
    xu_ly_sua_chua,
    tao_sua_chua,
    yeu_cau_sua_chua_cua_toi,
    tao_yeu_cau_sua_chua,
    chi_tiet_yeu_cau_sua_chua_cua_toi,
)

# Nghiep vu: chinh sach
from core.views_chinh_sach import (
    quan_ly_chinh_sach,
    chi_tiet_chinh_sach,
    tao_chinh_sach,
    xu_ly_chinh_sach,
)

# Nghiep vu: smart room
from core.views_smart_room import (
    smart_room_dashboard,
    smart_access_control,
    quan_ly_nguoi_o_cung,
    tao_nguoi_o_cung,
    chi_tiet_nguoi_o_cung,
    xu_ly_nguoi_o_cung,
    quan_ly_face_profile,
    tao_face_profile,
    chi_tiet_face_profile,
    xu_ly_face_profile,
    nhan_dien_su_dung_phong,
    face_id_dang_ky,
    trang_xac_thuc_face_id,
    face_id_xac_thuc,
    quan_ly_quyen_ra_vao,
    tao_quyen_ra_vao,
    chi_tiet_quyen_ra_vao,
    xu_ly_quyen_ra_vao,
    quan_ly_lich_su_ra_vao,
    tao_lich_su_ra_vao,
    chi_tiet_lich_su_ra_vao,
    xu_ly_lich_su_ra_vao,
)


urlpatterns = [
    path('dat-phong-cua-toi/', dat_phong_cua_toi, name='dat_phong_cua_toi'),
    path('dat-phong-cua-toi/<int:id>/', chi_tiet_dat_phong_cua_toi, name='chi_tiet_dat_phong_cua_toi'),
    path('dat-phong-cua-toi/<int:id>/thanh-toan-coc/', thanh_toan_coc_cua_toi, name='thanh_toan_coc_cua_toi'),
    path('dat-phong-cua-toi/<int:id>/huy/', huy_dat_phong_cua_toi, name='huy_dat_phong_cua_toi'),
    path('chinh-sach-ho-tro/', chinh_sach_ho_tro, name='chinh_sach_ho_tro'),

    # =====================================================
    # DJANGO ADMIN
    # =====================================================

    path(
        "admin/",
        admin.site.urls
    ),

    # =====================================================
    # TRANG CHỦ
    # =====================================================

    path(
        "",
        home,
        name="home"
    ),

    # =====================================================
    # PHÒNG - NGƯỜI DÙNG
    # =====================================================

    path(
        "phong/",
        danh_sach_phong,
        name="danh_sach_phong"
    ),

    path(
        "phong/<int:id>/",
        chi_tiet_phong,
        name="chi_tiet_phong"
    ),

    path(
        "phong/<int:id>/dat/",
        dat_phong,
        name="dat_phong"
    ),

    # =====================================================
    # Ở GHÉP - NGƯỜI THUÊ
    # =====================================================

    path(
        "phong/<int:id>/dang-ky-ghep/",
        dang_ky_ghep_phong,
        name="dang_ky_ghep_phong"
    ),

    path(
        "hop-dong/<int:id>/bat-tat-ghep/",
        bat_tat_cho_phep_ghep,
        name="bat_tat_cho_phep_ghep"
    ),

    path(
        "yeu-cau-ghep-cua-toi/",
        yeu_cau_ghep_cua_toi,
        name="yeu_cau_ghep_cua_toi"
    ),

    path(
        "quan-ly-yeu-cau-ghep/",
        quan_ly_yeu_cau_ghep_admin,
        name="quan_ly_yeu_cau_ghep"
    ),

    path(
        "yeu-cau-ghep/<int:id>/",
        chi_tiet_yeu_cau_ghep,
        name="chi_tiet_yeu_cau_ghep"
    ),

    path(
        "yeu-cau-ghep/<int:id>/xu-ly/",
        xu_ly_yeu_cau_ghep,
        name="xu_ly_yeu_cau_ghep"
    ),

    # =====================================================
    # TÀI KHOẢN
    # =====================================================

    path(
        "dang-ky/",
        dang_ky,
        name="dang_ky"
    ),

    path(
        "dang-nhap/",
        dang_nhap,
        name="dang_nhap"
    ),

    path(
        "dang-xuat/",
        dang_xuat,
        name="dang_xuat"
    ),

    path(
        "tai-khoan/",
        tai_khoan,
        name="tai_khoan"
    ),

    path(
        "tai-khoan/nhan-dien-su-dung-phong/",
        nhan_dien_su_dung_phong,
        name="nhan_dien_su_dung_phong"
    ),

    path(
        "tai-khoan/dat-phong/<int:id>/huy/",
        huy_dat_phong_cua_toi,
        name="huy_dat_phong_cua_toi_legacy"
    ),

    path(
        "tai-khoan/doi-mat-khau/",
        doi_mat_khau,
        name="doi_mat_khau_user"
    ),

    path(
        "tai-khoan/cap-nhat/",
        cap_nhat_thong_tin,
        name="cap_nhat_thong_tin"
    ),

    path(
        "doi-mat-khau/",
        doi_mat_khau,
        name="doi_mat_khau"
    ),

    path(
        "cap-nhat-thong-tin/",
        RedirectView.as_view(pattern_name="cap_nhat_thong_tin", permanent=False),
        name="cap_nhat_thong_tin_legacy"
    ),

    # =====================================================
    # HỢP ĐỒNG CỦA TÔI - NGƯỜI THUÊ
    # =====================================================

    path(
        "hop-dong-cua-toi/",
        hop_dong_cua_toi,
        name="hop_dong_cua_toi"
    ),

    path(
        "hop-dong-cua-toi/<int:id>/",
        chi_tiet_hop_dong_cua_toi,
        name="chi_tiet_hop_dong_cua_toi"
    ),

    # -----------------------------------------------------
    # GIA HẠN HỢP ĐỒNG - NGƯỜI THUÊ
    # -----------------------------------------------------

    path(
        "hop-dong-cua-toi/<int:id>/gia-han/",
        gui_yeu_cau_gia_han,
        name="gui_yeu_cau_gia_han"
    ),

    path(
        "yeu-cau-gia-han/<int:id>/huy/",
        huy_yeu_cau_gia_han,
        name="huy_yeu_cau_gia_han"
    ),

    # =====================================================
    # HỢP ĐỒNG - XUẤT PDF
    # =====================================================

    path(
        "hop-dong/<int:id>/xuat-pdf/",
        xuat_hop_dong_pdf,
        name="xuat_hop_dong_pdf"
    ),

    # =====================================================
    # HÓA ĐƠN CỦA TÔI - NGƯỜI THUÊ
    # =====================================================

    path(
        "hoa-don-cua-toi/",
        hoa_don_cua_toi,
        name="hoa_don_cua_toi"
    ),

    path(
        "hoa-don-cua-toi/<int:id>/",
        chi_tiet_hoa_don_cua_toi,
        name="chi_tiet_hoa_don_cua_toi"
    ),

    path(
        "hoa-don-cua-toi/<int:id>/thanh-toan/",
        thanh_toan_hoa_don_cua_toi,
        name="thanh_toan_hoa_don_cua_toi"
    ),

    # =====================================================
    # THÔNG BÁO CỦA TÔI
    # =====================================================

    path(
        "thong-bao-cua-toi/",
        thong_bao_cua_toi,
        name="thong_bao_cua_toi"
    ),

    path(
        "thong-bao-cua-toi/kiem-tra-moi/",
        kiem_tra_thong_bao_cua_toi_moi,
        name="kiem_tra_thong_bao_cua_toi_moi"
    ),

    path(
        "thong-bao-cua-toi/<int:id>/",
        chi_tiet_thong_bao_cua_toi,
        name="chi_tiet_thong_bao_cua_toi"
    ),

    # =====================================================
    # DASHBOARD ADMIN
    # =====================================================

    path(
        "dashboard-admin/",
        dashboard_admin,
        name="dashboard_admin"
    ),

    path(
        "thong-bao-admin/",
        thong_bao_admin,
        name="thong_bao_admin"
    ),

    path(
        "thong-bao-admin/kiem-tra-moi/",
        kiem_tra_thong_bao_admin_moi,
        name="kiem_tra_thong_bao_admin_moi"
    ),

    path(
        "thong-bao-admin/doc-tat-ca/",
        doc_tat_ca_thong_bao_admin,
        name="doc_tat_ca_thong_bao_admin"
    ),

    path(
        "thong-bao-admin/<int:id>/",
        chi_tiet_thong_bao_admin,
        name="chi_tiet_thong_bao_admin"
    ),

    path(
        "thong-bao-admin/<int:id>/doc/",
        doc_thong_bao_admin,
        name="doc_thong_bao_admin"
    ),

    # =====================================================
    # ADMIN - NHẬT KÝ THAO TÁC
    # =====================================================

    path(
        "nhat-ky-thao-tac/",
        nhat_ky_thao_tac,
        name="nhat_ky_thao_tac"
    ),

    path(
        "nhat-ky-thao-tac/<int:id>/",
        chi_tiet_nhat_ky_thao_tac,
        name="chi_tiet_nhat_ky_thao_tac"
    ),

    # =====================================================
    # QUẢN LÝ PHÒNG
    # =====================================================

    path(
        "quan-ly-phong/",
        quan_ly_phong,
        name="quan_ly_phong"
    ),

    path(
        "quan-ly-phong/tao/",
        tao_phong,
        name="tao_phong"
    ),

    path(
        "quan-ly-phong/<int:id>/sua/",
        sua_phong,
        name="sua_phong"
    ),

    path(
        "quan-ly-phong/<int:id>/xoa/",
        xoa_phong,
        name="xoa_phong"
    ),

    # =====================================================
    # QUẢN LÝ ĐẶT PHÒNG
    # =====================================================

    path(
        "quan-ly-dat-phong/",
        admin_quan_ly_dat_phong,
        name="quan_ly_dat_phong"
    ),

    path(
        "quan-ly-dat-phong/<int:id>/",
        admin_chi_tiet_dat_phong,
        name="chi_tiet_dat_phong"
    ),

    path(
        "quan-ly-dat-phong/<int:id>/xac-nhan-va-tao-hop-dong/",
        xac_nhan_dat_phong_va_tao_hop_dong,
        name="xac_nhan_dat_phong_va_tao_hop_dong"
    ),

    path(
        "quan-ly-dat-phong/<int:id>/tu-choi-coc/",
        tu_choi_thanh_toan_coc,
        name="tu_choi_thanh_toan_coc"
    ),

    path(
        "quan-ly-dat-phong/<int:id>/tu-choi-yeu-cau/",
        tu_choi_yeu_cau_dat_phong,
        name="tu_choi_yeu_cau_dat_phong"
    ),

    path(
        "quan-ly-dat-phong/<int:id>/xu-ly/",
        xu_ly_dat_phong,
        name="xu_ly_dat_phong"
    ),

    path(
        "quan-ly-dat-phong/<int:dat_phong_id>/tao-hop-dong/",
        tao_hop_dong,
        name="tao_hop_dong"
    ),

    # =====================================================
    # QUẢN LÝ HỢP ĐỒNG - ADMIN
    # =====================================================

    path(
        "quan-ly-hop-dong/",
        quan_ly_hop_dong,
        name="quan_ly_hop_dong"
    ),

    path(
        "quan-ly-hop-dong/<int:id>/",
        chi_tiet_hop_dong,
        name="chi_tiet_hop_dong"
    ),

    path(
        "quan-ly-hop-dong/<int:id>/sua/",
        sua_hop_dong,
        name="sua_hop_dong"
    ),

    path(
        "quan-ly-hop-dong/<int:id>/xu-ly/",
        xu_ly_hop_dong,
        name="xu_ly_hop_dong"
    ),


    path(
        "quan-ly-hop-dong/yeu-cau-gia-han/<int:id>/xu-ly/",
        xu_ly_yeu_cau_gia_han,
        name="xu_ly_yeu_cau_gia_han"
    ),

    # =====================================================
    # QUẢN LÝ HÓA ĐƠN - ADMIN
    # =====================================================

    path(
        "quan-ly-nguoi-thue/",
        quan_ly_nguoi_thue,
        name="quan_ly_nguoi_thue"
    ),

    path(
        "quan-ly-nguoi-thue/<int:id>/",
        chi_tiet_nguoi_thue,
        name="chi_tiet_nguoi_thue"
    ),

    path(
        "quan-ly-hoa-don/",
        quan_ly_hoa_don,
        name="quan_ly_hoa_don"
    ),

    path(
        "quan-ly-hoa-don/tao/",
        tao_hoa_don,
        name="tao_hoa_don"
    ),

    path(
        "quan-ly-hoa-don/<int:id>/",
        chi_tiet_hoa_don,
        name="chi_tiet_hoa_don"
    ),

    path(
        "quan-ly-hoa-don/<int:id>/xu-ly/",
        xu_ly_hoa_don,
        name="xu_ly_hoa_don"
    ),

    # =====================================================
    # QUẢN LÝ YÊU CẦU SỬA CHỮA
    # =====================================================

    path(
        "quan-ly-sua-chua/",
        quan_ly_sua_chua,
        name="quan_ly_sua_chua"
    ),

    path(
        "quan-ly-sua-chua/<int:id>/",
        chi_tiet_sua_chua,
        name="chi_tiet_sua_chua"
    ),

    path(
        "quan-ly-sua-chua/<int:id>/xu-ly/",
        xu_ly_sua_chua,
        name="xu_ly_sua_chua"
    ),

    path(
        "tao-sua-chua/",
        tao_sua_chua,
        name="tao_sua_chua"
    ),

    path(
        "yeu-cau-sua-chua-cua-toi/",
        yeu_cau_sua_chua_cua_toi,
        name="yeu_cau_sua_chua_cua_toi"
    ),

    path(
        "yeu-cau-sua-chua-cua-toi/tao/",
        tao_yeu_cau_sua_chua,
        name="tao_yeu_cau_sua_chua"
    ),

    path(
        "yeu-cau-sua-chua-cua-toi/<int:id>/",
        chi_tiet_yeu_cau_sua_chua_cua_toi,
        name="chi_tiet_yeu_cau_sua_chua_cua_toi"
    ),

    # =====================================================
    # QUẢN LÝ CHÍNH SÁCH HỖ TRỢ
    # =====================================================

    path(
        "quan-ly-chinh-sach/",
        quan_ly_chinh_sach,
        name="quan_ly_chinh_sach"
    ),

    path(
        "quan-ly-chinh-sach/tao/",
        tao_chinh_sach,
        name="tao_chinh_sach"
    ),

    path(
        "quan-ly-chinh-sach/<int:id>/",
        chi_tiet_chinh_sach,
        name="chi_tiet_chinh_sach"
    ),

    path(
        "quan-ly-chinh-sach/<int:id>/xu-ly/",
        xu_ly_chinh_sach,
        name="xu_ly_chinh_sach"
    ),

    # =====================================================
    # QUẢN LÝ THÔNG BÁO - ADMIN
    # =====================================================

    path(
        "quan-ly-thong-bao/",
        quan_ly_thong_bao,
        name="quan_ly_thong_bao"
    ),

    path(
        "quan-ly-thong-bao/tao/",
        tao_thong_bao,
        name="tao_thong_bao"
    ),

    path(
        "quan-ly-thong-bao/<int:id>/",
        chi_tiet_thong_bao,
        name="chi_tiet_thong_bao"
    ),

    path(
        "quan-ly-thong-bao/<int:id>/xu-ly/",
        xu_ly_thong_bao,
        name="xu_ly_thong_bao"
    ),

    # =====================================================
    # QUẢN LÝ CƠ SỞ
    # =====================================================

    path(
        "quan-ly-co-so/",
        quan_ly_co_so,
        name="quan_ly_co_so"
    ),

    path(
        "quan-ly-co-so/tao/",
        tao_co_so,
        name="tao_co_so"
    ),

    path(
        "quan-ly-co-so/<int:id>/",
        chi_tiet_co_so,
        name="chi_tiet_co_so"
    ),

    path(
        "quan-ly-co-so/<int:id>/xu-ly/",
        xu_ly_co_so,
        name="xu_ly_co_so"
    ),

    # =====================================================
    # SMART ROOM - DASHBOARD
    # =====================================================

    path(
        "smart-room/",
        smart_room_dashboard,
        name="smart_room_dashboard"
    ),

    # =====================================================
    # SMART ROOM - ACCESS CONTROL
    # =====================================================

    path(
        "smart-room/access-control/",
        smart_access_control,
        name="smart_access_control"
    ),

    # =====================================================
    # SMART ROOM - NGƯỜI Ở CÙNG
    # =====================================================

    path(
        "smart-room/nguoi-o-cung/",
        quan_ly_nguoi_o_cung,
        name="quan_ly_nguoi_o_cung"
    ),

    path(
        "smart-room/nguoi-o-cung/tao/",
        tao_nguoi_o_cung,
        name="tao_nguoi_o_cung"
    ),

    path(
        "smart-room/nguoi-o-cung/<int:id>/",
        chi_tiet_nguoi_o_cung,
        name="chi_tiet_nguoi_o_cung"
    ),

    path(
        "smart-room/nguoi-o-cung/<int:id>/xu-ly/",
        xu_ly_nguoi_o_cung,
        name="xu_ly_nguoi_o_cung"
    ),

    # =====================================================
    # SMART ROOM - FACE PROFILE
    # =====================================================

    path(
        "smart-room/face-profile/",
        quan_ly_face_profile,
        name="quan_ly_face_profile"
    ),

    path(
        "smart-room/face-profile/tao/",
        tao_face_profile,
        name="tao_face_profile"
    ),

    path(
        "smart-room/face-profile/<int:id>/",
        chi_tiet_face_profile,
        name="chi_tiet_face_profile"
    ),

    path(
        "smart-room/face-profile/<int:id>/xu-ly/",
        xu_ly_face_profile,
        name="xu_ly_face_profile"
    ),

    # =====================================================
    # SMART ROOM - FACE ID ĐĂNG KÝ WEBCAM
    # =====================================================

    path(
        "smart-room/face-profile/<int:id>/dang-ky/",
        face_id_dang_ky,
        name="face_id_dang_ky"
    ),

    path(
        "smart-room/face-id/",
        trang_xac_thuc_face_id,
        name="trang_xac_thuc_face_id"
    ),

    path(
        "smart-room/face-id/xac-thuc/",
        face_id_xac_thuc,
        name="face_id_xac_thuc"
    ),

    # =====================================================
    # SMART ROOM - QUYỀN RA VÀO
    # =====================================================

    path(
        "smart-room/quyen-ra-vao/",
        quan_ly_quyen_ra_vao,
        name="quan_ly_quyen_ra_vao"
    ),

    path(
        "smart-room/quyen-ra-vao/tao/",
        tao_quyen_ra_vao,
        name="tao_quyen_ra_vao"
    ),

    path(
        "smart-room/quyen-ra-vao/<int:id>/",
        chi_tiet_quyen_ra_vao,
        name="chi_tiet_quyen_ra_vao"
    ),

    path(
        "smart-room/quyen-ra-vao/<int:id>/xu-ly/",
        xu_ly_quyen_ra_vao,
        name="xu_ly_quyen_ra_vao"
    ),

    # =====================================================
    # SMART ROOM - LỊCH SỬ RA VÀO
    # =====================================================

    path(
        "smart-room/lich-su-ra-vao/",
        quan_ly_lich_su_ra_vao,
        name="quan_ly_lich_su_ra_vao"
    ),

    path(
        "smart-room/lich-su-ra-vao/tao/",
        tao_lich_su_ra_vao,
        name="tao_lich_su_ra_vao"
    ),

    path(
        "smart-room/lich-su-ra-vao/<int:id>/",
        chi_tiet_lich_su_ra_vao,
        name="chi_tiet_lich_su_ra_vao"
    ),

    path(
        "smart-room/lich-su-ra-vao/<int:id>/xu-ly/",
        xu_ly_lich_su_ra_vao,
        name="xu_ly_lich_su_ra_vao"
    ),
]


# =====================================================
# MEDIA FILES
# =====================================================

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
