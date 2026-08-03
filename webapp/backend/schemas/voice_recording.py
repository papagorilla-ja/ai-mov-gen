from datetime import datetime
from pydantic import BaseModel, ConfigDict


class VoiceRecordingRead(BaseModel):
    """収録音声ライブラリの1件。"""
    id: str
    name: str
    file_path: str
    mode: str
    duration_sec: float | None = None
    take_count: int
    created_at: datetime
    # 試聴用 URL（API 側で組み立てて返す）
    audio_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VoiceRecordingUpdate(BaseModel):
    name: str


class SessionStartRequest(BaseModel):
    """収録セッションの開始条件。"""
    mode: str = "script"
    item_count: int = 5


class SessionFinalizeRequest(BaseModel):
    """収録音声ライブラリへ保存するときの情報。"""
    name: str


class UseRecordingRequest(BaseModel):
    """収録音声を話者の参照音声として採用する。"""
    speaker_id: str
    recording_id: str
