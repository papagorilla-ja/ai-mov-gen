from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="contrast_stack",
    label="上下対比",
    type_id="contrast",
    when_to_use=(
        "2 つの説明がそれぞれ長く、左右に割ると 1 行が短くなりすぎるとき。"
        "上下に積むと 1 行の幅を full で使えるので、文章での対比に向く。"
    ),
    capacity=ANY, veil=0.85, orbs=1, phase="P1",
)
