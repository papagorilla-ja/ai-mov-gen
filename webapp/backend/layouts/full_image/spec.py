from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="full_image",
    label="全面画像",
    type_id="media",
    when_to_use=(
        "画像そのものに語らせるとき。章の導入や、現場の空気を伝えたい場面に使う。"
        "文字は最小限しか載せられない。"
    ),
    capacity=Capacity(min=1, max=1, ideal=(1, 1)),
    # 画面全部が画像になるため、背景モチーフは完全に消す。
    veil=1.0, orbs=0, phase="P0",
)
