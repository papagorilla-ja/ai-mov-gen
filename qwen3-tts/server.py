"""
Qwen3-TTS 推論サーバー (FastAPI ラッパー)

ホスト（macOS/Apple Silicon）でネイティブ実行し、MPS(Metal) を利用して高速化する。

エンドポイント:
  GET  /health              ヘルスチェック
  POST /synthesize          テキスト → WAV 音声合成（1シーン分をまとめて1リクエスト）
  GET  /models              利用可能なモデル一覧

■ 設計上の重要な前提（FIX-14）
Qwen3-TTS は自己回帰モデルであり、長いテキストを1回で投げると EOS を出せずに
`max_new_tokens` (既定 8192 = 約655秒) まで雑音を生成し続けて破綻する。
実測でコーデックは 12.5Hz、日本語の正常な発話レートは 5.1〜6.3 文字/秒。
そのため本サーバーは以下を必須とする:
  1. 1チャンクの文字数を MAX_ITEM_CHARS 以下に制限する（分割は呼び出し側の責務）
  2. チャンクごとに max_new_tokens の上限を必ず明示的に渡す
  3. 生成結果の長さを検証し、破綻していればシードを変えて再生成する

■ デバイスメモリの解放（FIX-19）
MPS の caching allocator は一度確保した Metal バッファをプロセス終了まで保持し続ける。
チャンク長・バッチ形状がリクエストごとに変わるため確保済みブロックが再利用されず、
1リクエストあたり約1GBのペースで物理フットプリントが増え続ける。実測では20リクエストで
6GB→28GB まで膨張し、20シーン規模の動画生成の途中で macOS の jetsam に
「killing largest compressed process」で強制終了された（クライアントからは
"Server disconnected without sending a response" に見える）。
そのため生成バッチごとに必ずデバイスキャッシュを解放する（_free_device_cache）。
"""
import gc
import io
import logging
import os
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from qwen_tts import Qwen3TTSModel

