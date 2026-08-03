import shutil
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from models.project import Project
from models.video import Video
from models.video_style import VideoStyle
from models.scenario import Scenario
from models.scene import Scene
from models.scene_asset import SceneAsset
from schemas.video import VideoCreate, VideoRead, VideoUpdate
from schemas.style import VideoStyleRead
from services.composition import generate_composition
from core.project_path import get_project_dir_name, get_project_dir

router = APIRouter(tags=["videos"])

PROJECTS_DIR = Path("/app/projects")
TEMPLATES_BLANK_DIR = Path("/app/templates/blank")

@router.get("/projects/{project_id}/videos", response_model=list[VideoRead])
async def list_videos(project_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Video).where(Video.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/projects/{project_id}/videos", response_model=VideoRead, status_code=status.HTTP_201_CREATED)
async def create_video(project_id: str, payload: VideoCreate, db: AsyncSession = Depends(get_db)):
    stmt_p = select(Project).where(Project.id == project_id)
    project = (await db.execute(stmt_p)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")

    video_id = str(uuid.uuid4())
    video_dir = get_project_dir(project) / "videos" / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    (video_dir / "assets/audio").mkdir(parents=True, exist_ok=True)
    (video_dir / "assets/images").mkdir(parents=True, exist_ok=True)
    (video_dir / "output").mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy(TEMPLATES_BLANK_DIR / "style.css", video_dir / "style.css")
        shutil.copy(TEMPLATES_BLANK_DIR / "app.js", video_dir / "app.js")
        shutil.copy(TEMPLATES_BLANK_DIR / "gsap.min.js", video_dir / "gsap.min.js")
        shutil.copy(TEMPLATES_BLANK_DIR / "chart.min.js", video_dir / "chart.min.js")
        shutil.copy(TEMPLATES_BLANK_DIR / "index.html", video_dir / "index.html")
        shutil.copy(TEMPLATES_BLANK_DIR / "meta.json", video_dir / "meta.json")
    except Exception as e:
        print(f"Template files copying failed: {e}")

    video = Video(
        id=video_id,
        project_id=project_id,
        name=payload.name,
        status="draft",
        output_dir=str(video_dir)
    )
    db.add(video)
    
    video_style = VideoStyle(
        video_id=video_id,
    )
    db.add(video_style)

    scenario = Scenario(
        video_id=video_id,
        source_type="paste",
    )
    db.add(scenario)

    await db.flush()
    return video

@router.get("/videos/{video_id}", response_model=VideoRead)
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")
    return video

@router.patch("/videos/{video_id}", response_model=VideoRead)
async def update_video(video_id: str, payload: VideoUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    if payload.name is not None:
        video.name = payload.name
    if payload.status is not None:
        video.status = payload.status
    if payload.duration_sec is not None:
        video.duration_sec = payload.duration_sec

    await db.flush()
    return video

@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    stmt_p = select(Project).where(Project.id == video.project_id)
    project = (await db.execute(stmt_p)).scalars().first()
    if project:
        video_dir = get_project_dir(project) / "videos" / video.id
        if video_dir.exists():
            shutil.rmtree(video_dir)

    await db.delete(video)
    await db.flush()

@router.post("/videos/{video_id}/duplicate", response_model=VideoRead, status_code=status.HTTP_201_CREATED)
async def duplicate_video(video_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Video).where(Video.id == video_id)
    src_video = (await db.execute(stmt)).scalars().first()
    if not src_video:
        raise HTTPException(status_code=404, detail="複製元の動画が見つかりません")

    stmt_p = select(Project).where(Project.id == src_video.project_id)
    project = (await db.execute(stmt_p)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")

    new_video_id = str(uuid.uuid4())
    new_video_dir = get_project_dir(project) / "videos" / new_video_id

    src_dir = get_project_dir(project) / "videos" / video_id
    if src_dir.exists():
        shutil.copytree(src_dir, new_video_dir)
    else:
        new_video_dir.mkdir(parents=True, exist_ok=True)
        (new_video_dir / "assets/audio").mkdir(parents=True, exist_ok=True)
        (new_video_dir / "assets/images").mkdir(parents=True, exist_ok=True)
        (new_video_dir / "output").mkdir(parents=True, exist_ok=True)

    new_video = Video(
        id=new_video_id,
        project_id=src_video.project_id,
        name=f"{src_video.name} - コピー",
        status="draft",
        output_dir=str(new_video_dir),
        duration_sec=src_video.duration_sec
    )
    db.add(new_video)

    stmt_style = select(VideoStyle).where(VideoStyle.video_id == video_id)
    src_style = (await db.execute(stmt_style)).scalars().first()
    if src_style:
        # 項目を1つずつ書き写すとデザイン項目が増えたときにコピー漏れが起きるため、
        # 複製すべきフィールドを一覧で持って回す。
        COPIED_STYLE_FIELDS = (
            "template_id",
            "color_primary", "color_secondary", "color_accent",
            "color_bg", "color_text_primary",
            "font_heading", "font_body",
            "background_motif", "decor_style", "type_scale", "transition",
            "style_prompt", "custom_css",
            "default_speaker_id", "default_speaker_b_id",
            "bgm_path", "bgm_volume",
            "canvas_width", "canvas_height",
        )
        new_style = VideoStyle(video_id=new_video_id)
        for field in COPIED_STYLE_FIELDS:
            setattr(new_style, field, getattr(src_style, field))
        db.add(new_style)

    stmt_scenario = select(Scenario).where(Scenario.video_id == video_id)
    src_scenario = (await db.execute(stmt_scenario)).scalars().first()
    if src_scenario:
        new_scenario = Scenario(
            video_id=new_video_id,
            source_type=src_scenario.source_type,
            source_content=src_scenario.source_content,
            chat_messages=src_scenario.chat_messages
        )
        db.add(new_scenario)
        await db.flush()

        stmt_scenes = select(Scene).where(Scene.scenario_id == src_scenario.id).order_by(Scene.index)
        src_scenes = (await db.execute(stmt_scenes)).scalars().all()
        for s in src_scenes:
            new_scene = Scene(
                scenario_id=new_scenario.id,
                index=s.index,
                title=s.title,
                layout_type=s.layout_type,
                slide_content_json=s.slide_content_json,
                narration_text=s.narration_text,
                narration_audio_path=s.narration_audio_path,
                narration_audio_duration=s.narration_audio_duration,
                speaker_id=s.speaker_id,
                data_start=s.data_start,
                data_duration=s.data_duration
            )
            db.add(new_scene)
            await db.flush()

            stmt_assets = select(SceneAsset).where(SceneAsset.scene_id == s.id)
            src_assets = (await db.execute(stmt_assets)).scalars().all()
            for asset in src_assets:
                new_asset = SceneAsset(
                    scene_id=new_scene.id,
                    slot=asset.slot,
                    asset_type=asset.asset_type,
                    file_path=asset.file_path,
                    svg_content=asset.svg_content,
                    display_config_json=asset.display_config_json
                )
                db.add(new_asset)

    await db.flush()
    return new_video


PROJECTS_DIR_V = Path("/app/projects")

@router.post("/videos/{video_id}/bgm", response_model=VideoStyleRead)
async def upload_bgm(
    video_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """BGM ファイルをアップロードして VideoStyle に保存する。"""
    # 動画 → プロジェクト
    stmt_v = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt_v)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    stmt_p = select(Project).where(Project.id == video.project_id)
    project = (await db.execute(stmt_p)).scalars().first()

    # スタイル取得または作成
    stmt_s = select(VideoStyle).where(VideoStyle.video_id == video_id)
    style = (await db.execute(stmt_s)).scalars().first()
    if not style:
        style = VideoStyle(video_id=video_id)
        db.add(style)
        await db.flush()

    # 旧 BGM ファイルを削除
    if style.bgm_path and Path(style.bgm_path).exists():
        Path(style.bgm_path).unlink(missing_ok=True)

    # 新ファイルを保存
    ext = Path(file.filename or "bgm.mp3").suffix.lower() or ".mp3"
    bgm_dir = get_project_dir(project) / "videos" / video_id / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    dest = bgm_dir / f"bgm{ext}"
    dest.write_bytes(await file.read())

    style.bgm_path = str(dest)
    await db.flush()
    return style


@router.delete("/videos/{video_id}/bgm", response_model=VideoStyleRead)
async def delete_bgm(video_id: str, db: AsyncSession = Depends(get_db)):
    """BGM を削除する。"""
    stmt_s = select(VideoStyle).where(VideoStyle.video_id == video_id)
    style = (await db.execute(stmt_s)).scalars().first()
    if not style:
        raise HTTPException(status_code=404, detail="スタイルが見つかりません")

    if style.bgm_path and Path(style.bgm_path).exists():
        Path(style.bgm_path).unlink(missing_ok=True)

    style.bgm_path = None
    await db.flush()
    return style


@router.post("/videos/{video_id}/preview")
async def generate_slide_preview(video_id: str, db: AsyncSession = Depends(get_db)):
    """スライド HTML プレビューを生成してアクセス URL を返す。

    TTS 合成・動画レンダリングは行わない。
    音声ファイルが未生成の場合でも HTML は正常に出力される。
    """
    stmt_v = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt_v)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    stmt_p = select(Project).where(Project.id == video.project_id)
    project = (await db.execute(stmt_p)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")

    stmt_style = select(VideoStyle).where(VideoStyle.video_id == video_id)
    style = (await db.execute(stmt_style)).scalars().first()
    if not style:
        style = VideoStyle(video_id=video_id)

    stmt_scenario = select(Scenario).where(Scenario.video_id == video_id)
    scenario = (await db.execute(stmt_scenario)).scalars().first()
    if not scenario:
        raise HTTPException(status_code=400, detail="シナリオがまだ作成されていません")

    stmt_scenes = select(Scene).where(Scene.scenario_id == scenario.id).order_by(Scene.index)
    scenes = list((await db.execute(stmt_scenes)).scalars().all())
    if not scenes:
        raise HTTPException(status_code=400, detail="シーンがありません")

    video_dir = get_project_dir(project) / "videos" / video.id
    video_dir.mkdir(parents=True, exist_ok=True)

    stmt_assets = select(SceneAsset).where(
        SceneAsset.scene_id.in_([s.id for s in scenes])
    )
    all_assets = (await db.execute(stmt_assets)).scalars().all()
    assets_map: dict = {}
    for a in all_assets:
        assets_map.setdefault(a.scene_id, []).append(a)

    generate_composition(video, scenes, style, TEMPLATES_BLANK_DIR, video_dir, assets_map)

    # preview=1 … 再生コントロール付きのダッシュボードUIを表示させるフラグ。
    #             付けない場合はレンダリングと同じ「素のステージ」表示になる。
    # t=…       … iframe のキャッシュ回避（呼び出し側で付け足さなくて済むようにする）
    preview_url = (
        f"/projects/{get_project_dir_name(project)}/videos/{video.id}/index.html"
        f"?preview=1&t={int(time.time() * 1000)}"
    )
    return {"preview_url": preview_url}
