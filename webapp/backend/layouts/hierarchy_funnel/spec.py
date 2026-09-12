from layouts._registry import Capacity, LayoutSpec

# ピラミッドと同じ座標系。preserveAspectRatio="none" で引き伸ばすため、
# ここでの比率と実際の表示比率は一致しなくてよい。
VB_W, VB_H = 1000, 620
TOP, BOTTOM = 24, 596
# 上が広く、下が狭い。下端も尖らせず台形で止める（最下段に文字が入らなくなるため）。
TOP_HALF, BOTTOM_HALF = 430, 110
BAND_GAP = 6


def _prepare(content: dict, ctx: dict) -> dict:
    """上から下へ絞り込まれていく帯を組み立てる。

    ピラミッドとは幅の向きが逆。ピラミッドが「上ほど上位・少数」を表すのに対し、
    こちらは「通るたびに減っていく」量そのものを表す。
    """
    root = content.get("root") or {}
    rows = ([root] if (root.get("label") or root.get("text")) else []) + list(content.get("children") or [])
    n = len(rows) or 1
    span = (BOTTOM - TOP) / n

    def half_width(y: float) -> float:
        return TOP_HALF + (y - TOP) / (BOTTOM - TOP) * (BOTTOM_HALF - TOP_HALF)

    bands = []
    for i in range(n):
        y0 = TOP + i * span + (BAND_GAP / 2 if i else 0)
        y1 = TOP + (i + 1) * span - (BAND_GAP / 2 if i < n - 1 else 0)
        w0, w1 = half_width(y0), half_width(y1)
        bands.append({
            "points": (f"{500 - w0:.1f},{y0:.1f} {500 + w0:.1f},{y0:.1f} "
                       f"{500 + w1:.1f},{y1:.1f} {500 - w1:.1f},{y1:.1f}"),
            # 下へ行くほど濃くする。絞り込まれて残ったものほど価値が高い、という読み方に合わせる。
            "alpha": round(0.18 + i * (0.26 / max(1, n - 1)), 3) if n > 1 else 0.30,
            "top_pct": round((y0 + y1) / 2 / VB_H * 100, 2),
            # 文字は帯の狭い方（下辺）の幅に収める
            "width_pct": round(max(14.0, (2 * min(w0, w1) - 40) / VB_W * 100), 2),
        })
    return {"bands": bands, "rows": rows, "viewbox": f"0 0 {VB_W} {VB_H}"}


SPEC = LayoutSpec(
    id="hierarchy_funnel",
    label="じょうろ（絞り込み）",
    type_id="hierarchy",
    when_to_use=(
        "段を下るごとに数が減っていく過程を示すとき。認知から購入まで、"
        "応募から採用までのような絞り込みに使う。上位概念の階層ならピラミッドを使う。"
    ),
    capacity=Capacity(min=2, max=5, ideal=(3, 4)),
    veil=0.85, orbs=1, phase="P2", prepare=_prepare,
    sample={
        "root": {"label": "研修を受けた", "text": "対象者 240 名"},
        "children": [
            {"label": "内容を覚えている", "text": "1 か月後 / 約 6 割"},
            {"label": "業務で試した", "text": "1 か月後 / 約 3 割"},
            {"label": "続いている", "text": "3 か月後 / 約 1 割"},
        ],
    },
)
