import os

import pytest

from libs.base.application_base import Application_Base


def test_application_base_initialization():
    with pytest.raises(TypeError):
        # Attempt to instantiate the abstract class directly
        Application_Base()


def test_application_base_init_method():
    class ConcreteApplication(Application_Base):
        def run(self):
            pass

        def initialize(self):
            pass

    app = ConcreteApplication(env_file_path=None)
    assert app.application_context is not None
    assert app.application_context.configuration is not None


def test_application_base_run_method():
    class ConcreteApplication(Application_Base):
        def initialize(self):
            pass

    with pytest.raises(TypeError):
        app = ConcreteApplication(env_file_path=None)
        # Attempt to call the run method which is not implemented
        app.run()


def test_application_base_initialize_method():
    class ConcreteApplication(Application_Base):
        def run(self):
            pass

    with pytest.raises(TypeError):
        app = ConcreteApplication(env_file_path=None)
        # Attempt to call the run method which is not implemented
        app.initialize()


def test_application_base_load_env():
    class ConcreteApplication(Application_Base):
        def run(self):
            pass

        def initialize(self):
            pass

    app = ConcreteApplication(env_file_path=None)
    app._load_env(env_file_path="../src/.env")
    assert app.application_context.configuration is not None


def test_application_base_get_derived_class_location():
    class ConcreteApplication(Application_Base):
        def run(self):
            pass

        def initialize(self):
            pass

    app = ConcreteApplication(env_file_path=None)
    derived_class_location = app._get_derived_class_location()
    assert derived_class_location is not None
    assert isinstance(derived_class_location, str)
    # Ensure the location should be a same path as the current file
    assert derived_class_location.__eq__(os.path.abspath(__file__))
