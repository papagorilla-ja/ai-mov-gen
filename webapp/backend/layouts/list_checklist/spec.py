from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="list_checklist",
    label="チェックリスト",
    type_id="list",
    when_to_use=(
        "受け手に「自分はどうか」と照合させたいとき。"
        "満たすべき条件や、確認してほしい項目を並べる場面に使う。"
    ),
    capacity=Capacity(min=2, max=6, ideal=(3, 5)),
    veil=0.85, orbs=1, phase="P1",
    sample={"items": [
        {"label": "目的を言葉にできる", "text": "何のための作業か説明できる", "icon": ""},
        {"label": "手順が書かれている", "text": "担当者が変わっても再現できる", "icon": ""},
        {"label": "結果が記録されている", "text": "後から検証できる形で残っている", "icon": ""},
    ]},
)
