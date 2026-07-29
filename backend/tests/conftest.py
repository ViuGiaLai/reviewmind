"""
conftest.py — pytest shared fixtures and patches.

Windows fix: SQLite (with WAL mode) keeps journal files open briefly
after the connection is closed. This causes TemporaryDirectory.__exit__
to raise PermissionError on Windows when it tries to delete the temp dir.
We patch TemporaryDirectory to use ignore_cleanup_errors=True (Python 3.10+).
"""
from __future__ import annotations

import sys
import tempfile
import pytest


if sys.platform == "win32" and sys.version_info >= (3, 10):
    _orig_tmp = tempfile.TemporaryDirectory

    class _WinCompatTmpDir(_orig_tmp):
        """TemporaryDirectory that ignores cleanup errors on Windows."""
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("ignore_cleanup_errors", True)
            super().__init__(*args, **kwargs)

    tempfile.TemporaryDirectory = _WinCompatTmpDir  # type: ignore[misc]
