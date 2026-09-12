from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="cover_summary",
    label="まとめ",
    type_id="cover",
    when_to_use=(
        "動画や章の最後に、持ち帰ってほしいことを確認するとき。"
        "chapters に「結局どうすればよいか」を短く並べる。新しい情報は足さない。"
    ),
    capacity=Capacity(min=2, max=5, ideal=(3, 4)),
    veil=0.8, orbs=1, phase="P1",
    sample={"subtitle": "ここまでの要点",
            "chapters": [{"label": "学んだ内容は翌日の業務で一度使う"},
                         {"label": "使った結果を短くても書き残す"},
                         {"label": "1 か月後に同じ資料を見返す"}]},
)
