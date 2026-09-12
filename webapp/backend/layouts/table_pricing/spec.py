from layouts._registry import Capacity, LayoutSpec


def _prepare(content: dict, ctx: dict) -> dict:
    """表を「列ごとのカード」に組み替える。

    headers の 2 列目以降が 1 枚ずつのカードになり、
    各行の 1 列目が項目名、その列の値が中身になる。
    表のまま出すと「どのプランの話か」を目で追う必要があるが、
    カードにすると 1 枚ずつ順に見られる。
    """
    headers = content.get("headers") or []
    rows = content.get("rows") or []
    plans = []
    for col in range(1, len(headers)):
        plans.append({
            "name": headers[col],
            "lines": [
                {"label": row[0] if row else "", "value": row[col] if col < len(row) else ""}
                for row in rows
            ],
        })
    return {"plans": plans}


SPEC = LayoutSpec(
    id="table_pricing",
    label="プラン比較（列カード）",
    type_id="table",
    when_to_use=(
        "いくつかの選択肢を、同じ項目で 1 枚ずつ比べさせるとき。料金プランや方式の比較に向く。"
        "headers の 1 列目は空にし、2 列目以降に選択肢の名前を書く。"
    ),
    capacity=Capacity(min=2, max=5, ideal=(3, 4)),
    veil=0.78, orbs=1, phase="P1", prepare=_prepare,
    sample={
        "headers": ["", "自習のみ", "集合研修", "伴走支援"],
        "rows": [
            ["期間", "随時", "1 日", "3 か月"],
            ["1人あたり費用", "0 円", "2 万円", "12 万円"],
            ["定着率", "低い", "中程度", "高い"],
        ],
    },
)
