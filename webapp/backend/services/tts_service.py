"""シーンのナレーションを Qwen3-TTS で音声化するサービス。

■ 処理の流れ（これだけ）
  1. ナレーション本文を TTS が安全に扱えるチャンクに分割する (split_for_tts)
  2. 1シーン分のチャンクをまとめて TTS サーバーに 1 リクエストで投げる
  3. 返ってきた WAV（連結・正規化済み）をそのまま保存する

Qwen3-TTS は長文を1回で投げると EOS を出せずに雑音を生成し続けて破綻するため、
チャンク分割は必須である（詳細は docs/antigravity_fix14_tts_overhaul.md）。
チャンクの連結・無音トリム・音量正規化は TTS サーバー側が行うので、
ここでは ffmpeg も一時ファイルも使わない。
"""
import hashlib
import json
import re
import unicodedata
import wave
from pathlib import Path

import httpx

from core.config import settings

# キャッシュ判定ハッシュのバージョン。TTS の生成方式を変えたら必ず上げること。
# （上げないと、破綻した過去の WAV が SceneTtsCache 経由で再利用されてしまう）
TTS_PIPELINE_VERSION = "fix14"

# TTS 1 チャンクあたりの最大文字数。
# 実測で 128〜142 文字帯は破綻ゼロ、260 文字超から確率的に破綻するため
# 十分な安全マージンを取って 120 を既定とする。
DEFAULT_MAX_CHUNK_CHARS = 120
# これ未満の断片は前後のチャンクに吸収する
MIN_CHUNK_CHARS = 8

# ヘルスチェックのタイムアウト（秒）。合成本体とは別に短く取る。
TTS_HEALTH_TIMEOUT_SEC = 5


def _max_chunk_chars() -> int:
    return int(getattr(settings, "tts_max_chunk_chars", DEFAULT_MAX_CHUNK_CHARS))


def derive_seed(key: str) -> int:
    """キー文字列から決定的なシードを導出する。

    シードを固定することで、同じ原稿からは常に同じ音声が得られる。
    （デバッグの再現性、キャッシュとの整合性、声質のブレ防止のため）
    """
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)


def compute_tts_hash(
    text: str,
    speaker_a_id: str | None,
    ref_path_a: str | None,
    dialog_lines: list[dict] | None = None,
    speaker_b_id: str | None = None,
    ref_path_b: str | None = None,
    slide_content_json: dict | str | None = None
) -> str:
    """TTS用のキャッシュ判定ハッシュを算出する"""
    if dialog_lines:
        content_str = ""
        if slide_content_json:
            if isinstance(slide_content_json, dict):
                content_str = json.dumps(slide_content_json, ensure_ascii=False)
            else:
                content_str = str(slide_content_json)
        hash_raw = (
            f"{TTS_PIPELINE_VERSION}|{content_str}"
            f"|{speaker_a_id or ''}|{ref_path_a or ''}"
            f"|{speaker_b_id or ''}|{ref_path_b or ''}"
        )
    else:
        hash_raw = f"{TTS_PIPELINE_VERSION}|{text or ''}|{speaker_a_id or ''}|{ref_path_a or ''}"
    return hashlib.md5(hash_raw.encode("utf-8")).hexdigest()


