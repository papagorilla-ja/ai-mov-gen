from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="table",
    label="表",
    type_id="table",
    when_to_use=(
        "複数の項目を複数の観点で突き合わせるとき。"
        "観点が 3 つ以上あって箇条書きでは対応関係が追えない場合に使う。"
    ),
    capacity=Capacity(min=2, max=6, ideal=(3, 5)),
    # 数字と文字を読ませるレイアウト。背景モチーフは強めに伏せる。
    veil=0.78, orbs=1, phase="P0",
)
