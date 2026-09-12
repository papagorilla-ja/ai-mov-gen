from layouts._registry import ANY, LayoutSpec

SPEC = LayoutSpec(
    id="cover_title",
    label="表紙",
    type_id="cover",
    when_to_use="動画の冒頭。何の動画かと、誰に向けたものかだけを示す。1 本に 1 回だけ使う。",
    capacity=ANY,
    # 表紙は背景を主役にする。以降のスライドと明確に質感を変えて「始まり」を示す。
    veil=0.1, orbs=2, phase="P1",
    sample={"subtitle": "現場で使える形に落とすための 30 分", "chapters": []},
)
