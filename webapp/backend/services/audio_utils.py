"""参照音声（reference.wav）を作るための音声後処理。

ブラウザのマイク収録は「前後に無音が入る」「録音レベルが人によってばらつく」
という癖があり、そのまま連結すると Qwen3-TTS の x-vector 抽出に入る有効な音声が
短くなったり、声質の再現が不安定になる。ここで無音トリムと音量正規化を行い、
複数テイクから均等に集めて既定 20 秒程度の参照音声に整える。

依存は numpy / soundfile のみ（backend の既存依存で完結させる）。
"""
from __future__ import annotations

import numpy as np
import soundfile as sf

TARGET_SR = 16000          # Qwen3-TTS 参照音声のサンプリングレート
DEFAULT_MAX_SEC = 20.0     # 参照音声の長さ上限
TARGET_RMS = 0.08          # 正規化後の目標 RMS（約 -22 dBFS）。小さめにして歪みを避ける
PEAK_CEILING = 0.95        # クリッピング防止のピーク上限
GAP_SEC = 0.15             # テイク間に挟む無音
SILENCE_FLOOR_RMS = 1e-4   # これ未満は「実質無音」（マイクがミュートだった等）として捨てる
_FRAME = 320               # 20ms @ 16kHz。無音判定のフレーム長


def _to_mono(data: np.ndarray) -> np.ndarray:
    """ステレオ等の多チャンネルをモノラルに畳み込む。"""
    if data.ndim > 1:
        return data.mean(axis=1)
    return data


def trim_silence(data: np.ndarray, threshold_ratio: float = 0.06, margin_sec: float = 0.05) -> np.ndarray:
    """前後の無音を落とす。

    フレームごとの RMS を求め、そのテイク内の最大 RMS に対する相対比で
    発話区間を判定する（絶対閾値だと録音レベル差に弱いため）。
    発話の立ち上がりが切れないよう、前後に margin_sec の余白を残す。
    """
    if data.size == 0:
        return data

    n_frames = max(1, data.size // _FRAME)
    frames = data[:n_frames * _FRAME].reshape(n_frames, _FRAME)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    if rms.max() <= 0:
        return data

    voiced = np.flatnonzero(rms >= rms.max() * threshold_ratio)
    if voiced.size == 0:
        return data

    margin = int(margin_sec * TARGET_SR)
    start = max(0, voiced[0] * _FRAME - margin)
    end = min(data.size, (voiced[-1] + 1) * _FRAME + margin)
    return data[start:end]


def normalize_level(data: np.ndarray, target_rms: float = TARGET_RMS) -> np.ndarray:
    """RMS を目標値に合わせ、ピークがクリップしないように抑える。"""
    if data.size == 0:
        return data
    rms = float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))
    if rms <= 0:
        return data

    gain = target_rms / rms
    peak = float(np.abs(data).max())
    if peak * gain > PEAK_CEILING:
        # 目標 RMS よりピーク優先（歪ませない）
        gain = PEAK_CEILING / peak
    return (data * gain).astype(np.float32)


def build_reference_audio(
    take_paths: list[str],
    output_path: str,
    max_sec: float = DEFAULT_MAX_SEC,
) -> tuple[float, int]:
    """複数テイクから参照音声を作って書き出す。

    各テイクを「無音トリム → 音量正規化」した上で、max_sec を
    テイク数で割った時間ずつ均等に採用して連結する。
    均等配分にすることで、感情・トーン指定モードのように
    テイクごとに声色が違う収録でも、全テイクの特徴が参照音声に入る。

    戻り値: (書き出した音声の秒数, 実際に採用したテイク数)
    """
    if not take_paths:
        raise ValueError("テイクが1つもありません")

    prepared: list[np.ndarray] = []
    for path in take_paths:
        data, sr = sf.read(path, always_2d=False)
        data = _to_mono(np.asarray(data, dtype=np.float32))
        if sr != TARGET_SR:
            # 収録時に 16kHz へ変換済みだが、念のため想定外のレートは弾く
            raise ValueError(f"想定外のサンプリングレートです: {sr}Hz ({path})")
        # マイクがミュートだった等、実質無音のテイクは参照音声に混ぜない
        if float(np.sqrt(np.mean(data.astype(np.float64) ** 2))) < SILENCE_FLOOR_RMS:
            continue
        data = trim_silence(data)
        if data.size == 0:
            continue
        prepared.append(normalize_level(data))

    if not prepared:
        raise ValueError("有効な音声が含まれていません（マイクがミュートになっていた可能性があります）")

    # テイクあたりの採用秒数（均等配分）
    budget_samples = int((max_sec / len(prepared)) * TARGET_SR)
    gap = np.zeros(int(GAP_SEC * TARGET_SR), dtype=np.float32)

    chunks: list[np.ndarray] = []
    for i, data in enumerate(prepared):
        chunks.append(data[:budget_samples] if data.size > budget_samples else data)
        if i < len(prepared) - 1:
            chunks.append(gap)

    combined = np.concatenate(chunks)
    # 念のため全体でも上限を超えないように切る
    limit = int(max_sec * TARGET_SR)
    if combined.size > limit:
        combined = combined[:limit]

    combined = np.clip(combined, -1.0, 1.0).astype(np.float32)
    sf.write(output_path, combined, TARGET_SR, subtype="PCM_16")
    return combined.size / TARGET_SR, len(prepared)
