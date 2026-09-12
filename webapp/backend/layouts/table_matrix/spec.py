from layouts._registry import Capacity, LayoutSpec

# 記号と、それをどう見せるか。◯△✕ は表記の揺れが大きいので広めに拾う。
MARKS = {
    "○": "ok", "◯": "ok", "〇": "ok", "◎": "ok", "✓": "ok", "✔": "ok", "可": "ok",
    "△": "mid", "▲": "mid", "±": "mid", "一部": "mid",
    "×": "ng", "✕": "ng", "✗": "ng", "－": "ng", "-": "ng", "不可": "ng", "なし": "ng",
}


def _prepare(content: dict, ctx: dict) -> dict:
    """各セルが記号かどうかを判定し、記号なら種別を付けて返す。

    テンプレートで判定すると、記号の揺れの吸収が Jinja の式に散らばる。
    ここで [[{"text":…, "mark":"ok"|"mid"|"ng"|None}, …], …] の形に整えておく。
    """
    cells = []
    for row in content.get("rows") or []:
        cells.append([
            {"text": str(cell), "mark": MARKS.get(str(cell).strip())}
            for cell in row
        ])
    return {"cells": cells}


SPEC = LayoutSpec(
    id="table_matrix",
    label="○× 比較表",
    type_id="table",
    when_to_use=(
        "複数の選択肢が、複数の条件を満たすかどうかを一覧で示すとき。"
        "セルには ○ △ × のような記号を入れる。数値や文章を入れるなら通常の表を使う。"
    ),
    capacity=Capacity(min=2, max=6, ideal=(3, 5)),
    veil=0.78, orbs=1, phase="P1", prepare=_prepare,
    sample={
        "headers": ["", "紙の帳票", "表計算", "業務システム"],
        "rows": [
            ["導入の手軽さ", "○", "○", "×"],
            ["検索できる", "×", "○", "○"],
            ["同時に編集できる", "×", "△", "○"],
            ["記録が自動で残る", "×", "×", "○"],
        ],
    },
)
