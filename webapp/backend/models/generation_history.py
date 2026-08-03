import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class GenerationHistory(Base):
    __tablename__ = "generation_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String, ForeignKey("videos.id"), nullable=False)
    output_path: Mapped[str | None] = mapped_column(Text)
    # running / completed / failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    log_text: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_sec: Mapped[float | None] = mapped_column(Float)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    thumbnail_path: Mapped[str | None] = mapped_column(Text)

    # リレーション
    video: Mapped["Video"] = relationship("Video", back_populates="generation_history")
