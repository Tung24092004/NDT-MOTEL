"""Admin-only read model for PAY-04 current-state exception reconciliation."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import QueryDict
from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from core.dich_vu.doi_soat_ngoai_le_thanh_toan import (
    AGE_BUCKETS,
    EVIDENCE_STATES,
    EXCEPTION_KINDS,
    TARGET_TYPES,
    reconciliation_report,
)
from core.dich_vu.phan_quyen import la_admin


def _choice(value, allowed, default=""):
    return value if value in allowed else default


@require_safe
@login_required(login_url="dang_nhap")
def doi_soat_ngoai_le_thanh_toan(request):
    if not la_admin(request):
        return redirect("tai_khoan")

    query = request.GET.get("q", "").strip()[:200]
    target_type = _choice(request.GET.get("loai", "").strip(), TARGET_TYPES)
    evidence_state = _choice(request.GET.get("chung_tu", "").strip(), EVIDENCE_STATES)
    exception_kind = _choice(
        request.GET.get("phan_loai", "can_xu_ly").strip(),
        EXCEPTION_KINDS,
        "can_xu_ly",
    )
    age_bucket = _choice(request.GET.get("tuoi", "").strip(), AGE_BUCKETS)
    facility_raw = request.GET.get("co_so", "").strip()
    facility_id = int(facility_raw) if facility_raw.isdigit() else None

    rows, summary, facilities = reconciliation_report(
        query=query,
        target_type=target_type,
        evidence_state=evidence_state,
        exception_kind=exception_kind,
        age_bucket=age_bucket,
        facility_id=facility_id,
    )
    page_obj = Paginator(rows, 20).get_page(request.GET.get("page"))
    pagination_params = QueryDict(mutable=True)
    for key, value in request.GET.items():
        if key != "page" and value:
            pagination_params[key] = value

    return render(request, "core/doi_soat_ngoai_le_thanh_toan.html", {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "summary": summary,
        "facilities": facilities,
        "q": query,
        "loai": target_type,
        "chung_tu": evidence_state,
        "phan_loai": exception_kind,
        "tuoi": age_bucket,
        "co_so": str(facility_id) if facility_id else "",
        "query_string": pagination_params.urlencode(),
    })
