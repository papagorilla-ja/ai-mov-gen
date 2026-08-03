import asyncio
import json
import shutil
import traceback
import wave
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy.future import select

from core.config import settings
from core.database import AsyncSessionLocal
from core.project_path import get_project_dir
from models.generation_history import GenerationHistory
from models.project import Project
from models.scenario import Scenario
from models.scene import Scene
from models.scene_asset import SceneAsset
from models.scene_tts_cache import SceneTtsCache
from models.speaker import Speaker
from models.video import Video
from models.video_style import VideoStyle
from services.composition import (
    TRANSITION_BUFFER,
    find_missing_css_refs,
    find_missing_local_refs,
    generate_composition,
)
from services.tts_service import (
    compute_tts_hash,
    derive_seed,
    ensure_tts_ready,
    synthesize_scene_audio,
)

TEMPLATES_BLANK_DIR = Path("/app/templates/blank")

def get_wav_duration(file_path: Path) -> float:
    with wave.open(str(file_path), "rb") as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)

async def request_render(
    video_dir: str,
    output_rel: str,
    fps: int,
    workers: int,
    renderer_timeout: float,
    log,
) -> None:
    """ホストのレンダラーサーバーに 1 本分のレンダリングを依頼する。"""
    # ─── 参照ファイルの実在確認 ───────────────────────────────
    # hyperframes は JS/CSS が 404 でもエラーを返さず完走し、
    # 「アニメーションが一切効いていない静止画の動画」を出力してしまう。
    # 無言で壊れた動画を作らないよう、依頼前にここで止める。
    missing = find_missing_local_refs(Path(video_dir) / "index.html")
    critical = [m for m in missing if m.endswith((".js", ".css")) or m == "index.html"]
    if critical:
        raise RuntimeError(
            "レンダリングに必要なファイルが見つかりません: "
            f"{', '.join(critical)}（対象ディレクトリ: {video_dir}）"
        )
    if missing:
        log(f"警告: 参照先が見つからないメディアがあります（そのまま続行します）: {', '.join(missing)}")

    # style.css が読む同梱フォントも 404 が無言で通る。
    # 欠けるとシステムフォントに差し替わり、指定した書体と違う動画が出来上がる。
    missing_css = find_missing_css_refs(Path(video_dir) / "style.css")
    if missing_css:
        log(f"警告: フォント等の参照先が見つかりません（既定の書体で続行します）: {', '.join(missing_css)}")

    payload = {
        "video_dir": video_dir,
        "output_path": output_rel,
        "timeout": int(renderer_timeout),
        "fps": fps,
    }
    if workers > 0:
        payload["workers"] = workers

    async with httpx.AsyncClient(timeout=renderer_timeout) as client:
        resp = await client.post(f"{settings.renderer_base_url}/render", json=payload)
        resp.raise_for_status()
        res_data = resp.json()
        if res_data.get("status") != "success":
            raise RuntimeError(
                f"HyperFrames rendering failed: {res_data.get('stderr') or res_data.get('message')}"
            )
        stdout = (res_data.get("stdout") or "").strip()
        if stdout:
            log(f"HyperFrames stdout: {stdout[-500:]}")


def split_scenes_into_chunks(scenes: list[Scene], chunk_sec: int) -> list[list[Scene]]:
    """シーン境界で、1 チャンクの尺が chunk_sec を超えないように分割する。

    1 シーンだけで chunk_sec を超える場合はそのシーン単体で 1 チャンクにする
    （シーンの途中で切ると音声とアニメーションがずれるため分割しない）。
    chunk_sec <= 0 なら分割しない。
    """
    if chunk_sec <= 0 or not scenes:
        return [list(scenes)]

    chunks: list[list[Scene]] = []
    current: list[Scene] = []
    current_sec = 0.0
    for scene in scenes:
        dur = (scene.narration_audio_duration or 0.0) + TRANSITION_BUFFER
        if current and current_sec + dur > chunk_sec:
            chunks.append(current)
            current = []
            current_sec = 0.0
        current.append(scene)
        current_sec += dur
    if current:
        chunks.append(current)
    return chunks


