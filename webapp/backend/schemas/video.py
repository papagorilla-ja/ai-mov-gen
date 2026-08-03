from datetime import datetime
from pydantic import BaseModel, ConfigDict

class VideoBase(BaseModel):
    name: str

class VideoCreate(VideoBase):
    pass

class VideoUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    duration_sec: float | None = None

class VideoRead(VideoBase):
    id: str
    project_id: str
    status: str
    output_dir: str | None = None
    duration_sec: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
