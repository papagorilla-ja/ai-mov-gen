import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from models.video_style import VideoStyle
from models.scenario import Scenario
from models.scene import Scene
from models.speaker import Speaker
from schemas.scene import SceneCreate, SceneRead, SceneUpdate, SceneReorder, AiDesignAdjustRequest
from schemas.scenario import NarrationGenerateRequest
from services.llm_service import (
    generate_narration as generate_narration_llm,
    generate_scene_content as generate_scene_content_llm,
    generate_image_prompt as generate_image_prompt_llm,
    ai_adjust_scene_design as ai_adjust_scene_design_llm
)
from services.composition import render_scene_preview_html, _validate_scene_html_fragment
from services.tts_service import derive_seed, synthesize_scene_audio
from services.jobs import preview_job_store

router = APIRouter(tags=["scenes"])


async def _load_scene_style(db: AsyncSession, scene: Scene) -> VideoStyle:
    stmt_sc = select(Scenario).where(Scenario.id == scene.scenario_id)
    scenario = (await db.execute(stmt_sc)).scalars().first()
    if scenario:
        stmt_style = select(VideoStyle).where(VideoStyle.video_id == scenario.video_id)
        style = (await db.execute(stmt_style)).scalars().first()
        if style:
            return style
    return VideoStyle()


async def _run_preview_synthesis(job_id: str, scene_id: str) -> None:
    """バックグラウンドで TTS 合成を実行し、結果をジョブストアに保存する。"""
    from core.database import AsyncSessionLocal
    import tempfile
    from pathlib import Path

    async with AsyncSessionLocal() as db:
        try:
            stmt = select(Scene).where(Scene.id == scene_id)
            scene = (await db.execute(stmt)).scalars().first()
            if not scene:
                preview_job_store.update(job_id, status="error", error="シーンが見つかりません")
                return

            if not scene.narration_text:
                preview_job_store.update(job_id, status="error", error="ナレーションテキストが空です")
                return

            stmt_sc = select(Scenario).where(Scenario.id == scene.scenario_id)
            scenario = (await db.execute(stmt_sc)).scalars().first()

            # 話者 A (およびデフォルト)
            speaker_a = None
            if scene.speaker_id:
                stmt_sp = select(Speaker).where(Speaker.id == scene.speaker_id)
                speaker_a = (await db.execute(stmt_sp)).scalars().first()
            else:
                if scenario:
                    stmt_style = select(VideoStyle).where(VideoStyle.video_id == scenario.video_id)
                    video_style = (await db.execute(stmt_style)).scalars().first()
                    if video_style and video_style.default_speaker_id:
                        stmt_sp = select(Speaker).where(Speaker.id == video_style.default_speaker_id)
                        speaker_a = (await db.execute(stmt_sp)).scalars().first()

            # 話者 B (およびデフォルト、chat_dialog 用)
            speaker_b = None
            dialog_lines = None
            if scene.layout_type == "chat_dialog" and scene.slide_content_json:
                # slide_content_json は JSON 文字列カラムなので必ず json.loads する。
                # （以前は isinstance(..., dict) で判定しており常に False だったため、
                #   プレビューでは複数話者の合成が一度も動いていなかった）
                try:
                    content_data = json.loads(scene.slide_content_json)
                    dialog_lines = content_data.get("lines") or None
                except Exception:
                    dialog_lines = None


                speaker_b_id = scene.speaker_b_id
                if not speaker_b_id and scenario:
                    stmt_style = select(VideoStyle).where(VideoStyle.video_id == scenario.video_id)
                    video_style = (await db.execute(stmt_style)).scalars().first()
                    if video_style:
                        speaker_b_id = video_style.default_speaker_b_id
                if speaker_b_id:
                    stmt_sp_b = select(Speaker).where(Speaker.id == speaker_b_id)
                    speaker_b = (await db.execute(stmt_sp_b)).scalars().first()

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_dir_path = Path(tmpdir)
                output_wav_path = tmp_dir_path / f"preview_{scene.id}.wav"
                
                audio_content = await synthesize_scene_audio(
                    text=scene.narration_text,
                    dialog_lines=dialog_lines,
                    speaker_a=speaker_a,
                    speaker_b=speaker_b,
                    output_wav_path=output_wav_path,
                    seed=derive_seed(scene.id),
                )
                preview_job_store.update(job_id, status="done", audio=audio_content)
        except Exception as e:
            preview_job_store.update(job_id, status="error", error=f"音声プレビュー生成エラー: {str(e)}")

