from layouts._registry import Capacity, LayoutSpec

# 点が枠線に重ならないようにする内側の余白（%）
EDGE = 6.0


def _prepare(content: dict, ctx: dict) -> dict:
    """plots の x / y を、枠内に収まる位置（%）に変換する。

    LLM は 0〜100 の範囲を外した値や、数値でない文字列を返すことがある。
    ここで必ず枠内に丸める（丸めないと点が図の外へ飛ぶ）。
    y は「大きいほど上」なので、画面座標に直すため反転させる。
    """
    def clamp(value, fallback=50.0):
        try:
            v = float(str(value).strip().replace("%", ""))
        except (TypeError, ValueError):
            v = fallback
        return round(min(100.0 - EDGE, max(EDGE, v)), 2)

    points = []
    for p in content.get("plots") or []:
        if not (p.get("label") or "").strip():
            continue
        points.append({
            "label": p["label"],
            "left": clamp(p.get("x")),
            "top": round(100.0 - clamp(p.get("y")), 2),
        })
    return {"points": points}


SPEC = LayoutSpec(
    id="matrix_plot",
    label="ポジショニングマップ",
    type_id="matrix",
    when_to_use=(
        "2 つの基準の上で「それぞれが今どこにいるか」を点で示すとき。"
        "plots に名前と位置（x / y を 0〜100）を書く。"
        "4 つの区分の性質を説明したいだけなら四象限を使う。"
    ),
    capacity=Capacity(min=4, max=4, ideal=(4, 4)),
    veil=0.85, orbs=1, phase="P2", prepare=_prepare,
)
