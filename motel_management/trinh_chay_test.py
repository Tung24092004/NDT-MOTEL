"""Keep test uploads isolated and remove them after each run."""
import shutil
import sys
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.test import override_settings
from django.test.runner import DiscoverRunner


class CleanTestRunner(DiscoverRunner):
    def run_tests(self, test_labels, **kwargs):
        previous_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        temporary_parent = Path(settings.BASE_DIR) / ".test-media"
        temporary_root = temporary_parent / uuid4().hex
        temporary_root.mkdir(parents=True)
        try:
            with override_settings(MEDIA_ROOT=temporary_root):
                return super().run_tests(test_labels, **kwargs)
        finally:
            shutil.rmtree(temporary_root)
            try:
                temporary_parent.rmdir()
            except OSError:
                pass
            sys.dont_write_bytecode = previous_bytecode
