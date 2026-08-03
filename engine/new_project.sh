#!/bin/bash
# templates/blank/ の雛形から新しいプロジェクトを作成する。
#
# 実行例 (コンテナ内 / ホスト側どちらでも、パスが見える場所で実行可):
#   bash engine/new_project.sh my-new-video
#
# 作成されるもの:
#   projects/my-new-video/
#     ├── source/            (パターン2用: 元PPTXなどを置く)
#     ├── index.html
#     ├── style.css
#     ├── app.js
#     ├── gsap.min.js
#     ├── meta.json
#     └── narration.md       (空のテンプレート)
set -e

PROJECT_NAME="$1"
if [ -z "$PROJECT_NAME" ]; then
  echo "使い方: new_project.sh <project名>" >&2
  exit 1
fi

ENGINE_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$ENGINE_DIR/.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/templates/blank"
PROJECT_DIR="$ROOT_DIR/projects/$PROJECT_NAME"

if [ -d "$PROJECT_DIR" ]; then
  echo "すでに存在します: $PROJECT_DIR" >&2
  exit 1
fi

mkdir -p "$PROJECT_DIR/source" "$PROJECT_DIR/assets/audio"
cp "$TEMPLATE_DIR/index.html" "$PROJECT_DIR/index.html"
cp "$TEMPLATE_DIR/style.css" "$PROJECT_DIR/style.css"
cp "$TEMPLATE_DIR/app.js" "$PROJECT_DIR/app.js"
cp "$TEMPLATE_DIR/gsap.min.js" "$PROJECT_DIR/gsap.min.js"
cp "$TEMPLATE_DIR/meta.json" "$PROJECT_DIR/meta.json"
cp "$TEMPLATE_DIR/narration.md" "$PROJECT_DIR/narration.md"

echo "作成しました: $PROJECT_DIR"
echo "次のステップ:"
echo "  1. ${PROJECT_DIR#$ROOT_DIR/}/index.html にスライドを追加"
echo "  2. ${PROJECT_DIR#$ROOT_DIR/}/narration.md にナレーション原稿を記入"
echo "  3. bash engine/render.sh $PROJECT_NAME を実行"
