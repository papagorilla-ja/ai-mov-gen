from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="comparison",
    label="左右対比",
    type_id="contrast",
    when_to_use=(
        "2 つを同じ観点で並べて違いを見せるとき。左を既知・従来、"
        "右を新しい方に置くと、視線の流れ（左→右）と意味の流れが一致する。"
    ),
    capacity=ANY, veil=0.85, orbs=1, phase="P0",
)
