from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="sequence_timeline",
    label="年表・横タイムライン",
    type_id="sequence",
    when_to_use=(
        "実際の時間の流れに沿って出来事を並べるとき。沿革や経緯に向く。"
        "label に時期（年・月・フェーズ名）、text に起きたことを書く。"
    ),
    capacity=Capacity(min=3, max=5, ideal=(3, 4)),
    veil=0.85, orbs=1, phase="P1",
    sample={"steps": [
        {"label": "2019", "text": "紙の帳票で運用を開始", "icon": ""},
        {"label": "2021", "text": "表計算ソフトへ置き換え", "icon": ""},
        {"label": "2023", "text": "業務システムに統合", "icon": ""},
        {"label": "2025", "text": "記録の自動収集を開始", "icon": ""},
    ]},
)
