from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="card_panel",
    label="カード横並び",
    type_id="list",
    when_to_use=(
        "並列の項目それぞれに説明文が付くとき。横に並べて「同じ重みの選択肢が"
        "複数ある」ことを一目で示す。3 枚が最も収まりが良い。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(3, 3)),
    veil=0.85, orbs=1, phase="P0",
)
