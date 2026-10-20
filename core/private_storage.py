from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivatePaymentEvidenceStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_PAYMENT_EVIDENCE_ROOT)
        kwargs.setdefault("base_url", None)
        super().__init__(*args, **kwargs)


private_payment_evidence_storage = PrivatePaymentEvidenceStorage()


class PrivateCoTenantIdentityEvidenceStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_COTENANT_IDENTITY_EVIDENCE_ROOT)
        kwargs.setdefault("base_url", None)
        super().__init__(*args, **kwargs)


private_cotenant_identity_evidence_storage = PrivateCoTenantIdentityEvidenceStorage()
