import json
import re
import httpx
from fastapi import HTTPException, status
from services.llm_client import chat_completion
from schemas.scenario import ScenarioProposal, ScenarioOutline, ScenarioOutlineItem

# scenario.py のテンプレートなどをこちらに移行して集約
PROMPT_B_TEMPLATE = """あなたは動画の構成を作成するアシスタントです。
ユーザーから入力された「テキスト」を読み取り、論理的な意味のまとまり（シーン）ごとに分割し、各シーンのスライドタイトル、レイアウト、スライド表示内容、およびナレーション原稿を作成してください。

**出力形式:**
必ず以下の JSON フォーマットのスキーマに合致するように出力してください。
マークダウンコードブロック（```json ... ```）で囲って出力してください。
前置きや説明文は一切含めないでください。JSON 以外の出力は無効です。

必ずインプットテキスト全体をカバーし、複数（2〜10程度）のシーンに分割してください。
1つのシーンにすべてをまとめないでください。

**重要指示:**
`text_only` は装飾が少ないため、内容に応じて `bullet_list`（要点列挙）・`comparison`（対比）・`card_panel`（複数トピックの並列提示）・`table`（数値や項目の一覧）・`graph_chart`（数値データの推移や比率）・`section_header`（章の区切り）を積極的に使い分けてください。1つの動画内で同じレイアウトが連続しすぎないようにしてください。

**JSON スキーマ:**
{
  "scenes": [
    {
      "index": 1,
      "layout_type": "bullet_list", // text_only, section_header, bullet_list, text_left_image_right, full_image, comparison, chat_dialog, card_panel, table, graph_chart から選択
      "title": "スライドタイトル",
      "slide_content_json": {
        // layout_type が bullet_list の場合:
        // "bullet_points": ["箇条書き項目1", "箇条書き項目2"]
        // layout_type が comparison の場合:
        // "left_text": "対比テキスト左", "right_text": "対比テキスト右"
        // layout_type が chat_dialog の場合:
        // "lines": [{"speaker": "A", "text": "こんにちは！"}, {"speaker": "B", "text": "よろしくおねがいします！"}]
        // layout_type が card_panel の場合:
        // "cards": [{"title": "機能1", "text": "説明1"}, {"title": "機能2", "text": "説明2"}]
        // layout_type が table の場合:
        // "headers": ["製品", "価格"], "rows": [["プランA", "¥1,000"], ["プランB", "¥2,000"]]
        // layout_type が graph_chart の場合:
        // "chart": {"type": "bar", "labels": ["2023", "2024"], "values": [100, 180], "unit": "成長率(%)"}
        // layout_type が section_header の場合:
        // "subtitle": "セクションのサブタイトル"
        // その他のレイアウトの場合:
        // "body": "スライド内に表示する要約テキスト"
      },
      "narration_text": "このスライドのナレーション原稿（丁寧語で300〜500文字程度）"
    }
  ]
}

**インプットテキスト:**
{{pasted_text}}"""


def extract_json_proposal(text: str) -> ScenarioProposal | None:
    """LLM の応答から ```json ... ``` ブロックまたは通常の JSON 構造を抽出し、パースする。"""
    try:
        # ```json ... ``` の抽出を試みる
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # text 内で最初に出現する { から最後に出現する } までを抽出
            match_raw = re.search(r"(\{.*\})", text, re.DOTALL)
            if match_raw:
                json_str = match_raw.group(1)
            else:
                json_str = text
                
        data = json.loads(json_str)
        # スキーマの検証
        return ScenarioProposal.model_validate(data)
    except Exception as e:
        print(f"JSON proposal parsing failed: {e}")
        return None


