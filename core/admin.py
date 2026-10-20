from django.contrib import admin, messages
from django import forms
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse

from .models import (
    CoSo,
    Phong,
    NguoiThue,
    DatPhong,
    HopDong,
    HoaDon,
    YeuCauSuaChua,
    ChinhSachHoTro,
    ThongBao,
    # Smart Room — Phase 1
    NguoiOCungPhong,
    FaceProfile,
    QuyenRaVao,
    LichSuRaVao,
    NhatKyThaoTac,
    LichSuThanhToan,
    LichSuHopDong,
    LichSuSuaChua,
    LichSuThongBao,
    LichSuTrangThai,
    KhaiBaoNguoiOCungDatPhong,
    ThanhToanCocDatPhong,
    QuyetToanCocDatPhong,
    RaSoatThanhToanHoaDonCu,
)


class ApplicationWorkflowAdmin(admin.ModelAdmin):
    """Lifecycle creation/deletion belongs to the application's guarded actions."""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    """Audit records are written by workflows, never by Django admin."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CoSo)
class CoSoAdmin(admin.ModelAdmin):
    list_display = (
        "ten_co_so",
        "dia_chi",
        "quan",
        "so_dien_thoai",
        "trang_thai",
    )

    search_fields = (
        "ten_co_so",
        "dia_chi",
        "quan",
    )

    list_filter = (
        "quan",
        "trang_thai",
    )


@admin.register(Phong)
class PhongAdmin(admin.ModelAdmin):
    readonly_fields = ("trang_thai",)
    list_display = (
        "so_phong",
        "co_so",
        "gia_thue",
        "dien_tich",
        "trang_thai",
    )

    search_fields = (
        "so_phong",
        "co_so__ten_co_so",
    )

    list_filter = (
        "co_so",
        "trang_thai",
    )


@admin.register(NguoiThue)
class NguoiThueAdmin(admin.ModelAdmin):
    list_display = (
        "ho_ten",
        "so_dien_thoai",
        "email",
        "cccd",
        "nghe_nghiep",
        "ngay_tao",
    )

    search_fields = (
        "ho_ten",
        "so_dien_thoai",
        "email",
        "cccd",
    )

    list_filter = (
        "gioi_tinh",
        "nghe_nghiep",
    )


@admin.register(DatPhong)
class DatPhongAdmin(ApplicationWorkflowAdmin):
    readonly_fields = ("phong", "nguoi_thue", "trang_thai", "ngay_duyet",
                       "ngay_tu_choi", "ngay_huy", "nguoi_xu_ly",
                       "so_nguoi_o", "dong_y_nhan_yeu_cau_ghep", "tien_coc_du_kien",
                       "gia_thue_thang_tai_thoi_diem_dat", "snapshot_gia_la_backfill",
                       "da_dong_y_dieu_khoan", "thoi_diem_dong_y_dieu_khoan",
                       "noi_dung_dieu_khoan_snapshot", "ty_le_hoan_coc_snapshot",
                       "han_thanh_toan_coc", "ma_yeu_cau")
    list_display = (
        "nguoi_thue",
        "phong",
        "ngay_dat",
        "ngay_nhan_phong",
        "tien_coc_du_kien",
        "trang_thai",
    )

    search_fields = (
        "nguoi_thue__ho_ten",
        "nguoi_thue__cccd",
        "nguoi_thue__so_dien_thoai",
        "phong__so_phong",
    )

    list_filter = (
        "trang_thai",
        "ngay_nhan_phong",
    )


@admin.register(HopDong)
class HopDongAdmin(ApplicationWorkflowAdmin):
    readonly_fields = ("dat_phong", "trang_thai", "ngay_bat_dau", "ngay_ket_thuc",
                       "ngay_ky", "ngay_huy", "ly_do_huy", "nguoi_cap_nhat")
    list_display = (
        "so_hop_dong",
        "dat_phong",
        "ngay_bat_dau",
        "ngay_ket_thuc",
        "tien_coc",
        "tien_thue_thang",
        "trang_thai",
    )

    search_fields = (
        "so_hop_dong",
        "dat_phong__nguoi_thue__ho_ten",
    )

    list_filter = (
        "trang_thai",
        "phuong_thuc_thanh_toan",
    )


@admin.register(HoaDon)
class HoaDonAdmin(ApplicationWorkflowAdmin):
    change_form_template = 'admin/core/hoadon/change_form.html'
    readonly_fields = ("hop_dong", "trang_thai", "ngay_thanh_toan", "ma_giao_dich",
                       "phuong_thuc", "nguoi_xac_nhan")
    list_display = (
        "hop_dong",
        "thang",
        "nam",
        "tien_phong",
        "tien_dien",
        "tien_nuoc",
        "tien_dich_vu",
        "phi_khac",
        "tong_tien",
        "han_thanh_toan",
        "trang_thai",
    )

    search_fields = (
        "hop_dong__so_hop_dong",
        "hop_dong__dat_phong__nguoi_thue__ho_ten",
    )

    list_filter = (
        "nam",
        "thang",
        "trang_thai",
        "phuong_thuc",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = tuple(self.readonly_fields)
        if obj and obj.financial_snapshot_is_locked():
            return readonly + tuple(
                field for field in HoaDon.FINANCIAL_SNAPSHOT_FIELDS
                if field not in readonly
            )
        return readonly

    def get_urls(self):
        return [path('<int:invoice_id>/legacy-review/', self.admin_site.admin_view(self.legacy_review_view), name='core_hoadon_legacy_review')] + super().get_urls()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        invoice = self.get_object(request, object_id); extra_context = extra_context or {}
        if invoice:
            from core.dich_vu.ra_soat_thanh_toan_cu import missing_paid_provenance
            extra_context['legacy_review_url'] = reverse('admin:core_hoadon_legacy_review', args=[invoice.pk])
            extra_context['can_legacy_review'] = invoice.trang_thai == 'da_thanh_toan' and bool(missing_paid_provenance(invoice)) and not hasattr(invoice, 'ra_soat_thanh_toan_cu')
        return super().change_view(request, object_id, form_url, extra_context)

    def legacy_review_view(self, request, invoice_id):
        invoice = get_object_or_404(HoaDon.objects.select_related('hop_dong'), pk=invoice_id)
        from core.dich_vu.ra_soat_thanh_toan_cu import missing_paid_provenance
        missing_provenance = missing_paid_provenance(invoice)
        unknown = 'Không có / UNKNOWN'
        legacy_facts = {
            'payment_date': invoice.ngay_thanh_toan or unknown,
            'payment_method': invoice.phuong_thuc or unknown,
            'transaction_reference': invoice.ma_giao_dich or unknown,
            'confirmer': invoice.nguoi_xac_nhan or unknown,
            'payment_history_exists': 'payment_history' not in missing_provenance,
            'missing_provenance': missing_provenance,
        }
        class ReviewForm(forms.Form):
            evidence_grade = forms.ChoiceField(choices=RaSoatThanhToanHoaDonCu.MUC_DO_BANG_CHUNG)
            note = forms.CharField(widget=forms.Textarea, max_length=4000)
        form = ReviewForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            from core.dich_vu.ra_soat_thanh_toan_cu import reconcile_legacy_paid_invoice
            try: reconcile_legacy_paid_invoice(actor=request.user, invoice_id=invoice.pk, **form.cleaned_data)
            except ValidationError as exc: form.add_error(None, exc)
            else:
                messages.success(request, 'Da ghi nhan ra soat du lieu thanh toan cu.')
                return redirect('admin:core_hoadon_change', invoice.pk)
        return render(request, 'admin/core/hoadon/legacy_review.html', {**self.admin_site.each_context(request), 'title':'Ra soat thanh toan cu', 'invoice':invoice, 'form':form, 'legacy_facts':legacy_facts})


@admin.register(RaSoatThanhToanHoaDonCu)
class RaSoatThanhToanHoaDonCuAdmin(ReadOnlyAuditAdmin):
    list_display = ('hoa_don', 'muc_do_bang_chung', 'nguoi_ra_soat', 'thoi_diem_ra_soat')


@admin.register(YeuCauSuaChua)
class YeuCauSuaChuaAdmin(admin.ModelAdmin):
    lifecycle_readonly_fields = (
        "nguoi_thue", "phong", "trang_thai", "nguoi_xu_ly",
        "nguoi_xu_ly_user", "ngay_bat_dau_xu_ly", "ngay_hoan_thanh",
        "ngay_tao", "ngay_cap_nhat",
    )
    list_display = (
        "tieu_de",
        "nguoi_thue",
        "phong",
        "loai_su_co",
        "muc_do",
        "trang_thai",
        "chi_phi",
        "ngay_tao",
    )

    search_fields = (
        "tieu_de",
        "noi_dung",
        "nguoi_thue__ho_ten",
        "phong__so_phong",
    )

    list_filter = (
        "loai_su_co",
        "muc_do",
        "trang_thai",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return self.lifecycle_readonly_fields if obj else ()


@admin.register(ChinhSachHoTro)
class ChinhSachHoTroAdmin(admin.ModelAdmin):
    list_display = (
        "ten_chinh_sach",
        "doi_tuong",
        "loai_ho_tro",
        "gia_tri_ho_tro",
        "ngan_sach",
        "ngay_bat_dau",
        "ngay_ket_thuc",
        "trang_thai",
    )

    search_fields = (
        "ten_chinh_sach",
        "doi_tuong",
        "doi_tuong_khac",
    )

    list_filter = (
        "loai_ho_tro",
        "trang_thai",
        "ngay_bat_dau",
        "ngay_ket_thuc",
    )

    fields = (
        "ten_chinh_sach",
        "doi_tuong",
        "doi_tuong_khac",
        "loai_ho_tro",
        "gia_tri_ho_tro",
        "ngan_sach",
        "ngay_bat_dau",
        "ngay_ket_thuc",
        "dieu_kien",
        "trang_thai",
        "mo_ta",
    )


@admin.register(ThongBao)
class ThongBaoAdmin(admin.ModelAdmin):
    list_display = (
        "tieu_de",
        "nguoi_thue",
        "loai",
        "da_doc",
        "ngay_tao",
    )

    search_fields = (
        "tieu_de",
        "noi_dung",
        "nguoi_thue__ho_ten",
    )

    list_filter = (
        "loai",
        "da_doc",
        "ngay_tao",
    )


# =========================================================
# SMART ROOM — PHASE 1
# =========================================================

@admin.register(NguoiOCungPhong)
class NguoiOCungPhongAdmin(ApplicationWorkflowAdmin):
    readonly_fields = ("hop_dong", "trang_thai", "ngay_vao", "ngay_ra")
    list_display = (
        "ho_ten",
        "hop_dong",
        "quan_he",
        "trang_thai",
        "ngay_vao",
        "ngay_tao",
    )
    search_fields = (
        "ho_ten",
        "cccd",
        "so_dien_thoai",
        "hop_dong__so_hop_dong",
    )
    list_filter = (
        "trang_thai",
        "gioi_tinh",
    )


@admin.register(FaceProfile)
class FaceProfileAdmin(ApplicationWorkflowAdmin):
    readonly_fields = ("nguoi_thue", "danh_tinh_nguoi_o_cung", "loai_chu_the",
                       "anh_dai_dien", "face_encoding", "trang_thai")
    list_display = (
        "__str__",
        "loai_chu_the",
        "trang_thai",
        "ngay_tao",
    )
    search_fields = (
        "nguoi_thue__ho_ten",
        "danh_tinh_nguoi_o_cung__cccd",
    )
    list_filter = (
        "loai_chu_the",
        "trang_thai",
    )


@admin.register(QuyenRaVao)
class QuyenRaVaoAdmin(ApplicationWorkflowAdmin):
    readonly_fields = ("hop_dong", "nguon_cap", "phong", "nguoi_thue", "nguoi_o_cung", "loai_quyen",
                       "trang_thai", "ngay_bat_dau", "ngay_ket_thuc")
    list_display = (
        "__str__",
        "phong",
        "loai_quyen",
        "trang_thai",
        "ngay_bat_dau",
        "ngay_ket_thuc",
    )
    search_fields = (
        "nguoi_thue__ho_ten",
        "nguoi_o_cung__ho_ten",
        "phong__so_phong",
        "ma_the",
    )
    list_filter = (
        "loai_quyen",
        "trang_thai",
    )


@admin.register(LichSuRaVao)
class LichSuRaVaoAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "ten_nguoi",
        "phong",
        "loai_su_kien",
        "nguon",
        "thoi_diem",
    )
    search_fields = (
        "ten_nguoi",
        "phong__so_phong",
    )
    list_filter = (
        "loai_su_kien",
        "nguon",
    )


@admin.register(NhatKyThaoTac)
class NhatKyThaoTacAdmin(ReadOnlyAuditAdmin):
    list_display = ('tieu_de', 'nguoi_thuc_hien', 'hanh_dong', 'module', 'thoi_diem')
    search_fields = ('tieu_de', 'noi_dung', 'doi_tuong')
    list_filter = ('hanh_dong', 'module', 'thoi_diem')


@admin.register(LichSuThanhToan)
class LichSuThanhToanAdmin(ReadOnlyAuditAdmin):
    list_display = ('hoa_don', 'so_tien', 'phuong_thuc', 'nguoi_thuc_hien', 'thoi_diem')
    search_fields = ('ma_giao_dich', 'noi_dung')
    list_filter = ('phuong_thuc', 'thoi_diem')


@admin.register(LichSuHopDong)
class LichSuHopDongAdmin(ReadOnlyAuditAdmin):
    list_display = ('hop_dong', 'hanh_dong', 'nguoi_thuc_hien', 'thoi_diem')
    search_fields = ('hop_dong__so_hop_dong', 'noi_dung')
    list_filter = ('hanh_dong', 'thoi_diem')


@admin.register(LichSuSuaChua)
class LichSuSuaChuaAdmin(ReadOnlyAuditAdmin):
    list_display = ('yeu_cau', 'hanh_dong', 'nguoi_thuc_hien', 'thoi_diem')
    search_fields = ('yeu_cau__tieu_de', 'noi_dung')
    list_filter = ('hanh_dong', 'thoi_diem')


@admin.register(LichSuThongBao)
class LichSuThongBaoAdmin(ReadOnlyAuditAdmin):
    list_display = ('thong_bao', 'hanh_dong', 'nguoi_thuc_hien', 'thoi_diem')
    search_fields = ('thong_bao__tieu_de',)
    list_filter = ('hanh_dong', 'thoi_diem')


@admin.register(LichSuTrangThai)
class LichSuTrangThaiAdmin(ReadOnlyAuditAdmin):
    list_display = ('doi_tuong', 'doi_tuong_id', 'trang_thai_cu', 'trang_thai_moi', 'thoi_diem')
    search_fields = ('doi_tuong', 'ly_do')
    list_filter = ('doi_tuong', 'thoi_diem')


@admin.register(KhaiBaoNguoiOCungDatPhong)
class KhaiBaoNguoiOCungDatPhongAdmin(ReadOnlyAuditAdmin):
    list_display = ('ho_ten', 'dat_phong', 'trang_thai_xac_minh', 'ngay_tao')
    search_fields = ('ho_ten', 'cccd', 'dat_phong__ma_yeu_cau')
    list_filter = ('trang_thai_xac_minh', 'ngay_tao')


@admin.register(ThanhToanCocDatPhong)
class ThanhToanCocDatPhongAdmin(ReadOnlyAuditAdmin):
    change_form_template = 'admin/core/thanhtoancocdatphong/change_form.html'
    list_display = ('ma_tham_chieu', 'dat_phong', 'so_tien', 'so_tien_thuc_nhan', 'trang_thai', 'settlement_status', 'nguoi_xac_nhan', 'ngay_tao')
    search_fields = ('ma_tham_chieu', 'ma_giao_dich', 'dat_phong__ma_yeu_cau')
    list_filter = ('trang_thai', 'phuong_thuc', 'ngay_tao')

    def get_readonly_fields(self, request, obj=None):
        return super().get_readonly_fields(request, obj) + ('settlement_status',)

    @admin.display(description='Quyet toan')
    def settlement_status(self, obj):
        try:
            return obj.quyet_toan.get_ket_qua_display()
        except QuyetToanCocDatPhong.DoesNotExist:
            return 'Chua quyet toan'

    def get_urls(self):
        return [
            path('<int:payment_id>/settle/', self.admin_site.admin_view(self.settle_view), name='core_thanhtoancocdatphong_settle'),
        ] + super().get_urls()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        payment = self.get_object(request, object_id)
        extra_context = extra_context or {}
        if payment:
            extra_context['settlement_url'] = reverse('admin:core_thanhtoancocdatphong_settle', args=[payment.pk])
            extra_context['settlement_status'] = self.settlement_status(payment)
            contract = getattr(payment.dat_phong, 'hop_dong', None)
            extra_context['can_settle'] = (
                payment.trang_thai == 'da_xac_nhan'
                and bool(payment.so_tien_thuc_nhan and payment.so_tien_thuc_nhan > 0)
                and not hasattr(payment, 'quyet_toan')
                and ((contract and contract.trang_thai in ('da_huy', 'da_het_han'))
                     or (not contract and payment.dat_phong.trang_thai == 'da_huy'))
            )
        return super().change_view(request, object_id, form_url, extra_context)

    def settle_view(self, request, payment_id):
        payment = get_object_or_404(ThanhToanCocDatPhong.objects.select_related('dat_phong'), pk=payment_id)

        class SettlementForm(forms.Form):
            outcome = forms.ChoiceField(choices=QuyetToanCocDatPhong.KET_QUA)
            amount = forms.DecimalField(min_value=1, decimal_places=0, max_digits=12)
            reason = forms.CharField(widget=forms.Textarea, max_length=4000)

        form = SettlementForm(request.POST or None, initial={'amount': payment.so_tien_thuc_nhan})
        if request.method == 'POST' and form.is_valid():
            from core.dich_vu.tien_coc import settle_confirmed_deposit
            try:
                settle_confirmed_deposit(actor=request.user, payment_id=payment.pk, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Da ghi nhan quyet toan coc.')
                return redirect('admin:core_thanhtoancocdatphong_change', payment.pk)
        return render(request, 'admin/core/thanhtoancocdatphong/settle.html', {
            **self.admin_site.each_context(request), 'title': 'Quyet toan coc dat phong',
            'payment': payment, 'form': form,
        })


@admin.register(QuyetToanCocDatPhong)
class QuyetToanCocDatPhongAdmin(ReadOnlyAuditAdmin):
    list_display = ('giao_dich_coc', 'ket_qua', 'so_tien', 'nguoi_quyet_toan', 'thoi_diem')
    search_fields = ('giao_dich_coc__ma_tham_chieu',)
    list_filter = ('ket_qua', 'thoi_diem')
