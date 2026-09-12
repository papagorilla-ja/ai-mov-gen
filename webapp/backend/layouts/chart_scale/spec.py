import math

from layouts._registry import Capacity, LayoutSpec

# 円の直径の下限・上限（枠の高さに対する割合）。
# 下限を置かないと、小さい値の円が点になって文字が入らなくなる。
MIN_RATIO, MAX_RATIO = 0.30, 1.0


def _prepare(content: dict, ctx: dict) -> dict:
    """値を「円の面積」に対応させる。

    直径を値に比例させると、面積は値の 2 乗で増えてしまい、
    差が実際よりずっと大きく見える。直径は平方根に比例させる。
    """
    cfg = content.get("chart") or {}
    labels = cfg.get("labels") or []
    values = cfg.get("values") or []
    pairs = [(labels[i], float(values[i])) for i in range(min(len(labels), len(values)))]
    top = max((v for _, v in pairs), default=0) or 1
    items = [
        {
            "label": label,
            "value": f"{value:g}",
            "ratio": round(MIN_RATIO + (MAX_RATIO - MIN_RATIO) * math.sqrt(max(0.0, value) / top), 3),
        }
        for label, value in pairs
    ]
    return {"items": items, "unit": cfg.get("unit") or ""}


SPEC = LayoutSpec(
    id="chart_scale",
    label="規模比較（面積）",
    type_id="chart",
    when_to_use=(
        "量の桁違いを体感させたいとき。棒グラフより「大きさそのもの」が伝わる。"
        "3〜4 件まで。細かい数値を読ませたいならグラフか表を使う。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(2, 3)),
    veil=0.78, orbs=1, phase="P1", prepare=_prepare,
    sample={"chart": {"type": "bar", "labels": ["紙の帳票", "表計算", "業務システム"],
                      "values": [1, 6, 40], "unit": "倍"}},
)
