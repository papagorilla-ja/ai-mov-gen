from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="list_stack",
    label="カード縦積み",
    type_id="list",
    when_to_use=(
        "並列の項目それぞれに、横並びでは入り切らない長さの説明が付くとき。"
        "1 項目 2〜3 行になる場合はこちら。短いなら番号付きリストを使う。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(2, 3)),
    veil=0.85, orbs=1, phase="P1",
)