@router.get("/videos/{video_id}/scenes", response_model=list[SceneRead])
async def list_scenes(video_id: str, db: AsyncSession = Depends(get_db)):
    stmt_sc = select(Scenario).where(Scenario.video_id == video_id)
    scenario = (await db.execute(stmt_sc)).scalars().first()
    if not scenario:
        return []
    
    stmt_scenes = select(Scene).where(Scene.scenario_id == scenario.id).order_by(Scene.index)
    result = await db.execute(stmt_scenes)
    return result.scalars().all()

@router.post("/videos/{video_id}/scenes", response_model=SceneRead, status_code=status.HTTP_201_CREATED)
async def create_scene(video_id: str, payload: SceneCreate, db: AsyncSession = Depends(get_db)):
    stmt_sc = select(Scenario).where(Scenario.video_id == video_id)
    scenario = (await db.execute(stmt_sc)).scalars().first()
    if not scenario:
        scenario = Scenario(video_id=video_id, source_type="paste")
        db.add(scenario)
        await db.flush()

    stmt_max = select(Scene.index).where(Scene.scenario_id == scenario.id).order_by(Scene.index.desc()).limit(1)
    max_index = (await db.execute(stmt_max)).scalar() or 0

    scene = Scene(
        scenario_id=scenario.id,
        index=max_index + 1,
        title=payload.title,
        layout_type=payload.layout_type,
        slide_content_json=payload.slide_content_json,
        narration_text=payload.narration_text,
        speaker_id=payload.speaker_id
    )
    db.add(scene)
    await db.flush()
    return scene

