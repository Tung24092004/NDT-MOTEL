"""Chon gallery hien thi ma khong thay doi du lieu luu tru."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from django.conf import settings

from core.dich_vu.room_gallery_mapping import (
    DEFAULT_GALLERY_CODE,
    GALLERY_CODES,
    GALLERY_FILES,
    ma_gallery_cua_phong,
)


@dataclass(frozen=True)
class TepAnhGallery:
    name: str

    @property
    def url(self):
        media_url = settings.MEDIA_URL.rstrip("/") + "/"
        return media_url + quote(self.name, safe="/")


@dataclass(frozen=True)
class AnhGalleryDungChung:
    id: str
    anh: TepAnhGallery
    thu_tu: int
    la_anh_dai_dien: bool
    gallery_code: str


def _anh_dai_dien(gallery):
    if not gallery:
        return None
    return next((anh for anh in gallery if anh.la_anh_dai_dien), gallery[0])


def _la_anh_mau_legacy(anh):
    name = str(getattr(anh.anh, "name", "")).replace("\\", "/").lstrip("/")
    return name.startswith("phong_mau/")


def _anh_rieng(phong):
    cache = getattr(phong, "_prefetched_objects_cache", {})
    if "hinh_anh" in cache:
        gallery = cache["hinh_anh"]
    else:
        gallery = phong.hinh_anh.order_by("thu_tu", "id")
    return sorted(
        (anh for anh in gallery if not _la_anh_mau_legacy(anh)),
        key=lambda anh: (anh.thu_tu, anh.id),
    )


def _thu_muc_cua_ma(loai_phong, gallery_code):
    if gallery_code not in GALLERY_CODES.get(loai_phong, ()):
        return None
    relative = PurePosixPath("phong_mau", loai_phong, gallery_code)
    root = Path(settings.MEDIA_ROOT).resolve()
    folder = (root / Path(*relative.parts)).resolve()
    try:
        folder.relative_to(root)
    except ValueError:
        return None
    return relative, folder


@lru_cache(maxsize=32)
def _gallery_tren_dia(loai_phong, gallery_code):
    location = _thu_muc_cua_ma(loai_phong, gallery_code)
    if not location:
        return ()
    relative, folder = location
    images = []
    for index, filename in enumerate(GALLERY_FILES.get(gallery_code, ())):
        if not (folder / filename).is_file():
            continue
        name = (relative / filename).as_posix()
        images.append(
            AnhGalleryDungChung(
                id=f"{gallery_code}-{index + 1}",
                anh=TepAnhGallery(name=name),
                thu_tu=index,
                la_anh_dai_dien=index == 0,
                gallery_code=gallery_code,
            )
        )
    return tuple(images)


def _gallery_dung_chung(phong):
    gallery_code = ma_gallery_cua_phong(phong)
    gallery = _gallery_tren_dia(phong.loai_phong, gallery_code)
    if gallery:
        return list(gallery)

    default_code = DEFAULT_GALLERY_CODE.get(phong.loai_phong)
    return list(_gallery_tren_dia(phong.loai_phong, default_code))


def chuan_bi_gallery_hien_thi(ds_phong):
    """Gan gallery cho danh sach phong ma khong phat sinh query fallback."""
    ds_phong = list(ds_phong)
    for phong in ds_phong:
        gallery = _anh_rieng(phong) or _gallery_dung_chung(phong)
        phong._gallery_hien_thi_cache = gallery
        phong._anh_dai_dien_hien_thi_cache = _anh_dai_dien(gallery)
        phong._ma_gallery_hien_thi_cache = (
            getattr(gallery[0], "gallery_code", None) if gallery else None
        )
    return ds_phong


def gallery_hien_thi(phong):
    if not hasattr(phong, "_gallery_hien_thi_cache"):
        chuan_bi_gallery_hien_thi([phong])
    return phong._gallery_hien_thi_cache


def anh_dai_dien_hien_thi(phong):
    if not hasattr(phong, "_anh_dai_dien_hien_thi_cache"):
        chuan_bi_gallery_hien_thi([phong])
    return phong._anh_dai_dien_hien_thi_cache


def ma_gallery_hien_thi(phong):
    if not hasattr(phong, "_ma_gallery_hien_thi_cache"):
        chuan_bi_gallery_hien_thi([phong])
    return phong._ma_gallery_hien_thi_cache

