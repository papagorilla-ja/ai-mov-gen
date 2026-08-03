#!/bin/bash
# AI-MovGen — 一括停止
#
# 使い方:
#   bash stop.sh           # コンテナを停止・削除 (ボリュームは保持)
#   bash stop.sh --clean   # コンテナ + 匿名ボリュームも削除 (DB は保持)
#   bash stop.sh --all     # コンテナ + 全ボリューム削除 (DB も消える: 注意!)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

# ─── カラー定義 ───────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[stop]${NC}  $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; }

# ─── 引数パース ───────────────────────────────────────────
MODE="normal"
for arg in "$@"; do
  case "$arg" in
    --clean) MODE="clean" ;;
    --all)   MODE="all"   ;;
  esac
done

# ─── 前提確認 ─────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  err "Docker が見つかりません。"
  exit 1
fi
if [ ! -f "$COMPOSE_FILE" ]; then
  warn "docker-compose.yml が見つかりません。すでに停止済みの可能性があります。"
  exit 0
fi

# ─── ホストネイティブ TTS (MPS) 停止 ─────────────────────
if [ -f "$SCRIPT_DIR/data/tts_host.pid" ]; then
  log "ホストネイティブ TTS (MPS) を停止しています..."
  kill "$(cat "$SCRIPT_DIR/data/tts_host.pid")" 2>/dev/null || true
  rm -f "$SCRIPT_DIR/data/tts_host.pid"
fi

# ─── ホストネイティブ Renderer (hyperframes --docker) 停止 ───
if [ -f "$SCRIPT_DIR/data/renderer_host.pid" ]; then
  log "ホストネイティブ Renderer (hyperframes --docker) を停止しています..."
  kill "$(cat "$SCRIPT_DIR/data/renderer_host.pid")" 2>/dev/null || true
  rm -f "$SCRIPT_DIR/data/renderer_host.pid"
fi

# ─── 停止 ─────────────────────────────────────────────────
case "$MODE" in
  normal)
    log "コンテナを停止・削除します (ボリュームは保持)..."
    docker compose -f "$COMPOSE_FILE" down
    ;;
  clean)
    log "コンテナ + 匿名ボリュームを削除します..."
    docker compose -f "$COMPOSE_FILE" down -v
    ;;
  all)
    warn "コンテナ + 全ボリューム (DB含む) を削除します。よろしいですか? [y/N]"
    read -r confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
      docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
      log "全リソースを削除しました。"
    else
      log "キャンセルしました。"
      exit 0
    fi
    ;;
esac

log "停止しました。"
echo ""
echo "  再起動 (自動ビルド): bash start.sh"
echo "  ビルドなしで起動:   bash start.sh --no-build"
