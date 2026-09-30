"""Gia lap dependency o module view thuc, thay cho global cua views.py cu."""
from contextlib import ExitStack, contextmanager
from importlib import import_module
from unittest.mock import patch


VIEW_MODULES = (
    "core.views_hop_dong",
    "core.views_quan_tri",
    "core.views_phong",
    "core.views_dang_nhap",
    "core.views_tai_khoan",
    "core.views_gia_han",
    "core.views_hoa_don",
    "core.views_thanh_toan",
    "core.views_nguoi_thue",
    "core.views_o_ghep",
    "core.views_sua_chua",
    "core.views_chinh_sach",
    "core.views_thong_bao",
    "core.views_smart_room",
    "core.views_nhat_ky",
)


@contextmanager
def gia_lap_views(name, **kwargs):
    with ExitStack() as stack:
        mocks = []
        for module_name in VIEW_MODULES:
            module = import_module(module_name)
            if hasattr(module, name):
                mocks.append(stack.enter_context(patch.object(module, name, **kwargs)))
        if not mocks:
            raise AttributeError(name)
        yield mocks
