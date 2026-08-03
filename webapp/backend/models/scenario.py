import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("video_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String, ForeignKey("videos.id"), nullable=False, unique=True)
    # pptx / paste / chat
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_content: Mapped[str | None] = mapped_column(Text)
    # JSON 文字列: チャット履歴 [{role, content}, ...]
    chat_messages: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # リレーション
    video: Mapped["Video"] = relationship("Video", back_populates="scenario")
    scenes: Mapped[list["Scene"]] = relationship("Scene", back_populates="scenario", order_by="Scene.index", cascade="all, delete-orphan")
