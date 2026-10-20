"""Tap hop ham view cho test hoi quy; khong duoc runtime import."""
from django.shortcuts import get_object_or_404
from core.dich_vu.ngay_thue import (
    tinh_ngay_ket_thuc_theo_thang,
)
from core.dich_vu.phan_quyen import (
    la_admin,
)
from core.views_hop_dong import (
    cap_nhat_trang_thai_hop_dong,
    cap_nhat_trang_thai_phong_theo_hop_dong,
    quan_ly_hop_dong,
    chi_tiet_hop_dong,
    sua_hop_dong,
    xu_ly_hop_dong,
    hop_dong_cua_toi,
    chi_tiet_hop_dong_cua_toi,
    xuat_hop_dong_pdf,
)
from core.views_tao_hop_dong import tao_hop_dong
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
from core.views_phong import (
    quan_ly_phong,
    xoa_phong,
    tao_phong,
    sua_phong,
)
from core.views_danh_sach_phong import danh_sach_phong
from core.views_chi_tiet_phong import chi_tiet_phong
from core.views_dang_ky import dang_ky
from core.views_dang_nhap import (
    dang_nhap,
    dang_xuat,
)
from core.views_tai_khoan import (
    doi_mat_khau,
    cap_nhat_thong_tin,
    tai_khoan,
    _lay_nguoi_thue_dang_dang_nhap,
)
from core.views_gia_han import (
    xu_ly_yeu_cau_gia_han,
    gui_yeu_cau_gia_han,
    huy_yeu_cau_gia_han,
)
from core.views_hoa_don import (
    hoa_don_cua_toi,
    chi_tiet_hoa_don_cua_toi,
    quan_ly_hoa_don,
    chi_tiet_hoa_don,
    tao_hoa_don,
)
from core.views_thanh_toan import (
    thanh_toan_hoa_don_cua_toi,
    xu_ly_hoa_don,
)
from core.views_nguoi_thue import (
    quan_ly_nguoi_thue,
    chi_tiet_nguoi_thue,
)
from core.views_o_ghep import (
    quan_ly_yeu_cau_ghep_admin,
    bat_tat_cho_phep_ghep,
    dang_ky_ghep_phong,
    yeu_cau_ghep_cua_toi,
    chi_tiet_yeu_cau_ghep,
    xu_ly_yeu_cau_ghep,
)
from core.views_sua_chua import (
    _lay_trang_thai_sua_chua_hop_le,
    _lay_loai_su_co_hop_le,
    _lay_muc_do_hop_le,
    _lay_phong_dang_thue_cua_nguoi_thue,
    quan_ly_sua_chua,
    chi_tiet_sua_chua,
    xu_ly_sua_chua,
    tao_sua_chua,
    yeu_cau_sua_chua_cua_toi,
    tao_yeu_cau_sua_chua,
    chi_tiet_yeu_cau_sua_chua_cua_toi,
)
from core.views_chinh_sach import (
    quan_ly_chinh_sach,
    chi_tiet_chinh_sach,
    tao_chinh_sach,
    xu_ly_chinh_sach,
)
from core.views_thong_bao import (
    quan_ly_thong_bao,
    chi_tiet_thong_bao,
    thong_bao_cua_toi,
    chi_tiet_thong_bao_cua_toi,
    tao_thong_bao,
    xu_ly_thong_bao,
)
from core.views_smart_room import (
    smart_room_dashboard,
    smart_access_control,
    quan_ly_nguoi_o_cung,
    chi_tiet_nguoi_o_cung,
    tao_nguoi_o_cung,
    xu_ly_nguoi_o_cung,
    _face_load_models,
    _face_image_from_base64,
    _face_detect,
    _face_feature,
    _face_feature_to_text,
    _face_feature_from_text,
    _face_compare,
    _smart_room_hop_dong_hop_le_cua_face_profile,
    _smart_room_hop_dong_cua_quyen,
    _smart_room_user_co_quyen_voi_face_profile,
    _smart_room_dong_bo_quyen_sau_dang_ky,
    nhan_dien_su_dung_phong,
    quan_ly_face_profile,
    chi_tiet_face_profile,
    tao_face_profile,
    face_id_dang_ky,
    trang_xac_thuc_face_id,
    _quyen_co_hop_dong_hien_tai,
    face_id_xac_thuc,
    xu_ly_face_profile,
    quan_ly_quyen_ra_vao,
    chi_tiet_quyen_ra_vao,
    tao_quyen_ra_vao,
    xu_ly_quyen_ra_vao,
    quan_ly_lich_su_ra_vao,
    chi_tiet_lich_su_ra_vao,
    tao_lich_su_ra_vao,
    xu_ly_lich_su_ra_vao,
)
from core.views_nhat_ky import (
    nhat_ky_thao_tac,
    chi_tiet_nhat_ky_thao_tac,
)
from core.views_dat_phong import dat_phong, huy_dat_phong_cua_toi
