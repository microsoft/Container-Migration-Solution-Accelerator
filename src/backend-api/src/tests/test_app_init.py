"""Trivial coverage for `app/__init__.py` (sys.path bootstrap)."""

import importlib
import os
import sys


def test_importing_app_package_inserts_source_root_into_syspath():
    # Import (or re-import) the app package
    if "app" in sys.modules:
        importlib.reload(sys.modules["app"])
    else:
        importlib.import_module("app")

    expected = os.path.dirname(os.path.abspath(sys.modules["app"].__file__))
    assert expected in sys.path
