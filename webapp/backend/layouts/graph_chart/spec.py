import json

from layouts._registry import Capacity, LayoutSpec


# グラフをどう開示するか。(data-anim, 秒数) の組。
#
# Chart.js 自身のアニメーションは使えない（animation: false のまま触らないこと）。
# あちらは requestAnimationFrame 駆動で、hyperframes が
# タイムラインを時刻 T へシークして 1 枚ずつ捕獲する方式とは同期せず、
# 撮るたびに違う絵になってしまう。
# 代わりに canvas を載せた箱を GSAP の clip-path で開ける。これならシークに追従する。
#
# 方向は種別で変える。棒と折れ線は「左から右へ描かれていく」のが読み順に合う。
# 円は左右の方向を持たないので、中心から広がらせる。
# 既定の 0.6 秒だと画面幅いっぱいの canvas では一瞬で通り過ぎるため、
# data-anim-duration で伸ばしている。
REVEAL_BY_TYPE = {
    "bar": ("draw-right", 1.2),
    "line": ("draw-right", 1.4),
    "pie": ("expand-circle", 0.9),
    "doughnut": ("expand-circle", 0.9),
}
DEFAULT_REVEAL = ("draw-right", 1.2)


def _prepare(content: dict, ctx: dict) -> dict:
    """Chart.js の描画スクリプトを組み立てる。

    canvas は CSS 変数を解釈できないため、テーマから導出した確定色を
    JS に埋め込む必要がある。テンプレートでは書けない処理なので、
    このレイアウトの中に閉じ込めている（composition.py には持ち込まない）。
    """
    from markupsafe import Markup
    from services.design_tokens import chart_palette

    cfg = content.get("chart") or {}
    if not cfg.get("values"):
        return {"chart_script": Markup(""), "canvas_id": "", "chart_w": 0, "chart_h": 0,
                "reveal_anim": DEFAULT_REVEAL[0], "reveal_sec": DEFAULT_REVEAL[1]}

    style = ctx.get("style")
    palette = chart_palette(style)
    canvas_id = f"chart-{ctx.get('scene_index', 0)}"
    chart_type = cfg.get("type", "bar")

    canvas_w = getattr(style, "canvas_width", 1920) or 1920
    canvas_h = getattr(style, "canvas_height", 1080) or 1080
    chart_w = max(400, canvas_w - 240)
    chart_h = max(300, canvas_h - 340)

    axis = ("{ ticks: { color: %s, font: { size: 18 } }, grid: { color: %s } }"
            % (json.dumps(palette["tick"]), json.dumps(palette["grid"])))
    scales = "{}" if chart_type in ("pie", "doughnut") else f"{{ x: {axis}, y: {axis} }}"

    # このスクリプトは #stage の中（＝ページ末尾の <script src="chart.min.js"> より前）に
    # 置かれるため、素直に書くと Chart がまだ未定義の状態で実行され、
    # 「グラフだけ何も出ない動画」が黙って出来上がる。
    # DOMContentLoaded まで待てば、同期読み込みの chart.min.js は必ず実行済みになる。
    script = f"""
(function() {{
  function draw() {{
    var el = document.getElementById({json.dumps(canvas_id)});
    if (!el || typeof Chart === 'undefined') return;
    new Chart(el.getContext('2d'), {{
      type: {json.dumps(chart_type)},
      data: {{
        labels: {json.dumps(cfg.get("labels") or [], ensure_ascii=False)},
        datasets: [{{
          label: {json.dumps(cfg.get("unit") or "", ensure_ascii=False)},
          data: {json.dumps(cfg.get("values") or [])},
          backgroundColor: {json.dumps(palette["series"])},
          borderColor: {json.dumps(palette["border"])},
          borderWidth: 2
        }}]
      }},
      options: {{
        responsive: false,
        animation: false,
        plugins: {{ legend: {{ labels: {{ color: {json.dumps(palette["legend"])}, font: {{ size: 20 }} }} }} }},
        scales: {scales}
      }}
    }});
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', draw);
  }} else {{
    draw();
  }}
}})();"""
    reveal_anim, reveal_sec = REVEAL_BY_TYPE.get(chart_type, DEFAULT_REVEAL)
    return {"chart_script": Markup(script), "canvas_id": canvas_id,
            "chart_w": chart_w, "chart_h": chart_h,
            "reveal_anim": reveal_anim, "reveal_sec": reveal_sec}


SPEC = LayoutSpec(
    id="graph_chart",
    label="グラフ",
    type_id="chart",
    when_to_use=(
        "数値そのものの大小や推移を見せるとき。"
        "数字を言葉で説明するより、形で一目で掴ませたい場合に使う。"
    ),
    capacity=Capacity(min=2, max=8, ideal=(3, 6)),
    veil=0.78, orbs=1, phase="P0", prepare=_prepare,
)
