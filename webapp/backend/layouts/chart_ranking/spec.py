from layouts._registry import Capacity, LayoutSpec


def _prepare(content: dict, ctx: dict) -> dict:
    """数値の大きい順に並べ、最大値に対する割合（棒の長さ）を付ける。

    Chart.js は使わない。順位・名前・数値・棒を横一列に並べたいが、
    canvas ではその組版ができないため HTML で組む。
    """
    cfg = content.get("chart") or {}
    labels = cfg.get("labels") or []
    values = cfg.get("values") or []
    pairs = [(labels[i], values[i]) for i in range(min(len(labels), len(values)))]
    pairs.sort(key=lambda p: p[1], reverse=True)
    top = max((v for _, v in pairs), default=0) or 1
    rows = [
        {
            "rank": i + 1,
            "label": label,
            # 小数が出るのは「3.2倍」のような指標のときだけ。整数はそのまま見せる。
            "value": f"{value:g}",
            "pct": round(max(4.0, value / top * 100), 1),
        }
        for i, (label, value) in enumerate(pairs)
    ]
    return {"rows": rows, "unit": cfg.get("unit") or ""}


SPEC = LayoutSpec(
    id="chart_ranking",
    label="ランキング",
    type_id="chart",
    when_to_use=(
        "数値の順位そのものを見せるとき。どれが一番かを印象づけたい場面に使う。"
        "推移や構成比を見せたいなら通常のグラフを使う。"
    ),
    capacity=Capacity(min=3, max=6, ideal=(3, 5)),
    veil=0.78, orbs=1, phase="P1", prepare=_prepare,
    sample={"chart": {"type": "bar",
                      "labels": ["手順書の不足", "引き継ぎ不足", "確認の抜け", "ツールの使い方", "その他"],
                      "values": [42, 31, 18, 7, 2], "unit": "件"}},
)
