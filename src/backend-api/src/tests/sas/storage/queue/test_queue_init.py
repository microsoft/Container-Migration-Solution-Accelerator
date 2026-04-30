"""Tests for src/app/libs/sas/storage/queue/__init__.py"""


def test_queue_module_exports_helper():
    """Test that queue module exports StorageQueueHelper"""
    from libs.sas.storage.queue import StorageQueueHelper
    assert StorageQueueHelper is not None


def test_queue_module_exports_async_helper():
    """Test that queue module exports AsyncStorageQueueHelper"""
    from libs.sas.storage.queue import AsyncStorageQueueHelper
    assert AsyncStorageQueueHelper is not None


def test_queue_all_exports():
    """Test that __all__ is properly defined in queue module"""
    from libs.sas.storage import queue
    
    expected_exports = ["StorageQueueHelper", "AsyncStorageQueueHelper"]
    
    for export in expected_exports:
        assert hasattr(queue, export), f"queue module missing export: {export}"
