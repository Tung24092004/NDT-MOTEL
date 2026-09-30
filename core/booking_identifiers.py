"""Stable opaque references; shared by models and historical migrations."""
from uuid import uuid4


def booking_reference():
    return 'DP' + uuid4().hex.upper()


def deposit_reference():
    return 'COC' + uuid4().hex.upper()


def normalize_cccd(value):
    return ''.join(str(value or '').split()).replace('.', '').replace('-', '')
