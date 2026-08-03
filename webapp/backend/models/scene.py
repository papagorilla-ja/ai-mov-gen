import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_id: Mapped[str] = mapped_column(String, ForeignKey("scenarios.id"), nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    # text_only / text_left_image_right / full_image / comparison / bullet_list / chat_dialog / section_header
    layout_type: Mapped[str] = mapped_column(String, nullable=False, default="text_only")
    # JSON: スライド表示テキスト等 {title, body, bullet_points, ...}
    slide_content_json: Mapped[str | None] = mapped_column(Text)
    narration_text: Mapped[str | None] = mapped_column(Text)
    # チャットのアウトライン段階で決めた「このシーンで扱う内容のあらすじ」。
    # ナレーション本文・スライド内容の深堀り時の起点（意図）として使う。
    outline_summary: Mapped[str | None] = mapped_column(Text)
    narration_audio_path: Mapped[str | None] = mapped_column(Text)
    narration_audio_duration: Mapped[float | None] = mapped_column(Float)
    speaker_id: Mapped[str | None] = mapped_column(String, ForeignKey("speakers.id"))
    speaker_b_id: Mapped[str | None] = mapped_column(String, ForeignKey("speakers.id"))
    # タイムライン計算後に保存
    data_start: Mapped[float | None] = mapped_column(Float)
    data_duration: Mapped[float | None] = mapped_column(Float)
    # AI調整または手動編集によるシーン単位のHTML/CSS上書き（NULL=自動生成のまま）
    custom_html: Mapped[str | None] = mapped_column(Text)
    custom_css: Mapped[str | None] = mapped_column(Text)
    # 外部の画像生成AI（Gemini 等）に貼り付けるためのプロンプト
    image_prompt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # リレーション
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="scenes")
    assets: Mapped[list["SceneAsset"]] = relationship("SceneAsset", back_populates="scene", cascade="all, delete-orphan")
    speaker: Mapped["Speaker | None"] = relationship("Speaker", foreign_keys=[speaker_id])
    speaker_b: Mapped["Speaker | None"] = relationship("Speaker", foreign_keys=[speaker_b_id])
