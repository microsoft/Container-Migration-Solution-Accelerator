from src.libs.base.ApplicationBase import ApplicationBase


def test_ApplicationBase():
    assert ApplicationBase.run is not None
    assert ApplicationBase.__init__ is not None
    assert ApplicationBase._initialize_kernel is not None
    assert ApplicationBase._load_env is not None
    assert ApplicationBase._get_derived_class_location is not None
    assert ApplicationBase._detect_plugins_directory is not None
