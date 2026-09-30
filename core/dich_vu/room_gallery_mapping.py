"""Catalog va mapping gallery phong dung chung, khong luu vao database."""

import re


GALLERY_CODES = {
    "phong_tieu_chuan": ("TC01", "TC02", "TC03", "TC04", "TC05"),
    "phong_cao_cap": ("CC01", "CC02", "CC03", "CC04"),
    "phong_gac_lung": ("GL01", "GL02", "GL03"),
    "can_ho_mini": ("CH01", "CH02", "CH03"),
}

DEFAULT_GALLERY_CODE = {
    loai_phong: codes[0]
    for loai_phong, codes in GALLERY_CODES.items()
}

GALLERY_FILES = {
    code: (
        "01_toan_canh.jpg",
        "02_khu_chinh.jpg",
        "03_tien_nghi.jpg",
        "04_wc_hoac_goc_phu.jpg",
        "05_goc_khac.jpg",
    )
    for codes in GALLERY_CODES.values()
    for code in codes
}

# Snapshot mapping cua 86 phong live, chia round-robin theo co so/tang/so phong.
# Phong tao moi khong co trong bang nay se dung cong thuc fallback ben duoi.
ROOM_GALLERY_OVERRIDES = {
    1: "TC01", 2: "TC02", 3: "GL01", 5: "CH03", 6: "TC05",
    7: "CC03", 9: "TC01", 10: "TC03", 11: "TC05", 12: "TC04",
    13: "TC03", 14: "CC01", 15: "CH01", 16: "TC04", 17: "GL02",
    18: "CC02", 19: "CH02", 20: "CC04", 21: "CH01", 22: "TC02",
    23: "GL03", 24: "CC01", 25: "CH02", 26: "CC02", 27: "CH03",
    28: "TC01", 29: "TC02", 30: "GL01", 31: "CC03", 32: "CH01",
    33: "TC03", 34: "TC04", 35: "GL02", 36: "CC04", 37: "CH02",
    38: "TC05", 39: "TC01", 40: "GL03", 41: "CC01", 42: "CH03",
    43: "TC02", 44: "TC03", 45: "GL01", 46: "CC02", 47: "CH01",
    48: "TC04", 49: "TC05", 50: "TC01", 51: "CC03", 52: "CH02",
    53: "TC02", 54: "TC03", 55: "GL02", 56: "CC04", 57: "CH03",
    58: "TC04", 59: "TC05", 60: "GL03", 61: "CC01", 62: "TC01",
    63: "TC02", 64: "GL01", 65: "CC02", 66: "TC03", 67: "TC04",
    68: "TC05", 69: "CC03", 70: "CH01", 71: "TC01", 72: "TC02",
    73: "GL02", 74: "CC04", 75: "CH02", 76: "TC03", 77: "TC04",
    78: "GL03", 79: "CC01", 80: "CH03", 81: "TC05", 82: "TC01",
    83: "GL01", 84: "CC02", 85: "TC02", 86: "TC03", 87: "GL02",
    88: "CC03",
}


def ma_gallery_cua_phong(phong):
    """Tra ma on dinh; cac so phong lien tiep duoc luan phien gallery."""
    codes = GALLERY_CODES.get(phong.loai_phong, ())
    if not codes:
        return None

    override = ROOM_GALLERY_OVERRIDES.get(phong.pk)
    if override in codes:
        return override

    digits = re.findall(r"\d+", str(phong.so_phong))
    room_key = int(digits[-1]) if digits else int(phong.pk or 0)
    facility_key = int(phong.co_so_id or 0)
    return codes[(room_key + facility_key - 1) % len(codes)]
