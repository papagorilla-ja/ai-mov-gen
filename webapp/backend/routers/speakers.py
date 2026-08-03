import json
import logging
import os
import shutil
import uuid
import math
import asyncio
from datetime import datetime
from pathlib import Path
import soundfile as sf
import numpy as np
from scipy.signal import resample_poly

from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from models.speaker import Speaker
from models.voice_recording import VoiceRecording
from schemas.speaker import SpeakerCreate, SpeakerRead, SpeakerUpdate
from schemas.voice_recording import (
    SessionFinalizeRequest,
    SessionStartRequest,
    UseRecordingRequest,
    VoiceRecordingRead,
    VoiceRecordingUpdate,
)
from services.audio_utils import build_reference_audio
from services.voice_corpus import MODE_LABELS, SUPPORTED_MODES, build_session_items

logger = logging.getLogger("speakers")

router = APIRouter(prefix="/speakers", tags=["speakers"])

# 収録セッションの作業ディレクトリと、収録音声ライブラリの保存先
SESSION_ROOT = Path("/tmp/heygen_sessions")
RECORDINGS_DIR = Path("/app/voice_samples/_recordings")

# セッションのメタ情報キャッシュ。実体は各セッションディレクトリの session.json にも
# 書き出しており、API 再起動後もそちらから復元できる（収録途中の消失を防ぐ）。
_sessions: dict[str, dict] = {}


def _session_dir(session_id: str) -> Path:
    return SESSION_ROOT / session_id


