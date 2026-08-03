from pydantic import BaseModel, ConfigDict
from datetime import datetime

class DisplayConfig(BaseModel):
    offset_sec: float = 0.5
    duration_sec: float | None = None
    x: str = "center"
    y: str = "center"
    max_width: str = "600px"
    max_height: str = "500px"
    border_radius: str = "16px"

class DisplayConfigUpdate(BaseModel):
    offset_sec: float | None = None
    duration_sec: float | None = None
    x: str | None = None
    y: str | None = None
    max_width: str | None = None
    max_height: str | None = None
    border_radius: str | None = None

class SceneAssetRead(BaseModel):
    id: str
    scene_id: str
    slot: int
    asset_type: str
    file_path: str | None = None
    svg_content: str | None = None
    display_config_json: str | None = None
    url: str | None = None

    model_config = ConfigDict(from_attributes=True)