def extract_outline_proposal(text: str) -> ScenarioOutline | None:
    """LLM 応答から軽量アウトライン JSON を抽出する。途中で切れていても、
    パースできる範囲の scene 要素だけを救済して返す。"""
    candidates = []
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        candidates.append(m.group(1))
    m2 = re.search(r"(\{.*\})", text, re.DOTALL)
    if m2:
        candidates.append(m2.group(1))
    for c in candidates:
        try:
            data = json.loads(c)
            return ScenarioOutline.model_validate(data)
        except Exception:
            pass
    # 2) 救済: "scenes": [ ... ] の中から、閉じている { ... } オブジェクトだけを個別に拾う
    try:
        arr_start = text.index('"scenes"')
        sub = text[arr_start:]
        items = []
        for obj in re.finditer(r"\{[^{}]*\}", sub):
            try:
                items.append(json.loads(obj.group(0)))
            except Exception:
                continue
        if items:
            return ScenarioOutline.model_validate({"scenes": items})
    except Exception:
        pass
    return None


LAYOUT_CONTENT_PROMPTS: dict[str, str] = {
    "text_only": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「本文テキストだけで見せるスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【body の作り方】
- あらすじを、視聴者がスライドを見ただけで理解できる説明文に展開する
- 80〜150文字。1〜3文。体言止めを避け、丁寧語（です・ます調）で書く
- ナレーションの丸写しにしない。スライドは「要点の提示」、ナレーションは「語り」と役割を分ける

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"body": "…"}}, "narration_text": "…"}}

出力例:
{{"slide_content_json": {{"body": "縄文時代は、農耕を持たないまま定住と祭祀の高度化を実現した、世界的にも稀な社会でした。その仕組みを、同時代の文明と比べながら見ていきます。"}}, "narration_text": "ここでは、縄文時代がなぜ特異な社会だったのかを整理します。…"}}""",

    "bullet_list": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「要点を箇条書きで見せるスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【bullet_points の作り方】
- 3〜5項目。項目数は内容に応じて決める（無理に5つにしない）
- 各項目 20〜40文字。1項目1メッセージ。長い説明文を入れない
- 並列な粒度に揃える（抽象度がバラバラにならないようにする）
- 文末は「〜する」「〜が重要」など簡潔に。句点は付けない

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"bullet_points": ["…", "…", "…"]}}, "narration_text": "…"}}

出力例:
{{"slide_content_json": {{"bullet_points": ["寒冷化と人口減少の時期は一致しない", "地域ごとに異なる適応戦略が存在した", "単一要因ではなく複合的な社会変動"]}}, "narration_text": "縄文社会の衰退を語るとき、しばしば寒冷化が原因として挙げられます。…"}}""",

    "card_panel": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「複数のトピックをカードで並べて見せるスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【cards の作り方】
- 2〜4枚。3枚が最も収まりが良い（横3カラムで表示される）
- 各 title は 6〜16文字の短い見出し（体言止め可）
- 各 text は 40〜70文字の説明文。丁寧語で書く
- カード同士が並列の関係になるようにする（時系列・手法・観点など軸を1つに揃える）

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"cards": [{{"title": "…", "text": "…"}}]}}, "narration_text": "…"}}

出力例:
{{"slide_content_json": {{"cards": [{{"title": "年代測定", "text": "放射性炭素年代測定により、遺物がいつのものかを高い精度で特定します。"}}, {{"title": "残留物分析", "text": "土器に残る有機物を調べ、当時どんな食物を調理していたかを復元します。"}}, {{"title": "同位体分析", "text": "人骨の同位体比から、集団の移動経路や食性の変化を追跡します。"}}]}}, "narration_text": "現代の考古学は、3つの科学的手法でアプローチします。…"}}""",

    "comparison": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「2つを左右に並べて対比するスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【作り方】
- left_title / right_title は比較対象の名前（4〜16文字）。必ず入れる
- left_text / right_text は各 60〜100文字。同じ観点で対比する（片方だけ別の話題にしない）
- 優劣を断定せず、事実ベースで違いを示す

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"left_title": "…", "left_text": "…", "right_title": "…", "right_text": "…"}}, "narration_text": "…"}}

出力例:
{{"slide_content_json": {{"left_title": "メソポタミア・エジプト", "left_text": "穀物農耕を基盤に都市国家が成立しました。階級社会が生まれ、青銅器と文字が発明されています。", "right_title": "縄文日本", "right_text": "農耕も金属器も持たないまま定住が進みました。祭祀は高度化する一方、社会的な不平等は低く保たれています。"}}, "narration_text": "同じ頃、世界では…"}}""",

    "table": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「表で情報を整理して見せるスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【作り方】
