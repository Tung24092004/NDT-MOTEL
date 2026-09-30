"""Explicit per-account notification recipients."""

from django.contrib.auth.models import User
from django.db.models import Q

from core.models import ThongBao


def notify_admins(*, booking, event, title, text, url=""):
    recipients = User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True))
    for recipient in recipients:
        ThongBao.objects.get_or_create(nguoi_nhan_user=recipient,
            ma_tham_chieu=f'BOOKING:{booking.pk}:{event}:{recipient.pk}',
            defaults={'loai': 'dat_phong', 'tieu_de': title, 'noi_dung': text, 'url_lien_ket': url})
