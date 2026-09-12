from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant" | "system"
    content: str

class ScenarioRead(BaseModel):
    id: str
    video_id: str
    source_type: str
    source_content: str | None = None
    chat_messages: str | None = None   # JSON 文字列
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ScenarioOutlineItem(BaseModel):
    """チャットのアウトライン段階での 1 シーン（軽量）。LLM 出力の揺れに強いよう全項目にデフォルトを持たせる。"""
    index: int = Field(default=1)
    title: str = Field(default="")
    summary: str = Field(default="")          # このシーンで扱う内容のあらすじ（1〜2文）
    # 段階 1 で決めるのは「情報の型」（14 択）。具体的な見せ方は
    # シーン内容の生成時（段階 2）に、実際の件数を見てから決める。
    content_type: str = Field(default="")
    # 後方互換。古いフロントや保存済みデータは見せ方の名前を直接送ってくる。
    layout_type: str = Field(default="")

class ScenarioOutline(BaseModel):
    """チャットのアウトライン LLM レスポンスのパース結果"""
    scenes: list[ScenarioOutlineItem]

class FromTextRequest(BaseModel):
    text: str

class ChatRequest(BaseModel):
    message: str

class FinalizeRequest(BaseModel):
    """チャットのアウトライン確定（スケルトンシーン作成）"""
    scenes: list[ScenarioOutlineItem]

class NarrationGenerateRequest(BaseModel):
    pass

class PptxImportResult(BaseModel):
    """PPTX 取り込み直後のレスポンス（ナレーション生成は非同期ジョブで進行する）"""
    scenario: ScenarioRead
    job_id: str
    slide_count: int
    scene_count: int
    visual_count: int
    warnings: list[str] = Field(default_factory=list)
