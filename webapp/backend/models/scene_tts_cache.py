"""シーン TTS キャッシュ — ナレーション音声の再利用判定に使用する"""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class SceneTtsCache(Base):
    __tablename__ = "scene_tts_cache"

    # シーン ID を PK とする（1 シーン = 1 キャッシュエントリ）
    scene_id: Mapped[str] = mapped_column(String, ForeignKey("scenes.id", ondelete="CASCADE"), primary_key=True)
    # ハッシュ入力: narration_text + speaker_id + reference_audio_path を結合した MD5
    narration_hash: Mapped[str] = mapped_column(String, nullable=False)
    # 生成済み WAV ファイルの絶対パス
    audio_path: Mapped[str] = mapped_column(Text, nullable=False)
