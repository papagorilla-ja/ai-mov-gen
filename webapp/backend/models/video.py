import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # draft / generating / completed / failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    output_dir: Mapped[str | None] = mapped_column(Text)
    duration_sec: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # リレーション
    project: Mapped["Project"] = relationship("Project", back_populates="videos")
    scenario: Mapped["Scenario | None"] = relationship("Scenario", back_populates="video", uselist=False, cascade="all, delete-orphan")
    style: Mapped["VideoStyle | None"] = relationship("VideoStyle", back_populates="video", uselist=False, cascade="all, delete-orphan")
    generation_history: Mapped[list["GenerationHistory"]] = relationship("GenerationHistory", back_populates="video", cascade="all, delete-orphan")
