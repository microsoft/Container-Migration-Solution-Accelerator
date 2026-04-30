from abc import ABC
from libs.services.interfaces import IDataService, ILoggerService, IHttpService


def test_idata_service_is_abstract():
    """Test that IDataService is an abstract base class."""
    assert issubclass(IDataService, ABC)


def test_ilogger_service_is_abstract():
    """Test that ILoggerService is an abstract base class."""
    assert issubclass(ILoggerService, ABC)


def test_ihttp_service_is_abstract():
    """Test that IHttpService is an abstract base class."""
    assert issubclass(IHttpService, ABC)


def test_idata_service_has_required_methods():
    """Test that IDataService has required abstract methods."""
    assert hasattr(IDataService, 'get_data')
    assert hasattr(IDataService, 'save_data')


def test_ilogger_service_has_required_methods():
    """Test that ILoggerService has required abstract methods."""
    assert hasattr(ILoggerService, 'log_info')
    assert hasattr(ILoggerService, 'log_error')


def test_ihttp_service_has_required_methods():
    """Test that IHttpService has required abstract methods."""
    assert hasattr(IHttpService, 'get')
    assert hasattr(IHttpService, 'post')


def test_idata_service_get_data_signature():
    """Test that IDataService.get_data has correct signature."""
    import inspect
    sig = inspect.signature(IDataService.get_data)
    params = list(sig.parameters.keys())
    assert 'self' in params
    assert 'key' in params


def test_idata_service_save_data_signature():
    """Test that IDataService.save_data has correct signature."""
    import inspect
    sig = inspect.signature(IDataService.save_data)
    params = list(sig.parameters.keys())
    assert 'self' in params
    assert 'key' in params
    assert 'data' in params


def test_ilogger_service_log_info_signature():
    """Test that ILoggerService.log_info has correct signature."""
    import inspect
    sig = inspect.signature(ILoggerService.log_info)
    params = list(sig.parameters.keys())
    assert 'self' in params
    assert 'message' in params


def test_ilogger_service_log_error_signature():
    """Test that ILoggerService.log_error has correct signature."""
    import inspect
    sig = inspect.signature(ILoggerService.log_error)
    params = list(sig.parameters.keys())
    assert 'self' in params
    assert 'message' in params
    assert 'exception' in params


def test_ihttp_service_get_signature():
    """Test that IHttpService.get has correct signature."""
    import inspect
    sig = inspect.signature(IHttpService.get)
    params = list(sig.parameters.keys())
    assert 'self' in params
    assert 'url' in params


def test_ihttp_service_post_signature():
    """Test that IHttpService.post has correct signature."""
    import inspect
    sig = inspect.signature(IHttpService.post)
    params = list(sig.parameters.keys())
    assert 'self' in params
    assert 'url' in params
    assert 'data' in params
