import uuid
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from sqlalchemy import delete as sa_delete
from core.database import get_db
from core.project_path import get_project_dir
from models.scenario import Scenario
from models.scene import Scene
from models.scene_asset import SceneAsset
from models.video import Video
from models.project import Project
from models.video_style import VideoStyle
from schemas.scenario import (
    ScenarioRead,
    FromTextRequest,
    ChatRequest,
    FinalizeRequest,
    ScenarioOutlineItem,
    PptxImportResult,
)
from services.llm_service import (
    extract_outline_proposal,
    generate_slide_narration,
    MAX_PASTE_CHARS,
    PROMPT_TOKENS_PER_SEC,
    TOKENS_PER_CHAR_JA,
    split_text_to_scenes,
    send_chat_message
)
from services.pptx_import import parse_pptx, SlideInfo
from layouts import _prompts, _types
from layouts import _registry as layouts
from layouts._types import CONTENT_TYPES

router = APIRouter(tags=["scenario"])

# PPTX 取り込み後のナレーション一括生成ジョブの進捗ストア（プロセス内メモリ、bulk_content_job_store と同じ方式）
pptx_narration_job_store: dict[str, dict] = {}


def _normalize_layout(raw: str) -> str:
    """見せ方の名前を実在するレイアウトに丸める。

    許可リストはここに持たない。layouts/ にディレクトリを置いた時点で
    使えるようになる（一覧を二重に持つと必ず片方が腐る）。
    """
    return layouts.normalize_layout_id(raw)


def _layout_for_outline(item, breadth: str | None = None) -> str:
    """アウトライン 1 件から、開始時点の見せ方を決める。

    段階 1 で決まるのは「型」なので、その型の代表レイアウトを置く。
    実際の見せ方は、シーン内容を生成したとき（段階 2・3）に
    件数を見てから確定する。
    """
    type_id = (item.content_type or "").strip()
    if type_id not in CONTENT_TYPES:
        # 古い形式（見せ方の名前が直接来る）からの後方互換
        type_id = layouts.type_of(item.layout_type) if item.layout_type else "statement"
    type_id = layouts.coerce_type(type_id, breadth)
    return _prompts.default_layout_for(type_id)

SYSTEM_PROMPT_C_TEMPLATE = """あなたは動画の構成を一緒に考えるアシスタントです。
ユーザーと対話しながら「どんな動画にするか」を整理し、動画の“章立て（アウトライン）”を作り上げます。
この段階ではナレーション本文やスライドの詳細は作りません。各シーンの「タイトル」と
「そのシーンで扱う内容のあらすじ（1〜2文）」、そして「情報の型」だけを決めます。
詳細な作り込みは後工程（シーン編集）で行います。

【対話の進め方】
- まずテーマ・対象視聴者・トーン・想定の長さなどを踏まえ、章立ての方針を自然文で提案・相談してください。
- ユーザーが「これで確定」「シーンにして」等と言ったとき、または構成が十分固まったと判断したときに、
  下記の JSON ブロックを返信に含めてください。

【シーン数の目安】
- 動画の想定長さに合わせてシーン数を決めます。1シーンあたり実尺およそ30〜45秒（ナレーション＋間＋図版）を目安に、
  10分の動画なら 14〜20 シーン程度を作ってください（内容が濃いテーマなら多めに分割し、深く掘り下げる）。
- 1つのシーンに詰め込みすぎず、話題ごとに分けてください。

【情報の型（content_type）】
そのシーンの内容が「どういう構造の情報か」を次から選んでください。
見た目（グラフか箇条書きか等）ではなく、情報の構造で選ぶことが重要です。

{type_menu}

- 同じ型が延々と続かないよう使い分けてください。ただし内容に合わない型を無理に混ぜないでください。
- 具体的な見せ方（何カラムで並べるか等）はここでは決めません。後工程が内容の分量を見て決めます。

【出力する JSON（アウトライン。これだけを ```json ブロックで囲む）】
```json
{{
  "scenes": [
    {{
      "index": 1,
      "title": "シーンのタイトル",
      "summary": "このシーンで扱う内容のあらすじを1〜2文で。",
      "content_type": "cover"
    }}
  ]
}}
```
- narration_text やスライドの詳細（bullet_points 等）はここでは絶対に出力しないでください（後工程で作ります）。
- 既に「現在のシーン構成」が提示されている場合は、それを土台に、ユーザーの指示に沿って
  追加・分割・統合・修正した“更新後の全シーンのアウトライン”を返してください（全シーンを省略せず列挙）。

JSON ブロックを返信に含めると、フロントに「この構成でシーンを作成」ボタンが表示されます。"""


