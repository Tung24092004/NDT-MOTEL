"""Stable opaque references; shared by models and historical migrations."""
import re
from uuid import uuid4

from django.core.exceptions import ValidationError


def booking_reference():
    return 'DP' + uuid4().hex.upper()


def deposit_reference():
    return 'COC' + uuid4().hex.upper()


def normalize_cccd(value):
    return ''.join(str(value or '').split()).replace('.', '').replace('-', '')


def normalize_companion_cccd(value):
    """Return canonical co-tenant CCCD, or ``None`` when it is absent."""
    cccd = normalize_cccd(value)
    if not cccd:
        return None
    if not re.fullmatch(r"(?:\d{9}|\d{12})", cccd):
        raise ValidationError({"cccd": "CCCD phai gom dung 9 hoac 12 chu so."})
    return cccd