# ─── 設定 ────────────────────────────────────────────────
MODEL_ID = os.environ.get("QWEN3_TTS_MODEL_ID", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")

if torch.cuda.is_available():
    DEVICE, TORCH_DTYPE = "cuda", torch.float16
elif torch.backends.mps.is_available():
    DEVICE, TORCH_DTYPE = "mps", torch.float32   # Apple Silicon MPS (float32 で安定)
else:
    DEVICE, TORCH_DTYPE = "cpu", torch.float32

MODEL_CACHE_DIR   = os.environ.get("MODEL_CACHE_DIR", os.environ.get("HF_HOME", "/app/model_cache"))
VOICE_SAMPLES_DIR = os.environ.get("VOICE_SAMPLES_DIR", "/app/voice_samples")
DEFAULT_REF_PATH  = os.path.join(VOICE_SAMPLES_DIR, "default", "reference.wav")

# ─── 生成長の見積もりパラメータ（実測値ベース） ───────────
# 655.28 秒の WAV が 8191 コーデックフレームに一致したことから 12.5Hz と確定
CODEC_FRAMES_PER_SEC = 12.5
# 正常時の実測レンジ 5.1〜6.3 文字/秒 の中央値
CHARS_PER_SEC = 5.9

# 1チャンクの最大文字数。これを超えるテキストは 400 で拒否する（最後の安全弁）。
MAX_ITEM_CHARS = int(os.environ.get("TTS_MAX_ITEM_CHARS", "160"))
# 生成トークン数の下限・上限
MIN_NEW_TOKENS_CAP = 160
MAX_NEW_TOKENS_CAP = 900

# サンプリング設定（破綻を減らすため既定より控えめにする）
GEN_TEMPERATURE = float(os.environ.get("TTS_TEMPERATURE", "0.7"))
GEN_REPETITION_PENALTY = float(os.environ.get("TTS_REPETITION_PENALTY", "1.10"))
DEFAULT_BATCH_SIZE = int(os.environ.get("TTS_BATCH_SIZE", "4"))
DEFAULT_GAP_SEC = float(os.environ.get("TTS_CHUNK_GAP_SEC", "0.28"))
MAX_RETRY = int(os.environ.get("TTS_MAX_RETRY", "2"))
# 破綻したチャンクを何段まで再帰的に分割するか（120文字 → 60 → 30）
MAX_SPLIT_DEPTH = 2
# これより短いチャンクは分割しても意味がないので強制トリムに回す
MIN_SPLIT_CHARS = 12

# 音量正規化
TARGET_RMS = 0.06     # おおよそ -24 dBFS RMS
PEAK_CEIL = 0.90
MAX_GAIN = 4.0

# バッチ生成のたびにデバイスキャッシュを解放するか（トラブル時に 0 で無効化できる）
FREE_DEVICE_CACHE = os.environ.get("TTS_FREE_DEVICE_CACHE", "1") != "0"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qwen3-tts")

# ─── FastAPI アプリ ───────────────────────────────────────
app = FastAPI(
    title="Qwen3-TTS Server",
    description="HyperFrames 動画作成アプリ専用 TTS 推論サーバー",
    version="2.0.0",
)

# ─── モデルのロード (起動時に1回だけ) ─────────────────────
tts_model = None

# 推論はプロセス全体で直列化する。
# FastAPI は同期の def エンドポイントをスレッドプールで実行するため、
# ロックがないと複数リクエストが同一モデルと torch のグローバル RNG を同時に触る。
_infer_lock = threading.Lock()

# 参照音声から抽出した話者プロンプト (x-vector) のキャッシュ。
# create_voice_clone_prompt() は x_vector_only_mode でも speech_tokenizer.encode() を
# 実行して結果を捨てるため、毎リクエスト呼ぶと純粋な無駄計算になる。
_prompt_cache: dict[tuple[str, float, int], list] = {}
_prompt_cache_lock = threading.Lock()
_PROMPT_CACHE_MAX = 8


@app.on_event("startup")
async def load_model():
    global tts_model

    # ── デフォルト参照音声の自動生成 ────────────────────────────────
    default_ref_path = Path(DEFAULT_REF_PATH)
    if not default_ref_path.exists():
        logger.info("デフォルト参照音声が存在しないため自動生成します。")
        default_ref_path.parent.mkdir(parents=True, exist_ok=True)
        # 2 秒間の 440 Hz 正弦波（A4）をデフォルト参照音声として使用
        sr = 24000
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        tone = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
        sf.write(str(default_ref_path), tone, sr, format="WAV", subtype="PCM_16")
        logger.info(f"デフォルト参照音声を生成しました: {default_ref_path}")
        logger.warning(
            "デフォルト参照音声はダミーです。"
            "実際の音声を話者設定からアップロードすると音質が向上します。"
        )

    # ── モデルのロード ───────────────────────────────────────────────
    logger.info(f"モデルをロード中: {MODEL_ID} (device={DEVICE})")
    start = time.time()

    # huggingface-hub の snapshot_download を使ってリポジトリ全体を明示的にダウンロード
    from huggingface_hub import snapshot_download
    logger.info(f"HuggingFace Hub からモデルリポジトリ全体をダウンロード中: {MODEL_ID}")
    local_dir = snapshot_download(
        repo_id=MODEL_ID,
        local_files_only=False,
        cache_dir=MODEL_CACHE_DIR
    )
    logger.info(f"モデルのダウンロード完了: {local_dir}")

    # ダウンロードされたローカルパスからロード
    tts_model = Qwen3TTSModel.from_pretrained(
        local_dir,
        device_map=DEVICE,
        dtype=TORCH_DTYPE,
    )

    logger.info(f"モデルロード完了 ({time.time() - start:.1f}秒)")
    logger.info(
        f"生成設定: temperature={GEN_TEMPERATURE} repetition_penalty={GEN_REPETITION_PENALTY} "
        f"batch_size={DEFAULT_BATCH_SIZE} max_item_chars={MAX_ITEM_CHARS} max_retry={MAX_RETRY}"
    )

    # ── ウォームアップ（同時に話者プロンプトのキャッシュも温める） ──
    try:
        logger.info("ウォームアップ実行中...")
        prompt_items = get_voice_clone_prompt(Path(DEFAULT_REF_PATH))
        _generate_batch(["ウォームアップ"], "Japanese", prompt_items, cap_tokens=160, seed=0,
                        temperature=GEN_TEMPERATURE)
        logger.info("ウォームアップ完了")
    except Exception as e:
        logger.warning(f"ウォームアップ失敗 (無視します): {e}")


# ─── スキーマ ─────────────────────────────────────────────
class SynthesizeItem(BaseModel):
    text: str = Field(..., description="読み上げるチャンク", min_length=1)
    reference_audio_path: str | None = Field(
        None, description="ボイスクローニング用の参照音声 WAV パス"
    )
    language: str = Field("ja", description="言語コード (ja, en, zh など)")


class SynthesizeRequest(BaseModel):
    # ── 新形式 ──
    items: list[SynthesizeItem] | None = Field(
        None, description="1シーン分のチャンク列。順に合成して1本の WAV に連結して返す。"
    )
    # ── 旧形式（後方互換）──
    text: str | None = Field(None, description="[旧形式] 読み上げるテキスト")
    reference_audio_path: str | None = Field(None, description="[旧形式] 参照音声パス")
    language: str | None = Field(None, description="[旧形式] 言語コード")

    seed: int | None = Field(None, description="生成の再現性用シード")
    gap_sec: float | None = Field(None, description="チャンク間に挿入する無音の秒数")
    batch_size: int | None = Field(None, description="バッチ推論のサイズ")

    def resolved_items(self) -> list[SynthesizeItem]:
        if self.items:
            return self.items
        if self.text:
            return [SynthesizeItem(
                text=self.text,
                reference_audio_path=self.reference_audio_path,
                language=self.language or "ja",
            )]
        return []


# ─── 言語コードのマッピング ───────────────────────────────
LANG_MAP = {
    "ja": "Japanese",
    "en": "English",
    "zh": "Chinese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian"
}


def _resolve_ref_path(p: str | None) -> str | None:
    if not p:
        return p
    # コンテナ内絶対パス /app/voice_samples/... をホストのディレクトリに読み替える
    if p.startswith("/app/voice_samples"):
        return VOICE_SAMPLES_DIR + p[len("/app/voice_samples"):]
    return p  # ホスト絶対パス等はそのまま（存在しなければ既存フォールバックで default に落ちる）


def _effective_ref_path(raw: str | None) -> Path:
    """リクエストの参照音声パスを、実在する Path に解決する。"""
    candidate = Path(_resolve_ref_path(raw) or DEFAULT_REF_PATH)
    if candidate.exists():
        return candidate
    fallback = Path(DEFAULT_REF_PATH)
    if fallback.exists():
        logger.warning(
            f"参照音声が見つかりません ({candidate})。デフォルト参照音声にフォールバックします。"
        )
        return fallback
    raise HTTPException(
        status_code=503,
        detail=f"参照音声ファイルが見つかりません: {candidate}",
    )


# ─── 話者プロンプト (x-vector) のキャッシュ ────────────────
def get_voice_clone_prompt(ref_path: Path):
    """参照音声パス + mtime + サイズをキーに VoiceClonePromptItem をキャッシュする。"""
    st = ref_path.stat()
    key = (str(ref_path), st.st_mtime, st.st_size)

    with _prompt_cache_lock:
        item = _prompt_cache.get(key)
    if item is not None:
        return item

    # 計算はロック外で行う（librosa 読み込み + エンコーダ前向き計算で重い）
    try:
        item = tts_model.create_voice_clone_prompt(
            ref_audio=str(ref_path),
            ref_text="",
            x_vector_only_mode=True,
        )
    except Exception as e:
        # librosa/audioread の一部の例外 (NoBackendError 等) は str(e) が空文字列を
        # 返すため、原因が分かるよう明示的にメッセージを組み立てる。
        reason = str(e) or type(e).__name__
        raise RuntimeError(
            f"参照音声ファイルの読み込みに失敗しました: {ref_path} "
            f"（不正な形式か壊れたファイルの可能性があります / {reason}）"
        ) from e

    with _prompt_cache_lock:
        if len(_prompt_cache) >= _PROMPT_CACHE_MAX:
            _prompt_cache.pop(next(iter(_prompt_cache)))
        _prompt_cache[key] = item
    return item


# ─── 生成長の見積もりと検証 ───────────────────────────────
def estimate_duration_sec(text: str) -> float:
    """テキストから想定される発話秒数。"""
    return max(0.5, len(text) / CHARS_PER_SEC)


def cap_new_tokens(text: str) -> int:
    """このテキストに許可する最大生成トークン数。

    想定尺の 2.0 倍 + 余裕分。これを渡さないとモデル既定の 8192 (=約655秒) が
    使われ、EOS 未発火時に雑音を生成し続ける。
    """
    frames = estimate_duration_sec(text) * CODEC_FRAMES_PER_SEC
    return int(min(MAX_NEW_TOKENS_CAP, max(MIN_NEW_TOKENS_CAP, frames * 2.0 + 60)))


def judge_chunk(text: str, dur_sec: float, cap_tokens: int) -> str:
    """'ok' | 'runaway' | 'too_long' | 'truncated' を返す。"""
    expected = estimate_duration_sec(text)
    cap_sec = cap_tokens / CODEC_FRAMES_PER_SEC

    if dur_sec >= cap_sec * 0.98:
        return "runaway"                       # 生成上限に張り付き = EOS 未発火
    if dur_sec > expected * 1.7 + 2.0:
        return "too_long"                      # 冗長・引き伸ばし
    if expected >= 3.0 and dur_sec < expected * 0.5:
        return "truncated"                     # 途中打ち切り
    return "ok"


# ─── 音声の後処理 ─────────────────────────────────────────
def trim_silence(audio: np.ndarray, sr: int, thresh: float = 0.012,
                 keep_ms: int = 40) -> np.ndarray:
    """先頭・末尾の無音を削る。keep_ms 分は残して不自然なブツ切りを避ける。"""
    win = max(1, sr // 100)          # 10ms 窓
    n = len(audio) // win
    if n == 0:
        return audio
    rms = np.sqrt(np.mean(audio[: n * win].reshape(n, win) ** 2, axis=1))
    voiced = np.where(rms > thresh)[0]
    if len(voiced) == 0:
        return audio
    keep = int(sr * keep_ms / 1000)
    s = max(0, voiced[0] * win - keep)
    e = min(len(audio), (voiced[-1] + 1) * win + keep)
    return audio[s:e]


def gap_after(text: str, base: float) -> float:
    """チャンクの末尾表現に応じた「間」の長さを返す。"""
    t = (text or "").rstrip()
    if t.endswith(("。", "．", "！", "？", "!", "?")):
        return base * 1.5
    if t.endswith(("、", "，", ",")):
        return base * 0.6
    return base


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """RMS ベースで音量を揃えてから、ピークリミッタをかける。"""
    if len(audio) == 0:
        return audio
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms > 1e-6:
        audio = audio * min(MAX_GAIN, TARGET_RMS / rms)
    peak = float(np.max(np.abs(audio)))
    if peak > PEAK_CEIL:
        audio = audio * (PEAK_CEIL / peak)
    return audio


# ─── デバイスメモリの解放 ─────────────────────────────────
def _free_device_cache() -> None:
    """生成で確保したデバイス側のキャッシュを解放する。

    これを呼ばないと MPS/CUDA の caching allocator が確保済みブロックを保持し続け、
    リクエストごとに物理フットプリントが単調増加してプロセスが OOM で殺される。
    生成1回あたり十数秒かかるのに対し解放はミリ秒オーダーなので、
    バッチごとに呼んでも実測で速度への影響はない。
    """
    if not FREE_DEVICE_CACHE:
        return
    # 解放前に Python 側の参照を切る（循環参照に掴まれたテンソルを確実に落とす）
    gc.collect()
    if DEVICE == "mps":
        torch.mps.empty_cache()
    elif DEVICE == "cuda":
        torch.cuda.empty_cache()


def device_memory_mb() -> float | None:
    """デバイスが確保中のメモリ量 (MB)。ログ用。取得できなければ None。"""
    try:
        if DEVICE == "mps":
            return torch.mps.driver_allocated_memory() / (1024 ** 2)
        if DEVICE == "cuda":
            return torch.cuda.memory_reserved() / (1024 ** 2)
    except Exception:
        pass
    return None


# ─── 推論本体 ─────────────────────────────────────────────
def _generate_batch(texts: list[str], language: str, prompt_items, cap_tokens: int,
                    seed: int | None, temperature: float) -> tuple[list[np.ndarray], int]:
    """1バッチ分を生成する。torch のグローバル RNG を触るためロック内で実行する。"""
    with _infer_lock:
        if seed is not None:
            torch.manual_seed(seed)
            if DEVICE == "mps":
                torch.mps.manual_seed(seed)
            elif DEVICE == "cuda":
                torch.cuda.manual_seed_all(seed)

        try:
            wavs, sr = tts_model.generate_voice_clone(
                text=texts,
                language=[language] * len(texts),
                voice_clone_prompt=prompt_items,
                max_new_tokens=cap_tokens,
                temperature=temperature,
                repetition_penalty=GEN_REPETITION_PENALTY,
            )
            out = [np.asarray(w, dtype=np.float32) for w in wavs]
        finally:
            # 生成の成否によらず必ず解放する。
            # 失敗時ほど中途半端な確保が残るため、例外パスでの解放が特に重要。
            wavs = None
            _free_device_cache()
    return out, sr


def _split_in_half(text: str) -> list[str]:
    """リトライで直らないチャンクを2分割する。読点があればそこで、なければ中央で割る。"""
    if len(text) < 4:
        return [text]
    mid = len(text) // 2
    best = None
    for i, ch in enumerate(text):
        if ch in "、，,。．！？!?" and 0 < i < len(text) - 1:
            if best is None or abs(i - mid) < abs(best - mid):
                best = i
    cut = (best + 1) if best is not None else mid
    return [text[:cut].strip(), text[cut:].strip()]


def _synthesize_one(text: str, language: str, prompt_items, seed: int | None,
                    attempt: int) -> tuple[np.ndarray, int, str]:
    """単一チャンクを生成し、(audio, sr, verdict) を返す。"""
    cap = cap_new_tokens(text)
    temp = max(0.4, GEN_TEMPERATURE - 0.1 * attempt)
    s = None if seed is None else seed + attempt * 7919
    wavs, sr = _generate_batch([text], language, prompt_items, cap, s, temp)
    audio = wavs[0]
    verdict = judge_chunk(text, len(audio) / sr, cap)
    return audio, sr, verdict


def _synthesize_safe(text: str, language: str, prompt_items, seed: int | None,
                     depth: int = 0) -> tuple[np.ndarray, int, int, bool]:
    """1チャンクを生成し、破綻していれば回復する。

    Returns: (audio, sr, attempts, degraded)
    """
    audio, sr, verdict = _synthesize_one(text, language, prompt_items, seed, 0)
    if verdict == "ok":
        return audio, sr, 1, False
    a, sr, n, degraded = _repair_chunk(text, language, prompt_items, seed, verdict, audio, sr, depth)
    return a, sr, n + 1, degraded


def _repair_chunk(text: str, language: str, prompt_items, seed: int | None,
                  verdict: str, audio: np.ndarray, sr: int,
                  depth: int = 0) -> tuple[np.ndarray, int, int, bool]:
    """破綻したチャンクを回復する。

    復旧の方針は破綻の種類で変える:
      - truncated（途中打ち切り）はサンプリング運の問題なので、シードを変えて引き直す
      - runaway / too_long はテキストが長すぎる兆候なので、引き直さず即座に分割する
        （同じ長さで引き直しても直りにくく、フル尺の生成時間を無駄にするだけ。
          実測では 120 文字の暴走ケースで再試行2回がいずれも上限に張り付いた）

    Returns: (audio, sr, attempts, degraded)
    """
    indent = "  " * (depth + 1)
    attempts = 0
    logger.warning(
        f"{indent}チャンク破綻を検知: verdict={verdict} chars={len(text)} "
        f"dur={len(audio)/sr:.2f}s expected={estimate_duration_sec(text):.2f}s "
        f"text={text[:30]}..."
    )

    # 1) 途中打ち切りのみ、シードと温度を変えて再試行する
    if verdict == "truncated":
        for attempt in range(1, MAX_RETRY + 1):
            attempts += 1
            audio, sr, verdict = _synthesize_one(text, language, prompt_items, seed, attempt)
            logger.info(f"{indent}リトライ{attempt}: verdict={verdict} dur={len(audio)/sr:.2f}s")
            if verdict == "ok":
                return audio, sr, attempts, False

    # 2) チャンクを2分割して再帰的に生成する（短いほど破綻しにくく、生成も速い）
    halves = _split_in_half(text)
    if depth < MAX_SPLIT_DEPTH and len(text) >= MIN_SPLIT_CHARS and len(halves) == 2 and all(halves):
        logger.info(f"{indent}分割して再合成します: {len(halves[0])}+{len(halves[1])}文字")
        parts: list[np.ndarray] = []
        degraded_any = False
        for h in halves:
            a, sr, n, deg = _synthesize_safe(h, language, prompt_items, seed, depth + 1)
            attempts += n
            degraded_any = degraded_any or deg
            parts.append(trim_silence(a, sr))
        return np.concatenate(parts).astype(np.float32), sr, attempts, degraded_any

    # 3) 最終手段: 想定尺で強制トリムして続行する（動画生成全体は失敗させない）
    audio = audio[: int(sr * estimate_duration_sec(text) * 1.3)]
    logger.warning(f"{indent}チャンクを強制トリムしました: text={text[:30]}...")
    return audio, sr, attempts, True


# ─── エンドポイント ───────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_ID,
        "device": DEVICE,
        "model_loaded": tts_model is not None,
        "max_item_chars": MAX_ITEM_CHARS,
        # メモリ肥大の兆候を外から観測できるようにしておく（FIX-19）
        "device_memory_mb": device_memory_mb(),
    }


@app.get("/models")
def list_models():
    return {
        "models": [
            {"id": "Qwen/Qwen3-TTS-12Hz-0.6B-Base", "size": "0.6B", "recommended": True},
            {"id": "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "size": "1.7B", "recommended": False},
        ],
        "current": MODEL_ID,
    }


@app.post("/synthesize", response_class=Response)
def synthesize(req: SynthesizeRequest):
    """1シーン分のチャンク列を合成し、連結した WAV バイナリを返す。"""
    if tts_model is None:
        raise HTTPException(status_code=503, detail="モデルがまだロード中です")

    items = req.resolved_items()
    if not items:
        raise HTTPException(status_code=400, detail="items または text が必要です")

    for i, it in enumerate(items):
        if len(it.text) > MAX_ITEM_CHARS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"items[{i}] が長すぎます ({len(it.text)}文字 > {MAX_ITEM_CHARS}文字)。"
                    "テキストの分割は呼び出し側で行ってください。"
                ),
            )

    gap_sec = req.gap_sec if req.gap_sec is not None else DEFAULT_GAP_SEC
    batch_size = max(1, req.batch_size or DEFAULT_BATCH_SIZE)
    started = time.time()

    # ── チャンクをグループ化する（同一参照音声・同一言語のみ同じバッチにまとめる）──
    groups: dict[tuple[str, str], list[int]] = {}
    for idx, it in enumerate(items):
        ref_path = _effective_ref_path(it.reference_audio_path)
        language = LANG_MAP.get((it.language or "ja").lower(), "Japanese")
        groups.setdefault((str(ref_path), language), []).append(idx)

    audios: list[np.ndarray | None] = [None] * len(items)
    sample_rate = 24000
    retry_count = 0
    degraded_count = 0

    try:
        for (ref_key, language), indices in groups.items():
            prompt_items = get_voice_clone_prompt(Path(ref_key))

            # パディングの無駄と max_new_tokens の緩みを減らすため長さ順に並べる。
            # 元の順序はインデックスで保持しているので連結時に復元される。
            indices_sorted = sorted(indices, key=lambda i: len(items[i].text))

            for b in range(0, len(indices_sorted), batch_size):
                batch_idx = indices_sorted[b:b + batch_size]
                batch_texts = [items[i].text for i in batch_idx]
                cap = max(cap_new_tokens(t) for t in batch_texts)

                wavs, sr = _generate_batch(
                    batch_texts, language, prompt_items, cap, req.seed, GEN_TEMPERATURE
                )
                sample_rate = sr

                for i, text, audio in zip(batch_idx, batch_texts, wavs):
                    verdict = judge_chunk(text, len(audio) / sr, cap)
                    if verdict != "ok":
                        audio, sr2, r, degraded = _repair_chunk(
                            text, language, prompt_items, req.seed, verdict, audio, sr
                        )
                        sample_rate = sr2
                        retry_count += r
                        if degraded:
                            degraded_count += 1
                    audios[i] = trim_silence(audio, sample_rate)

        # ── 順序どおりに、間を挟んで連結する ──
        pieces: list[np.ndarray] = []
        for i, audio in enumerate(audios):
            if audio is None:
                continue
            pieces.append(audio)
            if i < len(audios) - 1:
                g = gap_after(items[i].text, gap_sec)
                if g > 0:
                    pieces.append(np.zeros(int(sample_rate * g), dtype=np.float32))

        if not pieces:
            raise RuntimeError("合成結果が空です。")

        merged = normalize_audio(np.concatenate(pieces).astype(np.float32))

        buf = io.BytesIO()
        sf.write(buf, merged, sample_rate, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()

    except HTTPException:
        raise
    except Exception as e:
        # 一部の例外 (audioread.NoBackendError 等) は str(e) が空文字列になるため、
        # 型名にフォールバックして必ず原因が分かるメッセージにする。
        reason = str(e) or type(e).__name__
        logger.error(f"音声合成エラー: {reason}")
        raise HTTPException(status_code=500, detail=f"音声合成に失敗しました: {reason}")

    elapsed = time.time() - started
    total_sec = len(merged) / sample_rate
    mem = device_memory_mb()
    logger.info(
        f"合成完了: chunks={len(items)} retries={retry_count} degraded={degraded_count} "
        f"audio={total_sec:.2f}s elapsed={elapsed:.1f}s (RTF={elapsed/max(total_sec,0.01):.2f})"
        + (f" mem={mem:.0f}MB" if mem is not None else "")
    )

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "X-Sample-Rate": str(sample_rate),
            "X-Chunk-Count": str(len(items)),
            "X-Retry-Count": str(retry_count),
            "X-Degraded-Chunks": str(degraded_count),
            "X-Generate-Seconds": f"{elapsed:.1f}",
            "X-Audio-Seconds": f"{total_sec:.2f}",
        },
    )


# ─── ローカル起動 (docker CMD 以外でのデバッグ用) ─────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8100, reload=False)
