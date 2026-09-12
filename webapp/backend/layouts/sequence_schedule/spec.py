from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="sequence_schedule",
    label="日程表",
    type_id="sequence",
    when_to_use=(
        "いつ何をするかを、時期を主役にして示すとき。導入計画や当日の進行に向く。"
        "label に時期（第1週・9月など）、text にその期間にやることを書く。"
    ),
    capacity=Capacity(min=3, max=6, ideal=(4, 5)),
    veil=0.85, orbs=1, phase="P1",
    sample={"steps": [
        {"label": "第1週", "text": "対象業務の洗い出しと、現状の手順の記録", "icon": ""},
        {"label": "第2週", "text": "試験導入する範囲の決定と、関係者への説明", "icon": ""},
        {"label": "第3〜4週", "text": "限定範囲での運用と、気づいた点の収集", "icon": ""},
        {"label": "第5週", "text": "振り返りと、本格導入の可否判断", "icon": ""},
    ]},
)
