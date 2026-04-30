"""Tests for src/app/libs/sas/__init__.py"""


def test_sas_package_init():
    """Test that SAS package initializes correctly"""
    from libs.sas import source_root
    assert source_root is not None
    assert "sas" in source_root.lower()


def test_sas_path_in_sys_path():
    """Test that SAS package root is added to sys.path"""
    import sys
    import libs.sas
    
    # Check that the sas source root is in sys.path
    sas_root = libs.sas.source_root
    assert sas_root in sys.path or any(sas_root.lower() in p.lower() for p in sys.path)
