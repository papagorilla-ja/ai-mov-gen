#!/bin/bash
# AI-MovGen 動画作成 Web アプリ — 一括バックグラウンド起動
#
# 使い方:
#   bash start.sh           # 自動ビルド & バックグラウンド起動
#   bash start.sh --no-build # ビルドをスキップして起動
#   bash start.sh --logs    # 起動後にコンテナログを tail
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
APP_URL="http://localhost:3000"

# ─── カラー定義 ───────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[start]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; }

# ─── 引数パース (デフォルトで --build を内包) ─────────────
BUILD_FLAG="--build"
TAIL_LOGS=false
for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD_FLAG="" ;;
    --logs)     TAIL_LOGS=true ;;
  esac
done

# ─── 前提確認 ─────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  err "Docker が見つかりません。Docker Desktop を起動してください。"
  exit 1
fi
if [ ! -f "$COMPOSE_FILE" ]; then
  err "docker-compose.yml が見つかりません: $COMPOSE_FILE"
  err "先に Web アプリの docker-compose.yml を配置してください。"
  exit 1
fi

# ─── ホストネイティブ TTS (MPS) 起動 ─────────────────────
if [ -f "$SCRIPT_DIR/data/tts_host.pid" ]; then
  kill "$(cat "$SCRIPT_DIR/data/tts_host.pid")" 2>/dev/null || true
  rm -f "$SCRIPT_DIR/data/tts_host.pid"
fi

log "ホストネイティブ TTS (MPS) を起動します..."
cd "$SCRIPT_DIR/qwen3-tts"
source .venv-host/bin/activate
export MODEL_CACHE_DIR="$SCRIPT_DIR/data/model_cache"
export HF_HOME="$SCRIPT_DIR/data/model_cache"
export QWEN3_TTS_MODEL_ID="Qwen/Qwen3-TTS-12Hz-0.6B-Base"
export VOICE_SAMPLES_DIR="$SCRIPT_DIR/engine/voice_samples"
export PYTORCH_ENABLE_MPS_FALLBACK=1
# ─── TTS 生成パラメータ ───
# Qwen3-TTS は長いテキストを1回で投げると EOS を出せずに雑音を生成し続けて破綻する。
# TTS_MAX_ITEM_CHARS はその最後の安全弁（超過したリクエストは 400 で拒否する）。
export TTS_MAX_ITEM_CHARS=160
export TTS_TEMPERATURE=0.7          # 既定 0.9 より下げて破綻を抑える
export TTS_REPETITION_PENALTY=1.10  # 破綻時のコード列反復を抑える
export TTS_BATCH_SIZE=4             # 遅くなる場合は 1 に戻す
export TTS_CHUNK_GAP_SEC=0.28
export TTS_MAX_RETRY=2
nohup uvicorn server:app --host 127.0.0.1 --port 8100 \
  > "$SCRIPT_DIR/data/tts_host.log" 2>&1 &
echo $! > "$SCRIPT_DIR/data/tts_host.pid"
deactivate
cd "$SCRIPT_DIR"

# ─── ホストネイティブ Renderer (hyperframes --docker) 起動 ───
if [ -f "$SCRIPT_DIR/data/renderer_host.pid" ]; then
  kill "$(cat "$SCRIPT_DIR/data/renderer_host.pid")" 2>/dev/null || true
  rm -f "$SCRIPT_DIR/data/renderer_host.pid"
fi

log "ホストネイティブ Renderer (hyperframes) を起動します..."
docker info >/dev/null 2>&1 || { err "Docker Desktop が起動していません。起動してから再実行してください。"; exit 1; }

# レンダリングはホスト上でネイティブ実行するため ffmpeg/ffprobe が必須。
# （--docker 方式はコンテナ内に GPU が無く低速なうえ、hyperframes 側の不具合で失敗するため廃止した）
if ! command -v ffmpeg >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/ffmpeg ]; then
  err "ffmpeg が見つかりません。'brew install ffmpeg' を実行してから再実行してください。"
  exit 1
fi

cd "$SCRIPT_DIR/mlx"
source .venv-host/bin/activate
export PROJECTS_DIR_HOST="$SCRIPT_DIR/projects"
export NVM_DIR="$HOME/.nvm"
# Homebrew の ffmpeg を hyperframes から見えるようにする
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
nohup uvicorn renderer_server:app --host 127.0.0.1 --port 8200 \
  > "$SCRIPT_DIR/data/renderer_host.log" 2>&1 &
echo $! > "$SCRIPT_DIR/data/renderer_host.pid"
deactivate
cd "$SCRIPT_DIR"

# ─── 起動 ─────────────────────────────────────────────────
log "Web アプリを起動します (docker compose up -d ${BUILD_FLAG})..."
if ! docker compose -f "$COMPOSE_FILE" up -d $BUILD_FLAG; then
  err "docker compose up が失敗しました。api ログ:"
  docker compose -f "$COMPOSE_FILE" logs --tail=50 api 2>&1 | sed 's/^/  /'
  exit 1
fi

# ─── ヘルスチェック ───────────────────────────────────────
# TTS はモデルのロードとウォームアップに数十秒かかる。API だけを見て「起動完了」と
# 表示すると、UI は操作できるのに TTS だけ未起動という窓ができ、その間に動画生成を
# 実行すると「TTSサーバー接続エラー」で失敗する。そのため全サービスの ready を待つ。
INTERVAL=3

