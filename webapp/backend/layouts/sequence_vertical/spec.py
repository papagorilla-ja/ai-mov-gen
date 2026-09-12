from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="sequence_vertical",
    label="縦型フロー",
    type_id="sequence",
    when_to_use=(
        "手順の数が多い、または各ステップの説明が長くて横に並べきれないとき。"
        "上から下へ 1 つずつ追わせる。短い手順なら横型フローの方が全体を掴ませやすい。"
    ),
    capacity=Capacity(min=3, max=6, ideal=(4, 5)),
    veil=0.85, orbs=1, phase="P1",
    sample={"steps": [
        {"label": "現状を書き出す", "text": "いま実際にやっている手順を、省略せずそのまま書き出します。", "icon": "書類"},
        {"label": "詰まる箇所を探す", "text": "時間がかかる工程と、やり直しが起きる工程に印を付けます。", "icon": "検索"},
        {"label": "原因を 1 つに絞る", "text": "複数あっても、まず影響の大きいものを 1 つだけ選びます。", "icon": "目標"},
        {"label": "小さく試す", "text": "元に戻せる範囲で変更し、1 週間だけ運用してみます。", "icon": "実行"},
    ]},
)
