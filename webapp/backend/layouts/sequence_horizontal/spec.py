from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="sequence_horizontal",
    label="横型フロー",
    type_id="sequence",
    when_to_use=(
        "手順や段階を左から右へ進む形で見せるとき。"
        "各ステップの説明が短く、全体の流れを一目で掴ませたい場合に使う。"
    ),
    capacity=Capacity(min=2, max=5, ideal=(3, 4)),
    veil=0.85, orbs=1, phase="P0",
)
