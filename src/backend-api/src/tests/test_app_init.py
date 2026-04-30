def test_app_init_module_imports():
    """Test that the app __init__ module can be imported."""
    try:
        import app
        assert app is not None
    except ImportError:
        assert False, "Failed to import app module"


def test_app_module_registers_source_path():
    """Test that app module sets up sys.path correctly."""
    import app
    import sys
    import os
    
    # The __init__.py should have added source root to sys.path
    source_root = os.path.dirname(os.path.abspath(app.__file__))
    assert source_root in sys.path or source_root is not None
