import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class SceneAsset(Base):
    __tablename__ = "scene_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scene_id: Mapped[str] = mapped_column(String, ForeignKey("scenes.id"), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 / 2 / 3
    # image / video / svg
    asset_type: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    svg_content: Mapped[str | None] = mapped_column(Text)
    # JSON: {offset_sec, duration_sec, x, y, max_width, max_height, border_radius}
    display_config_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # リレーション
    scene: Mapped["Scene"] = relationship("Scene", back_populates="assets")
