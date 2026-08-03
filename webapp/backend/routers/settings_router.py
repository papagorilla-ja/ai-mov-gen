from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
from core.config import settings
from schemas.settings import SettingsSchema

router = APIRouter(prefix="/settings", tags=["settings"])


async def _db_load(db: AsyncSession) -> dict[str, str]:
    """app_settings テーブルからすべての設定を辞書として返す。"""
    result = await db.execute(text("SELECT key, value FROM app_settings"))
    return {row[0]: row[1] for row in result.fetchall()}


async def _db_save(db: AsyncSession, key: str, value: str) -> None:
    """キーバリューを upsert（INSERT OR REPLACE）する。"""
    await db.execute(
        text("INSERT OR REPLACE INTO app_settings (key, value) VALUES (:key, :value)"),
        {"key": key, "value": value},
    )


def _build_schema(db_values: dict[str, str]) -> SettingsSchema:
    """DB値とインメモリ settings のデフォルトをマージして SettingsSchema を返す。"""
    raw_think = db_values.get("enable_think")
    enable_think = raw_think.lower() == "true" if raw_think is not None else settings.enable_think
    return SettingsSchema(
        local_llm_base_url=db_values.get("local_llm_base_url", settings.local_llm_base_url),
        local_llm_model=db_values.get("local_llm_model", settings.local_llm_model),
        enable_think=enable_think,
        qwen3_tts_base_url=db_values.get("qwen3_tts_base_url", settings.qwen3_tts_base_url),
        tts_request_timeout=int(db_values.get("tts_request_timeout", str(settings.tts_request_timeout))),
        renderer_request_timeout=int(db_values.get("renderer_request_timeout", str(settings.renderer_request_timeout))),
        default_fps=int(db_values.get("default_fps", str(settings.default_fps))),
        default_resolution=db_values.get("default_resolution", settings.default_resolution),
        render_workers=int(db_values.get("render_workers", str(settings.render_workers))),
        render_chunk_sec=int(db_values.get("render_chunk_sec", str(settings.render_chunk_sec))),
    )


@router.get("", response_model=SettingsSchema)
async def get_settings(db: AsyncSession = Depends(get_db)):
    db_values = await _db_load(db)
    return _build_schema(db_values)


@router.patch("", response_model=SettingsSchema)
async def update_settings(payload: SettingsSchema, db: AsyncSession = Depends(get_db)):
    # DB に永続化
    await _db_save(db, "local_llm_base_url", payload.local_llm_base_url)
    await _db_save(db, "local_llm_model", payload.local_llm_model)
    await _db_save(db, "enable_think", str(payload.enable_think).lower())
    await _db_save(db, "qwen3_tts_base_url", payload.qwen3_tts_base_url)
    await _db_save(db, "tts_request_timeout", str(payload.tts_request_timeout))
    await _db_save(db, "renderer_request_timeout", str(payload.renderer_request_timeout))
    await _db_save(db, "default_fps", str(payload.default_fps))
    await _db_save(db, "default_resolution", payload.default_resolution)
    await _db_save(db, "render_workers", str(payload.render_workers))
    await _db_save(db, "render_chunk_sec", str(payload.render_chunk_sec))

    # 再起動なしでも有効になるよう、インメモリの settings にも即時反映
    settings.local_llm_base_url = payload.local_llm_base_url
    settings.local_llm_model = payload.local_llm_model
    settings.enable_think = payload.enable_think
    settings.qwen3_tts_base_url = payload.qwen3_tts_base_url
    settings.tts_request_timeout = payload.tts_request_timeout
    settings.renderer_request_timeout = payload.renderer_request_timeout
    settings.default_fps = payload.default_fps
    settings.default_resolution = payload.default_resolution
    settings.render_workers = payload.render_workers
    settings.render_chunk_sec = payload.render_chunk_sec

    return payload
