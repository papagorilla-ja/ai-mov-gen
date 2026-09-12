import math

from layouts._registry import Capacity, LayoutSpec

# 正方形の箱に置く。真円上に並べると、双方向矢印の角度が素直に求まる。
RADIUS_PCT = 33.0


def _prepare(content: dict, ctx: dict) -> dict:
    """ノードを円周に置き、すべての組を双方向の矢印でつなぐ。

    循環（一巡して戻る）ではなく「互いに影響し合う」関係なので、
    隣どうしではなく **全ての組** を結ぶ。2 件なら 1 本、3 件なら 3 本。
    """
    nodes = content.get("nodes") or []
    n = max(2, min(3, len(nodes)))
    # 2 件は左右、3 件は上・右下・左下。
    # 2 件のとき 180 度を先頭に置くのは、1 件目を左（読み始めの位置）に出すため。
    angles = [180, 0] if n == 2 else [-90, 30, 150]
    # 2 件を正方形の箱に置くと左右が窮屈になる。横長にして幅いっぱいに離す。
    # 2 件の矢印は必ず水平なので、箱を横長にしても矢印の角度はずれない
    # （3 件は斜めの矢印が出るため、角度が崩れないよう正方形のままにする）。
    aspect = "16 / 9" if n == 2 else "1 / 1"
    radius = 34.0 if n == 2 else RADIUS_PCT
    placed = [
        {
            "left": round(50 + radius * math.cos(math.radians(a)), 2),
            "top": round(50 + radius * math.sin(math.radians(a)), 2),
        }
        for a in angles[:n]
    ]

    links = []
    for i in range(n):
        for j in range(i + 1, n):
            ax, ay = placed[i]["left"], placed[i]["top"]
            bx, by = placed[j]["left"], placed[j]["top"]
            # 矢印は 2 点の中点に置き、2 点を結ぶ向きに回す
            links.append({
                "left": round((ax + bx) / 2, 2),
                "top": round((ay + by) / 2, 2),
                "angle": round(math.degrees(math.atan2(by - ay, bx - ax)), 1),
            })
    return {"positions": placed, "links": links, "node_count": n,
            "ar": aspect, "node_width": 30 if n == 2 else 34}


SPEC = LayoutSpec(
    id="cycle_mutual",
    label="相互関係（双方向）",
    type_id="cycle",
    when_to_use=(
        "互いに影響し合う関係を示すとき。一巡して戻る流れではなく、"
        "どちらからどちらへも作用がある場合に使う。順番があるなら円型サイクルを使う。"
    ),
    capacity=Capacity(min=2, max=3, ideal=(2, 3)),
    veil=0.85, orbs=1, phase="P2", prepare=_prepare,
    sample={"nodes": [
        {"label": "手順の質", "text": "分かりやすい手順は守られやすくなります。", "icon": "書類"},
        {"label": "現場の習熟", "text": "慣れた人ほど手順の改善点に気づきます。", "icon": "チーム"},
    ]},
)
