"""SQLAlchemy async エンジン + セッション管理"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

_IS_SQLITE = settings.database_url.startswith("sqlite")

# SQLite のロック競合時に待機する秒数。
# 動画生成はバックグラウンドタスクが数分にわたって書き込みを続けるため、
# その間に届いた API リクエストと衝突しやすい。既定の busy_timeout は 0 で、
# 競合すると待たずに即座に "database is locked" を返してしまう。
SQLITE_BUSY_TIMEOUT_SEC = 30

# aiosqlite は connect_args の timeout をそのまま sqlite3.connect に渡すため、
# これだけで busy_timeout が設定される（PRAGMA より確実に効く経路）。
_connect_args = {"timeout": float(SQLITE_BUSY_TIMEOUT_SEC)} if _IS_SQLITE else {}

engine = create_async_engine(settings.database_url, echo=False, connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


if _IS_SQLITE:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        """接続ごとに SQLite のロック挙動を調整する。"""
        cursor = dbapi_conn.cursor()
        try:
            # connect_args と同じ値を PRAGMA でも明示しておく（多重の保険）
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_SEC * 1000}")
            # WAL にすると読み取りが書き込みにブロックされなくなる。
            # Docker のバインドマウント上では有効化できないことがあるが、
            # その場合も busy_timeout だけで競合は緩和されるため続行する。
            cursor.execute("PRAGMA journal_mode=WAL")
        except Exception as e:
            print(f"[db] SQLite PRAGMA の設定に失敗しました（既定値で続行）: {e}")
        finally:
            cursor.close()


class Base(DeclarativeBase):
    """全モデルの基底クラス"""
    pass


from sqlalchemy import text

async def init_db():
    """起動時に全テーブルを作成 (存在しない場合のみ)"""
    # models パッケージをインポートしてテーブル定義を登録
    import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 既存テーブルへの新規カラム追加（冪等）
        for stmt in [
            "ALTER TABLE speakers ADD COLUMN avatar_path TEXT",
            "ALTER TABLE generation_history ADD COLUMN thumbnail_path TEXT",
            "ALTER TABLE video_styles ADD COLUMN bgm_path TEXT",
            "ALTER TABLE video_styles ADD COLUMN bgm_volume REAL DEFAULT 0.3",
            "ALTER TABLE scenes ADD COLUMN speaker_b_id TEXT REFERENCES speakers(id)",
            "ALTER TABLE video_styles ADD COLUMN default_speaker_b_id TEXT REFERENCES speakers(id)",
            "ALTER TABLE video_styles ADD COLUMN canvas_width INTEGER DEFAULT 1920",
            "ALTER TABLE video_styles ADD COLUMN canvas_height INTEGER DEFAULT 1080",
            "ALTER TABLE scenes ADD COLUMN custom_html TEXT",
            "ALTER TABLE scenes ADD COLUMN custom_css TEXT",
            "ALTER TABLE scenes ADD COLUMN outline_summary TEXT",
            "ALTER TABLE scenes ADD COLUMN image_prompt TEXT",
            # FIX-21: デザイン要素。既存動画の見た目を変えないよう現行相当を既定値にする
            "ALTER TABLE video_styles ADD COLUMN background_motif TEXT",
            "ALTER TABLE video_styles ADD COLUMN decor_style TEXT",
            "ALTER TABLE video_styles ADD COLUMN type_scale TEXT",
            "ALTER TABLE video_styles ADD COLUMN transition TEXT",
            "ALTER TABLE style_templates ADD COLUMN background_motif TEXT NOT NULL DEFAULT 'grid'",
            "ALTER TABLE style_templates ADD COLUMN decor_style TEXT NOT NULL DEFAULT 'glass'",
            "ALTER TABLE style_templates ADD COLUMN type_scale TEXT NOT NULL DEFAULT 'normal'",
            "ALTER TABLE style_templates ADD COLUMN transition TEXT NOT NULL DEFAULT 'none'",
        ]:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # カラムが既に存在する場合は無視

        # app_settings テーブルの作成（冪等 — 既に存在する場合は何もしない）
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        ))


async def get_db():
    """FastAPI Depends 用セッションジェネレータ"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
