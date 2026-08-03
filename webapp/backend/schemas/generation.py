from datetime import datetime
from pydantic import BaseModel, ConfigDict

class GenerationHistoryRead(BaseModel):
    id: str
    video_id: str
    output_path: str | None = None
    status: str
    log_text: str | None = None
    error_message: str | None = None
    duration_sec: float | None = None
    file_size_bytes: int | None = None
    thumbnail_path: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class GenerationStatus(BaseModel):
    step: str
    progress: float
    message: str | None = None
    error: str | None = None
