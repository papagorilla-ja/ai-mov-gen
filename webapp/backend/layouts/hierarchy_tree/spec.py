from layouts._registry import Capacity, LayoutSpec


def _prepare(content: dict, ctx: dict) -> dict:
    """root と children を 1 本の木にまとめる。

    テンプレートは「木の根」を 1 つ受け取って再帰で描くだけにしたいので、
    root が空でも必ず根が 1 つある形に整えてから渡す。
    """
    root = dict(content.get("root") or {})
    children = list(content.get("children") or [])
    if not (root.get("label") or root.get("text")):
        # 根が未入力なら、最初の子を根に繰り上げる（空の箱を頂点に置かない）
        if children:
            root = dict(children[0])
            children = root.pop("children", []) or children[1:]
        else:
            root = {"label": "", "text": ""}
    root["children"] = children
    return {"tree_root": root}


SPEC = LayoutSpec(
    id="hierarchy_tree",
    label="ツリー図・組織図",
    type_id="hierarchy",
    when_to_use=(
        "全体が何から構成されているかを、枝分かれの形で示すとき。"
        "組織の体制や、要素の分解に使う。量の増減を示したいならピラミッドやじょうろを使う。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(2, 4)),
    veil=0.85, orbs=1, phase="P2", prepare=_prepare,
    sample={
        "root": {"label": "品質を保つ仕組み", "text": ""},
        "children": [
            {"label": "決める", "text": "", "children": [
                {"label": "基準", "text": "", "children": []},
                {"label": "手順", "text": "", "children": []},
            ]},
            {"label": "守る", "text": "", "children": [
                {"label": "教育", "text": "", "children": []},
                {"label": "点検", "text": "", "children": []},
            ]},
            {"label": "直す", "text": "", "children": [
                {"label": "記録", "text": "", "children": []},
            ]},
        ],
    },
)
