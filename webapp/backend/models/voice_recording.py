import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class VoiceRecording(Base):
    """音声収集セッションで収録した音声（収録音声ライブラリ）。

    セッション完了時にここへ名前付きで保存し、話者の新規追加画面から
    参照音声として選択できるようにする。1つの収録音声を複数の話者に
    使い回せるよう、Speaker とは独立したテーブルにしている。
    """
    __tablename__ = "voice_recordings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # ユーザーが付ける名前（例: 「山田さんの声」）
    name: Mapped[str] = mapped_column(String, nullable=False)
    # 収録音声の保存先（/app/voice_samples/_recordings/{id}.wav）
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    # 収録モード: script（台本読み上げ）/ chat（チャット対話）/ emotion（感情・トーン指定）
    mode: Mapped[str] = mapped_column(String, nullable=False, default="script")
    # 参照音声としての長さ（秒）とテイク数
    duration_sec: Mapped[float | None] = mapped_column(Float)
    take_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