def _save_session(session_id: str, session: dict) -> None:
    """セッション情報をメモリとディスクの両方に保存する。"""
    _sessions[session_id] = session
    d = _session_dir(session_id)
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "mode": session["mode"],
        "items": session["items"],
        "recordings": session["recordings"],
        "created_at": session["created_at"].isoformat(),
    }
    (d / "session.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def _load_session(session_id: str) -> dict:
    """セッションを取得する。メモリに無ければディスクから復元する。"""
    session = _sessions.get(session_id)
    if session is not None:
        return session

    meta_path = _session_dir(session_id) / "session.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="セッションが見つかりません。もう一度やり直してください。")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        session = {
            "mode": meta["mode"],
            "items": meta["items"],
            # JSON のキーは文字列になるため int に戻す
            "recordings": {int(k): v for k, v in meta.get("recordings", {}).items()},
            "created_at": datetime.fromisoformat(meta["created_at"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"セッション情報の復元に失敗しました: {e}")
    _sessions[session_id] = session
    return session


def _recording_read(rec: VoiceRecording) -> VoiceRecordingRead:
    """試聴用 URL を付与して返却用スキーマに変換する。"""
    obj = VoiceRecordingRead.model_validate(rec)
    obj.audio_url = f"/api/v1/speakers/recordings/{rec.id}/audio"
    return obj


def resample_to_16k(input_path: str, output_path: str):
    data, sr = sf.read(input_path, always_2d=False)
    # ステレオ → モノラル変換
    if data.ndim > 1:
        data = data.mean(axis=1)
    # リサンプリング
    if sr != 16000:
        g = math.gcd(16000, sr)
        data = resample_poly(data, 16000 // g, sr // g)
    data = np.clip(data, -1.0, 1.0)
    sf.write(output_path, data.astype(np.float32), 16000, subtype="PCM_16")

@router.get("", response_model=list[SpeakerRead])
async def list_speakers(db: AsyncSession = Depends(get_db)):
    stmt = select(Speaker)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=SpeakerRead, status_code=status.HTTP_201_CREATED)
async def create_speaker(payload: SpeakerCreate, db: AsyncSession = Depends(get_db)):
    speaker = Speaker(
        name=payload.name,
        description=payload.description,
        reference_audio_path=payload.reference_audio_path,
        language=payload.language,
        is_system=payload.is_system
    )
    db.add(speaker)
    await db.flush()
    return speaker

@router.post("/upload-reference", response_model=SpeakerRead)
async def upload_reference(
    speaker_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Speaker).where(Speaker.id == speaker_id)
    speaker = (await db.execute(stmt)).scalars().first()
    if not speaker:
        raise HTTPException(status_code=404, detail="話者が見つかりません")
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".wav", ".mp3", ".m4a", ".flac"]:
        raise HTTPException(status_code=400, detail="対応フォーマットは WAV/MP3/M4A/FLAC です")
    
    target_dir = f"/app/voice_samples/{speaker_id}"
    os.makedirs(target_dir, exist_ok=True)
    
    tmp_path = f"{target_dir}/input.tmp"
    try:
        with open(tmp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        ref_path = f"{target_dir}/reference.wav"
        await asyncio.to_thread(resample_to_16k, tmp_path, ref_path)
        
        speaker.reference_audio_path = ref_path
        await db.flush()
        return speaker
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"音声ファイルの処理に失敗しました: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# ─── 音声収集セッション ────────────────────────────────────
# 収録の流れ:
#   1. start    … モードと収録本数を指定してセッションを作る（固定コーパスなので即応答）
#   2. record   … 1本ずつ音声をアップロード。16kHz モノラル WAV に変換して保存
#   3. finalize … 全テイクを整形・連結して「収録音声ライブラリ」に名前付きで保存
# 話者の作成は行わない。ライブラリに保存した音声を、話者の新規追加画面で選択する。

@router.get("/collection-session/modes")
async def session_modes():
    """選択できる収録モードの一覧を返す（画面のモード選択に使う）。"""
    return [{"value": m, "label": MODE_LABELS[m]} for m in SUPPORTED_MODES]


@router.post("/collection-session/start")
async def session_start(payload: SessionStartRequest):
    count = payload.item_count
    if count < 1 or count > 10:
        raise HTTPException(status_code=400, detail="収録本数は 1 以上 10 以下にしてください")
    if payload.mode not in SUPPORTED_MODES:
        raise HTTPException(status_code=400, detail=f"未対応の収録モードです: {payload.mode}")

    # 固定コーパスから提示項目を作る（LLM を使わないので待ち時間が発生しない）
    items = build_session_items(payload.mode, count)

    session_id = str(uuid.uuid4())
    _save_session(session_id, {
        "mode": payload.mode,
        "items": items,
        "recordings": {},
        "created_at": datetime.now(),
    })

    return {
        "session_id": session_id,
        "mode": payload.mode,
        "mode_label": MODE_LABELS[payload.mode],
        "items": items,
    }


@router.post("/collection-session/{session_id}/record")
async def session_record(
    session_id: str,
    sentence_index: int = Form(...),
    file: UploadFile = File(...),
):
    session = _load_session(session_id)
    if sentence_index < 1 or sentence_index > len(session["items"]):
        raise HTTPException(status_code=400, detail="不正な収録番号です")

    session_dir = _session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    # ブラウザによって webm(Chrome) / mp4(Safari) など形式が変わるため、
    # 拡張子は信用せず ffmpeg に判定させる（拡張子なしでも変換できる）
    input_path = session_dir / f"{sentence_index}.input"
    wav_path = session_dir / f"{sentence_index}.wav"

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if input_path.stat().st_size == 0:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="録音データが空です。もう一度録音してください。")

    # 16kHz モノラル WAV へ変換
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(input_path), "-ar", "16000", "-ac", "1", str(wav_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        # ffmpeg が失敗した場合は soundfile で直接読めるか試す
        try:
            await asyncio.to_thread(resample_to_16k, str(input_path), str(wav_path))
        except Exception as inner_e:
            detail = stderr.decode(errors="replace")[-400:]
            logger.error(f"録音の変換に失敗しました (session={session_id} index={sentence_index}): {detail} / {inner_e}")
            raise HTTPException(status_code=500, detail=f"音声ファイルの処理に失敗しました: {inner_e}")
    input_path.unlink(missing_ok=True)

    # 収録できた長さを返し、短すぎる場合は画面側で警告できるようにする
    try:
        info = await asyncio.to_thread(sf.info, str(wav_path))
        duration = float(info.duration)
    except Exception:
        duration = 0.0

    session["recordings"][sentence_index] = str(wav_path)
    _save_session(session_id, session)

    return {
        "sentence_index": sentence_index,
        "saved": True,
        "duration_sec": round(duration, 2),
        "recorded_count": len(session["recordings"]),
    }


@router.post("/collection-session/{session_id}/finalize", response_model=VoiceRecordingRead)
async def session_finalize(
    session_id: str,
    payload: SessionFinalizeRequest,
    db: AsyncSession = Depends(get_db)
):
    """収録したテイクを整形・連結し、収録音声ライブラリへ名前付きで保存する。"""
    session = _load_session(session_id)
    recordings = session["recordings"]
    if not recordings:
        raise HTTPException(status_code=400, detail="録音データがありません")

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="収録音声の名前を入力してください")

    take_paths = [recordings[idx] for idx in sorted(recordings.keys()) if os.path.exists(recordings[idx])]
    if not take_paths:
        raise HTTPException(status_code=400, detail="録音ファイルが見つかりません。もう一度収録してください。")

    recording_id = str(uuid.uuid4())
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RECORDINGS_DIR / f"{recording_id}.wav"

    try:
        # 無音トリム + 音量正規化 + テイク均等配分（既定 20 秒上限）
        duration, used_takes = await asyncio.to_thread(build_reference_audio, take_paths, str(out_path))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"参照音声の作成に失敗しました (session={session_id}): {e}")
        raise HTTPException(status_code=500, detail=f"音声の結合に失敗しました: {e}")

    rec = VoiceRecording(
        id=recording_id,
        name=name,
        file_path=str(out_path),
        mode=session["mode"],
        duration_sec=round(duration, 2),
        take_count=used_takes,
    )
    db.add(rec)
    await db.flush()

    shutil.rmtree(_session_dir(session_id), ignore_errors=True)
    _sessions.pop(session_id, None)

    return _recording_read(rec)


