from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="image_gallery",
    label="画像ギャラリー",
    type_id="media",
    when_to_use=(
        "複数の実物を並べて見比べさせるとき。"
        "画面キャプチャの一覧や、事例の写真を並列に見せる場合に使う。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(2, 3)),
    veil=0.72, orbs=1, phase="P0",
    # 型の既定サンプルは画像 1 枚。並べて見比べるレイアウトなので、
    # ギャラリーでは 3 枠で見せないと用途が伝わらない。
    sample={"images": [{"src": "", "caption": "取り込み前"},
                       {"src": "", "caption": "取り込み後"},
                       {"src": "", "caption": "確認画面"}],
            "body": "同じ操作を 3 つの画面で見比べます。"},
)
