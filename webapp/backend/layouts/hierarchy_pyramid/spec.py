from layouts._registry import Capacity, LayoutSpec

# 背景 SVG の座標系。preserveAspectRatio="none" で箱いっぱいに引き伸ばすため、
# ここでの比率と実際の表示比率は一致しなくてよい。
VB_W, VB_H = 1000, 620
TOP, BOTTOM = 24, 596
# 頂点を尖らせず台形から始める。尖らせると最上段に文字が入らず、
# 「一番言いたいことが一番読めない」という本末転倒な図になる。
APEX_HALF, BASE_HALF = 100, 430
BAND_GAP = 6


def _prepare(content: dict, ctx: dict) -> dict:
    """段数に応じて台形の帯を組み立てる。

    帯の頂点座標（SVG 用）と、文字を重ねる位置・最大幅（HTML 用）を返す。
    SVG を引き伸ばして描くので、両者は同じ割合で対応する。
    """
    # 頂点（root）はピラミッドの最上段そのもの。children だけを描くと
    # 「一番上に来るはずの概念」が図から消える。root に見出しがあれば先頭に足す。
    root = content.get("root") or {}
    rows = ([root] if (root.get("label") or root.get("text")) else []) + list(content.get("children") or [])
    n = len(rows) or 1
    span = (BOTTOM - TOP) / n

    def half_width(y: float) -> float:
        return APEX_HALF + (y - TOP) / (BOTTOM - TOP) * (BASE_HALF - APEX_HALF)

    bands = []
    for i in range(n):
        y0 = TOP + i * span + (BAND_GAP / 2 if i else 0)
        y1 = TOP + (i + 1) * span - (BAND_GAP / 2 if i < n - 1 else 0)
        w0, w1 = half_width(y0), half_width(y1)
        bands.append({
            "points": (f"{500 - w0:.1f},{y0:.1f} {500 + w0:.1f},{y0:.1f} "
                       f"{500 + w1:.1f},{y1:.1f} {500 - w1:.1f},{y1:.1f}"),
            # 上へ行くほど濃くする。頂点が結論・上位概念だと分かるようにする。
            "alpha": round(0.42 - i * (0.22 / max(1, n - 1)), 3) if n > 1 else 0.42,
            "top_pct": round((y0 + y1) / 2 / VB_H * 100, 2),
            # 文字は帯の狭い方（上辺）の幅に収める。はみ出して台形の外に出ないように。
            "width_pct": round(max(14.0, (2 * min(w0, w1) - 40) / VB_W * 100), 2),
        })
    return {"bands": bands, "rows": rows, "viewbox": f"0 0 {VB_W} {VB_H}"}


SPEC = LayoutSpec(
    id="hierarchy_pyramid",
    label="ピラミッド",
    type_id="hierarchy",
    when_to_use=(
        "上に行くほど抽象度が高い／数が少ない階層を示すとき。"
        "理念と施策、戦略と戦術、重要度の順位づけなどに使う。"
    ),
    capacity=Capacity(min=2, max=5, ideal=(3, 4)),
    veil=0.85, orbs=1, phase="P0", prepare=_prepare,
)
