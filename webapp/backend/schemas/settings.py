from pydantic import BaseModel

class SettingsSchema(BaseModel):
    local_llm_base_url: str
    local_llm_model: str
    enable_think: bool = False
    qwen3_tts_base_url: str
    tts_request_timeout: int = 1800
    renderer_request_timeout: int = 3600
    default_fps: int
    default_resolution: str
    # レンダリング並列ワーカー数（0 = hyperframes の auto に任せる）
    render_workers: int = 4
    # 分割レンダリングの閾値（秒。0 = 分割しない）
    render_chunk_sec: int = 300
