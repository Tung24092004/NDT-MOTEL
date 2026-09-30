"""Business notifications addressed to Admin accounts."""

from django.contrib.auth.models import User
from django.db.models import Q

from core.models import ThongBao

from core.dich_vu.thong_bao_dat_phong import notify_admins


def notify_booking_event(*, booking, event, title, text, url=""):
    notify_admins(
        booking=booking,
        event=event,
        title=title,
        text=text,
        url=url,
    )


def notify_admin_event(*, reference, notification_type, title, text, url=""):
    """Create one scoped notification per active Admin for a business event."""
    recipients = User.objects.filter(is_active=True).filter(
        Q(is_staff=True) | Q(is_superuser=True)
    )
    notifications = []
    for recipient in recipients:
        notification, _ = ThongBao.objects.get_or_create(
            nguoi_nhan_user=recipient,
            ma_tham_chieu=f"{reference}:{recipient.pk}",
            defaults={
                "loai": notification_type,
                "tieu_de": title,
                "noi_dung": text,
                "url_lien_ket": url,
            },
        )
        notifications.append(notification)
    return notifications
