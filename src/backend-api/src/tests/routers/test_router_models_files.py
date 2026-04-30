from routers.models.files import File, Batch, FileUploadResult, FileInfo


def test_file_initialization():
    """Test File class initialization."""
    file = File("file-123", "test.txt")
    
    assert file.file_id == "file-123"
    assert file.original_name == "test.txt"


def test_batch_initialization():
    """Test Batch class initialization."""
    batch = Batch("batch-456")
    
    assert batch.batch_id == "batch-456"


def test_file_upload_result_initialization():
    """Test FileUploadResult class initialization."""
    result = FileUploadResult(batch_id="batch-123", file_id="file-456", file_name="data.csv")
    
    assert result.batch.batch_id == "batch-123"
    assert result.file.file_id == "file-456"
    assert result.file.original_name == "data.csv"


def test_file_upload_result_structure():
    """Test FileUploadResult has correct nested structure."""
    result = FileUploadResult(batch_id="batch-789", file_id="file-999", file_name="report.pdf")
    
    assert hasattr(result, 'batch')
    assert hasattr(result, 'file')
    assert isinstance(result.batch, Batch)
    assert isinstance(result.file, File)


def test_file_with_various_names():
    """Test File with various filename patterns."""
    test_cases = [
        "document.txt",
        "archive.zip",
        "image.png",
        "data.csv",
        "file_with_underscore.pdf",
        "file-with-dash.docx",
    ]
    
    for filename in test_cases:
        file = File("id", filename)
        assert file.original_name == filename


def test_batch_with_uuid():
    """Test Batch with UUID-like IDs."""
    batch_id = "550e8400-e29b-41d4-a716-446655440000"
    batch = Batch(batch_id)
    assert batch.batch_id == batch_id


def test_file_upload_result_with_empty_names():
    """Test FileUploadResult with empty strings."""
    result = FileUploadResult(batch_id="", file_id="", file_name="")
    
    assert result.batch.batch_id == ""
    assert result.file.file_id == ""
    assert result.file.original_name == ""


def test_file_info_basic():
    """Test FileInfo Pydantic model."""
    file_info = FileInfo(
        filename="test.txt",
        content_type="text/plain",
        size=1024
    )
    
    assert file_info.filename == "test.txt"
    assert file_info.content_type == "text/plain"
    assert file_info.size == 1024


def test_file_info_with_content():
    """Test FileInfo with content."""
    file_info = FileInfo(
        filename="data.bin",
        content=b"binary data",
        content_type="application/octet-stream",
        size=11
    )
    
    assert file_info.filename == "data.bin"
    assert file_info.content == b"binary data"
    assert file_info.size == 11


def test_file_info_json_excludes_content():
    """Test that FileInfo serialization excludes content."""
    file_info = FileInfo(
        filename="test.txt",
        content=b"secret data",
        content_type="text/plain",
        size=11
    )
    
    # The content should be excluded from serialization
    model_dump = file_info.model_dump()
    assert "content" not in model_dump


def test_file_info_without_content():
    """Test FileInfo with None content."""
    file_info = FileInfo(
        filename="empty.txt",
        content=None,
        content_type="text/plain",
        size=0
    )
    
    assert file_info.content is None


def test_file_info_various_content_types():
    """Test FileInfo with various content types."""
    content_types = [
        "text/plain",
        "application/json",
        "image/png",
        "video/mp4",
        "application/zip",
        "application/pdf",
    ]
    
    for content_type in content_types:
        file_info = FileInfo(
            filename="test",
            content_type=content_type,
            size=100
        )
        assert file_info.content_type == content_type


def test_file_info_various_sizes():
    """Test FileInfo with various file sizes."""
    sizes = [0, 1, 1024, 1024*1024, 1024*1024*1024]
    
    for size in sizes:
        file_info = FileInfo(
            filename="test",
            content_type="application/octet-stream",
            size=size
        )
        assert file_info.size == size
