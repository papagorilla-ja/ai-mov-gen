"""アプリケーション設定 (環境変数 / デフォルト値)"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # データベース
    database_url: str = "sqlite+aiosqlite:////app/data/app.db"

    # CORS (環境変数での上書き不要。デフォルト値を使用)
    # pydantic-settings は list[str] を env から受け取る際に JSON 形式が必要なため、
    # docker-compose.yml では CORS_ORIGINS を設定しない運用とする。
    cors_origins: list[str] = ["http://localhost:3000"]

    # Qwen3-TTS サーバー (ホストネイティブ実行)
    qwen3_tts_base_url: str = "http://host.docker.internal:8100"

    # ローカル LLM (ホスト側で稼働)
    local_llm_base_url: str = "http://host.docker.internal:11434/v1"
    local_llm_model: str = "qwen3:14b"
    enable_think: bool = False

    # TTS タイムアウト設定
    tts_request_timeout: int = 1800

    # TTS 合成パラメータ
    # Qwen3-TTS は長文を1回で投げると EOS を出せずに雑音を出し続けて破綻するため、
    # チャンク分割は必須。実測で 128〜142 文字帯は破綻ゼロ、260 文字超から破綻し始める。
    tts_max_chunk_chars: int = 120
    # バッチ推論のサイズ。遅くなる場合は 1 に戻せば従来どおりの逐次実行になる。
    tts_batch_size: int = 4
    # チャンク間に挿入する無音の基準秒数（文末は 1.5 倍、読点は 0.6 倍）
    tts_chunk_gap_sec: float = 0.28

    # HyperFrames レンダラー
    renderer_base_url: str = "http://host.docker.internal:8200"
    renderer_request_timeout: int = 3600

    # 動画設定デフォルト
    # レンダリングのフレームレート。24 は映画と同じレートで、スライド主体の
    # 研修動画では 30 との差がほぼ分からない一方、フレーム数が 20% 減る。
    default_fps: int = 24
    default_resolution: str = "1920x1080"

    # レンダリング並列ワーカー数（Chrome 1 プロセスあたり約 256MB）。
    # 0 を指定すると hyperframes の auto（コア数から自動決定）に任せる。
    # auto は 14 コア機で大量に起動しメモリを圧迫するため、既定では明示的に絞る。
    render_workers: int = 4

    # この秒数を超える動画は分割してレンダリングし、最後に ffmpeg で連結する。
    # 1 回の Chrome セッションが扱うフレーム数を抑えてメモリ上限を制御する。
    # 0 で分割を無効化。
    render_chunk_sec: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