# ─── テキストの正規化とチャンク分割 ───────────────────────
def normalize_for_tts(text: str) -> str:
    """TTS に渡す前の軽量な正規化。読み上げに不要な表記ゆれを潰す。"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # 行頭の markdown 記号 (- * # >) を除去
    t = re.sub(r"^[ \t]*[-*#>]+[ \t]*", "", t, flags=re.MULTILINE)
    # 強調記号は読み上げ対象外
    t = t.replace("**", "").replace("__", "")
    # 空白の圧縮
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    # 句読点で終わっていない改行は文の区切りとみなす。
    # （これがないと、行が連結されたときに「見出し本文です」のように読まれてしまう）
    t = re.sub(r"(?<=[^\s。．！？!?、，,])\n", "。\n", t)
    return t.strip()


def split_for_tts(text: str, max_chars: int | None = None) -> list[str]:
    """テキストを TTS が安全に処理できるチャンク列に分割する。

    1) 句点・改行で文に分割
    2) max_chars を超える文は読点でさらに分割
    3) それでも超える場合は max_chars で強制分割
    4) 隣接する断片を max_chars 以内でマージ（呼び出し回数を減らす）
    """
    limit = max_chars or _max_chunk_chars()
    text = normalize_for_tts(text)
    if not text:
        return []

    # 1) 文分割
    sentences = [s.strip() for s in re.split(r"(?<=[。．！？!?\n])", text) if s.strip()]

    # 2)-3) 長すぎる文をさらに割る
    pieces: list[str] = []
    for s in sentences:
        if len(s) <= limit:
            pieces.append(s)
            continue
        for sub in [x.strip() for x in re.split(r"(?<=[、，,])", s) if x.strip()]:
            while len(sub) > limit:
                pieces.append(sub[:limit])
                sub = sub[limit:]
            if sub:
                pieces.append(sub)

    # 4) マージ
    chunks: list[str] = []
    for p in pieces:
        if chunks and len(chunks[-1]) + len(p) <= limit:
            chunks[-1] += p
        elif chunks and len(p) < MIN_CHUNK_CHARS:
            chunks[-1] += p          # 極小断片は長さ超過を許容して吸収
        else:
            chunks.append(p)

    return chunks


def generate_silent_wav(output_wav_path: Path, duration_sec: float = 2.0) -> bytes:
    """24kHz, 16-bit, モノラルの無音 WAV ファイルを指定秒数生成して保存し、バイト列を返す。"""
    sample_rate = 24000
    num_frames = int(sample_rate * duration_sec)
    silence_frames = b"\x00\x00" * num_frames

    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_wav_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence_frames)

    return output_wav_path.read_bytes()


def _build_items(text: str, dialog_lines: list[dict] | None, speaker_a, speaker_b) -> list[dict]:
    """TTS サーバーに渡すチャンク列を組み立てる。"""

    def make(chunk: str, speaker) -> dict:
        item = {
            "text": chunk,
            "language": speaker.language if speaker and speaker.language else "ja",
        }
        if speaker and speaker.reference_audio_path:
            item["reference_audio_path"] = speaker.reference_audio_path
        return item

    items: list[dict] = []
    if dialog_lines:
        for line in dialog_lines:
            speaker = speaker_b if line.get("speaker") == "B" else speaker_a
            for chunk in split_for_tts(line.get("text", "")):
                items.append(make(chunk, speaker))
    else:
        for chunk in split_for_tts(text):
            items.append(make(chunk, speaker_a))
    return items


async def ensure_tts_ready() -> None:
    """TTS サーバーが合成可能な状態かを確認し、駄目なら理由を明示して例外を送出する。

    既存音声の削除など、失敗すると後戻りできない処理の前に必ず呼ぶこと。
    確認せずに削除すると、TTS が停止していた場合に音声を失ったうえで合成にも失敗し、
    何も残らない状態になる。
    """
    url = f"{settings.qwen3_tts_base_url}/health"
    try:
        async with httpx.AsyncClient(timeout=TTS_HEALTH_TIMEOUT_SEC) as client:
            resp = await client.get(url)
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise RuntimeError(
            f"TTSサーバーに接続できません（起動していない可能性があります）: {url}"
            " — サーバーの起動を確認してから再実行してください。"
        ) from e
    except httpx.HTTPError as e:
        raise RuntimeError(
            f"TTSサーバーの状態を確認できません: {str(e) or repr(e)}"
        ) from e

    if resp.status_code != 200:
        raise RuntimeError(
            f"TTSサーバーが異常な応答を返しました (HTTP {resp.status_code})"
        )

    try:
        payload = resp.json()
    except ValueError as e:
        raise RuntimeError("TTSサーバーの応答を解釈できませんでした") from e

    # model_loaded が無い応答は Qwen3-TTS 以外のサーバー。
    # 設定ミス（例: レンダラーの URL を指定している）を「ロード中」と誤報しないよう分ける。
    if not isinstance(payload, dict) or "model_loaded" not in payload:
        raise RuntimeError(
            f"TTSサーバーではないサーバーが応答しました: {url}"
            " — 設定の TTS サーバー URL をご確認ください。"
        )

    if not payload["model_loaded"]:
        raise RuntimeError(
            "TTSサーバーはモデルのロード中です。しばらく待ってから再実行してください。"
        )


async def synthesize_scene_audio(
    text: str,
    dialog_lines: list[dict] | None,
    speaker_a,
    speaker_b,
    output_wav_path: Path,
    seed: int | None = None,
    stats: dict | None = None,
) -> bytes:
    """1シーン分の TTS 音声を合成し、output_wav_path に保存して WAV バイト列を返す。

    stats に dict を渡すと、チャンク数・リトライ回数・所要時間などの診断情報が格納される。
    """
    # テキストが空かつ対話行もない場合は TTS 呼び出しをスキップして無音を返す
    if not (text and text.strip()) and not dialog_lines:
        return generate_silent_wav(output_wav_path, duration_sec=2.0)

    items = _build_items(text, dialog_lines, speaker_a, speaker_b)
    if not items:
        return generate_silent_wav(output_wav_path, duration_sec=2.0)

    payload = {
        "items": items,
        "seed": seed,
        "gap_sec": getattr(settings, "tts_chunk_gap_sec", 0.28),
        "batch_size": getattr(settings, "tts_batch_size", 4),
    }

    timeout_val = getattr(settings, "tts_request_timeout", 1800)

    # 事前に TTS サーバーの状態を確認する。
    # 旧実装は接続エラーを握りつぶしていたが、httpx.ConnectError は HTTPError の
    # サブクラスであるため「サーバーが停止しているとき」にこそ機能していなかった。
    await ensure_tts_ready()

    async with httpx.AsyncClient(timeout=timeout_val) as client:
        try:
            resp = await client.post(f"{settings.qwen3_tts_base_url}/synthesize", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                raise RuntimeError(
                    "TTSサーバーは起動中（モデルロード中）です。もうしばらくお待ちください。"
                ) from e
            raise RuntimeError(
                f"TTSサーバーエラー ({e.response.status_code}): {e.response.text}"
            ) from e
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise RuntimeError(
                f"TTSサーバー接続エラー（サーバーが起動していない可能性があります）: {str(e) or repr(e)}"
            ) from e
        except httpx.TimeoutException as e:
            raise RuntimeError(
                "TTS音声合成がタイムアウトしました。"
                "ナレーションが長い、またはCPU推論が遅い可能性があります。"
                "ナレーションを短くするか、TTSタイムアウト設定を延長してください。"
            ) from e
        except (httpx.RemoteProtocolError, httpx.ReadError) as e:
            # 応答を返さずに接続が切れた = TTS サーバーのプロセスが合成中に死んでいる。
            # 実例として、MPS のキャッシュ肥大で macOS に強制終了された事象があった。
            # 原文（"Server disconnected without sending a response."）だけでは
            # 原因も次の手も分からないため、確認先を明示する。
            raise RuntimeError(
                "TTSサーバーが応答を返さずに切断されました"
                "（合成中にサーバープロセスが停止した可能性があります）。"
                "メモリ不足による強制終了が主な原因です。"
                "data/tts_host.log を確認し、start.sh で再起動してから再実行してください。"
                f" 詳細: {str(e) or repr(e)}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"音声合成エラー: {str(e) or repr(e)}") from e

    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    output_wav_path.write_bytes(resp.content)

    if stats is not None:
        stats.update({
            "chunks": resp.headers.get("X-Chunk-Count"),
            "retries": resp.headers.get("X-Retry-Count"),
            "degraded": resp.headers.get("X-Degraded-Chunks"),
            "generate_sec": resp.headers.get("X-Generate-Seconds"),
            "audio_sec": resp.headers.get("X-Audio-Seconds"),
        })
    return resp.content
