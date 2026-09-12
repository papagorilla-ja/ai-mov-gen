from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="media_annotated",
    label="画像＋注釈",
    type_id="media",
    when_to_use=(
        "1 枚の画面や図の「どこを見るか」を指し示すとき。"
        "各画像の caption に、見てほしい点を番号順に書く。"
    ),
    capacity=Capacity(min=1, max=4, ideal=(1, 3)),
    veil=0.8, orbs=1, phase="P1",
    sample={"images": [{"src": "", "caption": "入力欄はここ 1 か所だけ"},
                       {"src": "", "caption": "確定前に必ず確認画面が出る"},
                       {"src": "", "caption": "記録は自動で残る"}],
            "body": "実際の画面で、見るべき箇所は 3 つです。",
            "image_description": "業務システムの入力画面のスクリーンショット。横長。"},
)
