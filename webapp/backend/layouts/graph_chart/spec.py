import json

from layouts._registry import Capacity, LayoutSpec


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
        return {"chart_script": Markup(""), "canvas_id": "", "chart_w": 0, "chart_h": 0}

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
    return {"chart_script": Markup(script), "canvas_id": canvas_id,
            "chart_w": chart_w, "chart_h": chart_h}


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
