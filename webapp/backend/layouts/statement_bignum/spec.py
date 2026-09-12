from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="statement_bignum",
    label="巨大数値",
    type_id="statement",
    when_to_use=(
        "数字 1 つで驚かせたいとき。lead に数値と単位だけを書く（例:「78%」「3.2倍」）。"
        "複数の数値を比べたいならグラフを使う。"
    ),
    capacity=ANY,
    veil=0.6, orbs=2, phase="P1",
    sample={"lead": "72%", "body": "研修から 1 か月後に、内容を業務で一度も使わなかった人の割合です。",
            "note": "社内アンケート（n=240）"},
)
