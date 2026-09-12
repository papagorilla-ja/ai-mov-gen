from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="list_icon_row",
    label="ピクトグラム横並び",
    type_id="list",
    when_to_use=(
        "並列の項目を、絵で一目で区別させたいとき。各項目の説明が 1〜2 行と短く、"
        "文字より記号の方が速く伝わる場面に使う。icon を必ず埋めること。"
    ),
    capacity=Capacity(min=2, max=5, ideal=(3, 4)),
    veil=0.85, orbs=1, phase="P1",
)
