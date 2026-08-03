"""
AI-MovGen — FastAPI バックエンド

エントリポイント。ルーターのインポートと DB 初期化を担う。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import init_db

from routers import projects, videos, scenes, speakers, styles, settings_router, scenario, assets
from routers.generation import router as generation, ws_router

async def seed_data():
    from core.database import AsyncSessionLocal
    from models.speaker import Speaker
    from models.style_template import StyleTemplate
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as session:
        stmt_sp = select(Speaker).limit(1)
        has_speaker = (await session.execute(stmt_sp)).scalars().first()
        if not has_speaker:
            default_sp = Speaker(
                name="デフォルト話者 (ja)",
                description="システム標準話者。クリアな日本語音声。",
                reference_audio_path="/app/voice_samples/default/reference.wav",
                language="ja",
                is_system=True,
                avatar_path="avatar_01.jpg",
            )
            session.add(default_sp)
        else:
            # 既存のシステム話者にアバターが未設定・または旧svgの場合はjpgへ更新する
            if not has_speaker.avatar_path or has_speaker.avatar_path.endswith(".svg"):
                has_speaker.avatar_path = "avatar_01.jpg"

        from pathlib import Path
        css_content = ""
        css_path = Path("/app/templates/blank/style.css")
        if css_path.exists():
            css_content = css_path.read_text(encoding="utf-8")

        # スタイルプリセット。配色だけでなく背景モチーフ・装飾スタイル・組版・
        # 切替演出まで一式を運ぶ。「テンプレートを選べば1クリックで別世界の動画」に
        # なるよう、組み合わせが被らないように設計している。
        SYSTEM_TEMPLATES = [
            {
                "name": "Corporate Dark",
                "color_primary": "#6366f1", "color_secondary": "#8b5cf6", "color_accent": "#22d3ee",
                "color_bg": "#0f0f1a", "color_text_primary": "#f8fafc",
                "font_heading": "BIZ UDPGothic", "font_body": "BIZ UDPGothic",
                "background_motif": "grid", "decor_style": "glass",
                "type_scale": "normal", "transition": "none",
            },
            {
                "name": "Clean Light",
                "color_primary": "#2563eb", "color_secondary": "#7c3aed", "color_accent": "#0891b2",
                "color_bg": "#ffffff", "color_text_primary": "#1e293b",
                "font_heading": "BIZ UDPGothic", "font_body": "BIZ UDPGothic",
                "background_motif": "dots", "decor_style": "flat",
                "type_scale": "normal", "transition": "fade",
            },
            {
                "name": "Vibrant Modern",
                "color_primary": "#f97316", "color_secondary": "#ec4899", "color_accent": "#a855f7",
                "color_bg": "#18181b", "color_text_primary": "#fafafa",
                "font_heading": "YuGothic", "font_body": "BIZ UDPGothic",
                "background_motif": "mesh", "decor_style": "solid",
                "type_scale": "normal", "transition": "zoom",
            },
            {
                "name": "Minimal White",
                "color_primary": "#111827", "color_secondary": "#374151", "color_accent": "#6b7280",
                "color_bg": "#f9fafb", "color_text_primary": "#111827",
                "font_heading": "YuGothic", "font_body": "YuGothic",
                "background_motif": "plain", "decor_style": "outline",
                "type_scale": "relaxed", "transition": "fade",
            },
            {
                "name": "Warm Document",
                "color_primary": "#b45309", "color_secondary": "#a16207", "color_accent": "#0f766e",
                "color_bg": "#faf6ef", "color_text_primary": "#292524",
                "font_heading": "Hiragino Mincho ProN", "font_body": "BIZ UDPGothic",
                "background_motif": "noise", "decor_style": "flat",
                "type_scale": "relaxed", "transition": "fade",
            },
            {
                "name": "Deep Ocean",
                "color_primary": "#0ea5e9", "color_secondary": "#2563eb", "color_accent": "#5eead4",
                "color_bg": "#08192b", "color_text_primary": "#e8f4fb",
                "font_heading": "BIZ UDPGothic", "font_body": "BIZ UDPGothic",
                "background_motif": "waves", "decor_style": "glass",
                "type_scale": "normal", "transition": "slide",
            },
            {
                "name": "Mono Editorial",
                "color_primary": "#1c1917", "color_secondary": "#57534e", "color_accent": "#b91c1c",
                "color_bg": "#fafaf9", "color_text_primary": "#1c1917",
                "font_heading": "Toppan Bunkyu Midashi Mincho", "font_body": "YuMincho",
                "background_motif": "plain", "decor_style": "outline",
                "type_scale": "relaxed", "transition": "wipe",
            },
            {
                "name": "Friendly Campus",
                "color_primary": "#16a34a", "color_secondary": "#65a30d", "color_accent": "#f59e0b",
                "color_bg": "#f7fdf8", "color_text_primary": "#14532d",
                "font_heading": "Klee", "font_body": "Hiragino Maru Gothic ProN",
                "background_motif": "mesh", "decor_style": "flat",
                "type_scale": "normal", "transition": "fade",
            },
        ]

        # システムテンプレートは毎起動で上書きする。
        # 「既に同名があればスキップ」にしていた頃は、定義を直しても既存 DB に
        # 反映されず、古い配色のレコードが永久に残り続けていた。
        for tpl_data in SYSTEM_TEMPLATES:
            stmt_tpl = select(StyleTemplate).where(StyleTemplate.name == tpl_data["name"])
            tpl = (await session.execute(stmt_tpl)).scalars().first()
            if tpl is None:
                tpl = StyleTemplate(name=tpl_data["name"])
                session.add(tpl)
            tpl.is_system = True
            tpl.base_css = css_content
            for field, value in tpl_data.items():
                if field != "name":
                    setattr(tpl, field, value)
        await session.commit()

async def _apply_saved_settings() -> None:
    """起動時に app_settings テーブルから設定を読み込んで core.config.settings に反映する。"""
    from sqlalchemy import text
    from core.config import settings as app_settings
    from core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT key, value FROM app_settings"))
            rows = result.fetchall()
            for key, value in rows:
                if not value:
                    continue
                if key == "local_llm_base_url":
                    app_settings.local_llm_base_url = value
                elif key == "local_llm_model":
                    app_settings.local_llm_model = value
                elif key == "enable_think":
                    app_settings.enable_think = value.lower() == "true"
                elif key == "qwen3_tts_base_url":
                    app_settings.qwen3_tts_base_url = value
                elif key == "tts_request_timeout":
                    app_settings.tts_request_timeout = int(value)
                elif key == "tts_max_chunk_chars":
                    app_settings.tts_max_chunk_chars = int(value)
                elif key == "tts_batch_size":
                    app_settings.tts_batch_size = int(value)
                elif key == "tts_chunk_gap_sec":
                    app_settings.tts_chunk_gap_sec = float(value)
                elif key == "renderer_request_timeout":
                    app_settings.renderer_request_timeout = int(value)
                elif key == "default_fps":
                    app_settings.default_fps = int(value)
                elif key == "default_resolution":
                    app_settings.default_resolution = value
                elif key == "render_workers":
                    app_settings.render_workers = int(value)
                elif key == "render_chunk_sec":
                    app_settings.render_chunk_sec = int(value)
        print("[startup] DB から設定を読み込みました")
    except Exception as e:
        print(f"[startup] 設定の読み込みに失敗しました（デフォルト値を使用）: {e}")

async def _recover_stuck_generations() -> None:
    """サーバー起動時、中途半端に残存している generating / running タスクを failed に更新して復旧する。"""
    try:
        from core.database import AsyncSessionLocal
        from models.video import Video
        from models.generation_history import GenerationHistory
        from datetime import datetime
        from sqlalchemy.future import select

        async with AsyncSessionLocal() as session:
            stmt_hist = select(GenerationHistory).where(GenerationHistory.status == "running")
            histories = (await session.execute(stmt_hist)).scalars().all()
            for h in histories:
                h.status = "failed"
                h.error_message = "サーバー再起動により生成処理が中断されました"
                h.completed_at = datetime.now()

            stmt_video = select(Video).where(Video.status == "generating")
            videos = (await session.execute(stmt_video)).scalars().all()
            for v in videos:
                v.status = "failed"

            if histories or videos:
                await session.commit()
                print(f"[startup] スタックした生成タスクを復旧しました: {len(histories)} 件の履歴, {len(videos)} 件の動画")
    except Exception as e:
        print(f"[startup] 生成タスクの復旧中にエラーが発生しました: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時: DB 初期化 / 終了時: クリーンアップ"""
    await init_db()
    await seed_data()
    await _apply_saved_settings()
    await _recover_stuck_generations()
    yield


app = FastAPI(
    title="AI-MovGen API",
    description="AI-MovGen 動画作成 Web アプリのバックエンド API",
    version="0.1.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── ルーター登録 ─────────────────────────────────────────
app.include_router(projects,        prefix="/api/v1")
app.include_router(videos,          prefix="/api/v1")
app.include_router(scenes,          prefix="/api/v1")
app.include_router(speakers,        prefix="/api/v1")
app.include_router(styles,          prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(scenario,        prefix="/api/v1")
app.include_router(assets,          prefix="/api/v1")
app.include_router(generation,        prefix="/api/v1")
app.include_router(ws_router)

app.mount("/projects", StaticFiles(directory="/app/projects"), name="projects")

from pathlib import Path
# アバター等の静的アセット
_static_dir = Path("/app/static")
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")



# ─── ヘルスチェック (docker-compose の condition: service_healthy で使用) ──
@app.get("/api/health")
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "database": settings.database_url,
    }


# ─── ルート ───────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "AI-MovGen API — /docs でSwagger UIを確認できます"}
