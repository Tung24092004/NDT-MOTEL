"""Authoritative calculations and draft creation for invoices."""
import calendar
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.dich_vu.hop_dong import require_admin
from core.dich_vu.luu_tru import lay_hop_dong_luu_tru_hien_tai
from core.models import HoaDon, HopDong, NhatKyThaoTac, ThongBao


MIN_ELECTRICITY_UNIT_PRICE = Decimal("1")
MAX_ELECTRICITY_UNIT_PRICE = Decimal("100000")
BILLING_TIMEZONE = ZoneInfo("Asia/Bangkok")


def parse_localized_whole_number(raw_value, *, label):
    """Parse a non-decimal integer while accepting Vietnamese thousands separators."""
    raw = str(raw_value or "").strip().replace("\u00a0", "").replace(" ", "")
    if not raw:
        raise ValueError(f"{label} không được để trống.")
    if "." in raw and "," in raw:
        raise ValueError(f"{label} không đúng định dạng.")
    separator = "." if "." in raw else "," if "," in raw else None
    if separator:
        groups = raw.split(separator)
        if not groups[0] or any(len(group) != 3 for group in groups[1:]):
            raise ValueError(f"{label} không đúng định dạng.")
        raw = "".join(groups)
    if not raw.isascii() or not raw.isdigit():
        raise ValueError(f"{label} phải là số nguyên không âm.")
    return Decimal(raw)


def calculate_electricity_charge(*, previous_reading, current_reading, unit_price):
    previous = parse_localized_whole_number(previous_reading, label="Chỉ số điện cũ")
    current = parse_localized_whole_number(current_reading, label="Chỉ số điện mới")
    price = parse_localized_whole_number(unit_price, label="Đơn giá điện")
    if current < previous:
        raise ValueError("Chỉ số điện mới không được nhỏ hơn chỉ số điện cũ.")
    if not MIN_ELECTRICITY_UNIT_PRICE <= price <= MAX_ELECTRICITY_UNIT_PRICE:
        raise ValueError("Đơn giá điện phải lớn hơn 0 và không vượt quá 100.000 VNĐ/kWh.")
    return previous, current, price, (current - previous) * price


def billing_period(year, month):
    """Calendar-month billing period in the approved Bangkok business zone."""
    try:
        start = date(int(year), int(month), 1)
    except (TypeError, ValueError) as error:
        raise ValidationError("Ky hoa don phai la YYYY-MM hop le.") from error
    next_start = date(start.year + (start.month == 12), (start.month % 12) + 1, 1)
    return start, next_start


def due_date_for_period(contract, period_start):
    """Payment day in the following calendar month, clamped to month end."""
    due_year = period_start.year + (period_start.month == 12)
    due_month = (period_start.month % 12) + 1
    due_day = min(contract.ngay_thanh_toan_hang_thang, calendar.monthrange(due_year, due_month)[1])
    return date(due_year, due_month, due_day)


@transaction.atomic
def create_invoice_draft(*, actor, contract_id, year, month):
    """Create exactly one rent-only draft for an explicit eligible period.

    Meter and variable fee policies are not approved for this boundary, so the
    first draft includes only the authoritative contract rent snapshot.
    """
    require_admin(actor)
    period_start, next_period_start = billing_period(year, month)
    today = timezone.localdate(timezone=BILLING_TIMEZONE)
    if period_start < date(today.year, today.month, 1):
        raise ValidationError("Khong tao lai draft cho ky trong qua khu.")

    contract = HopDong.objects.select_for_update().select_related(
        "dat_phong__nguoi_thue", "dat_phong__phong"
    ).get(pk=contract_id)
    current = lay_hop_dong_luu_tru_hien_tai(nguoi_thue=contract.dat_phong.nguoi_thue)
    if not current or current.pk != contract.pk:
        raise ValidationError("Hop dong khong phai tenancy hien tai hop le.")
    if contract.ngay_bat_dau > period_start or contract.ngay_ket_thuc < (next_period_start - timedelta(days=1)):
        raise ValidationError("Hop dong khong co hieu luc tron ven ky hoa don.")
    if contract.tien_thue_thang is None or contract.tien_thue_thang <= 0:
        raise ValidationError("Hop dong thieu gia thue snapshot hop le.")

    try:
        invoice = HoaDon.objects.create(
            hop_dong=contract, thang=period_start.month, nam=period_start.year,
            tien_phong=contract.tien_thue_thang, tien_dien=Decimal("0"),
            tien_nuoc=Decimal("0"), tien_dich_vu=Decimal("0"), phi_khac=Decimal("0"),
            han_thanh_toan=due_date_for_period(contract, period_start),
            trang_thai="draft", nguoi_lap=actor,
            chi_tiet_phi="Draft ky dau: tien phong theo snapshot hop dong; chua bao gom dien, nuoc, dich vu.",
        )
    except IntegrityError as error:
        raise ValidationError("Ky hoa don nay da ton tai cho hop dong.") from error

    NhatKyThaoTac.objects.create(
        nguoi_thuc_hien=actor, hanh_dong="tao", module="Hoa don",
        doi_tuong="HoaDon", doi_tuong_id=invoice.pk,
        tieu_de=f"Tao draft hoa don {period_start:%m/%Y}",
        du_lieu_moi={"period": period_start.strftime("%Y-%m"), "status": "draft", "rent": str(invoice.tien_phong)},
    )
    return invoice