- headers は 2〜4列。各 2〜8文字の短い見出し
- rows は 2〜5行。各行の要素数は headers と必ず一致させる
- 各セルは 20文字以内を目安に簡潔に。長文を入れない
- 数値・分類・時期など、表にする意味がある情報だけを載せる

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"headers": ["…", "…"], "rows": [["…", "…"]]}}, "narration_text": "…"}}

出力例:
{{"slide_content_json": {{"headers": ["遺跡", "時期", "特徴"], "rows": [["三内丸山", "前期〜中期", "大型掘立柱建物と長期定住"], ["大湯環状列石", "後期", "祭祀空間としての配石遺構"], ["亀ヶ岡", "晩期", "洗練された遮光器土偶"]]}}, "narration_text": "代表的な遺跡を比べてみましょう。…"}}""",

    "graph_chart": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「グラフで数値を見せるスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【作り方】
- type は bar（項目比較）/ line（時系列の推移）/ pie（構成比）から内容に合うものを選ぶ
- labels と values は必ず同じ個数（3〜6個）にする
- values は数値のみ（単位や記号を混ぜない）。unit に単位名を書く
- あらすじに具体的な数値が無い場合は、代表的・概算であることが分かる粒度で妥当な値を置く

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"chart": {{"type": "bar", "labels": ["…"], "values": [1], "unit": "…"}}}}, "narration_text": "…"}}

出力例:
{{"slide_content_json": {{"chart": {{"type": "bar", "labels": ["前期", "中期", "後期", "晩期"], "values": [120, 260, 180, 90], "unit": "遺跡数（概数）"}}}}, "narration_text": "各時期の遺跡数の変化を見てみます。…"}}""",

    "chat_dialog": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「2人の会話形式で見せるスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【lines の作り方】
- 4〜8発言。speaker は "A"（質問・進行役）と "B"（回答・解説役）を交互に
- 各 text は 20〜60文字。話し言葉で自然に
- A が素朴な疑問を出し、B が分かりやすく答える流れにする

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"lines": [{{"speaker": "A", "text": "…"}}, {{"speaker": "B", "text": "…"}}]}}, "narration_text": "…"}}""",

    "section_header": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「章の区切りを示す扉スライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【subtitle の作り方】
- 30〜60文字。この章で何を扱うかを一言で示す
- 詳細な説明は書かない（扉なので簡潔に）

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"subtitle": "…"}}, "narration_text": "…"}}""",

    "text_left_image_right": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「左に解説テキスト、右に画像を置くスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【作り方】
- body は 80〜120文字。右側に画像が入る前提で、簡潔にまとめる
- image_description には「右側にどんな画像を置くべきか」を日本語で30〜60文字で書く

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"body": "…", "image_description": "…"}}, "narration_text": "…"}}""",

    "full_image": """あなたは研修動画のスライドを作るプロの構成作家です。
このシーンは「画面全体に画像を出し、その上にタイトルを重ねるスライド」です。

シーンタイトル: {title}
このシーンのあらすじ（意図）: {summary}

【作り方】
- body は画像に添える短い説明（40〜80文字）
- image_description には「どんな画像を全画面に置くべきか」を日本語で30〜60文字で書く

出力は次のJSONのみ（前置き・解説・コードブロック外の文字は禁止）:
{{"slide_content_json": {{"body": "…", "image_description": "…"}}, "narration_text": "…"}}""",
}

COMMON_CONTENT_SUFFIX = """

