"""Read-only current-state reconciliation rows for PAY-04."""
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.models import CoSo, HoaDon, ThanhToanCocDatPhong


TARGET_TYPES = {"coc", "hoa_don"}
EVIDENCE_STATES = {"cho_doi_soat", "da_chap_nhan", "tu_choi", "khong_co"}
EXCEPTION_KINDS = {
    "can_xu_ly",
    "cho_doi_soat",
    "tien_mat_cho_doi_soat",
    "thieu_chung_tu",
    "tu_choi",
    "da_chap_nhan",
    "bat_nhat",
}
AGE_BUCKETS = {"0_1", "2_3", "4_7", "8_plus"}
ACTIONABLE_KINDS = {
    "cho_doi_soat",
    "tien_mat_cho_doi_soat",
    "thieu_chung_tu",
    "bat_nhat",
}

KIND_LABELS = {
    "cho_doi_soat": "Cần xử lý",
    "tien_mat_cho_doi_soat": "Tiền mặt chờ xác nhận",
    "thieu_chung_tu": "Thiếu chứng từ / dữ liệu cũ",
    "tu_choi": "Đã từ chối",
    "da_chap_nhan": "Đã chấp nhận",
    "bat_nhat": "Bất nhất trạng thái",
}


def _evidence(target):
    if isinstance(target, HoaDon):
        return target.chung_tu_thanh_toan.order_by("-so_lan", "-pk").first()
    try:
        return target.chung_tu
    except ObjectDoesNotExist:
        return None


def _age_days(value):
    if not value:
        return 0
    return max((timezone.localdate() - timezone.localtime(value).date()).days, 0)


def _classify_deposit(payment, evidence):
    if evidence is None:
        return "thieu_chung_tu" if payment.trang_thai == "cho_xac_nhan" else "bat_nhat"
    pairs = {
        ("cho_doi_soat", "cho_xac_nhan"): "cho_doi_soat",
        ("tu_choi", "tu_choi"): "tu_choi",
        ("da_chap_nhan", "da_xac_nhan"): "da_chap_nhan",
    }
    return pairs.get((evidence.trang_thai, payment.trang_thai), "bat_nhat")


def _classify_invoice(invoice, evidence):
    if evidence is None:
        if invoice.trang_thai == "cho_xac_nhan" and invoice.phuong_thuc == "tien_mat":
            return "tien_mat_cho_doi_soat"
        return "thieu_chung_tu" if invoice.trang_thai == "cho_xac_nhan" else "bat_nhat"
    pairs = {
        ("cho_doi_soat", "cho_xac_nhan"): "cho_doi_soat",
        ("tu_choi", "chua_thanh_toan"): "tu_choi",
        ("tu_choi", "qua_han"): "tu_choi",
        ("da_chap_nhan", "da_thanh_toan"): "da_chap_nhan",
    }
    return pairs.get((evidence.trang_thai, invoice.trang_thai), "bat_nhat")


def _common_row(*, target_type, target, evidence, tenant, room, amount, reference,
                object_label, detail_url, kind, submitted_at, reason=""):
    return {
        "target_type": target_type,
        "target_type_label": "Tiền cọc" if target_type == "coc" else "Hóa đơn",
        "target_id": target.pk,
        "object_label": object_label,
        "reference": reference,
        "tenant_name": tenant.ho_ten if tenant else "Không xác định",
        "room_label": room.so_phong if room else "Không xác định",
        "facility_id": room.co_so_id if room else None,
        "facility_name": room.co_so.ten_co_so if room and room.co_so else "Không xác định",
        "amount": amount,
        "submitted_at": submitted_at,
        "age_days": _age_days(submitted_at),
        "target_status": target.trang_thai,
        "target_status_label": target.get_trang_thai_display(),
        "evidence_status": evidence.trang_thai if evidence else "khong_co",
        "evidence_status_label": evidence.get_trang_thai_display() if evidence else "Không có chứng từ",
        "kind": kind,
        "kind_label": KIND_LABELS[kind],
        "is_actionable": kind in ACTIONABLE_KINDS,
        "reviewer": evidence.nguoi_xu_ly.get_username() if evidence and evidence.nguoi_xu_ly else "Chưa xử lý",
        "review_reason": (evidence.ghi_chu_doi_soat if evidence else reason) or "",
        "detail_url": detail_url,
        "evidence_url": reverse("anh_chung_tu_thanh_toan", args=[evidence.pk]) if evidence else "",
    }


