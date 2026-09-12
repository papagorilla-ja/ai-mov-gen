import re
import logging
import httpx
from core.config import settings

logger = logging.getLogger("llm_client")

# 思考を止めるための「空の思考ブロック」。
#
# なぜこれが要るか:
#   Think モードを切るための指定は、サーバーによって受け口が違う。
#     - Ollama のネイティブ API … payload の "think": false
#     - vLLM / SGLang 等        … "chat_template_kwargs": {"enable_thinking": false}
#     - LM Studio の OpenAI 互換 … **どれも効かない**
#   実測では LM Studio + Qwen3 系 MLX モデルに対して
#   think / chat_template_kwargs / reasoning_effort / enable_thinking /
#   reasoning / システムやユーザー文中の /no_think の 8 通りを試したが、
#   1 つも思考を止められなかった。
#
#   そこで、アシスタントの発話を「思考済み」の状態から書き始めさせる。
#   モデルは </think> の続きを書くことになるので、思考を出しようがない。
#   Qwen3 系で広く使われている方法で、テンプレートの差異に依存しない。
#
# 効果（実測 / シーン内容の生成 4 件）:
#     なし … 1/4 件しか成功しない（3 件は思考でトークン上限に達し本文が空）/ 計 284 秒
#     あり … 4/4 件成功 / 計 33 秒
NO_THINK_PREFILL = {"role": "assistant", "content": "<think>\n\n</think>\n\n"}

# Think モードを有効にしたときの出力上限。
# 思考と本文の両方をこの枠内で出し切る必要があるため、通常より広く取る。
# 狭いままだと「思考の途中で打ち切られ、本文が 1 文字も返らない」ことになる。
THINK_MAX_TOKENS = 12288


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

    sent_messages = list(messages)
    if settings.enable_think:
        max_tokens = max(max_tokens, THINK_MAX_TOKENS)
    else:
        sent_messages.append(NO_THINK_PREFILL)

    payload = {
        "model": settings.local_llm_model,
        "messages": sent_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Ollama のネイティブ API 向け。LM Studio では無視されるが、
        # 送っても害は無いので、サーバーを差し替えたときのために残す。
        "think": settings.enable_think,
    }

    logger.info(f"ローカル LLM にリクエスト送信中... model={settings.local_llm_model}, think={settings.enable_think}")
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            # 念のため <think>...</think> ブロックを除去
            # （サーバーによっては思考を content に混ぜて返す）
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            # 出力の上限に達して打ち切られた場合、本文が途中で切れている。
            # 黙って壊れた JSON を返すと呼び出し側で分かりにくい失敗になるため、ここで残す。
            if choice.get("finish_reason") == "length":
                logger.warning(
                    "LLM の出力が上限 (max_tokens=%s) に達して打ち切られました。"
                    "本文 %s 文字。Think モードが有効なら無効化するか、上限を上げてください。",
                    max_tokens, len(content),
                )
            return content
        except Exception as e:
            logger.error(f"ローカル LLM 呼び出しエラー: {e}")
            raise RuntimeError(f"ローカル LLM の呼び出しに失敗しました: {e}")