【共通ルール】
- ナレーション(narration_text)は丁寧語（です・ます調）で、20〜35秒で読める300〜500文字程度
- スライドの文言をそのまま読み上げるのではなく、スライドを補足して語る内容にする
- JSON以外の文字（前置き・解説・「以下が結果です」等）は一切出力しない
"""


async def generate_scene_content(title: str, summary: str, layout_type: str) -> dict:
    """レイアウトタイプ別の専用プロンプトで slide_content_json と narration_text を生成する。"""
    template = LAYOUT_CONTENT_PROMPTS.get(layout_type) or LAYOUT_CONTENT_PROMPTS["text_only"]
    prompt = template.format(title=title or "無題", summary=summary or "（未設定）") + COMMON_CONTENT_SUFFIX
    raw = await chat_completion(messages=[{"role": "user", "content": prompt}], provider="local")
    clean = raw.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1]
    if "```" in clean:
        clean = clean.split("```")[0]
    clean = clean.strip()
    try:
        parsed = json.loads(clean)
    except Exception:
        m = re.search(r"(\{.*\})", raw, re.DOTALL)
        parsed = json.loads(m.group(1)) if m else {}
    slide_content = {}
    if isinstance(parsed, dict):
        if "slide_content_json" in parsed and isinstance(parsed["slide_content_json"], dict):
            slide_content = parsed["slide_content_json"]
        else:
            slide_content = {k: v for k, v in parsed.items() if k != "narration_text"}

    return {
        "slide_content_json": slide_content,
        "narration_text": parsed.get("narration_text") or "" if isinstance(parsed, dict) else "",
    }


async def generate_image_prompt(title: str, summary: str, layout_type: str,
                                slide_content: dict | None, image_description: str = "") -> dict:
    """外部の画像生成AI に貼り付けるプロンプトを作る。日本語プロンプトと日本語の意図説明を返す。"""
    prompt = f"""あなたは画像生成AI（Gemini / DALL-E / Midjourney 等）向けのプロンプト作成の専門家です。
研修動画のスライドに載せる画像を作るためのプロンプトを作成してください。

スライドタイトル: {title or "無題"}
このシーンのあらすじ: {summary or "（未設定）"}
レイアウト: {layout_type}
スライドに置きたい画像の内容: {image_description or "（指定なし）"}
スライドの内容: {json.dumps(slide_content, ensure_ascii=False) if slide_content else "なし"}

【プロンプトの条件】
- 日本語で書く（Gemini など日本語対応の画像生成AIに貼り付けて使う）
- 被写体・構図・画風・色調・ライティング・雰囲気を具体的に指定する
- 動画スライドの背景／挿絵として使うため、画像内に文字を入れないよう明示する
  （「文字・ロゴ・ウォーターマークは入れない」ことを明記する）
- 横長（16:9）で使うため、横長構図であることと、余白（被写体を中央〜片側に寄せる等）の指定を含める
- 研修資料にふさわしい、落ち着いた品位のある画風にする
- 実在の人物名・商標・特定作品の模倣は指定しない

出力は次のJSONのみ（前置き・解説なし）:
{{"image_prompt": "日本語の画像生成プロンプト", "note": "どんな画像を狙ったかの日本語の補足（40〜80字）"}}"""

    raw = await chat_completion(messages=[{"role": "user", "content": prompt}], provider="local")
    clean = raw.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1]
    if "```" in clean:
        clean = clean.split("```")[0]
    clean = clean.strip()
    try:
        parsed = json.loads(clean)
    except Exception:
        m = re.search(r"(\{.*\})", raw, re.DOTALL)
        parsed = json.loads(m.group(1)) if m else {}
    return {
        "image_prompt": parsed.get("image_prompt") or "",
        "note": parsed.get("note") or ""
    }


async def generate_narration(title: str, slide_content_json: dict | None, prev_narration: str, summary: str = "") -> str:
    """スライド情報をもとにナレーション文を生成する"""
    prompt = f"""以下のスライド情報をもとに、動画ナレーション文を生成してください。
