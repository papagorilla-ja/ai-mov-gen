"""レイアウトの描画 — Jinja2 環境とタイミング計算。

テンプレートは「何を出すか」だけを書き、「いつ出すか」は書かない。
テンプレートは登場の *役割* を data-seq で宣言し、実際の秒数はこの
モジュールが計算して data-start / data-duration に書き込む。

    <div class="clip" data-seq="head">              … タイトル。冒頭に出る
    <li class="clip" data-seq="spread" data-seq-index="{{ loop.index0 }}">
                                                     … 項目。シーン尺に均等配分
    <p  class="clip" data-seq="tail">               … まとめ。終盤に出る

この分業にしている理由:
  - 秒数をテンプレートに書くと、40 個のテンプレートに同じ計算が散らばる
  - シーンの尺はナレーション音声の長さで決まるため、テンプレートを書く時点では分からない
  - 「均等配分」の方針を変えたくなったとき、直す場所が 1 箇所で済む
"""

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from layouts._icons import icon_svg
from layouts._registry import LAYOUT_ROOT, LayoutSpec

# ---- タイミングの定数 ----------------------------------------------------
# シーン開始から見出しが出るまで。切替直後の一瞬を避ける。
HEAD_OFFSET = 0.5
# 最初の項目が出るまで。見出しを読む間を取る。
SPREAD_LEAD = 0.9
# 末尾に残す余白。ここで退場アニメーションが完了する。
EXIT_BUFFER = 0.5
# tail 要素が出る位置（シーン尺に対する割合）。
TAIL_RATIO = 0.8
# 項目同士の最小間隔。これを下回ると同時に出たように見えて分けた意味が消える。
MIN_STEP = 0.18


def _fmt(v: float) -> str:
    return f"{v:.2f}"


def _slot(el) -> int:
    """data-seq-index をスロット番号として読む。

    テンプレートの書き損じ（空文字・非数値・負値）で描画全体を落とさない。
    読めなければ先頭スロット扱いにする。
    """
    try:
        return max(0, int(el.get("data-seq-index") or 0))
    except (TypeError, ValueError):
        return 0


# ==========================================================================
# Jinja2 環境
# ==========================================================================

def _build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(LAYOUT_ROOT)),
        # 自動エスケープが今回 Jinja2 を採用した主な理由。
        # タイトルやナレーションに < や & が入っても HTML が壊れない。
        autoescape=select_autoescape(default_for_string=True, default=True),
        # 未定義変数は握りつぶさず落とす。テンプレートの打ち間違いを
        # 「空欄の動画が出来てしまう」形ではなく、その場のエラーで気づけるようにする。
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["icon"] = lambda name, cls="layout-icon": Markup(icon_svg(name, cls))
    env.filters["nl2br"] = lambda s: Markup("<br>".join(Markup.escape(s).split("\n")))
    return env


_ENV: Environment | None = None


def env() -> Environment:
    global _ENV
    if _ENV is None:
        _ENV = _build_env()
    return _ENV


# ==========================================================================
# タイミングの割り当て
# ==========================================================================

def apply_timing(html: str, scene_start: float, scene_duration: float) -> str:
    """data-seq の役割を実秒（data-start / data-duration）に変換する。

    全要素はシーン末尾（scene_start + scene_duration - EXIT_BUFFER）で
    揃って退場する。退場だけバラバラだと目が散るため。
    """
    frag = BeautifulSoup(html, "html.parser")
    end = scene_start + max(0.2, scene_duration - EXIT_BUFFER)

    def assign(el, start: float):
        # data-seq-offset で微差を付けられる。同じ役割の要素（アイブロウとタイトル）を
        # わずかにずらして出すためのもので、役割そのものは変えない。
        try:
            start += float(el.get("data-seq-offset") or 0)
        except ValueError:
            pass
        start = min(start, end - 0.2)
        el["data-start"] = _fmt(start)
        el["data-duration"] = _fmt(max(0.1, end - start))

    for el in frag.select('[data-seq="head"]'):
        assign(el, scene_start + HEAD_OFFSET)

    for el in frag.select('[data-seq="tail"]'):
        assign(el, scene_start + scene_duration * TAIL_RATIO)

    # data-seq-index は「何番目に出るか」ではなく「シーンのどのスロットで出るか」。
    # 同じ番号を付けた要素は同時に出る。
    # 例: 横型フローの矢印は、その矢印が指す先のステップと同じ番号を持つ。
    #     番号を単純な並び順にすると、最後の矢印だけが「何も無い方を指したまま
    #     次のステップを待つ」時間が生まれてしまう。
    #
    # スロット数はシーン全体でひとつに決める。以前は「同じ親を共有するグループ」
    # ごとに数え直していたが、図解レイアウトは位置決めの .diagram-node で
    # 要素を 1 個ずつ包むため、要素それぞれが単独のグループになってしまい、
    # slots が要素ごとに変わっていた。結果、12 秒のシーンで円環フローの 4 ノードが
    # 0.90 / 7.97 / 9.38 / 9.99 秒に出て、前半 7 秒が空白になっていた。
    # 1 シーン = 1 レイアウトなので、番号はそのテンプレートの作者が意図して
    # 振ったもの。シーン全体で通し番号として扱うのが正しい。
    spread = frag.select('[data-seq="spread"]')
    if spread:
        indices = [_slot(el) for el in spread]
        slots = max(indices) + 1
        usable = max(0.0, scene_duration - SPREAD_LEAD - EXIT_BUFFER)
        step = max(MIN_STEP, usable / slots)
        for el, idx in zip(spread, indices):
            assign(el, scene_start + SPREAD_LEAD + idx * step)

    # 役割を持たない .clip（テンプレートの書き忘れ）を放置すると、
    # app.js が data-start を読めずアニメーション対象から外れ、
    # 「その要素だけ最初から出っぱなし」という分かりにくい崩れ方をする。
    for el in frag.select(".clip"):
        if not el.get("data-start"):
            assign(el, scene_start + HEAD_OFFSET)

    return "".join(str(c) for c in frag.contents)


# ==========================================================================
# 描画
# ==========================================================================

def render(
    spec: LayoutSpec,
    content: dict,
    *,
    scene_start: float,
    scene_duration: float,
    aspect: str = "16:9",
    count: int = 0,
    extra: dict | None = None,
) -> str:
    """レイアウト 1 枚ぶんの HTML 断片を返す（<div class="slide"> の中身）。"""
    ctx = dict(extra or {})
    if spec.prepare:
        # レイアウト固有の前処理（グラフのスクリプト生成など）。
        # 失敗してもそのレイアウトが素の状態で描かれるだけで、動画生成は止めない。
        try:
            ctx.update(spec.prepare(content, ctx))
        except Exception as e:  # noqa: BLE001
            print(f"[layouts] {spec.id} の prepare が失敗: {e}")

    template = env().get_template(f"{spec.id}/template.html")
    html = template.render(
        c=content,
        s=spec,
        count=count,
        aspect=aspect,
        **ctx,
    )
    return apply_timing(html, scene_start, scene_duration)
