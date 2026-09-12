from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="contrast_axis",
    label="対立軸（両端）",
    type_id="contrast",
    when_to_use=(
        "2 つが「どちらが正しいか」ではなく「程度の両端」である関係を示すとき。"
        "速さと丁寧さ、標準化と柔軟性のように、間のどこかで折り合いをつける話に使う。"
    ),
    capacity=ANY, veil=0.85, orbs=1, phase="P1",
    sample={
        "left": {"title": "標準化を強める", "text": "誰がやっても同じ結果になりますが、例外に弱くなります。"},
        "right": {"title": "現場裁量を残す", "text": "例外に対応できますが、品質が人によってばらつきます。"},
        "verdict": "どちらかではなく、業務ごとにどの辺りに置くかを決めます",
    },
)
