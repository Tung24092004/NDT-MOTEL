from io import BytesIO
from contextlib import contextmanager

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import ChungTuThanhToan

MAX_EVIDENCE_SIZE = 5 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}


@contextmanager
def atomic_invoice_attempt_submission():
    """Rollback DB and narrowly remove only files created by this request."""
    created_attempts = []
    try:
        with transaction.atomic():
            yield created_attempts
    except Exception:
        for evidence in created_attempts:
            if evidence.anh and evidence.anh.name:
                evidence.anh.storage.delete(evidence.anh.name)
        raise


def validate_image(uploaded):
    if not uploaded:
        raise ValidationError("Vui lòng chọn ảnh chứng từ chuyển khoản.")
    if uploaded.size > MAX_EVIDENCE_SIZE:
        raise ValidationError("Ảnh chứng từ không được vượt quá 5 MB.")
    try:
        payload = uploaded.read()
        with Image.open(BytesIO(payload)) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Tệp tải lên không phải ảnh JPEG, PNG hoặc WEBP hợp lệ.")
    finally:
        uploaded.seek(0)
    if image_format not in ALLOWED_FORMATS:
        raise ValidationError("Chỉ chấp nhận ảnh JPEG, PNG hoặc WEBP.")
    mime_type, suffix = ALLOWED_FORMATS[image_format]
    uploaded.name = f"evidence{suffix}"
    return mime_type


def create_for_deposit(*, actor, payment, uploaded):
    if payment.dat_phong.nguoi_thue.tai_khoan_id != actor.id:
        raise PermissionDenied("Không có quyền tải chứng từ cho giao dịch này.")
    if payment.trang_thai != "chua_thanh_toan" or hasattr(payment, "chung_tu"):
        raise ValidationError("Giao dịch cọc không nhận thêm chứng từ ở trạng thái hiện tại.")
    mime_type = validate_image(uploaded)
    return ChungTuThanhToan.objects.create(
        giao_dich_coc=payment, nguoi_tai_len=actor, anh=uploaded,
        mime_type=mime_type, ma_doi_chieu=payment.ma_tham_chieu,
    )


def create_for_invoice(*, actor, invoice, uploaded):
    """Create an immutable invoice-evidence attempt under a locked invoice.

    Callers must lock the invoice first.  The sole pending attempt is the
    source of truth; a rejected attempt remains unchanged and retry creates a
    new numbered row.
    """
    if invoice.hop_dong.dat_phong.nguoi_thue.tai_khoan_id != actor.id:
        raise PermissionDenied("Không có quyền tải chứng từ cho hóa đơn này.")
    if invoice.trang_thai not in ("chua_thanh_toan", "qua_han"):
        raise ValidationError("Hóa đơn không nhận thêm chứng từ ở trạng thái hiện tại.")
    attempts = list(
        ChungTuThanhToan.objects.select_for_update()
        .filter(hoa_don=invoice).order_by("so_lan", "pk")
    )
    active_attempts = [attempt for attempt in attempts if attempt.trang_thai == "cho_doi_soat"]
    if len(active_attempts) > 1:
        raise ValidationError("Hóa đơn có nhiều chứng từ đang chờ đối soát; không thể tạo attempt mới an toàn.")
    active = active_attempts[0] if active_attempts else None
    if active:
        active._created_payment_attempt = False
        return active
    mime_type = validate_image(uploaded)
    next_attempt = max((attempt.so_lan or 0 for attempt in attempts), default=0) + 1
    evidence = ChungTuThanhToan(
        hoa_don=invoice, nguoi_tai_len=actor, anh=uploaded,
        mime_type=mime_type, ma_doi_chieu=f"NDTMOTEL HD{invoice.pk}", so_lan=next_attempt,
    )
    try:
        evidence.save(force_insert=True)
    except Exception:
        # FileField saves before its database INSERT.  On an INSERT failure,
        # only the just-generated file name is eligible for cleanup.
        if evidence.anh and evidence.anh.name:
            evidence.anh.storage.delete(evidence.anh.name)
        raise
    evidence._created_payment_attempt = True
    return evidence


def active_invoice_attempt(invoice, *, for_update=False):
    """Return the one pending invoice attempt, or fail closed on corruption.

    Ordering only makes the query deterministic.  It must never decide which
    evidence is active when an invariant violation has produced two pending
    attempts for the same invoice.
    """
    attempts = ChungTuThanhToan.objects.filter(
        hoa_don=invoice, trang_thai="cho_doi_soat",
    ).order_by("-so_lan", "-pk")
    if for_update:
        attempts = attempts.select_for_update()
    active_attempts = list(attempts[:2])
    if len(active_attempts) > 1:
        raise ValidationError("Hóa đơn có nhiều chứng từ đang chờ đối soát; không thể xử lý an toàn.")
    return active_attempts[0] if active_attempts else None


def mark_reviewed(evidence, *, accepted, reviewer, note=""):
    if evidence.trang_thai != "cho_doi_soat":
        raise ValidationError("Chỉ chứng từ đang chờ đối soát mới được xử lý.")
    evidence.trang_thai = "da_chap_nhan" if accepted else "tu_choi"
    evidence.nguoi_xu_ly = reviewer
    evidence.thoi_diem_xu_ly = timezone.now()
    evidence.ghi_chu_doi_soat = (note or "").strip()
    evidence.save(update_fields=["trang_thai", "nguoi_xu_ly", "thoi_diem_xu_ly", "ghi_chu_doi_soat", "ngay_cap_nhat"])
    return evidence