# ─── 収録音声ライブラリ ────────────────────────────────────

@router.get("/recordings", response_model=list[VoiceRecordingRead])
async def list_recordings(db: AsyncSession = Depends(get_db)):
    stmt = select(VoiceRecording).order_by(VoiceRecording.created_at.desc())
    recs = (await db.execute(stmt)).scalars().all()
    return [_recording_read(r) for r in recs]


@router.get("/recordings/{recording_id}/audio")
async def get_recording_audio(recording_id: str, db: AsyncSession = Depends(get_db)):
    """試聴用に収録音声を返す。"""
    stmt = select(VoiceRecording).where(VoiceRecording.id == recording_id)
    rec = (await db.execute(stmt)).scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="収録音声が見つかりません")
    if not os.path.exists(rec.file_path):
        raise HTTPException(status_code=404, detail="収録音声のファイルが見つかりません")
    return FileResponse(rec.file_path, media_type="audio/wav", filename=f"{rec.name}.wav")


@router.patch("/recordings/{recording_id}", response_model=VoiceRecordingRead)
async def rename_recording(
    recording_id: str,
    payload: VoiceRecordingUpdate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(VoiceRecording).where(VoiceRecording.id == recording_id)
    rec = (await db.execute(stmt)).scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="収録音声が見つかりません")
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="名前を入力してください")
    rec.name = name
    await db.flush()
    return _recording_read(rec)


@router.delete("/recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recording(recording_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(VoiceRecording).where(VoiceRecording.id == recording_id)
    rec = (await db.execute(stmt)).scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="収録音声が見つかりません")

    # 既に話者へ採用済みの参照音声はコピー済みなので、ライブラリ側の削除は話者に影響しない
    if os.path.exists(rec.file_path):
        os.remove(rec.file_path)
    await db.delete(rec)
    await db.flush()


@router.post("/use-recording", response_model=SpeakerRead)
async def use_recording_as_reference(
    payload: UseRecordingRequest,
    db: AsyncSession = Depends(get_db)
):
    """収録音声ライブラリの音声を、指定した話者の参照音声として採用する。"""
    stmt = select(Speaker).where(Speaker.id == payload.speaker_id)
    speaker = (await db.execute(stmt)).scalars().first()
    if not speaker:
        raise HTTPException(status_code=404, detail="話者が見つかりません")

    stmt_r = select(VoiceRecording).where(VoiceRecording.id == payload.recording_id)
    rec = (await db.execute(stmt_r)).scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="収録音声が見つかりません")
    if not os.path.exists(rec.file_path):
        raise HTTPException(status_code=404, detail="収録音声のファイルが見つかりません")

    # 話者ごとのディレクトリへコピーする（ライブラリ側を消しても話者が壊れないように）
    target_dir = f"/app/voice_samples/{speaker.id}"
    os.makedirs(target_dir, exist_ok=True)
    ref_path = f"{target_dir}/reference.wav"
    await asyncio.to_thread(shutil.copy2, rec.file_path, ref_path)

    speaker.reference_audio_path = ref_path
    await db.flush()
    return speaker

@router.get("/{speaker_id}", response_model=SpeakerRead)
async def get_speaker(speaker_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Speaker).where(Speaker.id == speaker_id)
    speaker = (await db.execute(stmt)).scalars().first()
    if not speaker:
        raise HTTPException(status_code=404, detail="話者が見つかりません")
    return speaker

@router.patch("/{speaker_id}", response_model=SpeakerRead)
async def update_speaker(
    speaker_id: str,
    payload: SpeakerUpdate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Speaker).where(Speaker.id == speaker_id)
    speaker = (await db.execute(stmt)).scalars().first()
    if not speaker:
        raise HTTPException(status_code=404, detail="話者が見つかりません")
    
    fs = payload.model_fields_set
    if 'name' in fs:
        speaker.name = payload.name
    if 'description' in fs:
        speaker.description = payload.description
    if 'language' in fs:
        speaker.language = payload.language
    if 'avatar_path' in fs:
        speaker.avatar_path = payload.avatar_path
    
    await db.flush()
    return speaker

@router.delete("/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_speaker(speaker_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Speaker).where(Speaker.id == speaker_id)
    speaker = (await db.execute(stmt)).scalars().first()
    if not speaker:
        raise HTTPException(status_code=404, detail="話者が見つかりません")
    if speaker.is_system:
        raise HTTPException(status_code=400, detail="システム話者は削除できません")
    
    target_dir = f"/app/voice_samples/{speaker_id}"
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
        
    await db.delete(speaker)
    await db.flush()
