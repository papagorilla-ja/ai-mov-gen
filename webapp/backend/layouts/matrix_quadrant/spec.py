from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="matrix_quadrant",
    label="四象限",
    type_id="matrix",
    when_to_use=(
        "2 つの基準の組み合わせで 4 通りに仕分けるとき。"
        "優先度の判断や、立ち位置の説明に使う。基準が 1 つなら対比を使う。"
    ),
    capacity=Capacity(min=4, max=4, ideal=(4, 4)),
    veil=0.85, orbs=1, phase="P0",
)