def system_prompt_c(breadth: str | None = None) -> str:
    """チャットのシステムプロンプト。使える型は動画の「レイアウトの幅」設定で絞る。"""
    return SYSTEM_PROMPT_C_TEMPLATE.format(
        type_menu=_prompts.type_menu(layouts.allowed_types(breadth))
    )


# ─── ヘルパー関数 ─────────────────────────────────────────────

def _rule_based_split(text: str) -> list[dict]:
    """LLM なしでテキストをシーンに分割するルールベースの処理。

    分割優先順位:
    1. "---" / "===" 区切り行
    2. 見出しパターン（「■」「【】」「第N章」「# 」など）
    3. 2行以上の連続空行
    4. 1行の空行
    5. 句点「。」で終わる文のまとまり（約200〜400文字ごと）
    """
    text = text.strip()

    # 1. --- または === 区切り
    if re.search(r'\n[ \t]*(?:---+|===+)[ \t]*\n', text):
        blocks = re.split(r'\n[ \t]*(?:---+|===+)[ \t]*\n', text)
        return _blocks_to_scenes(blocks)

    # 2. 見出しパターン（行頭の記号や番号）
    heading_pattern = r'(?m)^(?=(?:#{1,3} |【|■|◆|●|第\d+|[一二三四五六七八九十]\d*[章節部]|\d+[\.\．]))'
    if len(re.findall(heading_pattern, text)) >= 2:
        blocks = re.split(heading_pattern, text)
        blocks = [b.strip() for b in blocks if b.strip()]
        if len(blocks) >= 2:
            return _blocks_to_scenes(blocks)

    # 3. 2行以上の空行
    blocks = re.split(r'\n{3,}', text)
    if len(blocks) >= 2:
        return _blocks_to_scenes(blocks)

    # 4. 1行の空行
    blocks = re.split(r'\n{2}', text)
    if len(blocks) >= 2:
        return _blocks_to_scenes(blocks)

    # 5. 句点区切り（約250文字ごとに1シーン）
    CHARS_PER_SCENE = 250
    sentences = re.split(r'(?<=。)', text)
    scenes = []
    idx = 1
    current = ""
    for sent in sentences:
        current += sent
        if len(current) >= CHARS_PER_SCENE:
            scenes.append({"index": idx, "title": f"シーン {idx}", "narration": current.strip()})
            idx += 1
            current = ""
    if current.strip():
        scenes.append({"index": idx, "title": f"シーン {idx}", "narration": current.strip()})

    if len(scenes) >= 2:
        return scenes

    # 最終フォールバック: 全体を1シーンとして返す
    return [{"index": 1, "title": "シーン 1", "narration": text}]


def _blocks_to_scenes(blocks: list[str]) -> list[dict]:
    """テキストブロックのリストを scenes dict のリストに変換する共通ヘルパー。"""
    scenes = []
    idx = 1
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines:
            continue

        # 最初の行が短い（見出しらしい）ならタイトルとして使う
        first_line = lines[0].strip()
        # 見出し記号を除去してタイトルにする
        clean_title = re.sub(r'^[#■◆●【〔\d\.\s]+|[】〕]+$', '', first_line).strip()
        if clean_title and len(clean_title) <= 60 and len(lines) > 1:
            title = clean_title or f"シーン {idx}"
            narration = '\n'.join(lines[1:]).strip()
        else:
            title = f"シーン {idx}"
            narration = block

        scenes.append({"index": idx, "title": title, "narration": narration})
        idx += 1

    return scenes if scenes else [{"index": 1, "title": "シーン 1", "narration": "\n".join(blocks)}]


async def get_layout_breadth(video_id: str, db: AsyncSession) -> str | None:
    """動画の「レイアウトの幅」設定を引く。

    未設定（NULL）なら None を返し、レジストリ側の既定（standard）に委ねる。
    ここで既定値を書かないこと。既定を持つ場所は layouts/_registry.py だけにする。
    """
    stmt = select(VideoStyle.layout_breadth).where(VideoStyle.video_id == video_id)
    return (await db.execute(stmt)).scalars().first()