async def render_in_chunks(
    video: Video,
    style: VideoStyle,
    chunks: list[list[Scene]],
    assets_map: dict,
    video_dir: Path,
    output_path: Path,
    fps: int,
    workers: int,
    renderer_timeout: float,
    broadcast_fn,
    log,
) -> None:
    """チャンクごとにレンダリングし、ffmpeg で 1 本に連結する。"""
    chunk_root = video_dir / "_chunks"
    if chunk_root.exists():
        shutil.rmtree(chunk_root, ignore_errors=True)
    chunk_root.mkdir(parents=True, exist_ok=True)

    part_paths: list[Path] = []
    try:
        for i, chunk_scenes in enumerate(chunks, start=1):
            chunk_dir = chunk_root / f"chunk{i}"
            chunk_dir.mkdir(parents=True, exist_ok=True)

            # 音声などのアセットはシンボリックリンクで共有する（コピーしない）。
            # コンポジション内の参照は assets/audio/sceneN.wav の相対パスのままでよい。
            #
            # リンク先は必ず「相対パス」にすること。レンダリングはホスト側プロセスが行うため、
            # コンテナ内の絶対パス（/app/projects/...）で張るとホストから辿れなくなる。
            # chunk_dir は <video_dir>/_chunks/chunkN なので assets は 2 階層上にある。
            # 同梱フォント (1ファイル 2MB 超) も同じ理由でリンク共有する。
            # チャンクごとにコピーするとレンダリングのたびに数十MBの無駄が出る。
            for link_name in ("assets", "fonts"):
                link = chunk_dir / link_name
                if not link.is_symlink() and not link.exists():
                    link.symlink_to(Path(f"../../{link_name}"), target_is_directory=True)

            # generate_composition は渡されたシーンだけで 0 秒からタイムラインを組み直すため、
            # チャンク単体で正しい尺の動画になる
            generate_composition(
                video, chunk_scenes, style, TEMPLATES_BLANK_DIR, chunk_dir, assets_map, fps=fps
            )

            progress = 0.8 + 0.15 * (i / len(chunks))
            await broadcast_fn(
                "rendering", progress, f"レンダリング中... ({i}/{len(chunks)})", None
            )
            log(f"チャンク {i}/{len(chunks)}: {len(chunk_scenes)} シーンをレンダリング中...")

            await request_render(
                video_dir=str(chunk_dir),
                output_rel="part.mp4",
                fps=fps,
                workers=workers,
                renderer_timeout=renderer_timeout,
                log=log,
            )
            part = chunk_dir / "part.mp4"
            if not part.exists():
                raise RuntimeError(f"チャンク {i} の出力が見つかりません: {part}")
            part_paths.append(part)

        # ─── ffmpeg concat で連結 ────────────────────────────────
        # 全チャンクは同じ設定でエンコードされているため再エンコード不要（-c copy）
        list_file = chunk_root / "parts.txt"
        list_file.write_text(
            "".join(f"file '{p}'\n" for p in part_paths), encoding="utf-8"
        )
        log(f"{len(part_paths)} 個のチャンクを連結しています...")
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(output_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not output_path.exists():
            raise RuntimeError(
                f"チャンクの連結に失敗しました: {stderr.decode(errors='replace')[-500:]}"
            )
        log("チャンクの連結が完了しました。")
    finally:
        shutil.rmtree(chunk_root, ignore_errors=True)


async def purge_scene_audio(db, scenes: list[Scene], audio_dir: Path, log) -> int:
    """既存のナレーション音声と TTS キャッシュを削除する（音声再作成オプション用）。

    キャッシュ判定は参照音声の「パス」を含むため、同じ話者の参照音声を録り直しても
    パスが変わらずキャッシュが効き続ける。ここで明示的に破棄することで、
    確実に全シーンを合成し直せるようにする。
    """
    scene_ids = [s.id for s in scenes]
    stmt_cache = select(SceneTtsCache).where(SceneTtsCache.scene_id.in_(scene_ids))
    cache_rows = (await db.execute(stmt_cache)).scalars().all()

    removed_files = 0
    # キャッシュが指す WAV と、シーンが参照する WAV の両方を削除する
    for row in cache_rows:
        p = Path(row.audio_path)
        if p.exists():
            p.unlink()
            removed_files += 1
        await db.delete(row)

    for scene in scenes:
        wav_path = audio_dir / f"scene{scene.index}.wav"
        if wav_path.exists():
            wav_path.unlink()
            removed_files += 1
        scene.narration_audio_path = None
        scene.narration_audio_duration = None

    await db.flush()
    log(f"音声再作成: 既存のキャッシュ {len(cache_rows)} 件 / 音声ファイル {removed_files} 件を削除しました")
    return len(cache_rows)


async def run_generation(video_id: str, generation_id: str, broadcast_fn, regenerate_audio: bool = False):
    async with AsyncSessionLocal() as db:
        stmt_v = select(Video).where(Video.id == video_id)
        video = (await db.execute(stmt_v)).scalars().first()
        if not video:
            print(f"Video {video_id} not found")
            return

        stmt_p = select(Project).where(Project.id == video.project_id)
        project = (await db.execute(stmt_p)).scalars().first()
        
        stmt_style = select(VideoStyle).where(VideoStyle.video_id == video_id)
        style = (await db.execute(stmt_style)).scalars().first()
        if not style:
            style = VideoStyle(video_id=video_id)
            db.add(style)
            await db.flush()

        stmt_scenario = select(Scenario).where(Scenario.video_id == video_id)
        scenario = (await db.execute(stmt_scenario)).scalars().first()
        if not scenario:
            scenario = Scenario(video_id=video_id, source_type="paste")
            db.add(scenario)
            await db.flush()

        stmt_scenes = select(Scene).where(Scene.scenario_id == scenario.id).order_by(Scene.index)
        scenes = list((await db.execute(stmt_scenes)).scalars().all())

        stmt_history = select(GenerationHistory).where(GenerationHistory.id == generation_id)
        history = (await db.execute(stmt_history)).scalars().first()
        if not history:
            print(f"GenerationHistory {generation_id} not found")
            return

        video.status = "generating"
        history.status = "running"
        await db.commit()

        video_dir = get_project_dir(project) / "videos" / video.id
        video_dir.mkdir(parents=True, exist_ok=True)
        audio_dir = video_dir / "assets/audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        logs = []
        def log(msg):
            print(msg)
            logs.append(f"[{datetime.now().isoformat()}] {msg}")

        try:
            # ─── ステップ1: 音声合成 ──────────────────────────────────
            # コンポジションより先に音声を作り、実際の尺を確定させる。
            # （旧実装は仮の尺で HTML を組んでから build_timeline.py で計算し直しており、
            #   同じ計算が2箇所に存在し、初回と2回目でアニメーションの速さが変わっていた）
            log("ステップ1: 音声合成を開始...")
            await broadcast_fn("tts", 0.05, "ナレーション音声を合成中...", None)

            total_scenes = len(scenes)

            if total_scenes == 0:
                raise ValueError("合成するシーンがありません。シーンを追加してください。")

            # 音声再作成オプション: 既存音声とキャッシュを破棄してから合成し直す
            if regenerate_audio:
                # 削除する前に必ず TTS が使えることを確認する。
                # 確認せずに削除すると、TTS が停止していた場合に既存の音声を失った
                # うえで合成にも失敗し、動画に使える音声が何も残らなくなる。
                await broadcast_fn("tts", 0.03, "TTSサーバーを確認しています...", None)
                await ensure_tts_ready()
                log("TTSサーバーの稼働を確認しました。既存の音声を削除します。")

                await broadcast_fn("tts", 0.05, "既存の音声を削除しています...", None)
                await purge_scene_audio(db, scenes, audio_dir, log)

            # 動画 ID から決定的にシードを導出する。
            # 同じ原稿からは常に同じ音声が得られ、声質のブレも防げる。
            seed = derive_seed(video.id)
            empty_narration_count = 0

            # シーンごとのキャッシュエントリを一括取得
            scene_ids = [s.id for s in scenes]
            stmt_cache = select(SceneTtsCache).where(SceneTtsCache.scene_id.in_(scene_ids))
            cache_rows = (await db.execute(stmt_cache)).scalars().all()
            cache_map: dict[str, SceneTtsCache] = {c.scene_id: c for c in cache_rows}

            skipped_count = 0

            for idx, scene in enumerate(scenes, start=1):
                text = scene.narration_text or " "

                # ─── 話者 A を解決 ──────────────────────────────────────
                speaker_a = None
                if scene.speaker_id:
                    stmt_sp = select(Speaker).where(Speaker.id == scene.speaker_id)
                    speaker_a = (await db.execute(stmt_sp)).scalars().first()
                elif style.default_speaker_id:
                    stmt_sp = select(Speaker).where(Speaker.id == style.default_speaker_id)
                    speaker_a = (await db.execute(stmt_sp)).scalars().first()

                speaker_a_id_for_hash = scene.speaker_id or style.default_speaker_id
                ref_path_a_for_hash = speaker_a.reference_audio_path if speaker_a else None

                # ─── chat_dialog の行リストを取得 ───────────────────────
                dialog_lines = []
                if scene.layout_type == "chat_dialog" and scene.slide_content_json:
                    try:
                        content_data = json.loads(scene.slide_content_json)
                        dialog_lines = content_data.get("lines", [])
                    except Exception:
                        dialog_lines = []

                # ─── 話者 B を解決（chat_dialog のみ） ──────────────────
                speaker_b = None
                speaker_b_id_for_hash = None
                ref_path_b_for_hash = None
                if dialog_lines:
                    if scene.speaker_b_id:
                        stmt_sp_b = select(Speaker).where(Speaker.id == scene.speaker_b_id)
                        speaker_b = (await db.execute(stmt_sp_b)).scalars().first()
                    elif style.default_speaker_b_id:
                        stmt_sp_b = select(Speaker).where(Speaker.id == style.default_speaker_b_id)
                        speaker_b = (await db.execute(stmt_sp_b)).scalars().first()
                    speaker_b_id_for_hash = scene.speaker_b_id or style.default_speaker_b_id
                    ref_path_b_for_hash = speaker_b.reference_audio_path if speaker_b else None

                current_hash = compute_tts_hash(
                    text=text,
                    speaker_a_id=speaker_a_id_for_hash,
                    ref_path_a=ref_path_a_for_hash,
                    dialog_lines=dialog_lines,
                    speaker_b_id=speaker_b_id_for_hash,
                    ref_path_b=ref_path_b_for_hash,
                    slide_content_json=scene.slide_content_json
                )

                cached = cache_map.get(scene.id)
                wav_path = audio_dir / f"scene{scene.index}.wav"

                if (
                    cached is not None
                    and cached.narration_hash == current_hash
                    and Path(cached.audio_path).exists()
                ):
                    # ─── キャッシュヒット: WAV を再利用 ──────────────────
                    log(f"シーン {idx}/{total_scenes}: キャッシュ利用（スキップ）")
                    await broadcast_fn(
                        "tts",
                        0.05 + (0.6 * (idx / total_scenes)),
                        f"シーン {idx}/{total_scenes} はキャッシュを使用（スキップ）",
                        None
                    )
                    cached_wav = Path(cached.audio_path)
                    if cached_wav != wav_path and cached_wav.exists():
                        shutil.copy2(str(cached_wav), str(wav_path))
                    skipped_count += 1
                else:
                    # ─── キャッシュミス: TTS で再合成 ────────────────────
                    if not (scene.narration_text or "").strip() and not dialog_lines:
                        empty_narration_count += 1
                        log(
                            f"シーン {idx}/{total_scenes}: "
                            "ナレーションが未入力のため 2.0秒の無音を挿入します"
                        )

                    log(f"シーン {idx}/{total_scenes} の音声を合成中...")
                    await broadcast_fn(
                        "tts",
                        0.05 + (0.6 * (idx / total_scenes)),
                        f"シーン {idx}/{total_scenes} の音声を合成中...",
                        None
                    )

                    tts_stats: dict = {}
                    await synthesize_scene_audio(
                        text=text,
                        dialog_lines=dialog_lines,
                        speaker_a=speaker_a,
                        speaker_b=speaker_b,
                        output_wav_path=wav_path,
                        seed=seed,
                        stats=tts_stats,
                    )
                    if tts_stats:
                        log(
                            f"  TTS: チャンク {tts_stats.get('chunks')} / "
                            f"リトライ {tts_stats.get('retries')} / "
                            f"品質低下 {tts_stats.get('degraded')} / "
                            f"所要 {tts_stats.get('generate_sec')}秒"
                        )

                    # キャッシュを更新（upsert）
                    if cached is not None:
                        cached.narration_hash = current_hash
                        cached.audio_path = str(wav_path)
                    else:
                        new_cache = SceneTtsCache(
                            scene_id=scene.id,
                            narration_hash=current_hash,
                            audio_path=str(wav_path),
                        )
                        db.add(new_cache)

                # WAV が確定したのでメタデータを更新
                if wav_path.exists():
                    duration = get_wav_duration(wav_path)
                else:
                    duration = 0.0

                scene.narration_audio_path = str(wav_path)
                scene.narration_audio_duration = duration
                log(f"シーン {idx} の音声長: {duration:.2f}秒")

            log(f"音声合成完了: {total_scenes - skipped_count} シーンを合成、{skipped_count} シーンをスキップ")
            if empty_narration_count:
                log(f"ナレーション未入力: {empty_narration_count} シーン（2.0秒の無音になっています）")

            # composition が確定した音声尺を読めるようにフラッシュする
            await db.flush()

            # ─── ステップ2: コンポジション ────────────────────────────
            # 実際の音声尺だけを使って index.html を 1 回で完成させる。
            # タイムラインの計算はここが唯一の場所。
            log("ステップ2: コンポジションの生成を開始...")
            await broadcast_fn("composition", 0.7, "コンポジションを生成中...", None)

            stmt_assets = select(SceneAsset).where(
                SceneAsset.scene_id.in_([s.id for s in scenes])
            )
            all_assets = (await db.execute(stmt_assets)).scalars().all()
            assets_map = {}
            for a in all_assets:
                assets_map.setdefault(a.scene_id, []).append(a)

            # generate_composition が scene.data_start / scene.data_duration /
            # video.duration_sec を設定するため、HTML を読み直す必要はない
            render_fps = int(getattr(settings, "default_fps", 24) or 24)
            generate_composition(
                video, scenes, style, TEMPLATES_BLANK_DIR, video_dir, assets_map, fps=render_fps
            )
            await db.commit()
            log(f"コンポジションを書き出しました。合計尺: {video.duration_sec:.2f}秒 "
                f"({video.duration_sec / 60:.1f}分)")

            log("ステップ3: HyperFrames レンダリングを開始...")
            await broadcast_fn("rendering", 0.8, "動画をレンダリング中...", None)

            output_path = video_dir / f"output/{generation_id}.mp4"
            output_path.parent.mkdir(exist_ok=True)

            renderer_timeout = float(getattr(settings, "renderer_request_timeout", 3600))
            render_workers = int(getattr(settings, "render_workers", 0) or 0)
            chunk_sec = int(getattr(settings, "render_chunk_sec", 0) or 0)
            total_duration = video.duration_sec or 0.0

            chunks = split_scenes_into_chunks(scenes, chunk_sec)
            if len(chunks) > 1:
                # ─── 分割レンダリング ────────────────────────────────
                # 長尺動画を1回のブラウザセッションで処理するとフレーム数に比例して
                # メモリが増え続け、途中で停止する。シーン境界で分割して
                # 1回あたりのフレーム数を抑え、最後に ffmpeg で連結する。
                log(f"分割レンダリング: 合計 {total_duration:.0f}秒 を {len(chunks)} 個に分割します"
                    f"（閾値 {chunk_sec}秒）")
                await render_in_chunks(
                    video=video, style=style, chunks=chunks, assets_map=assets_map,
                    video_dir=video_dir, output_path=output_path,
                    fps=render_fps, workers=render_workers,
                    renderer_timeout=renderer_timeout,
                    broadcast_fn=broadcast_fn, log=log,
                )
                # 分割時はシーンの data_start がチャンク基準で上書きされているため、
                # 全体コンポジションを作り直して DB の値と index.html を元に戻す
                generate_composition(
                    video, scenes, style, TEMPLATES_BLANK_DIR, video_dir, assets_map, fps=render_fps
                )
                await db.commit()
            else:
                await request_render(
                    video_dir=str(video_dir),
                    output_rel=f"output/{generation_id}.mp4",
                    fps=render_fps,
                    workers=render_workers,
                    renderer_timeout=renderer_timeout,
                    log=log,
                )
            log("HyperFrames レンダリングが完了しました。")

            file_size = 0
            if output_path.exists():
                file_size = output_path.stat().st_size

            # ─── BGM ミックス（設定されている場合のみ） ──────────────
            if style.bgm_path and Path(style.bgm_path).exists():
                bgm_volume = style.bgm_volume if style.bgm_volume is not None else 0.3
                mixed_path = output_path.parent / f"{generation_id}_bgm_tmp.mp4"
                log(f"BGM ミックスを開始... volume={bgm_volume}")
                try:
                    # 動画の長さからフェードアウト開始点を計算（末尾2秒）
                    video_duration = video.duration_sec or 0.0
                    fade_start = max(0.0, video_duration - 2.0)
                    bgm_filter = (
                        f"[1:a]volume={bgm_volume}[bgm_vol];"
                        f"[bgm_vol]afade=t=out:st={fade_start:.2f}:d=2[bgm_fade];"
                        f"[0:a][bgm_fade]amix=inputs=2:duration=first[out]"
                    )
                    bgm_proc = await asyncio.create_subprocess_exec(
                        "ffmpeg",
                        "-i", str(output_path),
                        "-stream_loop", "-1",
                        "-i", style.bgm_path,
                        "-filter_complex", bgm_filter,
                        "-map", "0:v",
                        "-map", "[out]",
                        "-c:v", "copy",
                        str(mixed_path),
                        "-y",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await bgm_proc.communicate()
                    if mixed_path.exists():
                        shutil.move(str(mixed_path), str(output_path))
                        log("BGM ミックス完了")
                    else:
                        log("BGM ミックス失敗（元の音声のまま続行）")
                except Exception as e:
                    log(f"BGM ミックスエラー（スキップ）: {e}")

            # ─── サムネイル抽出 ────────────────────────────────────────
            thumb_path = output_path.parent / f"{generation_id}_thumb.jpg"
            try:
                thumb_proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-i", str(output_path),
                    "-ss", "0",          # 先頭フレーム
                    "-vframes", "1",
                    "-q:v", "3",         # JPEG 品質 (1=最高, 31=最低)
                    str(thumb_path),
                    "-y",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await thumb_proc.communicate()
                if thumb_path.exists():
                    # web アクセスパス: /projects/{...} にマップされるよう /app/ を除去
                    history.thumbnail_path = str(thumb_path).replace("/app/", "")
                    log(f"サムネイル生成完了: {thumb_path.name}")
                else:
                    log("サムネイル生成に失敗しました（ffmpeg 出力なし）")
            except Exception as e:
                log(f"サムネイル生成エラー（スキップ）: {e}")

            history.status = "completed"
            history.output_path = str(output_path)
            history.file_size_bytes = file_size
            history.duration_sec = video.duration_sec
            history.completed_at = datetime.now()
            
            video.status = "completed"
            await db.commit()

            await broadcast_fn("rendering", 1.0, "レンダリング完了", None)

        except Exception as e:
            tb = traceback.format_exc()
            raw_err = str(e).strip()
            err_msg = raw_err if raw_err else f"{type(e).__name__}: レンダリング処理中にエラーが発生しました ({repr(e)})"
            log(f"エラーが発生しました: {err_msg}\n{tb}")
            
            history.status = "failed"
            history.error_message = err_msg
            history.completed_at = datetime.now()
            
            video.status = "failed"
            await db.commit()

            await broadcast_fn("failed", 1.0, f"エラー: {err_msg}", err_msg)
        
        finally:
            history.log_text = "\n".join(logs)
            await db.commit()
