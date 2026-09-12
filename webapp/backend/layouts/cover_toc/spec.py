from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="cover_toc",
    label="目次",
    type_id="cover",
    when_to_use=(
        "これから話す章を先に見せて、全体の見通しを与えるとき。"
        "chapters に章のタイトルだけを並べる。説明は書かない。"
    ),
    capacity=Capacity(min=2, max=8, ideal=(3, 6)),
    veil=0.8, orbs=1, phase="P1",
    sample={"subtitle": "この動画で扱う 4 つのこと",
            "chapters": [{"label": "なぜ定着しないのか"}, {"label": "設計の 3 原則"},
                         {"label": "現場での試し方"}, {"label": "効果の測り方"}]},
)
