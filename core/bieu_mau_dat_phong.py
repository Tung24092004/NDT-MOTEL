"""Typed input for tenant booking; prices and identity never come from POST."""
from django import forms
from django.forms import formset_factory
from django.utils import timezone
from django.core.validators import MaxValueValidator

from .booking_identifiers import normalize_cccd


class BookingForm(forms.Form):
    ngay_nhan_phong = forms.DateField(label='Ngày nhận phòng', widget=forms.DateInput(attrs={'type': 'date'}))
    so_thang_thue = forms.IntegerField(label='Số tháng thuê', min_value=1, max_value=36, initial=3)
    so_nguoi_o = forms.IntegerField(label='Số người ở', min_value=1, initial=1)
    dong_y_nhan_yeu_cau_ghep = forms.BooleanField(label='Đồng ý nhận yêu cầu ở ghép sau khi có hợp đồng', required=False)
    ghi_chu = forms.CharField(label='Ghi chú', required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    da_dong_y_dieu_khoan = forms.BooleanField(label='Tôi đã đọc và đồng ý với thông tin, chi phí và điều khoản đặt phòng.')

    def __init__(self, *args, capacity, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'ndt-f5-control'
        self.fields['so_nguoi_o'].max_value = capacity
        self.fields['so_nguoi_o'].validators.append(MaxValueValidator(capacity))
        self.fields['so_nguoi_o'].widget.attrs['max'] = capacity
        self.fields['ngay_nhan_phong'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean_ngay_nhan_phong(self):
        value = self.cleaned_data['ngay_nhan_phong']
        if value < timezone.localdate():
            raise forms.ValidationError('Ngày nhận phòng không được ở quá khứ.')
        return value


class RentalQuoteForm(forms.Form):
    """The read-only rental-selection inputs, before a booking is submitted."""

    ngay_nhan_phong = forms.DateField(
        label='Ngày bắt đầu dự kiến', widget=forms.DateInput(attrs={'type': 'date'})
    )
    so_thang_thue = forms.IntegerField(label='Thời hạn thuê (tháng)', min_value=1, max_value=36, initial=3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'ndt-f5-control'
        self.fields['ngay_nhan_phong'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean_ngay_nhan_phong(self):
        value = self.cleaned_data['ngay_nhan_phong']
        if value < timezone.localdate():
            raise forms.ValidationError('Ngày bắt đầu không được ở quá khứ.')
        return value


class CompanionForm(forms.Form):
    ho_ten = forms.CharField(label='Họ tên', max_length=150)
    ngay_sinh = forms.DateField(label='Ngày sinh', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    gioi_tinh = forms.ChoiceField(label='Giới tính', required=False, choices=[('', 'Chọn'), ('nam', 'Nam'), ('nu', 'Nữ'), ('khac', 'Khác')])
    cccd = forms.CharField(label='CCCD', max_length=30)
    so_dien_thoai = forms.CharField(label='Số điện thoại', required=False, max_length=20)
    email = forms.EmailField(label='Email', required=False)
    quan_he = forms.CharField(label='Quan hệ', required=False, max_length=50)
    ghi_chu = forms.CharField(label='Ghi chú', required=False, max_length=500)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'ndt-f5-control'

    def clean_cccd(self):
        value = normalize_cccd(self.cleaned_data['cccd'])
        if len(value) != 12 or not value.isascii() or not value.isdigit():
            raise forms.ValidationError('CCCD phải gồm 12 chữ số.')
        return value


CompanionFormSet = formset_factory(CompanionForm, extra=0, can_delete=True,
                                 max_num=100, validate_max=True, absolute_max=100)
