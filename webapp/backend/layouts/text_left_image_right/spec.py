from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="text_left_image_right",
    label="テキスト＋画像",
    type_id="media",
    when_to_use=(
        "説明文と、それが指す実物（写真・画面・図版）を同時に見せるとき。"
        "文章だけでは伝わらない具体物がある場合に使う。"
    ),
    capacity=Capacity(min=1, max=1, ideal=(1, 1)),
    veil=0.85, orbs=1, phase="P0",
)