- 口語体・丁寧語（です・ます調）
- 20〜35秒で読める長さ（300〜500文字目安）
- スライドのタイトルや要点を自然に説明する
- ナレーションのテキストのみ返す（説明・JSON 不要）

スライドタイトル: {title or "無題のシーン"}
このシーンのあらすじ: {summary or "なし"}
スライド内容: {json.dumps(slide_content_json, ensure_ascii=False) if slide_content_json else "なし"}
前のシーンのナレーション（参考）: {prev_narration}"""

    try:
        reply = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            provider="local"
        )
        return reply.strip()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM サーバーに接続できません: {str(e)}")


def _format_options(options: list[dict]) -> str:
    """LLM に見せる選択肢の一覧を「値: 説明」の箇条書きにする。"""
    return "\n".join(f'  - "{o["value"]}": {o["description"]}' for o in options)


async def apply_style_prompt(current_style_dict: dict, style_prompt: str) -> dict:
    """現在のスタイルに指示プロンプトを適用して新しいデザイン設定一式を生成する。

    配色だけを返させると「和風にして」の指示に対して色だけ変わり、背景は
    グリッド・カードはグラスのまま、という嚙み合わない結果になる。
    そのため背景モチーフ・装飾スタイル・組版・切替まで一括で選ばせる。
    選択肢は design_tokens.py から流し込み、プロンプト内に値を直書きしない。
    """
    from services.design_tokens import (
        BACKGROUND_MOTIFS,
        DECOR_STYLES,
        DEFAULTS,
        FONT_CHOICES,
        TRANSITIONS,
        TYPE_SCALES,
    )

    font_list = "\n".join(f'  - "{o["value"]}": {o["description"]}' for o in FONT_CHOICES)

    prompt_text = f"""あなたはクリエイティブなフロントエンドデザイナーです。
ユーザーから「研修動画のデザイン指示」を受け取り、それに合わせたデザイン設定一式を提案してください。

**配色の条件:**
- color_primary, color_secondary, color_accent, color_bg, color_text_primary を16進数カラーコード（例: #ffffff）で返してください。
- color_bg と color_text_primary のコントラスト比を必ず 7:1 以上確保してください。ここが不足すると本文が読めなくなります。
- 背景を明るくする場合は文字色を必ず濃くしてください（逆も同様）。

**フォント（この一覧の値をそのまま使うこと。他の名前は使用不可）:**
{font_list}

**背景モチーフ background_motif（この一覧の値のみ）:**
{_format_options(BACKGROUND_MOTIFS)}

**装飾スタイル decor_style（この一覧の値のみ）:**
{_format_options(DECOR_STYLES)}

**組版 type_scale（この一覧の値のみ）:**
{_format_options(TYPE_SCALES)}

**シーン切替 transition（この一覧の値のみ）:**
{_format_options(TRANSITIONS)}

**出力形式:**
前置きや解説は一切出力せず、以下の JSON のみを出力してください。

{{
  "color_primary": "メインカラー",
  "color_secondary": "サブカラー",
  "color_accent": "アクセントカラー",
  "color_bg": "背景カラー",
  "color_text_primary": "テキストカラー",
  "font_heading": "見出しフォント名",
  "font_body": "本文フォント名",
  "background_motif": "背景モチーフの値",
  "decor_style": "装飾スタイルの値",
  "type_scale": "組版の値",
  "transition": "シーン切替の値"
}}

現在の設定:
- color_primary: {current_style_dict.get("color_primary") or DEFAULTS["color_primary"]}
- color_bg: {current_style_dict.get("color_bg") or DEFAULTS["color_bg"]}
- color_text_primary: {current_style_dict.get("color_text_primary") or DEFAULTS["color_text_primary"]}
- background_motif: {current_style_dict.get("background_motif") or DEFAULTS["background_motif"]}
- decor_style: {current_style_dict.get("decor_style") or DEFAULTS["decor_style"]}

