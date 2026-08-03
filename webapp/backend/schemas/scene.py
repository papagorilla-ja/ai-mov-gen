from datetime import datetime
from pydantic import BaseModel, ConfigDict

class SceneBase(BaseModel):
    title: str | None = None
    layout_type: str = "text_only"
    slide_content_json: str | None = None
    narration_text: str | None = None
    outline_summary: str | None = None
    speaker_id: str | None = None
    speaker_b_id: str | None = None
    image_prompt: str | None = None

class SceneCreate(SceneBase):
    pass

class SceneUpdate(BaseModel):
    title: str | None = None
    layout_type: str | None = None
    slide_content_json: str | None = None
    narration_text: str | None = None
    outline_summary: str | None = None
    speaker_id: str | None = None
    speaker_b_id: str | None = None
    data_start: float | None = None
    data_duration: float | None = None
    custom_html: str | None = None
    custom_css: str | None = None
    image_prompt: str | None = None

class SceneRead(SceneBase):
    id: str
    scenario_id: str
    index: int
    narration_audio_path: str | None = None
    narration_audio_duration: float | None = None
    data_start: float | None = None
    data_duration: float | None = None
    custom_html: str | None = None
    custom_css: str | None = None
    image_prompt: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SceneReorder(BaseModel):
    new_index: int

class AiDesignAdjustRequest(BaseModel):
    instruction: str
