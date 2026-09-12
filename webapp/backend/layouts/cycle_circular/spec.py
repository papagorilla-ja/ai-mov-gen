import math

from layouts._registry import Capacity, LayoutSpec

# 正方形の箱を前提に配置する。箱を正方形に固定しておくと、
# ノードは真円の上に並び、矢印の回転角も素直に「接線の向き」で決まる。
# 横長の箱で楕円配置にすると、矢印の向きが目で見て合わなくなる。
RADIUS_PCT = 37.0


def _prepare(content: dict, ctx: dict) -> dict:
    nodes = content.get("nodes") or []
    n = len(nodes) or 1
    placed, arrows = [], []
    for i in range(n):
        # 真上から始めて時計回り。読み手の「12 時から時計回り」の期待に合わせる。
        theta = math.radians(-90 + i * 360 / n)
        placed.append({
            "left": round(50 + RADIUS_PCT * math.cos(theta), 2),
            "top": round(50 + RADIUS_PCT * math.sin(theta), 2),
        })
        # ノードとノードの中間に矢印を置く。向きは接線（進行方向）。
        phi = math.radians(-90 + (i + 0.5) * 360 / n)
        arrows.append({
            "left": round(50 + RADIUS_PCT * math.cos(phi), 2),
            "top": round(50 + RADIUS_PCT * math.sin(phi), 2),
            "angle": round(math.degrees(phi) + 90, 1),
        })
    return {"positions": placed, "arrows": arrows}


SPEC = LayoutSpec(
    id="cycle_circular",
    label="円型サイクル",
    type_id="cycle",
    when_to_use=(
        "終わりが始まりに戻る反復を示すとき。改善サイクルや、"
        "回し続けること自体が主題の場合に使う。単なる手順には横型フローを使う。"
    ),
    capacity=Capacity(min=3, max=6, ideal=(3, 5)),
    veil=0.85, orbs=1, phase="P0", prepare=_prepare,
)