def map_outline_item(scenario_id: str, item: ScenarioOutlineItem, index: int,
                     existing: Scene | None = None, breadth: str | None = None) -> Scene:
    """アウトライン 1 件からスケルトンシーンを作る。
    existing に深堀り済みシーンが渡された場合は、その成果（ナレーション・カスタムHTML等）を保持し、
    タイトルとあらすじだけ更新する（確定を繰り返しても作り込みが消えないように）。"""
    layout_type = _layout_for_outline(item, breadth)
    summary = item.summary or ""

    has_work = bool(existing and ((existing.narration_text or "").strip() or (existing.custom_html or "").strip()))
    if has_work:
        # 既に作り込み済み: 中身は保持し、意図（title/あらすじ）だけ最新化
        existing.index = index
        existing.title = item.title or existing.title
        existing.outline_summary = summary or existing.outline_summary
        return existing

    # スケルトン（新規、または未着手の既存）: あらすじを型に合う場所へ流し込む。
    # 固有の内容は「AI でシーン内容を生成」で埋まる。それまでの間も
    # あらすじが表示されるので、真っ白なスライドにはならない。
    type_id = layouts.type_of(layout_type)
    content = _types.normalize(type_id, {"title": item.title or ""})
    _types.fill_from_summary(type_id, content, summary)

    scene = existing or Scene(scenario_id=scenario_id, index=index)
    scene.index = index
    scene.title = item.title or f"シーン {index}"
    scene.layout_type = layout_type
    scene.slide_content_json = json.dumps(content, ensure_ascii=False)
    scene.narration_text = scene.narration_text or ""  # 空のまま（深堀りで生成）
    scene.outline_summary = summary
    return scene


async def delete_existing_scenario(video_id: str, db: AsyncSession):
    """ビデオに紐づく既存のシナリオ・シーン・シーンアセット（DB行＋実ファイル）を一括削除する。

    Scene の cascade="all, delete-orphan" は ORM の一括 DELETE では発火しないため、
    scene_assets は明示的に取得してファイル実体ごと削除する（さもないと再取り込みのたびに孤児化する）。
    """
    stmt = select(Scenario).where(Scenario.video_id == video_id)
    scenario = (await db.execute(stmt)).scalars().first()
    if not scenario:
        return

    stmt_v = select(Video, Project).join(Project, Video.project_id == Project.id).where(Video.id == video_id)
    row = (await db.execute(stmt_v)).first()
    if row:
        video, project = row
        video_dir = get_project_dir(project) / "videos" / video.id
        stmt_assets = (
            select(SceneAsset)
            .join(Scene, SceneAsset.scene_id == Scene.id)
            .where(Scene.scenario_id == scenario.id)
        )
        assets = (await db.execute(stmt_assets)).scalars().all()
        for asset in assets:
            if asset.file_path:
                fp = video_dir / asset.file_path
                if fp.exists():
                    fp.unlink()
        await db.execute(
            sa_delete(SceneAsset).where(
                SceneAsset.scene_id.in_(select(Scene.id).where(Scene.scenario_id == scenario.id))
            )
        )

    # 非同期環境での lazy load を避けるため、シーンを先に直接 DELETE してからシナリオを削除
    await db.execute(sa_delete(Scene).where(Scene.scenario_id == scenario.id))
    await db.execute(sa_delete(Scenario).where(Scenario.id == scenario.id))
    await db.flush()


def _slide_visual_summary(slide: SlideInfo) -> str:
    if not slide.visuals:
        return ""
    kinds = {"raster": "写真・図版", "vector": "図解"}
    parts = [kinds.get(v.kind, v.kind) for v in slide.visuals]
    return "、".join(parts) + "が含まれる"


def _slide_table_summary(slide: SlideInfo) -> str:
    if not slide.table:
        return ""
    headers = slide.table.get("headers", [])
    rows = slide.table.get("rows", [])
    return f"見出し: {', '.join(headers)}（{len(rows)}行）"


