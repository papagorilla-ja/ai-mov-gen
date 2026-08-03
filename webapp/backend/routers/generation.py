from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from models.video import Video
from models.generation_history import GenerationHistory
from schemas.generation import GenerationHistoryRead
from workers.renderer import run_generation
from pathlib import Path
from datetime import datetime, timedelta

router = APIRouter(tags=["generation"])
ws_router = APIRouter(tags=["ws"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.latest_progress: Dict[str, dict] = {}

    async def connect(self, video_id: str, websocket: WebSocket):
        await websocket.accept()
        if video_id not in self.active_connections:
            self.active_connections[video_id] = []
        self.active_connections[video_id].append(websocket)
        
        # 接続直後に、最新の進捗キャッシュがあれば送信して初期取りこぼしを防ぐ
        if video_id in self.latest_progress:
            try:
                await websocket.send_json(self.latest_progress[video_id])
            except Exception:
                pass

    def disconnect(self, video_id: str, websocket: WebSocket):
        if video_id in self.active_connections:
            self.active_connections[video_id].remove(websocket)
            if not self.active_connections[video_id]:
                del self.active_connections[video_id]

    async def broadcast(self, video_id: str, message: dict):
        self.latest_progress[video_id] = message
        if video_id in self.active_connections:
            for connection in self.active_connections[video_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

@ws_router.websocket("/ws/videos/{video_id}/generation-progress")
async def websocket_endpoint(websocket: WebSocket, video_id: str):
    await manager.connect(video_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(video_id, websocket)


@router.post("/videos/{video_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    regenerate_audio: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """動画生成を開始する。

    regenerate_audio=True の場合は、既存のナレーション音声とその TTS キャッシュを
    破棄してから全シーンを合成し直す。話者を変更したときや、同じ話者の参照音声を
    録り直したとき（パスが同じためキャッシュが自動では無効化されない）に使う。
    """
    stmt = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    if video.status == "generating":
        raise HTTPException(status_code=400, detail="この動画は既に生成処理中です")

    history = GenerationHistory(
        video_id=video_id,
        status="running"
    )
    db.add(history)
    await db.flush()

    generation_id = history.id

    async def broadcast_progress(step: str, progress: float, message: str | None = None, error: str | None = None):
        msg = {
            "step": step,
            "progress": progress,
            "message": message,
            "error": error
        }
        await manager.broadcast(video_id, msg)

    background_tasks.add_task(
        run_generation, video_id, generation_id, broadcast_progress, regenerate_audio
    )

    return {
        "message": "動画の生成処理を開始しました",
        "generation_id": generation_id,
        "regenerate_audio": regenerate_audio,
    }


async def _check_and_fail_timeouts(video_id: str, db: AsyncSession) -> None:
    """開始から60分以上経過しても running のままのタスクを failed に更新する。"""
    threshold = datetime.now() - timedelta(minutes=60)
    stmt = (
        select(GenerationHistory)
        .where(
            GenerationHistory.video_id == video_id,
            GenerationHistory.status == "running",
            GenerationHistory.started_at < threshold
        )
    )
    stuck_histories = (await db.execute(stmt)).scalars().all()
    if stuck_histories:
        for h in stuck_histories:
            h.status = "failed"
            h.error_message = "処理がタイムアウトしました（60分超過）"
            h.completed_at = datetime.now()

        stmt_v = select(Video).where(Video.id == video_id, Video.status == "generating")
        v = (await db.execute(stmt_v)).scalars().first()
        if v:
            v.status = "failed"

        await db.commit()


@router.get("/videos/{video_id}/generation-status", response_model=GenerationHistoryRead)
async def get_generation_status(video_id: str, db: AsyncSession = Depends(get_db)):
    await _check_and_fail_timeouts(video_id, db)
    stmt = (
        select(GenerationHistory)
        .where(GenerationHistory.video_id == video_id)
        .order_by(GenerationHistory.started_at.desc())
        .limit(1)
    )
    history = (await db.execute(stmt)).scalars().first()
    if not history:
        raise HTTPException(status_code=404, detail="生成履歴が見つかりません")
    return history


@router.get("/videos/{video_id}/generations", response_model=list[GenerationHistoryRead])
async def list_generations(video_id: str, db: AsyncSession = Depends(get_db)):
    await _check_and_fail_timeouts(video_id, db)
    stmt = (
        select(GenerationHistory)
        .where(GenerationHistory.video_id == video_id)
        .order_by(GenerationHistory.started_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/videos/{video_id}/reset-status")
async def reset_generation_status(video_id: str, db: AsyncSession = Depends(get_db)):
    stmt_v = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt_v)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    video.status = "failed"

    stmt_h = select(GenerationHistory).where(
        GenerationHistory.video_id == video_id,
        GenerationHistory.status == "running"
    )
    running_histories = (await db.execute(stmt_h)).scalars().all()
    for h in running_histories:
        h.status = "failed"
        h.error_message = "ユーザーにより手動でリセットされました"
        h.completed_at = datetime.now()

    await db.commit()
    return {"message": "生成ステータスを強制リセットしました"}


@router.delete("/generations/{gen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generation(gen_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(GenerationHistory).where(GenerationHistory.id == gen_id)
    history = (await db.execute(stmt)).scalars().first()
    if not history:
        raise HTTPException(status_code=404, detail="生成履歴が見つかりません")

    if history.status == "running":
        stmt_v = select(Video).where(Video.id == history.video_id, Video.status == "generating")
        v = (await db.execute(stmt_v)).scalars().first()
        if v:
            v.status = "failed"

    if history.output_path:
        Path(history.output_path).unlink(missing_ok=True)
    if history.thumbnail_path:
        Path(history.thumbnail_path).unlink(missing_ok=True)

    await db.delete(history)
    await db.commit()


@router.get("/generations/{gen_id}/download")
async def download_video(gen_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(GenerationHistory).where(GenerationHistory.id == gen_id)
    history = (await db.execute(stmt)).scalars().first()
    if not history:
        raise HTTPException(status_code=404, detail="生成履歴が見つかりません")

    if history.status != "completed" or not history.output_path:
        raise HTTPException(status_code=400, detail="この動画は生成中、または生成に失敗しています")

    path = Path(history.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="動画ファイルが見つかりません")

    stmt_v = select(Video).where(Video.id == history.video_id)
    video = (await db.execute(stmt_v)).scalars().first()
    filename = f"{video.name if video else 'video'}.mp4"

    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        filename=filename
    )


@router.get("/generations/{gen_id}/play")
async def play_video(gen_id: str, db: AsyncSession = Depends(get_db)):
    """インアプリ再生用のインライン・Range対応エンドポイント"""
    stmt = select(GenerationHistory).where(GenerationHistory.id == gen_id)
    history = (await db.execute(stmt)).scalars().first()
    if not history:
        raise HTTPException(status_code=404, detail="生成履歴が見つかりません")

    if history.status != "completed" or not history.output_path:
        raise HTTPException(status_code=400, detail="この動画は生成中、または生成に失敗しています")

    path = Path(history.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="動画ファイルが見つかりません")

    # filename を指定しないことで Content-Disposition: inline 扱いとし、RangeRequests に対応させる
    return FileResponse(
        path=str(path),
        media_type="video/mp4"
    )


def _srt_time(seconds: float) -> str:
    """秒数を SRT タイムスタンプ形式 (HH:MM:SS,mmm) に変換する"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


@router.get("/generations/{gen_id}/subtitle.srt")
async def download_subtitle(gen_id: str, db: AsyncSession = Depends(get_db)):
    """生成完了済み動画の SRT 字幕ファイルを生成してダウンロードする。"""
    from models.scenario import Scenario
    from models.scene import Scene

    # 生成履歴 → video_id
    stmt_h = select(GenerationHistory).where(GenerationHistory.id == gen_id)
    history = (await db.execute(stmt_h)).scalars().first()
    if not history or history.status != "completed":
        raise HTTPException(status_code=404, detail="完了済み生成が見つかりません")

    # シナリオ → シーン一覧
    stmt_sc = select(Scenario).where(Scenario.video_id == history.video_id)
    scenario = (await db.execute(stmt_sc)).scalars().first()
    if not scenario:
        raise HTTPException(status_code=404, detail="シナリオが見つかりません")

    stmt_scenes = (
        select(Scene)
        .where(Scene.scenario_id == scenario.id)
        .where(Scene.data_start.is_not(None))
        .order_by(Scene.index)
    )
    scenes = (await db.execute(stmt_scenes)).scalars().all()
    if not scenes:
        raise HTTPException(status_code=404, detail="タイミング情報のあるシーンが見つかりません。先に動画を生成してください。")

    # SRT 生成
    lines = []
    for i, scene in enumerate(scenes, start=1):
        start_sec = scene.data_start or 0.0
        end_sec = start_sec + (scene.data_duration or 0.0)
        text = (scene.narration_text or "").strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{_srt_time(start_sec)} --> {_srt_time(end_sec)}")
        lines.append(text)
        lines.append("")

    srt_content = "\n".join(lines)

    return Response(
        content=srt_content.encode("utf-8"),
        media_type="application/x-subrip",
        headers={"Content-Disposition": f"attachment; filename=subtitle_{gen_id[:8]}.srt"},
    )
