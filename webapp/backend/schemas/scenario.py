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

class ScenarioSceneItem(BaseModel):
    """LLM が生成するシーン 1 件の構造（新スキーマ・composition.py と直結）。
    LLM 出力の揺れに強いよう index/title/narration_text にもデフォルトを持たせる。"""
    index: int = Field(default=1)
    title: str = Field(default="")
    # composition.py が解釈する値: text_only / section_header / bullet_list /
    #   text_left_image_right / full_image / comparison / chat_dialog / card_panel / table / graph_chart
    layout_type: str = Field(default="text_only")
    # レイアウト別の中身: {bullet_points:[...]} / {left_text,right_text} / {lines:[{speaker,text}]} /
    #   {cards:[{title,text}]} / {headers:[...],rows:[[...]]} / {chart:{type,labels,values,unit}} / {body:"..."}
    slide_content_json: dict = Field(default_factory=dict)
    narration_text: str = Field(default="")

class ScenarioProposal(BaseModel):
    """LLM レスポンスのパース結果 (Route A/B 用)"""
    scenes: list[ScenarioSceneItem]

class ScenarioOutlineItem(BaseModel):
    """チャットのアウトライン段階での 1 シーン（軽量）。LLM 出力の揺れに強いよう全項目にデフォルトを持たせる。"""
    index: int = Field(default=1)
    title: str = Field(default="")
    summary: str = Field(default="")          # このシーンで扱う内容のあらすじ（1〜2文）
    layout_type: str = Field(default="text_only")  # レイアウトの「提案」。確定後シーン側で変更可

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
