from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="list_profile",
    label="人物・役割紹介",
    type_id="list",
    when_to_use=(
        "登場人物や担当者、役割の分担を紹介するとき。"
        "label に名前や役割名、text に担当内容を書く。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(3, 3)),
    veil=0.85, orbs=1, phase="P1",
    sample={"items": [
        {"label": "研修企画", "text": "目的とゴールを決め、内容の骨格をつくります。", "icon": "計画"},
        {"label": "現場責任者", "text": "業務の実態に合っているかを確認します。", "icon": "人"},
        {"label": "受講者", "text": "学んだことを翌日の業務で試します。", "icon": "チーム"},
    ]},
)
