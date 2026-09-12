from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="formula_multiply",
    label="数式（掛け算・足し算）",
    type_id="formula",
    when_to_use=(
        "複数の要素が組み合わさって結果が決まることを示すとき。"
        "「どれか 1 つでも欠けたら成立しない」ことを掛け算で表すのに向く。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(2, 3)),
    veil=0.85, orbs=1, phase="P0",
)
