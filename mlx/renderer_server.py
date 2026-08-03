"""
HyperFrames レンダリングワーカー — HTTP サーバー (ホストネイティブ実行版)

api コンテナからのレンダリングジョブを受け取り、ホスト上で hyperframes render を
実行して MP4 を生成する。

FIX-17 で --docker を廃止しネイティブ実行に統一した。理由（すべて実測で確認）:
  - --docker はコンテナ内に GPU が無く browserGpuMode=software (SwiftShader) になり、
    さらに --experimental-fast-capture が engage せず screenshot キャプチャに落ちる
  - ネイティブ実行では captureMode が drawelement / beginframe になり大幅に高速
    （10秒コンポジションで 12.2秒 → 5.1秒）
  - hyperframes 0.7.82 の --docker は実プロジェクトで
    「Missing manifest at /usr/local/lib/core/dist/hyperframe.manifest.json」で失敗する

ホスト要件: hyperframes (npm) と ffmpeg/ffprobe (brew install ffmpeg)

エンドポイント:
  GET  /health   ヘルスチェック
  POST /render   レンダリング実行
"""
import asyncio
import os
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="HyperFrames Renderer", version="1.0.0")

# ─── 設定 ────────────────────────────────────────────────
PROJECTS_DIR_CONTAINER = "/app/projects"
DEFAULT_HOST_PROJECTS = str(Path(__file__).resolve().parent.parent / "projects")
PROJECTS_DIR_HOST = os.environ.get("PROJECTS_DIR_HOST", DEFAULT_HOST_PROJECTS)
HYPERFRAMES = None  # (path, bin_dir)


def find_hyperframes() -> tuple[str, str] | None:
    """(hyperframes バイナリのパス, その bin ディレクトリ) を返す。"""
    # NVM 管理下を優先探索
    nvm_versions = Path(os.environ.get("NVM_DIR", str(Path.home() / ".nvm"))) / "versions" / "node"
    if nvm_versions.exists():
        for v in sorted(nvm_versions.iterdir(), reverse=True):
            hf = v / "bin" / "hyperframes"
            if hf.exists():
                return str(hf), str(v / "bin")
    hf = shutil.which("hyperframes")
    if hf:
        return hf, str(Path(hf).parent)
    return None


def _to_host_path(p: str) -> str:
    """コンテナ絶対パス (/app/projects/...) をホスト絶対パスにマッピングする。"""
    if p.startswith(PROJECTS_DIR_CONTAINER):
        return PROJECTS_DIR_HOST + p[len(PROJECTS_DIR_CONTAINER):]
    return p


# Homebrew の既定パス。GUI から起動した場合など PATH に含まれないことがあるため明示する。
EXTRA_BIN_DIRS = ["/opt/homebrew/bin", "/usr/local/bin"]


def find_ffmpeg() -> str | None:
    """ffmpeg の場所を返す。ネイティブレンダリングの必須依存。"""
    found = shutil.which("ffmpeg")
    if found:
        return found
    # PATH に無くても Homebrew の標準位置にあれば採用する
    for d in EXTRA_BIN_DIRS:
        candidate = Path(d) / "ffmpeg"
        if candidate.exists():
            return str(candidate)
    return None


@app.on_event("startup")
async def startup():
    global HYPERFRAMES
    HYPERFRAMES = find_hyperframes()
    if HYPERFRAMES:
        print(f"hyperframes を検出: {HYPERFRAMES[0]} (bin_dir={HYPERFRAMES[1]})", flush=True)
    else:
        print("警告: hyperframes が見つかりません。レンダリングは失敗します。", flush=True)

    ff = find_ffmpeg()
    if ff:
        print(f"ffmpeg を検出: {ff}", flush=True)
    else:
        print("警告: ffmpeg が見つかりません。`brew install ffmpeg` を実行してください。", flush=True)


# ─── スキーマ ─────────────────────────────────────────────

