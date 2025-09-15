from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class ProcessCreateResponse(BaseModel):
    process_id: str


class FileInfo(BaseModel):
    filename: str
    content_type: str
    size: int


class ProcessSummaryFileInfo(BaseModel):
    filename: str


class ProcessInfo(BaseModel):
    process_id: str
    created_at: datetime
    file_count: int


class ProcessSummaryResponse(BaseModel):
    Process: ProcessInfo
    files: List[ProcessSummaryFileInfo]


class FileContentResponse(BaseModel):
    content: str


class enlist_process_queue_response(BaseModel):
    user_id: str
    process_id: str
    message: Optional[str] = None
    files: Optional[List[FileInfo]] = None

    def to_base64(self) -> str:
        """
        Convert the response to a base64 encoded string.
        This is useful for creating queue message.
        """
        import base64

        return base64.b64encode(self.model_dump_json().encode()).decode()
