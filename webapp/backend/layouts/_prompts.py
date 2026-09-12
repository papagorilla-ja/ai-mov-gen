"""LLM プロンプトの部品を、型とレイアウトの定義から自動で組み立てる。

プロンプトに値を直書きしない（design_tokens.py と同じ方針）。
レイアウトを 1 つ足したら、AI が選べる候補にも自動で載る。

2 段階にしている理由:
    ローカルの qwen3:14b に 40 種類のスキーマを一度に見せるのは、
    トークン量でも選択精度でも成立しない。

      段階 1 … 「この内容はどの型か」            14 択
      段階 2 … その型のスキーマで内容を作りつつ
               「どの見せ方か」を選ぶ             4〜6 択
      段階 3 … 件数・縦横比・連続の検査（LLM 不使用、_registry.resolve）
"""

from layouts._icons import icon_names
from layouts._registry import layouts_for_type
from layouts._types import CONTENT_TYPES, COMMON_FIELDS, FieldSpec


# ==========================================================================
# 段階 1 — 型の一覧
# ==========================================================================

def type_menu(allowed: tuple[str, ...] | None = None) -> str:
    """「この内容はどの型か」を選ばせるための一覧。"""
    ids = allowed or tuple(CONTENT_TYPES)
    lines = []
    for tid in ids:
        ct = CONTENT_TYPES.get(tid)
        if ct:
            lines.append(f'  - "{ct.id}"（{ct.label}）: {ct.description}')
    return "\n".join(lines)


# ==========================================================================
# 段階 2 — 型のスキーマと見せ方の候補
# ==========================================================================

def _field_line(f: FieldSpec, indent: str, last: bool = False) -> list[str]:
    """1 フィールドを「JSON の形 + 書き方の指針」の行にする。

    末尾カンマの有無まで正しく出すこと。LLM はこの雛形をそのまま真似るため、
    壊れた JSON を見せると壊れた JSON を返してくる。
    """
    note = f"{f.label}"
    if f.hint:
        note += f" — {f.hint}"
    if f.max_chars:
        note += f"（{f.max_chars}文字以内）"
    comma = "" if last else ","

    if f.kind == "items":
        out = [f'{indent}"{f.name}": [                 // {note}', f"{indent}  {{"]
        for i, child in enumerate(f.children):
            out.extend(_field_line(child, indent + "    ", last=(i == len(f.children) - 1)))
        out.append(f"{indent}  }}")
        out.append(f"{indent}]{comma}")
        return out
    if f.kind == "group":
        out = [f'{indent}"{f.name}": {{                // {note}']
        for i, child in enumerate(f.children):
            out.extend(_field_line(child, indent + "  ", last=(i == len(f.children) - 1)))
        out.append(f"{indent}}}{comma}")
        return out
    if f.kind == "tree":
        return [f'{indent}"{f.name}": [{{"label": "…", "text": "…", "children": []}}]{comma}   // {note}']
    if f.kind == "table":
        return [f'{indent}"headers": ["…", "…"],   // {note}', f'{indent}"rows": [["…", "…"]]{comma}']
    if f.kind == "chart":
        return [f'{indent}"chart": {{"type": "bar|line|pie", "labels": ["…"], "values": [0], "unit": "…"}}{comma}   // {note}']
    if f.kind == "images":
        return [f'{indent}"image_description": "…"{comma}   // どんな画像を置くべきかを日本語 30〜60 文字で']
    if f.kind == "choice":
        opts = " | ".join(f.options)
        return [f'{indent}"{f.name}": "{opts}"{comma}   // {note}（この中から選ぶ）']
    return [f'{indent}"{f.name}": "…"{comma}   // {note}']


def schema_sketch(type_id: str) -> str:
    """その型の JSON の形を、書き方の指針つきで組み立てる。"""
    ct = CONTENT_TYPES.get(type_id)
    if not ct:
        return "{}"
    # 画像そのものは人間がアップロードするので、AI には「何を置くべきか」だけ書かせる。
    fields = list(COMMON_FIELDS) + list(ct.fields)
    lines = ["{"]
    for i, f in enumerate(fields):
        lines.extend(_field_line(f, "  ", last=(i == len(fields) - 1)))
    lines.append("}")
    return "\n".join(lines)


def layout_menu(type_id: str, aspect: str = "16:9") -> str:
    """その型に属する見せ方の候補一覧。"""
    lines = []
    for s in layouts_for_type(type_id):
        if aspect not in s.aspect:
            continue
        cap = "件数の制限なし" if s.capacity.any else f"{s.capacity.min}〜{s.capacity.max}件"
        lines.append(f'  - "{s.id}"（{s.label} / {cap}）: {s.when_to_use}')
    return "\n".join(lines)


def default_layout_for(type_id: str) -> str:
    specs = layouts_for_type(type_id)
    return specs[0].id if specs else "text_only"


ICON_VOCABULARY_NOTE = (
    "icon に書けるのは次の語だけです（それ以外を書くとアイコンは表示されません）:\n  "
    + " / ".join(icon_names())
)


def content_prompt(type_id: str, title: str, summary: str, aspect: str = "16:9") -> str:
    """段階 2 のプロンプト。内容の生成と見せ方の選択を 1 回のやり取りで行う。"""
    ct = CONTENT_TYPES.get(type_id) or CONTENT_TYPES["statement"]
    menu = layout_menu(type_id, aspect)
    fallback = default_layout_for(type_id)
    uses_icon = any(
        child.name == "icon" for f in ct.fields for child in f.children
    )

    return f"""あなたは研修動画のスライドを作るプロの構成作家です。

このシーンは「{ct.label}」の型で作ります。
{ct.description}

シーンタイトル: {title or "無題"}
このシーンのあらすじ（意図）: {summary or "（未設定）"}

【1】次の JSON の形で、スライドに載せる内容を作ってください。
コメント（//）は書き方の指針です。出力には含めないでください。

{schema_sketch(type_id)}

【2】あわせて、この内容に最も合う「見せ方」を次から 1 つ選び、layout に書いてください。

{menu or f'  - "{fallback}"'}

{ICON_VOCABULARY_NOTE if uses_icon else ""}

【共通ルール】
- ナレーション(narration_text)は丁寧語（です・ます調）で、20〜35秒で読める300〜500文字程度
- スライドの文言をそのまま読み上げるのではなく、スライドを補足して語る内容にする
- 指定した文字数の目安を必ず守る。長いと動画のスライドからはみ出します
- JSON以外の文字（前置き・解説・「以下が結果です」等）は一切出力しない

出力は次の形の JSON のみ:
{{"layout": "見せ方の値", "slide_content_json": {{ ここに【1】の内容 }}, "narration_text": "…"}}"""