class RenderRequest(BaseModel):
    video_dir: str       # コンテナ内絶対パス (例: /app/projects/p1/videos/v1)
    output_path: str     # video_dir からの相対パス (例: output/abc123.mp4)
    timeout: int = 3600  # レンダリングタイムアウト (秒)
    fps: int | None = None       # フレームレート（未指定なら hyperframes の既定 30）
    workers: int | None = None   # 並列ワーカー数（Chrome 1 プロセス約 256MB。未指定は auto）
    quality: str | None = None   # draft / standard / high


class RenderResponse(BaseModel):
    status: str          # "success" | "error"
    stdout: str = ""
    stderr: str = ""
    message: str = ""


# ─── エンドポイント ───────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "hyperframes": HYPERFRAMES[0] if HYPERFRAMES else "not found",
        "ffmpeg": find_ffmpeg() or "not found",
    }


@app.post("/render", response_model=RenderResponse)
async def render(req: RenderRequest):
    host_video_dir = Path(_to_host_path(req.video_dir))
    if not host_video_dir.exists():
        raise HTTPException(status_code=400, detail=f"ディレクトリが存在しません: {host_video_dir}")

    if not HYPERFRAMES:
        raise HTTPException(status_code=503, detail="hyperframes が見つかりません。環境変数やパス設定をご確認ください。")

    if not find_ffmpeg():
        raise HTTPException(
            status_code=503,
            detail="ffmpeg が見つかりません。ホストで `brew install ffmpeg` を実行してください。",
        )

    hf_bin, hf_bindir = HYPERFRAMES
    # ネイティブ実行。macOS + ハードウェア GPU では fast-capture が自動で有効になり、
    # captureMode が drawelement / beginframe になって screenshot 方式より大幅に速い。
    cmd = [hf_bin, "render", "--output", req.output_path]
    if req.fps:
        cmd += ["--fps", str(req.fps)]
    if req.workers:
        # ワーカー数を明示することで Chrome プロセスの増えすぎによるメモリ逼迫を防ぐ
        cmd += ["--workers", str(req.workers)]
    if req.quality:
        cmd += ["--quality", req.quality]

    print(f"[render] cwd={host_video_dir} cmd={' '.join(cmd)} timeout={req.timeout}", flush=True)

    env = {**os.environ}
    # hyperframes (Node.js) と ffmpeg/ffprobe (Homebrew) の両方が見つかるよう PATH を調整。
    # Apple Silicon の Homebrew は /opt/homebrew/bin なので必ず含めること。
    env["PATH"] = ":".join(
        [hf_bindir, *EXTRA_BIN_DIRS, "/usr/bin", "/bin", "/usr/sbin", "/sbin", env.get("PATH", "")]
    )
    # hyperframes は起動時に新バージョンを検知すると、レンダリングを続けたまま
    # バックグラウンドで `npm install -g hyperframes@X` を実行する。
    # インストール中はパッケージのファイルが一時的に消えるため、実行中のレンダリングが
    # "[HyperframeRuntimeLoader] Missing manifest" で失敗する。
    # hyperframes は毎日のように更新されるため放置すると再発するので、
    # レンダリング用の子プロセスでは自己更新を無効化する。
    # （更新は start.sh が通知し、ユーザーが明示的に実行する運用にする）
    env["HYPERFRAMES_NO_UPDATE_CHECK"] = "1"
    env["HYPERFRAMES_NO_AUTO_INSTALL"] = "1"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(host_video_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=req.timeout,
        )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        print(f"[render] returncode={proc.returncode}", flush=True)
        if stdout:
            print(f"[render][stdout] {stdout[:500]}", flush=True)
        if stderr:
            print(f"[render][stderr] {stderr[:500]}", flush=True)

        if proc.returncode != 0:
            return RenderResponse(
                status="error",
                stdout=stdout,
                stderr=stderr,
                message=f"hyperframes が終了コード {proc.returncode} で失敗しました",
            )

        return RenderResponse(status="success", stdout=stdout, stderr=stderr)

    except asyncio.TimeoutError:
        return RenderResponse(
            status="error",
            message=f"タイムアウト: レンダリングが {req.timeout // 60} 分以内に完了しませんでした",
        )
    except Exception as e:
        return RenderResponse(status="error", message=str(e))


# ─── ローカル起動 ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("renderer_server:app", host="127.0.0.1", port=8200, reload=False)
