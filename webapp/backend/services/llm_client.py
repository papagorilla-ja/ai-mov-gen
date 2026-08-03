import re
import logging
import httpx
from core.config import settings

logger = logging.getLogger("llm_client")

async def chat_completion(
    messages: list[dict],
    provider: str = "local",   # 引数は残すが値は無視する（常にローカル LLM を使用）
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """ローカル LLM（OpenAI 互換 API）に問い合わせ、応答テキストを返す。"""
    if not settings.local_llm_base_url:
        raise ValueError("LOCAL_LLM_BASE_URL が設定されていません。設定画面で確認してください。")

    url = settings.local_llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.local_llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "think": settings.enable_think,  # 設定に応じて Think モードのオン/オフを切替 (Ollama / Qwen / DeepSeek 互換)
    }

    logger.info(f"ローカル LLM にリクエスト送信中... model={settings.local_llm_model}, think={settings.enable_think}")
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # 念のため <think>...</think> ブロックを除去（Ollama バージョンによる差異を吸収）
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            logger.error(f"ローカル LLM 呼び出しエラー: {e}")
            raise RuntimeError(f"ローカル LLM の呼び出しに失敗しました: {e}")
