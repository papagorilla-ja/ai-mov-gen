from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="section_header",
    label="章扉",
    type_id="cover",
    when_to_use=(
        "話題が大きく切り替わるとき。ここまでの内容を一度閉じて、"
        "次に何を扱うかだけを示す。内容そのものは載せない。"
    ),
    capacity=ANY,
    # 章扉は背景モチーフを主役にする。ここだけ覆いを外して「間」を作る。
    veil=0.0, orbs=2, phase="P0",
)
