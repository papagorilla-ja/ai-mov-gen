import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class VideoStyle(Base):
    __tablename__ = "video_styles"
    __table_args__ = (UniqueConstraint("video_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String, ForeignKey("videos.id"), nullable=False, unique=True)
    template_id: Mapped[str | None] = mapped_column(String, ForeignKey("style_templates.id"))
    color_primary: Mapped[str | None] = mapped_column(String)
    color_secondary: Mapped[str | None] = mapped_column(String)
    color_accent: Mapped[str | None] = mapped_column(String)
    color_bg: Mapped[str | None] = mapped_column(String)
    color_text_primary: Mapped[str | None] = mapped_column(String)
    font_heading: Mapped[str | None] = mapped_column(String)
    font_body: Mapped[str | None] = mapped_column(String)
    # デザイン要素（値の一覧と既定値は services/design_tokens.py が持つ）。
    # 既存動画の見た目を変えないよう、既定値は現行相当の grid / glass / normal / none。
    background_motif: Mapped[str | None] = mapped_column(String)
    decor_style: Mapped[str | None] = mapped_column(String)
    type_scale: Mapped[str | None] = mapped_column(String)
    transition: Mapped[str | None] = mapped_column(String)
    # FIX-22: 1 本の動画で AI に使わせるレイアウトの幅（minimal / standard / rich）。
    # 40 種あっても毎シーン違う図解が出ると、視聴者は毎回「図の読み方」を
    # 学び直すことになる。動画ごとにここで絞る。値の一覧は layouts/_registry.py。
    layout_breadth: Mapped[str | None] = mapped_column(String)
    style_prompt: Mapped[str | None] = mapped_column(Text)
    custom_css: Mapped[str | None] = mapped_column(Text)
    default_speaker_id: Mapped[str | None] = mapped_column(String, ForeignKey("speakers.id"))
    default_speaker_b_id: Mapped[str | None] = mapped_column(String, ForeignKey("speakers.id"))
    bgm_path: Mapped[str | None] = mapped_column(Text)
    bgm_volume: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    # 読み上げ速度の倍率。合成済みの音声に後段で掛ける（値の一覧は design_tokens.py）。
    # TTS のキャッシュより後ろで適用するため、ここを変えても音声の再合成は起きない。
    narration_speed: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    canvas_width: Mapped[int] = mapped_column(Integer, default=1920, nullable=False)
    canvas_height: Mapped[int] = mapped_column(Integer, default=1080, nullable=False)

    # リレーション
    video: Mapped["Video"] = relationship("Video", back_populates="style")
    template: Mapped["StyleTemplate | None"] = relationship("StyleTemplate")
    default_speaker: Mapped["Speaker | None"] = relationship("Speaker", foreign_keys=[default_speaker_id])
    default_speaker_b: Mapped["Speaker | None"] = relationship("Speaker", foreign_keys=[default_speaker_b_id])