def _slide_to_content(slide: SlideInfo) -> dict:
    """SlideInfo を slide_content_json に変換する（1スライド=1シーン）。

    PPTX から取れるのは「見出し・箇条書き・本文・表・画像」だけなので、
    ここでは素直にその形で詰め、型のスキーマへの整形は
    _types.normalize() に任せる（旧キーもそこで吸収される）。
    """
    raw: dict = {
        "title": slide.title or f"スライド {slide.index}",
        "image_position": slide.image_position,
    }
    if slide.bullets:
        raw["bullet_points"] = slide.bullets[:6]
    if slide.table:
        raw["headers"] = slide.table.get("headers", [])
        raw["rows"] = slide.table.get("rows", [])
    if slide.body_text:
        raw["body"] = slide.body_text
        raw["subtitle"] = slide.body_text
    elif slide.bullets:
        raw["subtitle"] = slide.bullets[0]

    layout_type = _normalize_layout(slide.layout_type)
    return _types.normalize(layouts.type_of(layout_type), raw)


def _save_slide_visuals(slide: SlideInfo, scene_id: str, scene_index: int, video_dir: Path) -> list[SceneAsset]:
    """スライドのビジュアルを assets/images/scene_{index}/slot{n}.* に保存し、SceneAsset を作る。

    パス規約は routers/assets.py の手動アップロードと完全に揃える（差し替えUIがそのまま使えるように）。
    """
    if not slide.visuals:
        return []
    asset_dir = video_dir / "assets/images" / f"scene_{scene_index}"
    asset_dir.mkdir(parents=True, exist_ok=True)

    default_config = {
        "offset_sec": 0.5, "duration_sec": None, "x": "center", "y": "center",
        "max_width": "600px", "max_height": "500px", "border_radius": "16px",
    }

    assets = []
    for slot, visual in enumerate(slide.visuals, start=1):
        file_rel_path = f"assets/images/scene_{scene_index}/slot{slot}{visual.ext}"
        dest_path = video_dir / file_rel_path
        dest_path.write_bytes(visual.data)
        assets.append(SceneAsset(
            scene_id=scene_id,
            slot=slot,
            asset_type="image",
            file_path=file_rel_path,
            svg_content=None,
            display_config_json=json.dumps(default_config),
        ))
    return assets


async def _run_pptx_narration_job(job_id: str, scenario_id: str, slides: list[SlideInfo]):
    """PPTX 取り込み後、シーンごとに1回ずつ LLM を呼んでナレーションを生成するバックグラウンドジョブ。

    1スライドの LLM 呼び出しが失敗しても他のシーンには影響しない
    （そのシーンのナレーションが空のまま残るだけ）。
    """
    from core.database import AsyncSessionLocal
    total = len(slides)
    pptx_narration_job_store[job_id] = {"status": "processing", "done": 0, "total": total, "current_title": "", "error": None}

    async with AsyncSessionLocal() as db:
        stmt_scenes = select(Scene).where(Scene.scenario_id == scenario_id).order_by(Scene.index)
        scenes = {s.index: s for s in (await db.execute(stmt_scenes)).scalars().all()}

        prev_title = ""
        for slide in slides:
            scene = scenes.get(slide.index)
            pptx_narration_job_store[job_id]["current_title"] = slide.title or f"スライド {slide.index}"
            if scene is not None and not (scene.narration_text or "").strip():
                try:
                    narration = await generate_slide_narration(
                        slide_title=slide.title,
                        bullets=slide.bullets,
                        table_summary=_slide_table_summary(slide),
                        visual_summary=_slide_visual_summary(slide),
                        notes=slide.notes,
                        prev_title=prev_title,
                    )
                    scene.narration_text = narration
                    await db.commit()
                except Exception as e:
                    print(f"[pptx_narration] slide {slide.index} 失敗: {e}")
            prev_title = slide.title or prev_title
            pptx_narration_job_store[job_id]["done"] += 1

        pptx_narration_job_store[job_id]["status"] = "completed"


# ─── エンドポイント実装 ─────────────────────────────────────────

@router.get("/videos/{video_id}/scenario", response_model=ScenarioRead | None)
async def get_scenario(video_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.video_id == video_id)
    scenario = (await db.execute(stmt)).scalars().first()
    return scenario

@router.get("/videos/{video_id}/scenario/from-pptx/status/{job_id}")
async def get_pptx_import_status(video_id: str, job_id: str):
    job = pptx_narration_job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return job

