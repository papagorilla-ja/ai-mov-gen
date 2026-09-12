from layouts._registry import Capacity, LayoutSpec


def _prepare(content: dict, ctx: dict) -> dict:
    """root と children を「外側から内側へ」の一本の入れ子にする。

    ツリーのような枝分かれではなく、A ⊃ B ⊃ C という含む・含まれるの連鎖。
    children は同列の兄弟ではなく、外から順に絞られていく層として扱う。
    """
    root = content.get("root") or {}
    layers = ([root] if (root.get("label") or root.get("text")) else []) \
        + list(content.get("children") or [])
    return {"layers": layers}


SPEC = LayoutSpec(
    id="hierarchy_nested",
    label="入れ子（包含）",
    type_id="hierarchy",
    when_to_use=(
        "「A の中に B があり、その中に C がある」という含む・含まれるの関係を示すとき。"
        "枝分かれではなく一本の入れ子。並列に分かれるならツリー図を使う。"
    ),
    capacity=Capacity(min=2, max=4, ideal=(3, 3)),
    veil=0.85, orbs=1, phase="P2", prepare=_prepare,
    sample={
        "root": {"label": "会社の方針", "text": "何を大事にするか"},
        "children": [
            {"label": "部門の計画", "text": "方針を自部門に翻訳したもの"},
            {"label": "個人の目標", "text": "今期の自分がやること"},
        ],
    },
)
