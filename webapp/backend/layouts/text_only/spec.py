from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="text_only",
    label="本文カード",
    type_id="statement",
    when_to_use=(
        "伝えたいことが 1 つで、分解も比較もしないとき。"
        "導入・結論・次の章へのつなぎなど、文章で語る場面に使う。"
    ),
    capacity=ANY,
    veil=0.85,
    orbs=1,
    phase="P0",
)