デザイン指示: {style_prompt}"""

    try:
        reply = await chat_completion(
            messages=[{"role": "user", "content": prompt_text}],
            provider="local"
        )
        clean_reply = reply.strip()
        if "```json" in clean_reply:
            clean_reply = clean_reply.split("```json")[1]
        if "```" in clean_reply:
            clean_reply = clean_reply.split("```")[0]
        clean_reply = clean_reply.strip()
        
        parsed = json.loads(clean_reply)
        return parsed
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM接続エラーが発生しました。ローカルLLMサーバーの起動状態を確認してください。: {str(e)}"
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"LLMの応答がJSONフォーマットではありませんでした。もう一度お試しください。({str(e)})"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"スタイルAI生成中に予期しないエラーが発生しました: {str(e)}"
        )


async def generate_slide_narration(
    slide_title: str,
    bullets: list[str],
    table_summary: str,
    visual_summary: str,
    notes: str,
    prev_title: str,
) -> str:
    """PPTX の1スライド分の情報からナレーション文（プレーンテキスト）を生成する。

    ノートがあればそれを土台に整えるだけにし、無ければ他の情報から新規生成する。
    JSON を使わずプレーンテキストで受け取ることで、パース失敗の余地を無くす。
    """
    bullets_text = "\n".join(f"- {b}" for b in bullets) if bullets else "（なし）"
    context_lines = [
        f"スライドタイトル: {slide_title or '（無題）'}",
        f"箇条書き:\n{bullets_text}",
    ]
    if table_summary:
        context_lines.append(f"表の内容: {table_summary}")
    if visual_summary:
        context_lines.append(f"画像・図解の内容: {visual_summary}")
    if prev_title:
        context_lines.append(f"直前のスライドのタイトル: {prev_title}（話の接続を自然にすること）")
    context = "\n".join(context_lines)

    if notes and len(notes.strip()) >= 20:
        prompt = f"""以下は研修動画のスライドに付いている「発表者ノート」です。
内容や意味を変えずに、動画のナレーションとして自然に読み上げられる、丁寧語（です・ます調）の文章に整えてください。

【発表者ノート】
{notes}

【スライド情報（参考）】
{context}

【出力ルール】
- 前置き・見出し・箇条書き記号（-, ・, 1. など）は一切付けない
- 整えた本文だけをプレーンテキストで出力する
- ノートに無い情報を新たに付け加えない"""
    else:
        prompt = f"""あなたは研修動画のナレーション原稿を書くプロの構成作家です。
以下のスライド情報をもとに、20〜35秒で読み切れる（300〜500文字程度)、丁寧語（です・ます調）のナレーション原稿を書いてください。

【スライド情報】
{context}

【出力ルール】
- 前置き・見出し・箇条書き記号（-, ・, 1. など）は一切付けない
- ナレーション本文だけをプレーンテキストで出力する
- スライドの文言をそのまま読み上げず、内容を補足しながら語る"""

    raw = await chat_completion(messages=[{"role": "user", "content": prompt}], provider="local")
    text = raw.strip()
    # 先頭に付きがちな "ナレーション:" 等のラベル行や Markdown 記号を除去
    text = re.sub(r"^(ナレーション|narration)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```[a-z]*\n?|```$", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"^[-・*]\s+", "", text, flags=re.MULTILINE)
    return text.strip()


async def split_text_to_scenes(text: str) -> str:
    """プレーンテキストからシーン分割提案の生の応答を生成する"""
    prompt = PROMPT_B_TEMPLATE.replace("{{pasted_text}}", text)
    try:
        llm_response = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは動画シナリオを生成するアシスタントです。"
                        "ユーザーの指示に従い、指定された JSON フォーマットのみを返してください。"
                        "前置き・解説・マークダウンのコードブロック以外のテキストは出力しないでください。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            provider="local"
        )
        return llm_response
    except Exception as e:
        raise RuntimeError(f"LLM 呼び出しに失敗しました: {e}")


async def send_chat_message(messages: list[dict]) -> str:
    """AIチャット（壁打ち）の返答を生成する"""
    try:
        reply = await chat_completion(
            messages=messages,
            provider="local"
        )
        return reply
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM サーバーに接続できません: {str(e)}")


SCENE_HTML_GROUNDING_PROMPT = """あなたは HyperFrames という動画レンダリングフレームワーク向けに、
1つのスライド（シーン）の HTML/CSS 断片を編集するアシスタントです。
以下のルールを厳密に守ってください。

