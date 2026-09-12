from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="formula_equation",
    label="定義式（結果から示す）",
    type_id="formula",
    when_to_use=(
        "「○○とは、△△と□□で決まるものだ」と定義するとき。"
        "result を先に大きく出し、その内訳として terms を見せる。"
        "要素の掛け合わせそのものを主役にしたいなら掛け算・足し算を使う。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(2, 3)),
    veil=0.7, orbs=2, phase="P2",
    sample={
        "terms": [{"label": "頻度", "note": "どれだけ繰り返すか"},
                  {"label": "深さ", "note": "どこまで掘り下げるか"}],
        "operator": "×",
        "result": {"label": "定着度", "note": "研修が行動に変わる度合い"},
    },
)
