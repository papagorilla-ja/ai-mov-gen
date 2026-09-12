from layouts._registry import Capacity, LayoutSpec

# 外側から内側へ。直径（正方形の箱に対する %）。
# 隣り合う輪の差を十分に取らないと、間に文字が入らない。
DIAMETERS = [96, 66, 36]


def _prepare(content: dict, ctx: dict) -> dict:
    """同心円の直径と、見出しを置く高さを決める。

    見出しは「その輪の上端の少し内側」に置く。輪の中央に置くと、
    一つ内側の円と重なって読めなくなる。
    """
    sets = [s for s in (content.get("sets") or []) if (s.get("label") or s.get("text"))]
    rings = []
    for i, s in enumerate(sets[:3]):
        d = DIAMETERS[i]
        rings.append({
            "label": s.get("label") or "",
            "text": s.get("text") or "",
            "diameter": d,
            # 円の上端は (100 - d) / 2。そこから内側へ少し下げた位置に見出しを置く。
            "label_top": round((100 - d) / 2 + (4 if i < 2 else d / 2 - 4), 2),
            "innermost": i == len(sets[:3]) - 1,
        })
    return {"rings": rings}


SPEC = LayoutSpec(
    id="sets_inclusion",
    label="包含（領域）",
    type_id="sets",
    when_to_use=(
        "「B は A の一部である」という含まれる関係を示すとき。"
        "重なりではなく、まるごと内側にある場合に使う。一部だけ重なるならベン図を使う。"
    ),
    capacity=Capacity(min=2, max=3, ideal=(2, 3)),
    veil=0.85, orbs=1, phase="P2", prepare=_prepare,
    sample={
        "sets": [
            {"label": "知っていること", "text": "本や研修で触れた範囲"},
            {"label": "できること", "text": "手順書を見れば実行できる範囲"},
            {"label": "教えられること", "text": "理由まで説明できる範囲"},
        ],
        "overlaps": [],
    },
)