def _deposit_rows(query, facility_id, evidence_state):
    queryset = (
        ThanhToanCocDatPhong.objects
        .filter(Q(chung_tu__isnull=False) | Q(trang_thai="cho_xac_nhan"))
        .select_related(
            "chung_tu",
            "chung_tu__nguoi_xu_ly",
            "dat_phong__nguoi_thue",
            "dat_phong__phong__co_so",
        )
        .distinct()
    )
    if query:
        queryset = queryset.filter(
            Q(ma_tham_chieu__icontains=query)
            | Q(dat_phong__ma_yeu_cau__icontains=query)
            | Q(dat_phong__nguoi_thue__ho_ten__icontains=query)
            | Q(dat_phong__phong__so_phong__icontains=query)
            | Q(dat_phong__phong__co_so__ten_co_so__icontains=query)
        )
    if facility_id:
        queryset = queryset.filter(dat_phong__phong__co_so_id=facility_id)
    if evidence_state == "khong_co":
        queryset = queryset.filter(chung_tu__isnull=True)
    elif evidence_state:
        queryset = queryset.filter(chung_tu__trang_thai=evidence_state)

    rows = []
    for payment in queryset:
        evidence = _evidence(payment)
        booking = payment.dat_phong
        room = booking.phong
        submitted_at = (
            evidence.ngay_tao if evidence else
            payment.thoi_diem_user_bao_da_thanh_toan or payment.ngay_cap_nhat
        )
        kind = _classify_deposit(payment, evidence)
        rows.append(_common_row(
            target_type="coc",
            target=payment,
            evidence=evidence,
            tenant=booking.nguoi_thue,
            room=room,
            amount=payment.so_tien,
            reference=evidence.ma_doi_chieu if evidence else payment.ma_tham_chieu,
            object_label=booking.ma_yeu_cau,
            detail_url=reverse("chi_tiet_dat_phong", args=[booking.pk]),
            kind=kind,
            submitted_at=submitted_at,
            reason=payment.ly_do_tu_choi,
        ))
    return rows


def _invoice_rows(query, facility_id, evidence_state):
    queryset = (
        HoaDon.objects
        .filter(Q(chung_tu_thanh_toan__isnull=False) | Q(trang_thai="cho_xac_nhan"))
        .select_related(
            "hop_dong__dat_phong__nguoi_thue",
            "hop_dong__dat_phong__phong__co_so",
        )
        .distinct()
    )
    if query:
        query_filter = (
            Q(chung_tu_thanh_toan__ma_doi_chieu__icontains=query)
            | Q(hop_dong__so_hop_dong__icontains=query)
            | Q(hop_dong__dat_phong__nguoi_thue__ho_ten__icontains=query)
            | Q(hop_dong__dat_phong__phong__so_phong__icontains=query)
            | Q(hop_dong__dat_phong__phong__co_so__ten_co_so__icontains=query)
        )
        if query.isdigit():
            query_filter |= Q(pk=int(query))
        queryset = queryset.filter(query_filter)
    if facility_id:
        queryset = queryset.filter(hop_dong__dat_phong__phong__co_so_id=facility_id)
    rows = []
    for invoice in queryset:
        evidence = _evidence(invoice)
        # Filters describe the current attempt, never an older immutable row.
        if evidence_state == "khong_co" and evidence is not None:
            continue
        if evidence_state and evidence_state != "khong_co" and (
            evidence is None or evidence.trang_thai != evidence_state
        ):
            continue
        booking = invoice.hop_dong.dat_phong
        room = booking.phong
        submitted_at = evidence.ngay_tao if evidence else invoice.ngay_cap_nhat
        kind = _classify_invoice(invoice, evidence)
        rows.append(_common_row(
            target_type="hoa_don",
            target=invoice,
            evidence=evidence,
            tenant=booking.nguoi_thue,
            room=room,
            amount=invoice.tong_tien,
            reference=evidence.ma_doi_chieu if evidence else f"NDTMOTEL HD{invoice.pk}",
            object_label=f"HĐ-{invoice.pk} · {invoice.thang}/{invoice.nam}",
            detail_url=reverse("chi_tiet_hoa_don", args=[invoice.pk]),
            kind=kind,
            submitted_at=submitted_at,
        ))
    return rows


def _in_age_bucket(days, bucket):
    return (
        (bucket == "0_1" and days <= 1)
        or (bucket == "2_3" and 2 <= days <= 3)
        or (bucket == "4_7" and 4 <= days <= 7)
        or (bucket == "8_plus" and days >= 8)
    )


def reconciliation_report(*, query="", target_type="", evidence_state="",
                          exception_kind="can_xu_ly", age_bucket="", facility_id=None):
    """Return filtered current-state rows and summary without mutating any model."""
    rows = []
    if target_type in ("", "coc"):
        rows.extend(_deposit_rows(query, facility_id, evidence_state))
    if target_type in ("", "hoa_don"):
        rows.extend(_invoice_rows(query, facility_id, evidence_state))

    if exception_kind == "can_xu_ly":
        rows = [row for row in rows if row["kind"] in ACTIONABLE_KINDS]
    elif exception_kind:
        rows = [row for row in rows if row["kind"] == exception_kind]
    if age_bucket:
        rows = [row for row in rows if _in_age_bucket(row["age_days"], age_bucket)]

    rows.sort(key=lambda row: (row["submitted_at"], row["target_type"], row["target_id"]))
    summary = {kind: 0 for kind in KIND_LABELS}
    for row in rows:
        summary[row["kind"]] += 1
    summary["tong_so"] = len(rows)
    summary["can_xu_ly"] = sum(1 for row in rows if row["is_actionable"])
    facilities = CoSo.objects.order_by("ten_co_so", "pk")
    return rows, summary, facilities
