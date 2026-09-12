from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="statement_hero",
    label="大見出し一文",
    type_id="statement",
    when_to_use=(
        "その章で一番言いたい一文を、画面いっぱいに置いて印象づけるとき。"
        "情報量を捨ててでも 1 つのメッセージを刻みたい場面に使う。"
    ),
    capacity=ANY,
    # 文字が主役なので背景は少しだけ透かす
    veil=0.55, orbs=2, phase="P1",
    sample={"lead": "研修は、受けた時点では何も変わりません",
            "body": "変わるのは、翌日の業務で一度でも使ってみたときです。",
            "note": ""},
)
