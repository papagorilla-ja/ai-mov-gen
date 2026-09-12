from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="media_case",
    label="事例紹介",
    type_id="media",
    when_to_use=(
        "実際にあった例を 1 件だけ取り上げて紹介するとき。"
        "抽象的な説明の後に置くと、受け手が自分の現場に置き換えやすくなる。"
    ),
    capacity=Capacity(min=1, max=1, ideal=(1, 1)),
    veil=0.8, orbs=1, phase="P1",
    sample={"images": [{"src": "", "caption": "製造部 第2ライン"}],
            "body": "手順書を写真付きに作り直したところ、新人の立ち上がりが 3 週間から 5 日に短くなりました。"
                    "変えたのは書式だけで、作業そのものは変えていません。",
            "image_description": "作業台で手順書を見ながら作業している様子。横長。"},
)
