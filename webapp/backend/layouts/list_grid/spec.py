from layouts._registry import Capacity, LayoutSpec

SPEC = LayoutSpec(
    id="list_grid",
    label="複数羅列（グリッド）",
    type_id="list",
    when_to_use=(
        "項目が 4 つ以上あり、一覧性そのものを見せたいとき。"
        "各項目は見出し中心の短さにする。説明が長いならカード縦積みを使う。"
    ),
    capacity=Capacity(min=4, max=6, ideal=(4, 6)),
    veil=0.85, orbs=1, phase="P1",
    sample={"items": [
        {"label": "手順書", "text": "作業の型を残す", "icon": "書類"},
        {"label": "チェック", "text": "抜けを防ぐ", "icon": "確認"},
        {"label": "記録", "text": "結果を追える", "icon": "データ"},
        {"label": "振り返り", "text": "次に生かす", "icon": "改善"},
        {"label": "共有", "text": "個人知を組織知に", "icon": "チーム"},
        {"label": "更新", "text": "現場に合わせ直す", "icon": "循環"},
    ]},
)
