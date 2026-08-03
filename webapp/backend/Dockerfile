# HyperFrames Web App — FastAPI バックエンド
FROM --platform=linux/arm64 python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# curl: ヘルスチェック用 / libsndfile1: soundfile (音声ファイル長取得) 用 / ffmpeg: 音声形式変換用
# libreoffice-impress + poppler-utils(pdftocairo): PPTX 取り込み時に図解を SVG 化するため
# fonts-noto-cjk: LibreOffice が日本語スライドをレイアウト崩れなく PDF 化するため
RUN apt-get update && apt-get install -y \
    curl \
    libsndfile1 \
    ffmpeg \
    libreoffice-impress \
    poppler-utils \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存パッケージ (コードより先にコピーしてキャッシュを活用)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコード
COPY . .
COPY static/ /app/static/

# 実行時に作成されるディレクトリ (ボリュームマウントで上書きされるが念のため)
RUN mkdir -p /app/data /app/voice_samples /app/projects /app/engine /app/templates

EXPOSE 8000

# コンテナ内では --reload を使用しない (watchfiles が ARM64/Docker 環境で誤動作するため)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