@router.post("/videos/{video_id}/scenario/from-pptx", response_model=PptxImportResult)
async def from_pptx(
    video_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # 動画・プロジェクトの存在チェック
    stmt_v = select(Video, Project).join(Project, Video.project_id == Project.id).where(Video.id == video_id)
    row = (await db.execute(stmt_v)).first()
    if not row:
        raise HTTPException(status_code=404, detail="ビデオが見つかりません")
    video, project = row

    if not (file.filename or "").lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="PPTX ファイル（.pptx）を選択してください")

    video_dir = get_project_dir(project) / "videos" / video.id
    source_dir = video_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = source_dir / file.filename
    with open(pptx_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    workdir = Path("/tmp/heygen_pptx") / uuid.uuid4().hex
    try:
        slides, warnings = parse_pptx(pptx_path, workdir)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PPTX の解析に失敗しました: {e}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if not slides:
        raise HTTPException(status_code=400, detail="有効なスライドが見つかりませんでした")

    # 既存シナリオ・シーン・アセットの削除
    await delete_existing_scenario(video_id, db)

    # シナリオの作成
    scenario = Scenario(
        video_id=video_id,
        source_type="pptx",
        source_content=file.filename
    )
    db.add(scenario)
    await db.flush()

    visual_count = 0
    for slide in slides:
        content = _slide_to_content(slide)
        scene = Scene(
            scenario_id=scenario.id,
            index=slide.index,
            title=slide.title or f"スライド {slide.index}",
            layout_type=_normalize_layout(slide.layout_type),
            slide_content_json=json.dumps(content, ensure_ascii=False),
            narration_text=(slide.notes if slide.notes and len(slide.notes.strip()) >= 20 else ""),
            outline_summary=(slide.title + "。" + "、".join(slide.bullets[:2]))[:120],
        )
        db.add(scene)
        await db.flush()

        for asset in _save_slide_visuals(slide, scene.id, slide.index, video_dir):
            db.add(asset)
        visual_count += len(slide.visuals)

        warnings.extend(f"スライド{slide.index}: {w}" for w in slide.warnings)

    await db.flush()

    job_id = str(uuid.uuid4())
    background_tasks.add_task(_run_pptx_narration_job, job_id, scenario.id, slides)

    return PptxImportResult(
        scenario=scenario,
        job_id=job_id,
        slide_count=len(slides),
        scene_count=len(slides),
        visual_count=visual_count,
        warnings=warnings,
    )

@router.get("/scenario/paste-limits")
async def paste_limits():
    """テキスト貼り付けの上限と、待ち時間を見積もるための係数を返す。

    画面側に数値を直書きすると必ずサーバーとずれるため、ここを唯一の正とする。
    （背景モチーフやレイアウトの選択肢を /style-options や /layouts が
      配っているのと同じ考え方。）
    """
    return {
        "max_chars": MAX_PASTE_CHARS,
        "tokens_per_char": TOKENS_PER_CHAR_JA,
        "prompt_tokens_per_sec": PROMPT_TOKENS_PER_SEC,
    }


@router.post("/videos/{video_id}/scenario/from-text", response_model=ScenarioRead)
async def from_text(
    video_id: str,
    payload: FromTextRequest,
    db: AsyncSession = Depends(get_db)
):
    # 動画の存在チェック
    stmt_v = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt_v)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="ビデオが見つかりません")

    # Route B もチャットと同じ 2 段階にする。ここで作るのは章立てだけで、
    # スライドの中身とナレーションは後続の一括生成（generate-content-all）が
    # 型ごとの専用プロンプトで深掘りする。
    # 長すぎる貼り付けはここで明確に断る。
    # 以前は上限が無く、そのまま LLM へ投げていたため、コンテキストを超えると
    # 「ローカル LLM の呼び出しに失敗しました」としか出ず原因が分からなかった。
    # なお通常の長さ（数千〜数万字）は弾かない。長いと遅いことは画面側が
    # 文字数と目安時間で伝える。
    if len(payload.text) > MAX_PASTE_CHARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"貼り付けたテキストが長すぎます（{len(payload.text):,} 文字）。"
                f"{MAX_PASTE_CHARS:,} 文字以下に分けてから実行してください。"
            ),
        )

    breadth = await get_layout_breadth(video_id, db)
    outline = None
    try:
        llm_response = await split_text_to_scenes(payload.text, breadth)
        outline = extract_outline_proposal(llm_response)
        if outline:
            print(f"[from_text] LLM 分割成功: {len(outline.scenes)} シーン")
        else:
            print("[from_text] LLM レスポンスのパースに失敗、ルールベース分割にフォールバック")
            print(f"[from_text] LLM raw response (先頭500文字): {llm_response[:500]}")
    except Exception as e:
        print(f"[from_text] LLM 呼び出し失敗、ルールベース分割にフォールバック: {e}")

    # 既存シナリオ・シーンの削除
    await delete_existing_scenario(video_id, db)

    # シナリオの作成
    scenario = Scenario(
        video_id=video_id,
        source_type="paste",
        source_content=payload.text
    )
    db.add(scenario)
    await db.flush()

    # シーンの展開: LLM 提案があればそれを使用、なければルールベース分割
    if outline and outline.scenes:
        for i, item in enumerate(outline.scenes, start=1):
            db.add(map_outline_item(scenario.id, item, index=i, breadth=breadth))
    else:
        for sd in _rule_based_split(payload.text):
            scene = Scene(
                scenario_id=scenario.id,
                index=sd["index"],
                title=sd["title"],
                layout_type="text_only",
                slide_content_json=json.dumps(
                    {"title": sd["title"], "body": ""}, ensure_ascii=False
                ),
                narration_text=sd["narration"],
            )
            db.add(scene)
    await db.flush()

    return scenario