# サービスが応答するまでポーリングする。
#   $1: 表示名 / $2: ヘルスチェック URL / $3: 応答に含まれるべき文字列 (空なら疎通のみ)
#   $4: 最大待機秒数 / $5: 監視する pid ファイル (空なら監視しない) / $6: 失敗時に出すログ
# 戻り値: 0=ready / 1=タイムアウト / 2=プロセス停止
wait_for() {
  local label="$1" url="$2" expect="$3" max_wait="$4" pidfile="$5" logfile="$6"
  local elapsed=0 body
  printf "  %-22s" "$label"

  while [ "$elapsed" -lt "$max_wait" ]; do
    # バックグラウンド起動したプロセスが死んでいたら、待たずに打ち切る
    if [ -n "$pidfile" ] && [ -f "$pidfile" ] && ! kill -0 "$(cat "$pidfile")" 2>/dev/null; then
      echo " ✗ プロセスが停止しました"
      [ -n "$logfile" ] && [ -f "$logfile" ] && tail -15 "$logfile" | sed 's/^/      /'
      return 2
    fi

    body="$(curl -sf -m 3 "$url" 2>/dev/null || true)"
    if [ -n "$body" ] && { [ -z "$expect" ] || [[ "$body" == *"$expect"* ]]; }; then
      echo " ✓ ready (${elapsed}秒)"
      return 0
    fi

    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
    echo -n "."
  done

  echo " ✗ タイムアウト (${max_wait}秒)"
  [ -n "$logfile" ] && [ -f "$logfile" ] && tail -15 "$logfile" | sed 's/^/      /'
  return 1
}

log "サービスの起動を待機中..."
STARTUP_OK=true

# API: webapp 経由で /settings が引ければ疎通確認とみなす
wait_for "API" "http://localhost:3000/api/v1/settings" "" 90 "" "" || {
  STARTUP_OK=false
  warn "直近の api ログ:"
  docker compose -f "$COMPOSE_FILE" logs --tail=30 api 2>&1 | sed 's/^/  /'
}

# TTS: 疎通だけでなくモデルのロード完了まで待つ（初回はモデル取得で更に時間がかかる）
wait_for "TTS (Qwen3-TTS)" "http://127.0.0.1:8100/health" '"model_loaded":true' 300 \
  "$SCRIPT_DIR/data/tts_host.pid" "$SCRIPT_DIR/data/tts_host.log" || STARTUP_OK=false

# Renderer: hyperframes と ffmpeg を解決できている状態を ready とみなす
wait_for "Renderer" "http://127.0.0.1:8200/health" '"status":"ok"' 90 \
  "$SCRIPT_DIR/data/renderer_host.pid" "$SCRIPT_DIR/data/renderer_host.log" || STARTUP_OK=false

# レンダラーは応答していても依存コマンドを見つけられていないことがあるため個別に確認する
RENDERER_HEALTH="$(curl -sf -m 3 http://127.0.0.1:8200/health 2>/dev/null || true)"
if [[ "$RENDERER_HEALTH" == *'"hyperframes":"not found"'* ]]; then
  warn "hyperframes が見つかりません。'npm install -g hyperframes' をご確認ください。"
  STARTUP_OK=false
fi
if [[ "$RENDERER_HEALTH" == *'"ffmpeg":"not found"'* ]]; then
  warn "レンダラーから ffmpeg を解決できません。'brew install ffmpeg' をご確認ください。"
  STARTUP_OK=false
fi

# hyperframes の自己更新はレンダリング中のパッケージ入れ替えを引き起こすため
# renderer_server.py 側で無効化している。代わりに起動時に更新の有無だけを通知する。
if command -v hyperframes >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  HF_CURRENT="$(hyperframes --version 2>/dev/null | tr -d '[:space:]' || true)"
  HF_LATEST="$(npm view hyperframes version --fetch-timeout=5000 2>/dev/null | tr -d '[:space:]' || true)"
  if [ -n "$HF_CURRENT" ] && [ -n "$HF_LATEST" ] && [ "$HF_CURRENT" != "$HF_LATEST" ]; then
    warn "hyperframes の新しいバージョンがあります: ${HF_CURRENT} → ${HF_LATEST}"
    warn "更新する場合は動画生成をしていないときに 'npm install -g hyperframes@${HF_LATEST}' を実行してください。"
  fi
fi

if [ "$STARTUP_OK" = true ]; then
  log "起動完了!"
  log "Web UI: ${APP_URL}"
  log "API:    http://localhost:8000"
else
  warn "一部のサービスが起動していません。この状態で動画を生成すると失敗します。"
  warn "再起動するには: bash stop.sh && bash start.sh"
fi

# ─── サービス一覧表示 ─────────────────────────────────────
echo ""
docker compose -f "$COMPOSE_FILE" ps

# ─── ログ tail (オプション) ───────────────────────────────
if [ "$TAIL_LOGS" = true ]; then
  echo ""
  log "ログを表示します (Ctrl+C で終了)..."
  docker compose -f "$COMPOSE_FILE" logs -f
fi
