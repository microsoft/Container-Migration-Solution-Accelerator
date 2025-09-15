from datetime import datetime, timezone
from pydantic import BaseModel, Field

# NOTE: keeping file_id and original_name naming to match existing frontend
class File:
    file_id: str
    original_name: str

    def __init__(self, file_id: str, original_name: str):
        self.file_id = file_id
        self.original_name = original_name

# NOTE: keeping "batch" instead of "process" naming to match existing frontend
class Batch:
    batch_id: str

    def __init__(self, batch_id: str):
        self.batch_id = batch_id

class FileUploadResult:
    def __init__(self, batch_id: str, file_id: str, file_name: str):
        self.batch = Batch(batch_id)
        self.file = File(file_id, file_name)


class FileInfo(BaseModel):
    filename: str
    # Don't serialize
    content: bytes | None = Field(exclude=True, default=None)
    content_type: str
    size: int