def _validate_draft_for_publication(invoice):
    """Validate a loaded draft using the same rules as the publish mutation."""
    contract = invoice.hop_dong
    current = lay_hop_dong_luu_tru_hien_tai(nguoi_thue=contract.dat_phong.nguoi_thue)
    period_start, next_period_start = billing_period(invoice.nam, invoice.thang)
    if not current or current.pk != contract.pk:
        raise ValidationError("Tenancy không còn hợp lệ để phát hành.")
    if contract.ngay_bat_dau > period_start or contract.ngay_ket_thuc < next_period_start - timedelta(days=1):
        raise ValidationError("Hợp đồng không phủ toàn vẹn kỳ hóa đơn.")
    if invoice.han_thanh_toan != due_date_for_period(contract, period_start):
        raise ValidationError("Hạn thanh toán draft không khớp quy tắc hợp đồng.")
    amounts = (invoice.tien_phong, invoice.tien_dien, invoice.tien_nuoc, invoice.tien_dich_vu, invoice.phi_khac)
    if any(amount is None or amount < 0 for amount in amounts) or invoice.tong_tien <= 0:
        raise ValidationError("Các khoản tiền draft không hợp lệ.")


def review_invoice_draft(invoice):
    """Return server-derived review data safe for the Admin detail template."""
    if invoice.trang_thai != "draft":
        return {"can_publish": False, "blocked_reason": ""}
    try:
        _validate_draft_for_publication(invoice)
    except ValidationError as error:
        return {"can_publish": False, "blocked_reason": error.messages[0]}
    return {"can_publish": True, "blocked_reason": ""}


@transaction.atomic
def publish_invoice_draft(*, actor, invoice_id):
    """Atomically publish one reviewed draft without accepting payment."""
    require_admin(actor)
    invoice = HoaDon.objects.select_for_update().select_related(
        "hop_dong__dat_phong__nguoi_thue", "hop_dong__dat_phong__phong"
    ).get(pk=invoice_id)
    if invoice.trang_thai != "draft":
        return invoice, False
    _validate_draft_for_publication(invoice)
    contract = invoice.hop_dong
    invoice.trang_thai = "chua_thanh_toan"
    invoice.save(update_fields=["trang_thai", "ngay_cap_nhat"])
    NhatKyThaoTac.objects.create(
        nguoi_thuc_hien=actor, hanh_dong="cap_nhat", module="Hoa don",
        doi_tuong="HoaDon", doi_tuong_id=invoice.pk,
        tieu_de=f"Phat hanh hoa don {invoice.thang:02d}/{invoice.nam}",
        du_lieu_cu={"trang_thai": "draft"}, du_lieu_moi={"trang_thai": "chua_thanh_toan"},
    )
    ThongBao.objects.get_or_create(
        nguoi_thue=contract.dat_phong.nguoi_thue,
        ma_tham_chieu=f"INVOICE:{invoice.pk}:PUBLISHED",
        defaults={"loai": "thanh_toan", "muc_do": "quan_trong",
                  "tieu_de": "Hoa don da duoc phat hanh",
                  "noi_dung": f"Hoa don {invoice.thang:02d}/{invoice.nam} da duoc phat hanh. Vui long kiem tra va thanh toan truoc {invoice.han_thanh_toan:%d/%m/%Y}.",
                  "url_lien_ket": f"/hoa-don-cua-toi/{invoice.pk}/"},
    )
    return invoice, True
