import json
import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from models.scene import Scene
from models.scenario import Scenario
from models.video import Video
from models.project import Project
from models.scene_asset import SceneAsset
from schemas.asset import SceneAssetRead, DisplayConfigUpdate
from core.project_path import get_project_dir_name, get_project_dir

router = APIRouter(tags=["assets"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".webm"}

@router.post("/scenes/{scene_id}/assets/{slot}", response_model=SceneAssetRead, status_code=201)
async def upload_asset(
    scene_id: str,
    slot: int,
    file: UploadFile | None = File(None),
    asset_type: str = Form("image"),
    svg_content: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    # 1. シーン取得
    stmt = (
        select(Scene, Scenario, Video, Project)
        .join(Scenario, Scene.scenario_id == Scenario.id)
        .join(Video, Scenario.video_id == Video.id)
        .join(Project, Video.project_id == Project.id)
        .where(Scene.id == scene_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")
    scene, scenario, video, project = row

    # 2. 既存アセットの削除
    stmt_exist = select(SceneAsset).where(SceneAsset.scene_id == scene_id, SceneAsset.slot == slot)
    exist_asset = (await db.execute(stmt_exist)).scalars().first()
    
    video_dir = get_project_dir(project) / "videos" / video.id
    if exist_asset:
        if exist_asset.file_path:
            old_file = video_dir / exist_asset.file_path
            if old_file.exists():
                old_file.unlink()
        await db.delete(exist_asset)
        await db.flush()

    file_rel_path = None
    if asset_type == "svg":
        if not svg_content:
            raise HTTPException(status_code=400, detail="svg_content が空です")
    else:
        if not file:
            raise HTTPException(status_code=400, detail="ファイルがアップロードされていません")
        
        # 拡張子チェック
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"許可されていないファイル形式です。許可形式: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # ファイルサイズチェック
        size = getattr(file, "size", None)
        if size is None:
            file.file.seek(0, os.SEEK_END)
            size = file.file.tell()
            file.file.seek(0)
            
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="ファイルサイズが 50MB を超えています")

        asset_dir = video_dir / "assets/images" / f"scene_{scene.index}"
        asset_dir.mkdir(parents=True, exist_ok=True)
        
        file_rel_path = f"assets/images/scene_{scene.index}/slot{slot}{ext}"
        dest_path = video_dir / file_rel_path
        
        try:
            with dest_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ファイルの保存に失敗しました: {str(e)}")

    # デフォルト表示設定
    default_config = {
        "offset_sec": 0.5,
        "duration_sec": None,
        "x": "center",
        "y": "center",
        "max_width": "600px",
        "max_height": "500px",
        "border_radius": "16px"
    }

    new_asset = SceneAsset(
        scene_id=scene_id,
        slot=slot,
        asset_type=asset_type,
        file_path=file_rel_path,
        svg_content=svg_content if asset_type == "svg" else None,
        display_config_json=json.dumps(default_config)
    )
    db.add(new_asset)
    await db.flush()

    read_obj = SceneAssetRead.model_validate(new_asset)
    if new_asset.file_path:
        read_obj.url = f"/projects/{get_project_dir_name(project)}/videos/{video.id}/{new_asset.file_path}"
    return read_obj

@router.patch("/scenes/{scene_id}/assets/{slot}", response_model=SceneAssetRead)
async def update_asset_config(
    scene_id: str,
    slot: int,
    payload: DisplayConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SceneAsset, Project, Video)
        .join(Scene, SceneAsset.scene_id == Scene.id)
        .join(Scenario, Scene.scenario_id == Scenario.id)
        .join(Video, Scenario.video_id == Video.id)
        .join(Project, Video.project_id == Project.id)
        .where(SceneAsset.scene_id == scene_id, SceneAsset.slot == slot)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="指定されたスロットの素材が見つかりません")
    asset, project, video = row

    try:
        cfg = json.loads(asset.display_config_json or "{}")
    except Exception:
        cfg = {}

    fs = payload.model_fields_set
    for field in ["offset_sec", "duration_sec", "x", "y", "max_width", "max_height", "border_radius"]:
        if field in fs:
            cfg[field] = getattr(payload, field)

    asset.display_config_json = json.dumps(cfg)
    await db.flush()

    read_obj = SceneAssetRead.model_validate(asset)
    if asset.file_path:
        read_obj.url = f"/projects/{get_project_dir_name(project)}/videos/{video.id}/{asset.file_path}"
    return read_obj

@router.delete("/scenes/{scene_id}/assets/{slot}", status_code=204)
async def delete_asset(
    scene_id: str,
    slot: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SceneAsset, Scene, Scenario, Video, Project)
        .join(Scene, SceneAsset.scene_id == Scene.id)
        .join(Scenario, Scene.scenario_id == Scenario.id)
        .join(Video, Scenario.video_id == Video.id)
        .join(Project, Video.project_id == Project.id)
        .where(SceneAsset.scene_id == scene_id, SceneAsset.slot == slot)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="素材が見つかりません")
    asset, scene, scenario, video, project = row

    if asset.file_path:
        video_dir = get_project_dir(project) / "videos" / video.id
        file_path = video_dir / asset.file_path
        if file_path.exists():
            file_path.unlink()

    await db.delete(asset)
    await db.flush()

@router.get("/scenes/{scene_id}/assets", response_model=list[SceneAssetRead])
async def list_assets(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SceneAsset, Project, Video)
        .join(Scene, SceneAsset.scene_id == Scene.id)
        .join(Scenario, Scene.scenario_id == Scenario.id)
        .join(Video, Scenario.video_id == Video.id)
        .join(Project, Video.project_id == Project.id)
        .where(SceneAsset.scene_id == scene_id)
        .order_by(SceneAsset.slot)
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    output = []
    for asset, project, video in rows:
        read_obj = SceneAssetRead.model_validate(asset)
        if asset.file_path:
            read_obj.url = f"/projects/{get_project_dir_name(project)}/videos/{video.id}/{asset.file_path}"
        output.append(read_obj)
    return output
