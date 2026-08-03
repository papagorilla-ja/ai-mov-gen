import shutil
import io
import json
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from core.database import get_db
from models.project import Project
from models.video import Video
from models.video_style import VideoStyle
from models.scenario import Scenario
from models.scene import Scene
from models.scene_asset import SceneAsset
from schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

PROJECTS_DIR = Path("/app/projects")

@router.get("", response_model=list[ProjectRead])
async def list_projects(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Project, func.count(Video.id).label("video_count"))
        .outerjoin(Project.videos)
        .group_by(Project.id)
    )
    result = await db.execute(stmt)
    projects_with_counts = []
    for row in result:
        proj, count = row
        read_obj = ProjectRead.model_validate(proj)
        read_obj.video_count = count
        projects_with_counts.append(read_obj)
    return projects_with_counts

@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.name == payload.name)
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="同名のプロジェクトが既に存在します")

    proj = Project(name=payload.name, description=payload.description)
    db.add(proj)
    await db.flush()

    # ディレクトリ作成
    proj_dir = PROJECTS_DIR / proj.name
    proj_dir.mkdir(parents=True, exist_ok=True)

    read_obj = ProjectRead.model_validate(proj)
    read_obj.video_count = 0
    return read_obj

@router.post("/import", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def import_project(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """ZIP ファイルからプロジェクトをインポートする。新しい ID でレコードを再作成する。"""
    content = await file.read()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            zf.extractall(tmp_dir)

        manifest_path = Path(tmp_dir) / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(status_code=400, detail="無効な ZIP ファイルです (manifest.json が見つかりません)")

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        if manifest.get("app") not in ("AI-MovGen", "HyperFrames"):
            raise HTTPException(status_code=400, detail="AI-MovGen のエクスポートファイルではありません")

        old_project = manifest["project"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_project_name = f"{old_project['name']}_import_{timestamp}"

        # ID マッピング: {旧ID: 新ID}
        id_map: dict[str, str] = {}

        # プロジェクト作成
        new_project_id = str(uuid.uuid4())
        id_map[old_project["id"]] = new_project_id
        new_project = Project(
            id=new_project_id,
            name=new_project_name,
            description=old_project.get("description"),
        )
        db.add(new_project)

        # 各動画を再作成
        for vid_export in manifest.get("videos", []):
            old_vid = vid_export["video"]
            new_vid_id = str(uuid.uuid4())
            id_map[old_vid["id"]] = new_vid_id

            new_video = Video(
                id=new_vid_id,
                project_id=new_project_id,
                name=old_vid["name"],
                status="draft",
            )
            db.add(new_video)

            # VideoStyle
            style_data = vid_export.get("style")
            if style_data:
                new_style = VideoStyle(
                    video_id=new_vid_id,
                    template_id=style_data.get("template_id"),
                    color_primary=style_data.get("color_primary"),
                    color_secondary=style_data.get("color_secondary"),
                    color_accent=style_data.get("color_accent"),
                    color_bg=style_data.get("color_bg"),
                    color_text_primary=style_data.get("color_text_primary"),
                    font_heading=style_data.get("font_heading"),
                    font_body=style_data.get("font_body"),
                    default_speaker_id=style_data.get("default_speaker_id"),
                )
                db.add(new_style)

            # Scenario
            sc_data = vid_export.get("scenario")
            new_sc_id = str(uuid.uuid4())
            new_scenario = Scenario(
                id=new_sc_id,
                video_id=new_vid_id,
                source_type=(sc_data or {}).get("source_type", "paste"),
            )
            db.add(new_scenario)

            # Scenes + Assets
            new_vid_dir = PROJECTS_DIR / new_project_name / "videos" / new_vid_id
            new_vid_dir.mkdir(parents=True, exist_ok=True)

            for scene_export in vid_export.get("scenes", []):
                new_scene_id = str(uuid.uuid4())
                id_map[scene_export["id"]] = new_scene_id

                new_scene = Scene(
                    id=new_scene_id,
                    scenario_id=new_sc_id,
                    index=scene_export["index"],
                    title=scene_export.get("title"),
                    layout_type=scene_export.get("layout_type", "text_only"),
                    slide_content_json=scene_export.get("slide_content_json"),
                    narration_text=scene_export.get("narration_text"),
                    speaker_id=scene_export.get("speaker_id"),
                    # 音声パスはリセット（次回生成時に再合成される）
                    narration_audio_path=None,
                    narration_audio_duration=None,
                )
                db.add(new_scene)

                # SceneAsset
                for asset_export in scene_export.get("assets", []):
                    new_asset_id = str(uuid.uuid4())
                    new_file_path = None

                    if asset_export.get("file_path"):
                        old_vid_id = old_vid["id"]
                        src = Path(tmp_dir) / "files" / old_vid_id / asset_export["file_path"]
                        if src.exists():
                            dst = new_vid_dir / asset_export["file_path"]
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(src), str(dst))
                            new_file_path = asset_export["file_path"]

                    new_asset = SceneAsset(
                        id=new_asset_id,
                        scene_id=new_scene_id,
                        slot=asset_export["slot"],
                        asset_type=asset_export["asset_type"],
                        file_path=new_file_path,
                        svg_content=asset_export.get("svg_content"),
                        display_config_json=asset_export.get("display_config_json"),
                    )
                    db.add(new_asset)

        await db.flush()

        stmt_result = select(Project).where(Project.id == new_project_id)
        result = (await db.execute(stmt_result)).scalars().first()
        return result


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    proj = (await db.execute(stmt)).scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")

    count_stmt = select(func.count(Video.id)).where(Video.project_id == project_id)
    video_count = (await db.execute(count_stmt)).scalar() or 0

    read_obj = ProjectRead.model_validate(proj)
    read_obj.video_count = video_count
    return read_obj

@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    proj = (await db.execute(stmt)).scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")

    old_name = proj.name
    if payload.name is not None and payload.name != proj.name:
        stmt_check = select(Project).where(Project.name == payload.name)
        existing = (await db.execute(stmt_check)).scalars().first()
        if existing:
            raise HTTPException(status_code=400, detail="同名のプロジェクトが既に存在します")
        
        old_dir = PROJECTS_DIR / old_name
        new_dir = PROJECTS_DIR / payload.name
        if old_dir.exists():
            old_dir.rename(new_dir)
        else:
            new_dir.mkdir(parents=True, exist_ok=True)
        proj.name = payload.name

    if payload.description is not None:
        proj.description = payload.description

    await db.flush()

    count_stmt = select(func.count(Video.id)).where(Video.project_id == project_id)
    video_count = (await db.execute(count_stmt)).scalar() or 0

    read_obj = ProjectRead.model_validate(proj)
    read_obj.video_count = video_count
    return read_obj

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    proj = (await db.execute(stmt)).scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")

    proj_dir = PROJECTS_DIR / proj.name
    if proj_dir.exists():
        shutil.rmtree(proj_dir)

    await db.delete(proj)
    await db.flush()


@router.get("/{project_id}/export")
async def export_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """プロジェクトを ZIP ファイルとしてエクスポートする。
    DB レコード（JSON）+ シーンアセットファイルを含む。音声・生成済み MP4 は含まない。"""

    # プロジェクト取得
    stmt_p = select(Project).where(Project.id == project_id)
    project = (await db.execute(stmt_p)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")

    # 動画一覧
    stmt_v = select(Video).where(Video.project_id == project_id)
    videos = (await db.execute(stmt_v)).scalars().all()

    # 各動画に紐づくデータを収集
    export_videos = []
    for video in videos:
        stmt_sty = select(VideoStyle).where(VideoStyle.video_id == video.id)
        style = (await db.execute(stmt_sty)).scalars().first()

        stmt_sc = select(Scenario).where(Scenario.video_id == video.id)
        scenario = (await db.execute(stmt_sc)).scalars().first()

        scenes_data = []
        if scenario:
            stmt_scenes = (
                select(Scene)
                .where(Scene.scenario_id == scenario.id)
                .order_by(Scene.index)
            )
            scenes = (await db.execute(stmt_scenes)).scalars().all()
            for scene in scenes:
                stmt_assets = select(SceneAsset).where(SceneAsset.scene_id == scene.id)
                assets = (await db.execute(stmt_assets)).scalars().all()
                scenes_data.append({
                    "id": scene.id,
                    "index": scene.index,
                    "title": scene.title,
                    "layout_type": scene.layout_type,
                    "slide_content_json": scene.slide_content_json,
                    "narration_text": scene.narration_text,
                    "speaker_id": scene.speaker_id,
                    "assets": [
                        {
                            "id": a.id,
                            "slot": a.slot,
                            "asset_type": a.asset_type,
                            "file_path": a.file_path,      # video_dir 相対パス
                            "svg_content": a.svg_content,
                            "display_config_json": a.display_config_json,
                        }
                        for a in assets
                    ],
                })

        export_videos.append({
            "video": {
                "id": video.id,
                "name": video.name,
            },
            "style": {
                "template_id": style.template_id if style else None,
                "color_primary": style.color_primary if style else None,
                "color_secondary": style.color_secondary if style else None,
                "color_accent": style.color_accent if style else None,
                "color_bg": style.color_bg if style else None,
                "color_text_primary": style.color_text_primary if style else None,
                "font_heading": style.font_heading if style else None,
                "font_body": style.font_body if style else None,
                "default_speaker_id": style.default_speaker_id if style else None,
            } if style else None,
            "scenario": {
                "source_type": scenario.source_type if scenario else "paste",
            } if scenario else None,
            "scenes": scenes_data,
        })

    manifest = {
        "version": "1.0",
        "app": "AI-MovGen",
        "exported_at": datetime.now().isoformat(),
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
        },
        "videos": export_videos,
    }

    # ZIP を in-memory で構築
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        # アセットファイルを追加
        for vid_export in export_videos:
            vid_id = vid_export["video"]["id"]
            vid_dir = PROJECTS_DIR / project.name / "videos" / vid_id

            for scene_export in vid_export["scenes"]:
                for asset_export in scene_export["assets"]:
                    file_rel = asset_export.get("file_path")
                    if file_rel:
                        abs_path = vid_dir / file_rel
                        if abs_path.exists():
                            # ZIP 内パス: files/{video_id}/{file_rel}
                            zf.write(str(abs_path), f"files/{vid_id}/{file_rel}")

    buf.seek(0)
    filename = f"project_{project.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
