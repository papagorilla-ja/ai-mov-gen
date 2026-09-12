from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="statement_quote",
    label="引用・言葉",
    type_id="statement",
    when_to_use=(
        "誰かの言葉や定義をそのまま引くとき。"
        "自分の説明ではなく「引用である」ことを形で示したい場面に使う。note に出典を書く。"
    ),
    capacity=ANY,
    veil=0.62, orbs=2, phase="P1",
    sample={"lead": "知識とは、使える形で思い出せるものだけを言う",
            "body": "覚えているかどうかではなく、必要な場面で取り出せるかどうかが基準になります。",
            "note": "— 認知科学の教科書的な定義より"},
)
