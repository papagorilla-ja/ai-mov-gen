from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="bullet_list",
    label="番号付きリスト",
    type_id="list",
    when_to_use=(
        "要点を順に読ませたいとき。1 項目が 1 行に収まる短さで、"
        "上から下へ目で追う内容に向く。"
    ),
    capacity=Capacity(min=2, max=6, ideal=(3, 5)),
    veil=0.85,
    orbs=1,
    phase="P0",
)
