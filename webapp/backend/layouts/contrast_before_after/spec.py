from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="contrast_before_after",
    label="ビフォーアフター",
    type_id="contrast",
    when_to_use=(
        "「変わる前」と「変わった後」を示すとき。左右対比との違いは、"
        "左から右への変化そのものが主題であること。left に現状、right に変化後を書く。"
    ),
    capacity=ANY, veil=0.85, orbs=1, phase="P1",
    sample={
        "left": {"title": "いまの状態", "text": "手順が人によって違い、担当者が休むと作業が止まっていました。"},
        "right": {"title": "変えたあと", "text": "手順書に沿えば誰でも同じ結果になり、引き継ぎが 30 分で済みます。"},
        "verdict": "属人化の解消は、休みを取りやすくすることでもあります",
    },
)