@router.get("/scenes/{scene_id}", response_model=SceneRead)
async def get_scene(scene_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")
    return scene

@router.patch("/scenes/{scene_id}", response_model=SceneRead)
async def update_scene(scene_id: str, payload: SceneUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")

    # model_fields_set: 明示的に送信されたフィールドだけを更新する
    # (null 送信でクリア可能、未送信フィールドは無視)
    fs = payload.model_fields_set
    if 'title' in fs:
        scene.title = payload.title
    if 'layout_type' in fs:
        scene.layout_type = payload.layout_type
    if 'slide_content_json' in fs:
        scene.slide_content_json = payload.slide_content_json
    if 'narration_text' in fs:
        scene.narration_text = payload.narration_text
    if 'speaker_id' in fs:
        scene.speaker_id = payload.speaker_id  # null 送信でクリア可
    if 'speaker_b_id' in fs:
        scene.speaker_b_id = payload.speaker_b_id  # null 送信でクリア可
    if 'data_start' in fs:
        scene.data_start = payload.data_start
    if 'data_duration' in fs:
        scene.data_duration = payload.data_duration
    if 'custom_html' in fs:
        scene.custom_html = payload.custom_html  # null 送信でクリア可
    if 'custom_css' in fs:
        scene.custom_css = payload.custom_css

    await db.flush()
    return scene


@router.get("/scenes/{scene_id}/effective-html")
async def get_scene_effective_html(scene_id: str, db: AsyncSession = Depends(get_db)):
    """このシーンの「現在の実効 HTML/CSS」を返す（custom_html があればそれ、なければ自動生成結果）。"""
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")

    style = await _load_scene_style(db, scene)
    return {
        "html": render_scene_preview_html(scene, style),
        "css": scene.custom_css or "",
        "is_custom": bool(scene.custom_html),
    }


@router.post("/scenes/{scene_id}/ai-design-adjust", response_model=SceneRead)
async def ai_design_adjust(scene_id: str, payload: AiDesignAdjustRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")

    style = await _load_scene_style(db, scene)
    current_html = render_scene_preview_html(scene, style)
    scene_dom_id = f"scene-{scene.id}"
    style_vars = {
        "color_primary": style.color_primary,
        "color_secondary": style.color_secondary,
        "color_accent": style.color_accent,
        "color_bg": style.color_bg,
        "color_text_primary": style.color_text_primary,
    }

    try:
        result = await ai_adjust_scene_design_llm(
            current_html=current_html,
            current_css=scene.custom_css or "",
            instruction=payload.instruction,
            scene_dom_id=scene_dom_id,
            style_vars=style_vars,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AIデザイン調整に失敗しました: {str(e) or repr(e)}")

    ok, err = _validate_scene_html_fragment(result["html"])
    if not ok:
        raise HTTPException(status_code=502, detail=f"AIの生成結果が不正でした: {err}")

    scene.custom_html = result["html"]
    scene.custom_css = result["css"]
    await db.flush()
    return scene

@router.delete("/scenes/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(scene_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")

    scenario_id = scene.scenario_id
    await db.delete(scene)
    await db.flush()

    stmt_scenes = select(Scene).where(Scene.scenario_id == scenario_id).order_by(Scene.index)
    scenes = (await db.execute(stmt_scenes)).scalars().all()
    for idx, s in enumerate(scenes, start=1):
        s.index = idx
    await db.flush()

@router.post("/scenes/{scene_id}/reorder", response_model=list[SceneRead])
async def reorder_scene(scene_id: str, payload: SceneReorder, db: AsyncSession = Depends(get_db)):
    stmt = select(Scene).where(Scene.id == scene_id)
    target_scene = (await db.execute(stmt)).scalars().first()
    if not target_scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")

    scenario_id = target_scene.scenario_id
    stmt_scenes = select(Scene).where(Scene.scenario_id == scenario_id).order_by(Scene.index)
    scenes = list((await db.execute(stmt_scenes)).scalars().all())

    if target_scene in scenes:
        scenes.remove(target_scene)

    new_index = payload.new_index
    if new_index < 1:
        new_index = 1
    elif new_index > len(scenes) + 1:
        new_index = len(scenes) + 1

    scenes.insert(new_index - 1, target_scene)

    for idx, s in enumerate(scenes, start=1):
        s.index = idx

    await db.flush()
    return scenes

@router.post("/scenes/{scene_id}/preview-audio/start", status_code=status.HTTP_202_ACCEPTED)
async def start_preview_audio(scene_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """プレビュー音声合成をバックグラウンドで開始し、ジョブIDを即座に返す。
    TTS 合成に時間がかかっても HTTP リクエスト自体はすぐに完了するため、
    フロントエンド側のタイムアウトに引っかからない。"""
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")
    if not scene.narration_text:
        raise HTTPException(status_code=400, detail="ナレーションテキストが空です")

    job_id = str(uuid.uuid4())
    preview_job_store.register(job_id)
    background_tasks.add_task(_run_preview_synthesis, job_id, scene_id)
    return {"job_id": job_id}


@router.get("/scenes/preview-audio/{job_id}/status")
async def get_preview_audio_status(job_id: str):
    """ポーリング用: ジョブの現在の状態を返す（軽量・即時応答）。"""
    job = preview_job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません（期限切れの可能性があります）")
    return {"status": job["status"], "error": job["error"]}


@router.get("/scenes/preview-audio/{job_id}/audio")
async def get_preview_audio_result(job_id: str):
    """合成が完了したジョブから WAV バイナリを取得する。"""
    job = preview_job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません（期限切れの可能性があります）")
    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=job["error"] or "音声合成に失敗しました")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="音声はまだ準備中です")
    return Response(content=job["audio"], media_type="audio/wav")


def normalize_slide_content(layout_type: str, content: dict) -> dict:
    """LLM生成結果をレイアウトに合わせて正規化・バリデーションする"""
    if not isinstance(content, dict):
        return {}
    res = {**content}

    # body のエイリアスマッピング（LLM が text や content 等の別キーで出力した場合の対応）
    if not res.get("body"):
        for alt_key in ["text", "content", "description"]:
            if isinstance(res.get(alt_key), str) and res[alt_key].strip():
                res["body"] = res[alt_key].strip()
                break

    if layout_type == "bullet_list":
        bp = res.get("bullet_points")
        if isinstance(bp, str):
            bp = [line.strip() for line in bp.split("\n") if line.strip()]
        elif isinstance(bp, list):
            bp = [str(x).strip() for x in bp if str(x).strip()]
        else:
            bp = []
        res["bullet_points"] = bp

    elif layout_type == "card_panel":
        cards = res.get("cards")
        norm_cards = []
        if isinstance(cards, list):
            for c in cards:
                if isinstance(c, dict):
                    norm_cards.append({
                        "title": str(c.get("title") or "").strip(),
                        "text": str(c.get("text") or "").strip()
                    })
        res["cards"] = norm_cards

    elif layout_type == "table":
        headers = res.get("headers")
        if isinstance(headers, str):
            headers = [h.strip() for h in headers.split(",") if h.strip()]
        elif not isinstance(headers, list):
            headers = []
        headers = [str(h).strip() for h in headers]
        res["headers"] = headers

        rows = res.get("rows")
        norm_rows = []
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, str):
                    r_list = [col.strip() for col in r.split(",")]
                elif isinstance(r, list):
                    r_list = [str(col).strip() for col in r]
                else:
                    r_list = []
                if len(r_list) < len(headers):
                    r_list.extend([""] * (len(headers) - len(r_list)))
                elif len(r_list) > len(headers) and len(headers) > 0:
                    r_list = r_list[:len(headers)]
                norm_rows.append(r_list)
        res["rows"] = norm_rows

    elif layout_type == "graph_chart":
        chart = res.get("chart")
        if not isinstance(chart, dict):
            chart = {}
        chart_type = chart.get("type") or "bar"
        labels = chart.get("labels") or []
        if isinstance(labels, str):
            labels = [l.strip() for l in labels.split(",") if l.strip()]
        values = chart.get("values") or []
        if isinstance(values, str):
            values = [v.strip() for v in values.split(",") if v.strip()]
        norm_values = []
        for v in values:
            try:
                norm_values.append(float(v) if "." in str(v) else int(v))
            except Exception:
                pass
        min_len = min(len(labels), len(norm_values))
        res["chart"] = {
            "type": str(chart_type),
            "labels": [str(l) for l in labels[:min_len]],
            "values": norm_values[:min_len],
            "unit": str(chart.get("unit") or "")
        }

    elif layout_type == "chat_dialog":
        lines = res.get("lines")
        norm_lines = []
        if isinstance(lines, list):
            for i, l in enumerate(lines):
                if isinstance(l, dict):
                    spk = str(l.get("speaker") or ("A" if i % 2 == 0 else "B")).strip().upper()
                    norm_lines.append({
                        "speaker": spk if spk in ["A", "B"] else ("A" if i % 2 == 0 else "B"),
                        "text": str(l.get("text") or "").strip()
                    })
        res["lines"] = norm_lines

    return res


@router.post("/scenes/{scene_id}/generate-content", response_model=SceneRead)
async def generate_scene_content(scene_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")

    result = await generate_scene_content_llm(
        title=scene.title or "",
        summary=scene.outline_summary or "",
        layout_type=scene.layout_type or "text_only",
    )
    norm_content = normalize_slide_content(scene.layout_type or "text_only", result["slide_content_json"])
    try:
        current = json.loads(scene.slide_content_json) if scene.slide_content_json else {}
    except Exception:
        current = {}
    merged = {**current, **norm_content}
    merged.setdefault("title", scene.title or current.get("title", ""))
    if current.get("summary"):
        merged.setdefault("summary", current["summary"])
    scene.slide_content_json = json.dumps(merged, ensure_ascii=False)
    if result["narration_text"]:
        scene.narration_text = result["narration_text"]
    await db.flush()
    return scene


@router.post("/scenes/{scene_id}/generate-image-prompt", response_model=SceneRead)
async def generate_image_prompt(scene_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")
    try:
        content = json.loads(scene.slide_content_json) if scene.slide_content_json else {}
    except Exception:
        content = {}
    result = await generate_image_prompt_llm(
        title=scene.title or "",
        summary=scene.outline_summary or "",
        layout_type=scene.layout_type or "text_only",
        slide_content=content,
        image_description=content.get("image_description", ""),
    )
    if not result["image_prompt"]:
        raise HTTPException(status_code=502, detail="画像プロンプトの生成に失敗しました")

    scene.image_prompt = result["image_prompt"]
    if result.get("note"):
        content["image_prompt_note"] = result["note"]
        scene.slide_content_json = json.dumps(content, ensure_ascii=False)
    await db.flush()
    return scene


@router.post("/scenes/{scene_id}/generate-narration", response_model=SceneRead)
async def generate_narration(
    scene_id: str,
    payload: NarrationGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    # シーンの存在確認
    stmt = select(Scene).where(Scene.id == scene_id)
    scene = (await db.execute(stmt)).scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="シーンが見つかりません")

    # 同一シナリオ内の全シーンを取得して並べる
    stmt_scenes = select(Scene).where(Scene.scenario_id == scene.scenario_id).order_by(Scene.index)
    all_scenes = (await db.execute(stmt_scenes)).scalars().all()

    prev_narration = ""
    current_idx = -1
    for i, s in enumerate(all_scenes):
        if s.id == scene_id:
            current_idx = i
            break

    if current_idx > 0:
        prev_narration = all_scenes[current_idx - 1].narration_text or ""

    reply = await generate_narration_llm(
        title=scene.title,
        slide_content_json=scene.slide_content_json,
        prev_narration=prev_narration,
        summary=scene.outline_summary or ""
    )

    scene.narration_text = reply.strip()
    await db.flush()

    return scene


bulk_content_job_store: dict[str, dict] = {}

def _is_scene_empty_content(scene: Scene) -> bool:
    if not scene.slide_content_json:
        return True
    try:
        data = json.loads(scene.slide_content_json)
        keys = ["bullet_points", "left_text", "right_text", "cards", "headers", "rows", "chart", "lines"]
        for k in keys:
            if k in data and data[k]:
                return False
        return True
    except Exception:
        return True


async def _run_bulk_generate_content(job_id: str, video_id: str, only_empty: bool):
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            stmt_sc = select(Scenario).where(Scenario.video_id == video_id)
            scenario = (await db.execute(stmt_sc)).scalars().first()
            if not scenario:
                bulk_content_job_store[job_id] = {"status": "error", "error": "シナリオが見つかりません"}
                return

            stmt_scenes = select(Scene).where(Scene.scenario_id == scenario.id).order_by(Scene.index)
            all_scenes = (await db.execute(stmt_scenes)).scalars().all()

            target_scenes = [s for s in all_scenes if (not only_empty or _is_scene_empty_content(s))]
            total = len(target_scenes)

            bulk_content_job_store[job_id] = {
                "status": "processing",
                "done": 0,
                "total": total,
                "current_title": "",
                "error": None
            }

            if total == 0:
                bulk_content_job_store[job_id]["status"] = "completed"
                return

            for idx, scene in enumerate(target_scenes):
                bulk_content_job_store[job_id]["current_title"] = scene.title or f"Scene {scene.index}"
                result = await generate_scene_content_llm(
                    title=scene.title or "",
                    summary=scene.outline_summary or "",
                    layout_type=scene.layout_type or "text_only",
                )
                norm_content = normalize_slide_content(scene.layout_type or "text_only", result["slide_content_json"])
                try:
                    current = json.loads(scene.slide_content_json) if scene.slide_content_json else {}
                except Exception:
                    current = {}
                merged = {**current, **norm_content}
                merged.setdefault("title", scene.title or current.get("title", ""))
                if current.get("summary"):
                    merged.setdefault("summary", current["summary"])
                scene.slide_content_json = json.dumps(merged, ensure_ascii=False)
                if result["narration_text"]:
                    scene.narration_text = result["narration_text"]
                await db.commit()
                bulk_content_job_store[job_id]["done"] = idx + 1

            bulk_content_job_store[job_id]["status"] = "completed"
        except Exception as e:
            bulk_content_job_store[job_id] = {"status": "error", "error": str(e)}


@router.post("/videos/{video_id}/scenes/generate-content-all/start")
async def start_generate_content_all(
    video_id: str,
    background_tasks: BackgroundTasks,
    only_empty: bool = True,
    db: AsyncSession = Depends(get_db)
):
    job_id = str(uuid.uuid4())
    bulk_content_job_store[job_id] = {
        "status": "processing",
        "done": 0,
        "total": 0,
        "current_title": "準備中...",
        "error": None
    }
    background_tasks.add_task(_run_bulk_generate_content, job_id, video_id, only_empty)
    return {"job_id": job_id}


@router.get("/scenes/generate-content-all/status/{job_id}")
async def get_generate_content_all_status(job_id: str):
    job = bulk_content_job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return job


