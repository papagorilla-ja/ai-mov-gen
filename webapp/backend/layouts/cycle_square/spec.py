from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="cycle_square",
    label="四角型サイクル（4 段階）",
    type_id="cycle",
    when_to_use=(
        "4 段階で一巡する反復を示すとき。PDCA のように段階が 4 つに固定されている"
        "場合に向く。横長の画面を無駄なく使える。件数が 4 でないなら円型サイクルを使う。"
    ),
    # 4 件ちょうどのときだけ成立する形。3 件や 5 件は円型サイクルへ回る。
    capacity=Capacity(min=4, max=4, ideal=(4, 4)),
    veil=0.85, orbs=1, phase="P2",
    sample={"nodes": [
        {"label": "計画", "text": "何を確かめたいかを決めます。", "icon": "計画"},
        {"label": "実行", "text": "決めた範囲で実際にやってみます。", "icon": "実行"},
        {"label": "評価", "text": "結果を記録し、狙いと比べます。", "icon": "分析"},
        {"label": "改善", "text": "分かったことを次の計画に入れます。", "icon": "改善"},
    ]},
)