【出力対象】
1つのスライドの中身の断片のみを返します。<html>/<head>/<body>、
data-composition-id を持つルート要素、GSAP のタイムライン登録スクリプト
（window.__timelines への登録）は含めないでください
（このアプリでは全シーン共通のアニメーション制御スクリプトが既に1つ用意されているため不要です）。

【必須ルール】
- 利用できる既製クラス: slide-eyebrow / slide-title / slide-body-area / body-card / body-text /
  bullet-list / bullet-item / bullet-num / bullet-content / card-grid(.cols-2|.cols-3) /
  info-card / info-card-index / info-card-title / info-card-text /
  comparison-cols / comparison-col(.left|.right) / comparison-col-head / comparison-vs /
  section-title / section-rule / section-subtitle / data-table / deco-orb(.deco-orb-1|.deco-orb-2)
  → まずこれらの組み合わせで構成し、必要な差分だけ style 属性や css で足すこと。
- アニメーション・表示制御の対象にしたい要素には必ず class="clip" を付与する
- class="clip" を持つ要素には data-start（スライド内の相対開始秒）と
  data-duration（表示継続秒）を必ず付与する（スライド全体の開始時刻ではなく相対値でよい）
- 複数のカードや箇条書きを出すときは、要素ごとに data-start を 0.2〜0.3 秒ずつずらして
  順番に登場させること（一斉に出さない）
- レイヤーの重なり順を変えたい場合のみ data-track-index を使う（省略可。大きいほど手前）
- React 等のフレームワークは使わず、プレーンな HTML/CSS のみ。<script> は
  グラフ描画（Chart.js。既にページ全体で読み込み済み）以外の用途では使わないこと
- 独自CSSを追加する場合、セレクタは必ず指定された scene_dom_id 配下にスコープすること
  （他のシーンに影響を与えないため）
- 「(中略)」「...は省略」等の不完全な出力は禁止
- 前置き・説明文なしで、指定したJSON形式のみを返すこと

【よくあるミス】
- class="clip" を付け忘れる → 要素が表示されない
- data-start/data-duration を付け忘れる → タイミング制御ができない
- 独自に <script> でタイムラインを再登録してしまう → 既存の制御と衝突するため不要

【Few-shot例】
例1: 本文をカードで見せる（text_only）
指示: 本文が味気ないので、カードで見せて装飾を足してください

出力:
{"html": "<div class=\"deco-orb deco-orb-1\"></div>\n<div class=\"clip slide-eyebrow\" data-start=\"0.50\" data-duration=\"9.50\">Scene 03</div>\n<h1 class=\"clip slide-title\" data-start=\"0.65\" data-duration=\"9.35\">なぜ今、縄文なのか？</h1>\n<div class=\"slide-body-area\">\n  <div class=\"clip body-card\" data-start=\"0.95\" data-duration=\"9.05\">\n    <p class=\"body-text\">持続可能な資源利用や多様な定住形態が、現代の環境・社会課題にどのような示唆を与えるかを論じます。</p>\n  </div>\n</div>", "css": ""}

例2: 箇条書きを番号バッジ付きカードにして順番に出す（bullet_list）
指示: 箇条書きをカードにして、順番に出てくるようにしてください

