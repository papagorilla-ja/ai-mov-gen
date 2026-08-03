import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class StyleTemplate(Base):
    __tablename__ = "style_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    preview_image_path: Mapped[str | None] = mapped_column(Text)
    base_css: Mapped[str] = mapped_column(Text, nullable=False)
    color_primary: Mapped[str] = mapped_column(String, nullable=False, default="#6366f1")
    color_secondary: Mapped[str] = mapped_column(String, nullable=False, default="#8b5cf6")
    color_accent: Mapped[str] = mapped_column(String, nullable=False, default="#22d3ee")
    color_bg: Mapped[str] = mapped_column(String, nullable=False, default="#0f0f1a")
    color_text_primary: Mapped[str] = mapped_column(String, nullable=False, default="#f8fafc")
    font_heading: Mapped[str] = mapped_column(String, nullable=False, default="BIZ UDPGothic")
    font_body: Mapped[str] = mapped_column(String, nullable=False, default="BIZ UDPGothic")
    # 配色だけでなく背景・質感・組版まで運ばせる。ここが色しか持たないと
    # 「テンプレートを選んでも背景と質感が既定のまま」になり、選択制の意味が失われる。
    background_motif: Mapped[str] = mapped_column(String, nullable=False, default="grid")
    decor_style: Mapped[str] = mapped_column(String, nullable=False, default="glass")
    type_scale: Mapped[str] = mapped_column(String, nullable=False, default="normal")
    transition: Mapped[str] = mapped_column(String, nullable=False, default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
