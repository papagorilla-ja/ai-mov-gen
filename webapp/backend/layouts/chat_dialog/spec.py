from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="chat_dialog",
    label="吹き出し対話",
    type_id="dialog",
    when_to_use=(
        "受け手が抱きそうな疑問を代弁させて答えるとき。"
        "一方的な説明が続いて集中が切れる箇所に挟むと効く。"
    ),
    capacity=Capacity(min=2, max=8, ideal=(4, 6)),
    veil=0.85, orbs=0, phase="P0",
)