出力:
{"html": "<div class=\"deco-orb deco-orb-2\"></div>\n<div class=\"clip slide-eyebrow\" data-start=\"0.50\" data-duration=\"9.50\">Key Points</div>\n<h1 class=\"clip slide-title\" data-start=\"0.65\" data-duration=\"9.35\">衰退説の再検討</h1>\n<div class=\"slide-body-area\">\n  <div class=\"bullet-list\">\n    <div class=\"clip bullet-item\" data-start=\"0.95\" data-duration=\"9.05\"><div class=\"bullet-num\">1</div><div class=\"bullet-content\"><p>寒冷化と人口減少の時期は必ずしも一致していない</p></div></div>\n    <div class=\"clip bullet-item\" data-start=\"1.20\" data-duration=\"8.80\"><div class=\"bullet-num\">2</div><div class=\"bullet-content\"><p>地域ごとに異なる適応戦略が確認されている</p></div></div>\n    <div class=\"clip bullet-item\" data-start=\"1.45\" data-duration=\"8.55\"><div class=\"bullet-num\">3</div><div class=\"bullet-content\"><p>単一要因ではなく複合的な社会変動として捉える</p></div></div>\n  </div>\n</div>", "css": ""}

例3: 3つのトピックをカードグリッドで並べる（card_panel）
指示: 3つの手法をカードで横に並べて見せてください

出力:
{"html": "<div class=\"deco-orb deco-orb-1\"></div>\n<div class=\"clip slide-eyebrow\" data-start=\"0.50\" data-duration=\"9.50\">Methods</div>\n<h1 class=\"clip slide-title\" data-start=\"0.65\" data-duration=\"9.35\">現代考古学の手法</h1>\n<div class=\"slide-body-area\">\n  <div class=\"card-grid cols-3\">\n    <div class=\"clip info-card\" data-start=\"0.95\" data-duration=\"9.05\"><div class=\"info-card-index\">01</div><div class=\"info-card-title\">年代測定</div><p class=\"info-card-text\">放射性炭素年代測定により、遺物の年代を高精度で特定します。</p></div>\n    <div class=\"clip info-card\" data-start=\"1.20\" data-duration=\"8.80\"><div class=\"info-card-index\">02</div><div class=\"info-card-title\">残留物分析</div><p class=\"info-card-text\">土器に残る有機物から、当時の食生活を科学的に復元します。</p></div>\n    <div class=\"clip info-card\" data-start=\"1.45\" data-duration=\"8.55\"><div class=\"info-card-index\">03</div><div class=\"info-card-title\">同位体分析</div><p class=\"info-card-text\">人骨の同位体比から、移動経路や食性の変化を追跡します。</p></div>\n  </div>\n</div>", "css": ""}
"""


async def ai_adjust_scene_design(current_html: str, current_css: str, instruction: str, scene_dom_id: str, style_vars: dict) -> dict:
    """シーン単位のAIデザイン調整。"""
    user_prompt = f"""このシーンの scene_dom_id は "{scene_dom_id}" です。
現在のスタイル変数（配色）: {json.dumps(style_vars, ensure_ascii=False)}

現在のHTML断片:
```html
{current_html}
```

現在のカスタムCSS（未設定なら空）:
```css
{current_css}
```

ユーザーからの調整指示: {instruction}

上記のルールに従い、更新後のHTML断片とCSSを次のJSON形式のみで返してください。
{{"html": "...", "css": "..."}}
"""
    raw = await chat_completion(
        messages=[
            {"role": "system", "content": SCENE_HTML_GROUNDING_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        provider="local"
    )
    clean_raw = raw.strip()
    if "```json" in clean_raw:
        clean_raw = clean_raw.split("```json")[1]
    if "```" in clean_raw:
        clean_raw = clean_raw.split("```")[0]
    clean_raw = clean_raw.strip()

    parsed = {}
    try:
        parsed = json.loads(clean_raw)
    except Exception:
        match = re.search(r"(\{.*\})", raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
            except Exception:
                pass

    return {
        "html": parsed.get("html") or current_html,
        "css": parsed.get("css") if parsed.get("css") is not None else current_css,
    }
