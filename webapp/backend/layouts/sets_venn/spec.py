from layouts._registry import Capacity, LayoutSpec

# viewBox とスライド上の箱の縦横比を一致させる（fixed-ar）。
# 一致していれば円が楕円に潰れず、% で置いた文字も円にぴったり重なる。
VB_W, VB_H = 1000, 700
AR = "1000 / 700"

# 2 集合と 3 集合で配置が変わる。半径は「重なりに文字が入る」ことを優先して決めている。
LAYOUTS = {
    2: {
        "circles": [(385, 350, 260), (615, 350, 260)],
        "labels":  [(200, 350), (800, 350)],
        "overlap": (500, 350),
    },
    3: {
        "circles": [(400, 285, 230), (600, 285, 230), (500, 470, 230)],
        "labels":  [(210, 160), (790, 160), (500, 655)],
        "overlap": (500, 340),
    },
}


def _prepare(content: dict, ctx: dict) -> dict:
    sets = content.get("sets") or []
    n = max(2, min(3, len(sets)))
    cfg = LAYOUTS[n]
    circles = [
        {"cx": cx, "cy": cy, "r": r, "cls": ["dg-fill", "dg-fill-2", "dg-fill-3"][i]}
        for i, (cx, cy, r) in enumerate(cfg["circles"])
    ]
    labels = [{"left": round(x / VB_W * 100, 2), "top": round(y / VB_H * 100, 2)}
              for x, y in cfg["labels"]]
    ox, oy = cfg["overlap"]
    return {
        "circles": circles,
        "label_pos": labels,
        "overlap_pos": {"left": round(ox / VB_W * 100, 2), "top": round(oy / VB_H * 100, 2)},
        "viewbox": f"0 0 {VB_W} {VB_H}",
        "ar": AR,
    }


SPEC = LayoutSpec(
    id="sets_venn",
    label="ベン図",
    type_id="sets",
    when_to_use=(
        "複数の条件が重なる領域そのものを見せたいとき。"
        "「両方を満たすと何になるか」が主題の場合に使う。単なる違いの列挙には対比を使う。"
    ),
    capacity=Capacity(min=2, max=3, ideal=(2, 3)),
    veil=0.85, orbs=1, phase="P0", prepare=_prepare,
)
