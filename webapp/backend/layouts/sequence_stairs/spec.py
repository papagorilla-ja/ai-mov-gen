from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="sequence_stairs",
    label="階段（段階的な到達）",
    type_id="sequence",
    when_to_use=(
        "段を上がるほど水準が上がる、という関係を示すとき。"
        "習熟度やレベル、成熟度モデルに向く。単なる作業手順には横型フローを使う。"
    ),
    capacity=Capacity(min=3, max=5, ideal=(3, 4)),
    veil=0.85, orbs=1, phase="P1",
    sample={"steps": [
        {"label": "知っている", "text": "説明を聞けば内容が分かる", "icon": ""},
        {"label": "できる", "text": "手順書を見ながら実行できる", "icon": ""},
        {"label": "教えられる", "text": "他人に手順の理由まで説明できる", "icon": ""},
    ]},
)