@router.post("/videos/{video_id}/scenario/chat")
async def chat(
    video_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    # 動画の存在チェック
    stmt_v = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt_v)).scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="ビデオが見つかりません")

    # 既存シナリオの取得、または新規作成
    stmt_s = select(Scenario).where(Scenario.video_id == video_id)
    scenario = (await db.execute(stmt_s)).scalars().first()
    if not scenario:
        scenario = Scenario(
            video_id=video_id,
            source_type="chat",
            chat_messages=json.dumps([])
        )
        db.add(scenario)
        await db.flush()
        
    messages = json.loads(scenario.chat_messages or "[]")
    if not messages:
        breadth = await get_layout_breadth(video_id, db)
        messages.append({"role": "system", "content": system_prompt_c(breadth)})

    # 現在のシーン構成を LLM に最新状態として渡す（確定後の修正フローに対応）
    stmt_scenes = select(Scene).where(Scene.scenario_id == scenario.id).order_by(Scene.index)
    current_scenes = (await db.execute(stmt_scenes)).scalars().all()
    if current_scenes:
        lines = [
            f'{s.index}. {s.title or "無題"} — {s.outline_summary or (s.narration_text or "")[:40]}'
            for s in current_scenes
        ]
        context_msg = "【現在のシーン構成】\n" + "\n".join(lines)
        # 直近の system 文脈として毎回入れ替える（重複を避けるため既存の同種は除去）
        messages = [m for m in messages if not (m.get("role") == "system" and m.get("content", "").startswith("【現在のシーン構成】"))]
        messages.append({"role": "system", "content": context_msg})
        
    messages.append({"role": "user", "content": payload.message})
    
    reply = await send_chat_message(messages)
        
    proposal = extract_outline_proposal(reply)
    
    # 履歴を更新して保存
    messages.append({"role": "assistant", "content": reply})
    scenario.chat_messages = json.dumps(messages, ensure_ascii=False)
    await db.flush()
    
    return {
        "reply": reply,
        "proposal": proposal.model_dump() if proposal else None
    }

@router.post("/videos/{video_id}/scenario/finalize", response_model=ScenarioRead)
async def finalize_scenario(
    video_id: str,
    payload: FinalizeRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt_s = select(Scenario).where(Scenario.video_id == video_id)
    scenario = (await db.execute(stmt_s)).scalars().first()
    if not scenario:
        scenario = Scenario(
            video_id=video_id,
            source_type="chat",
            chat_messages=json.dumps([])
        )
        db.add(scenario)
        await db.flush()

    # 既存シーンを index -> Scene で引けるように取得
    stmt_scenes = select(Scene).where(Scene.scenario_id == scenario.id)
    existing_scenes = (await db.execute(stmt_scenes)).scalars().all()
    by_index = {s.index: s for s in existing_scenes}

    breadth = await get_layout_breadth(video_id, db)
    new_count = len(payload.scenes)
    for i, item in enumerate(payload.scenes, start=1):
        existing = by_index.get(i)
        scene = map_outline_item(scenario.id, item, index=i, existing=existing, breadth=breadth)
        if existing is None:
            db.add(scene)
    # アウトラインより多い余剰シーンは削除
    for idx, s in by_index.items():
        if idx > new_count:
            await db.delete(s)

    await db.flush()
    return scenario
