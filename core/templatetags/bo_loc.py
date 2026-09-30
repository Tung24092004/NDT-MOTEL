from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def vnd(value):
    """
    Định dạng tiền Việt Nam có dấu chấm ngăn cách hàng nghìn.

    Ví dụ:
    5000000 -> 5.000.000
    200000  -> 200.000
    15000   -> 15.000
    3000    -> 3.000
    """

    if value is None or value == "":
        return "0"

    try:
        value = Decimal(str(value))
        value = value.quantize(Decimal("1"))
        return f"{value:,.0f}".replace(",", ".")
    except (InvalidOperation, ValueError, TypeError):
        return str(value)


STATUS_LABELS = {
    "cho_xac_minh": "Chờ xác minh",
    "da_xac_minh": "Đã xác minh",
    "chua_thanh_toan": "Chưa thanh toán",
    "cho_xac_nhan": "Chờ đối soát",
    "da_xac_nhan": "Đã xác nhận cọc",
    "tu_choi": "Từ chối",
    "da_huy": "Đã hủy",
    "da_hoan_tien": "Đã hoàn tiền",
}


@register.filter
def status_label(value):
    """Hiển thị nhãn trạng thái dễ đọc mà không đổi giá trị lưu DB."""
    if value is None:
        return ""
    return STATUS_LABELS.get(str(value), str(value).replace("_", " ").capitalize())
