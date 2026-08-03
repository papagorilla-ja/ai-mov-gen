import json
import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
from models.video import Video
from models.scene import Scene
from models.video_style import VideoStyle
from services.design_tokens import (
    build_theme_css,
    chart_palette,
    normalize_transition,
    stage_classes,
)

TRANSITION_BUFFER = 0.6

# index.html が相対パスで読み込むランタイムファイル。
# コンポジションを書き出すディレクトリには必ずこの3つが揃っている必要がある。
# 欠けるとブラウザ側で 404 になり、GSAP タイムラインが登録されないまま
# 「アニメーションが一切効いていない静止画の動画」が正常終了で出力されてしまう。
RUNTIME_FILES = ("app.js", "gsap.min.js", "chart.min.js")

# style.css が @font-face で読み込む同梱フォント。
# 欠けてもレンダリングは完走してしまい、システムフォントに差し替わった
# 動画が「成功」として出力されるため、ランタイムファイル同様に同期する。
FONT_DIR_NAME = "fonts"
FONT_FILES = ("BIZUDPGothic-Regular.woff2", "BIZUDPGothic-Bold.woff2")


def _parse_slide_content(scene: Scene, assets_map: dict | None = None) -> dict:
    """slide_content_json をパースし、レイアウト分岐で使う値一式を返す。"""
    content = {}
    if scene.slide_content_json:
        try:
            content = json.loads(scene.slide_content_json)
        except Exception:
            pass

    title_text = content.get("title", scene.title or f"Scene {scene.index}")
    body_text = content.get("body", "")
    bullet_points = content.get("bullet_points", [])
    if isinstance(bullet_points, str):
        bullet_points = [bp.strip() for bp in bullet_points.split("\n") if bp.strip()]

    subtitle_text = content.get("subtitle", "")
    image_src = content.get("image_src", "")
    image_position = content.get("image_position", "right")

    if assets_map and scene.layout_type in ["full_image", "text_left_image_right"]:
        scene_assets = assets_map.get(scene.id, [])
        slot1_asset = next((a for a in scene_assets if a.slot == 1), None)
        if slot1_asset and slot1_asset.file_path:
            image_src = slot1_asset.file_path

    gallery_assets = []
    if assets_map and scene.layout_type == "image_gallery":
        gallery_assets = sorted(assets_map.get(scene.id, []), key=lambda a: a.slot)

    return {
        "content": content,
        "title_text": title_text,
        "body_text": body_text,
        "bullet_points": bullet_points,
        "subtitle_text": subtitle_text,
        "image_src": image_src,
        "image_position": image_position if image_position in ("left", "right") else "right",
        "gallery_assets": gallery_assets,
        "summary": content.get("summary", ""),
    }


def _body_card(soup, text: str, elem_start: float, elem_duration: float):
    """本文テキストをカードで見せる共通ブロック（フォールバックにも使う）。"""
    if not text:
        return None
    wrap = soup.new_tag("div", attrs={
        "class": "clip body-card",
        "data-start": f"{elem_start:.2f}",
        "data-duration": f"{elem_duration:.2f}",
    })
    p = soup.new_tag("p", attrs={"class": "body-text"})
    p.string = text
    wrap.append(p)
    return wrap


def _build_slide_content(soup, scene: Scene, parsed: dict, elem_start: float, elem_duration: float, style: VideoStyle | None = None) -> list:
    """レイアウト種別に応じた HTML タグ群を構築してリストで返す。"""
    content = parsed["content"]
    title_text = parsed["title_text"]
    body_text = parsed["body_text"]
    bullet_points = parsed["bullet_points"]
    subtitle_text = parsed["subtitle_text"]
    image_src = parsed["image_src"]
    image_position = parsed.get("image_position", "right")
    gallery_assets = parsed.get("gallery_assets", [])
    elems = []

    canvas_w = style.canvas_width if style else 1920
    canvas_h = style.canvas_height if style else 1080

    # あらすじ（FIX-10 のアウトライン由来）。固有コンテンツが未生成のときの保険に使う。
    fallback_text = (
        parsed.get("summary")
        or content.get("summary")
        or body_text
        or (scene.outline_summary or "")
    )
    STAGGER = 0.25   # 要素ごとの登場間隔（秒）

    def _head(eyebrow_text: str):
        """アイブロウ + タイトル を elems に積む共通処理。"""
        eb = soup.new_tag("div", attrs={
            "class": "clip slide-eyebrow",
            "data-start": f"{elem_start:.2f}",
            "data-duration": f"{elem_duration:.2f}",
        })
        eb.string = eyebrow_text
        elems.append(eb)
        h1 = soup.new_tag("h1", attrs={
            "class": "clip slide-title",
            "data-start": f"{(elem_start + 0.15):.2f}",
            "data-duration": f"{(elem_duration - 0.15):.2f}",
        })
        h1.string = title_text
        elems.append(h1)

    if scene.layout_type == "section_header":
        orb1 = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-1"})
        orb2 = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-2"})
        elems.append(orb1)
        elems.append(orb2)

        h1 = soup.new_tag("h1", attrs={
            "class": "clip section-title",
            "data-start": f"{elem_start:.2f}",
            "data-duration": f"{elem_duration:.2f}"
        })
        h1.string = title_text
        elems.append(h1)

        rule = soup.new_tag("div", attrs={
            "class": "clip section-rule",
            "data-start": f"{(elem_start + 0.2):.2f}",
            "data-duration": f"{(elem_duration - 0.2):.2f}"
        })
        elems.append(rule)

        sub = subtitle_text or fallback_text
        if sub:
            p = soup.new_tag("p", attrs={
                "class": "clip section-subtitle",
                "data-start": f"{(elem_start + 0.4):.2f}",
                "data-duration": f"{(elem_duration - 0.4):.2f}"
            })
            p.string = sub
            elems.append(p)

    elif scene.layout_type == "text_left_image_right":
        orb = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-1"})
        elems.append(orb)

        container_class = "two-col-container grid-2col"
        if image_position == "left":
            container_class += " reverse"
        container = soup.new_tag("div", attrs={
            "class": container_class,
        })

        left_col = soup.new_tag("div", attrs={"class": "col-left"})
        eb = soup.new_tag("div", attrs={
            "class": "clip slide-eyebrow",
            "data-start": f"{elem_start:.2f}",
            "data-duration": f"{elem_duration:.2f}",
        })
        eb.string = f"Scene {scene.index:02d}"
        left_col.append(eb)

        h1 = soup.new_tag("h1", attrs={
            "class": "clip slide-title",
            "data-start": f"{(elem_start + 0.15):.2f}",
            "data-duration": f"{(elem_duration - 0.15):.2f}"
        })
        h1.string = title_text
        left_col.append(h1)

        display_text = body_text or fallback_text
        if display_text:
            bc = _body_card(soup, display_text, elem_start + 0.3, elem_duration - 0.3)
            if bc:
                left_col.append(bc)
        container.append(left_col)

        right_col = soup.new_tag("div", attrs={"class": "col-right"})
        if image_src:
            img = soup.new_tag("img", attrs={
                "class": "clip illustration",
                "src": image_src,
                "data-start": f"{(elem_start + 0.3):.2f}",
                "data-duration": f"{(elem_duration - 0.3):.2f}"
            })
        else:
            img = soup.new_tag("div", attrs={
                "class": "clip illustration illustration--placeholder",
                "data-start": f"{(elem_start + 0.3):.2f}",
                "data-duration": f"{(elem_duration - 0.3):.2f}"
            })
        right_col.append(img)
        container.append(right_col)
        elems.append(container)

    elif scene.layout_type == "full_image":
        if image_src:
            img = soup.new_tag("img", attrs={
                "class": "clip full-screen-image",
                "src": image_src,
                "data-start": f"{elem_start:.2f}",
                "data-duration": f"{elem_duration:.2f}"
            })
        else:
            img = soup.new_tag("div", attrs={
                "class": "clip full-screen-image full-screen-image--placeholder",
                "data-start": f"{elem_start:.2f}",
                "data-duration": f"{elem_duration:.2f}"
            })
        elems.append(img)
        
        if title_text:
            h1 = soup.new_tag("h1", attrs={
                "class": "clip image-overlay-title",
                "data-start": f"{(elem_start + 0.5):.2f}",
                "data-duration": f"{(elem_duration - 0.5):.2f}"
            })
            h1.string = title_text
            elems.append(h1)

    elif scene.layout_type == "image_gallery":
        orb = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-1"})
        elems.append(orb)

        _head(f"Scene {scene.index:02d}")

        count = len(gallery_assets) or 1
        cols = "cols-3" if count >= 3 else "cols-2"
        grid = soup.new_tag("div", attrs={"class": f"gallery-grid {cols}"})
        for n, asset in enumerate(gallery_assets, start=1):
            item_start = elem_start + 0.3 + (n - 1) * 0.25
            item_dur = max(0.1, elem_duration - (item_start - elem_start))
            item = soup.new_tag("figure", attrs={
                "class": "clip gallery-item",
                "data-start": f"{item_start:.2f}",
                "data-duration": f"{item_dur:.2f}",
            })
            img = soup.new_tag("img", attrs={
                "class": "gallery-media",
                "src": asset.file_path or "",
            })
            item.append(img)
            grid.append(item)
        elems.append(grid)

        display_text = body_text or fallback_text
        if display_text:
            bc = _body_card(soup, display_text, elem_start + 0.3 + count * 0.25, elem_duration - (0.3 + count * 0.25))
            if bc:
                elems.append(bc)

    elif scene.layout_type == "bullet_list":
        orb = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-2"})
        elems.append(orb)

        _head("Key Points")

        area = soup.new_tag("div", attrs={"class": "slide-body-area"})
        if not bullet_points and fallback_text:
            bullet_points = [fallback_text]

        if bullet_points:
            list_wrap = soup.new_tag("div", attrs={"class": "bullet-list"})
            for n, bp in enumerate(bullet_points, start=1):
                item_start = elem_start + 0.3 + (n - 1) * STAGGER
                item_dur = max(0.1, elem_duration - (item_start - elem_start))
                item = soup.new_tag("div", attrs={
                    "class": "clip bullet-item",
                    "data-start": f"{item_start:.2f}",
                    "data-duration": f"{item_dur:.2f}"
                })
                num = soup.new_tag("div", attrs={"class": "bullet-num"})
                num.string = str(n)
                cont = soup.new_tag("div", attrs={"class": "bullet-content"})
                p = soup.new_tag("p")
                p.string = bp
                cont.append(p)
                item.append(num)
                item.append(cont)
                list_wrap.append(item)
            area.append(list_wrap)
        else:
            bc = _body_card(soup, fallback_text, elem_start + 0.3, elem_duration - 0.3)
            if bc:
                area.append(bc)
        elems.append(area)

    elif scene.layout_type == "comparison":
        orb = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-1"})
        elems.append(orb)

        _head("Comparison")

        area = soup.new_tag("div", attrs={"class": "slide-body-area"})
        left_text = content.get("left_text", "")
        right_text = content.get("right_text", "")

        if not left_text and not right_text:
            bc = _body_card(soup, fallback_text, elem_start + 0.3, elem_duration - 0.3)
            if bc:
                area.append(bc)
        else:
            container = soup.new_tag("div", attrs={"class": "comparison-container"})
            cols = soup.new_tag("div", attrs={"class": "comparison-cols"})
            
            l_start = elem_start + 0.3
            left_col = soup.new_tag("div", attrs={
                "class": "clip comparison-col left",
                "data-start": f"{l_start:.2f}",
                "data-duration": f"{max(0.1, elem_duration - 0.3):.2f}"
            })
            if content.get("left_title"):
                head = soup.new_tag("div", attrs={"class": "comparison-col-head"})
                head.string = content["left_title"]
                left_col.append(head)

            left_p = soup.new_tag("p")
            left_p.string = left_text
            left_col.append(left_p)
            cols.append(left_col)

            vs_start = elem_start + 0.45
            vs_badge = soup.new_tag("div", attrs={
                "class": "clip comparison-vs",
                "data-start": f"{vs_start:.2f}",
                "data-duration": f"{max(0.1, elem_duration - 0.45):.2f}"
            })
            vs_badge.string = "VS"
            cols.append(vs_badge)

            r_start = elem_start + 0.6
            right_col = soup.new_tag("div", attrs={
                "class": "clip comparison-col right",
                "data-start": f"{r_start:.2f}",
                "data-duration": f"{max(0.1, elem_duration - 0.6):.2f}"
            })
            if content.get("right_title"):
                head = soup.new_tag("div", attrs={"class": "comparison-col-head"})
                head.string = content["right_title"]
                right_col.append(head)

            right_p = soup.new_tag("p")
            right_p.string = right_text
            right_col.append(right_p)
            cols.append(right_col)

            container.append(cols)
            area.append(container)

        elems.append(area)

    elif scene.layout_type == "chat_dialog":
        _head("Discussion")

        area = soup.new_tag("div", attrs={"class": "slide-body-area"})
        container = soup.new_tag("div", attrs={"class": "dialog-container"})

        lines = content.get("lines", [])
        if not lines and fallback_text:
            lines = [{"speaker": "A", "text": fallback_text}]

        for n, line in enumerate(lines):
            speaker = line.get("speaker", "A").upper()
            text = line.get("text", "")
            line_start = elem_start + 0.3 + n * STAGGER
            line_dur = max(0.1, elem_duration - (line_start - elem_start))
            line_class = "clip dialog-line speaker-a" if speaker == "A" else "clip dialog-line speaker-b"
            line_div = soup.new_tag("div", attrs={
                "class": line_class,
                "data-start": f"{line_start:.2f}",
                "data-duration": f"{line_dur:.2f}"
            })
            bubble = soup.new_tag("div", attrs={"class": "bubble"})
            bubble.string = text
            line_div.append(bubble)
            container.append(line_div)

        area.append(container)
        elems.append(area)

    elif scene.layout_type == "card_panel":
        orb = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-1"})
        elems.append(orb)

        _head("Topics")

        area = soup.new_tag("div", attrs={"class": "slide-body-area"})
        cards = content.get("cards", [])

        if not cards:
            bc = _body_card(soup, fallback_text, elem_start + 0.3, elem_duration - 0.3)
            if bc:
                area.append(bc)
        else:
            grid_class = "card-grid cols-3" if len(cards) >= 3 else "card-grid cols-2"
            grid = soup.new_tag("div", attrs={"class": grid_class})
            for n, c in enumerate(cards, start=1):
                card_start = elem_start + 0.3 + (n - 1) * STAGGER
                card_dur = max(0.1, elem_duration - (card_start - elem_start))
                card = soup.new_tag("div", attrs={
                    "class": "clip info-card",
                    "data-start": f"{card_start:.2f}",
                    "data-duration": f"{card_dur:.2f}"
                })
                idx_el = soup.new_tag("div", attrs={"class": "info-card-index"})
                idx_el.string = f"{n:02d}"
                card.append(idx_el)

                if c.get("title"):
                    ct = soup.new_tag("div", attrs={"class": "info-card-title"})
                    ct.string = c["title"]
                    card.append(ct)
                if c.get("text"):
                    cp = soup.new_tag("p", attrs={"class": "info-card-text"})
                    cp.string = c["text"]
                    card.append(cp)
                grid.append(card)
            area.append(grid)

        elems.append(area)

    elif scene.layout_type == "table":
        orb = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-2"})
        elems.append(orb)

        _head("Data")

        area = soup.new_tag("div", attrs={"class": "slide-body-area"})
        headers = content.get("headers", [])
        rows = content.get("rows", [])

        if not rows:
            bc = _body_card(soup, fallback_text, elem_start + 0.3, elem_duration - 0.3)
            if bc:
                area.append(bc)
        else:
            table = soup.new_tag("table", attrs={"class": "data-table"})
            if headers:
                thead = soup.new_tag("thead")
                tr = soup.new_tag("tr")
                for h in headers:
                    th = soup.new_tag("th")
                    th.string = str(h)
                    tr.append(th)
                thead.append(tr)
                table.append(thead)

            tbody = soup.new_tag("tbody")
            for n, row in enumerate(rows):
                row_start = elem_start + 0.3 + n * STAGGER
                row_dur = max(0.1, elem_duration - (row_start - elem_start))
                tr = soup.new_tag("tr", attrs={
                    "class": "clip",
                    "data-start": f"{row_start:.2f}",
                    "data-duration": f"{row_dur:.2f}"
                })
                for cell in row:
                    td = soup.new_tag("td")
                    td.string = str(cell)
                    tr.append(td)
                tbody.append(tr)
            table.append(tbody)
            area.append(table)

        elems.append(area)

    elif scene.layout_type == "graph_chart":
        orb = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-1"})
        elems.append(orb)

        _head("Chart")

        area = soup.new_tag("div", attrs={"class": "slide-body-area"})
        chart_cfg = content.get("chart", {})
        values = chart_cfg.get("values", [])

        if not values:
            bc = _body_card(soup, fallback_text, elem_start + 0.3, elem_duration - 0.3)
            if bc:
                area.append(bc)
        else:
            chart_type = chart_cfg.get("type", "bar")
            labels = chart_cfg.get("labels", [])
            unit = chart_cfg.get("unit", "")

            canvas_id = f"chart-{scene.index}"
            chart_w = max(400, canvas_w - 240)
            chart_h = max(300, canvas_h - 340)

            wrap = soup.new_tag("div", attrs={
                "class": "clip chart-canvas-wrap",
                "data-start": f"{(elem_start + 0.3):.2f}",
                "data-duration": f"{(elem_duration - 0.3):.2f}"
            })
            canvas = soup.new_tag("canvas", attrs={
                "id": canvas_id,
                "width": str(chart_w),
                "height": str(chart_h),
            })
            wrap.append(canvas)
            area.append(wrap)

            # canvas は CSS 変数を解釈できないため、確定した色を JS へ埋め込む。
            # グラフだけスライドの配色から浮くのを防ぐ。
            palette = chart_palette(style)
            axis_js = (
                "{ ticks: { color: %s, font: { size: 14 } }, grid: { color: %s } }"
                % (json.dumps(palette["tick"]), json.dumps(palette["grid"]))
            )
            scales_js = "{}" if chart_type in ("pie", "doughnut") else f"{{ x: {axis_js}, y: {axis_js} }}"

            chart_js = f"""
            (function() {{
              var ctx = document.getElementById('{canvas_id}').getContext('2d');
              new Chart(ctx, {{
                type: {json.dumps(chart_type)},
                data: {{
                  labels: {json.dumps(labels, ensure_ascii=False)},
                  datasets: [{{
                    label: {json.dumps(unit, ensure_ascii=False)},
                    data: {json.dumps(values)},
                    backgroundColor: {json.dumps(palette["series"])},
                    borderColor: {json.dumps(palette["border"])},
                    borderWidth: 2
                  }}]
                }},
                options: {{
                  responsive: false,
                  animation: false,
                  plugins: {{ legend: {{ labels: {{ color: {json.dumps(palette["legend"])}, font: {{ size: 16 }} }} }} }},
                  scales: {scales_js}
                }}
              }});
            }})();
            """
            script_tag = soup.new_tag("script")
            script_tag.string = chart_js
            elems.append(script_tag)

        elems.append(area)

    else:
        orb = soup.new_tag("div", attrs={"class": "deco-orb deco-orb-1"})
        elems.append(orb)

        _head(f"Scene {scene.index:02d}")

        area = soup.new_tag("div", attrs={"class": "slide-body-area"})
        display_text = body_text or fallback_text
        if display_text:
            bc = _body_card(soup, display_text, elem_start + 0.3, elem_duration - 0.3)
            if bc:
                area.append(bc)
        elems.append(area)

    return elems


def render_scene_preview_html(scene: Scene, style: VideoStyle | None = None) -> str:
    """1シーン分の「現在の実効 HTML」を文字列で返す。
    custom_html が設定されていればそれを、なければ自動生成結果を返す。"""
    if scene.custom_html:
        return scene.custom_html
    soup = BeautifulSoup("", "html.parser")
    parsed = _parse_slide_content(scene)
    elem_duration = max(0.1, (scene.data_duration or 10.0) - 1.0)
    elem_start = 0.5
    elems = _build_slide_content(soup, scene, parsed, elem_start, elem_duration, style)
    frag = soup.new_tag("div")
    for el in elems:
        frag.append(el)
    return "".join(str(c) for c in frag.contents)


def _validate_scene_html_fragment(html: str) -> tuple[bool, str]:
    """AI/手動編集された HTML 断片の最低限の妥当性チェック。"""
    if not html or not html.strip():
        return False, "空のHTMLは保存できません"
    try:
        frag = BeautifulSoup(html, "html.parser")
    except Exception as e:
        return False, f"HTMLの解析に失敗しました: {e}"
    if not frag.find(class_="clip"):
        return False, 'class="clip" を持つ要素が1つも見つかりません（このままでは何も表示されません）'
    if frag.find(attrs={"data-composition-id": True}):
        return False, "data-composition-id を含む要素は不可です（シーン単位の断片のみを返してください）"
    return True, ""


def sync_runtime_files(template_dir: Path, output_dir: Path) -> list[str]:
    """テンプレートのランタイムファイル (JS) を出力先へ同期する。

    動画作成時に一度コピーするだけでは以下の2つの穴が残る。
      - 分割レンダリングのチャンクディレクトリ (_chunks/chunkN) には存在しない
      - テンプレートを更新しても、作成済みの動画には反映されない
    どちらも「中身が空の動画」を生むため、コンポジションを書き出すたびに同期する。
    """
    copied: list[str] = []
    for name in RUNTIME_FILES:
        src = template_dir / name
        if not src.exists():
            continue
        dst = output_dir / name
        if dst.exists():
            src_stat, dst_stat = src.stat(), dst.stat()
            # 同サイズかつ出力先の方が新しければ最新とみなす（copy2 は mtime を引き継ぐ）
            if dst_stat.st_size == src_stat.st_size and dst_stat.st_mtime >= src_stat.st_mtime:
                continue
        shutil.copy2(src, dst)
        copied.append(name)
    return copied


def sync_font_dir(template_dir: Path, output_dir: Path) -> list[str]:
    """同梱フォントを出力先へ同期する。

    style.css は fonts/*.woff2 を相対パスで参照するため、コンポジションを
    書き出すディレクトリにフォントが無いとシステムフォントへ黙って差し替わる。
    分割レンダリングのチャンクでは renderer 側が相対シンボリックリンクを張るので、
    既に解決可能なら何もしない（1ファイル 2MB 超のため無駄なコピーを避ける）。
    """
    src_dir = template_dir / FONT_DIR_NAME
    if not src_dir.is_dir():
        return []

    dst_dir = output_dir / FONT_DIR_NAME
    copied: list[str] = []
    for name in FONT_FILES:
        src = src_dir / name
        if not src.exists():
            continue
        # シンボリックリンク経由でも実体に辿り着けるなら同期不要
        dst = dst_dir / name
        if dst.resolve().exists() and dst.resolve().stat().st_size == src.stat().st_size:
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(name)
    return copied


def find_missing_css_refs(css_path: Path) -> list[str]:
    """style.css が url() で参照するローカルファイルのうち、実在しないものを返す。

    フォントの 404 はレンダリングを止めず、システムフォントへ差し替わった映像が
    そのまま出力される。index.html 側と同じく無言の失敗になるため事前に検出する。
    """
    if not css_path.exists():
        return ["style.css"]

    base_dir = css_path.parent
    css_text = css_path.read_text(encoding="utf-8")

    # 埋め込み SVG (data URI) は先に丸ごと取り除く。
    # 中の filter="url(#n)" のような内部参照を実ファイルと誤認してしまうため。
    css_text = re.sub(r"""url\(\s*(["'])data:.*?\1\s*\)""", "", css_text, flags=re.S)

    missing: list[str] = []
    for raw in re.findall(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", css_text):
        ref = raw.strip()
        # 外部URL・残存する data URI・フラグメント参照は検証対象外
        if not ref or ref.startswith(("http://", "https://", "//", "data:", "#", "%23")):
            continue
        if not (base_dir / ref).resolve().exists():
            missing.append(ref)
    return sorted(set(missing))


def find_missing_local_refs(html_path: Path) -> list[str]:
    """index.html が参照するローカルファイルのうち、実在しないものを返す。

    hyperframes は JS/CSS の 404 をエラーにせずレンダリングを完走してしまい、
    アニメーションが適用されない静止画の動画が「成功」として出力される。
    無言の失敗になるため、レンダリング前にここで検出する。
    """
    if not html_path.exists():
        return ["index.html"]

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    base_dir = html_path.parent

    refs: list[str] = []
    for tag_name, attr in (
        ("script", "src"), ("link", "href"), ("img", "src"),
        ("audio", "src"), ("video", "src"),
    ):
        for el in soup.find_all(tag_name):
            value = (el.get(attr) or "").strip()
            if value:
                refs.append(value)

    missing: list[str] = []
    for ref in refs:
        # 外部URL・データURIは検証対象外
        if ref.startswith(("http://", "https://", "//", "data:")):
            continue
        # シンボリックリンク (チャンクの assets) も辿れるよう resolve する
        if not (base_dir / ref).resolve().exists():
            missing.append(ref)
    return sorted(set(missing))


def generate_composition(
    video: Video,
    scenes: list[Scene],
    style: VideoStyle,
    template_dir: Path,
    output_dir: Path,
    assets_map: dict[str, list] | None = None,
    fps: int | None = None,
):
    """コンポジション（index.html / style.css / meta.json）を書き出す。

    fps を指定するとルート要素に data-fps を付与する。hyperframes は
    「コンポジションのルート data-fps、無ければ 30」という優先順位で
    フレームレートを決めるため、ここで付けないと設定値が効かない。
    """
    base_html_path = template_dir / "index.html"
    if base_html_path.exists():
        soup = BeautifulSoup(base_html_path.read_text(encoding="utf-8"), "html.parser")
    else:
        soup = BeautifulSoup("<html><body><div id='stage'></div></body></html>", "html.parser")

    stage = soup.find(id="stage")
    if stage is None:
        stage = soup.new_tag("div", id="stage")
        soup.body.append(stage)

    stage.clear()

    # 背景は「模様の層」と「光の層」の2枚構成。どちらも中身は空で、
    # #stage に付く motif-* クラスに応じて CSS 側が描き分ける。
    stage.append(soup.new_tag("div", attrs={"class": "stage-bg-motif"}))
    stage.append(soup.new_tag("div", attrs={"class": "stage-bg-glow"}))

    cumulative_start = 0.0
    scene_custom_css_blocks = []

    for scene in scenes:
        audio_dur = scene.narration_audio_duration if scene.narration_audio_duration is not None else 10.0
        data_duration = audio_dur + TRANSITION_BUFFER
        data_start = cumulative_start

        scene.data_start = data_start
        scene.data_duration = data_duration

        slide_class = f"slide slide-layout-{scene.layout_type} clip"
        slide_div = soup.new_tag("div", attrs={
            "id": f"scene-{scene.id}",
            "class": slide_class,
            "data-start": f"{data_start:.2f}",
            "data-duration": f"{data_duration:.2f}"
        })

        elem_duration = max(0.1, data_duration - 1.0)
        elem_start = data_start + 0.5

        if scene.custom_html:
            # AI/手動編集済みのカスタム HTML を優先使用（自動生成をスキップ）
            custom_frag = BeautifulSoup(scene.custom_html, "html.parser")
            for child in list(custom_frag.contents):
                slide_div.append(child)
        else:
            parsed = _parse_slide_content(scene, assets_map)
            for el in _build_slide_content(soup, scene, parsed, elem_start, elem_duration, style):
                slide_div.append(el)

        if scene.custom_css:
            scene_custom_css_blocks.append(scene.custom_css)

        if assets_map and scene.layout_type != "image_gallery":
            # image_gallery は _build_slide_content 側で全スロットをグリッド描画済みのため対象外
            scene_assets = assets_map.get(scene.id, [])
            for asset in sorted(scene_assets, key=lambda a: a.slot):
                # 主画像としてスロット1を消費したレイアウトでは、個別の絶対配置描画をスキップ
                if asset.slot == 1 and scene.layout_type in ["full_image", "text_left_image_right"]:
                    continue
                el = _asset_to_html(soup, asset, data_start, data_duration)
                if el:
                    slide_div.append(el)

        stage.append(slide_div)

        audio_tag = soup.new_tag("audio", attrs={
            # id はレンダラーがメディア要素を発見するために必要
            # （無いと "media_missing_id: this audio will be SILENT in renders" と警告される）
            "id": f"audio-scene-{scene.index}",
            "src": f"assets/audio/scene{scene.index}.wav",
            "data-start": f"{data_start:.2f}",
            "data-duration": f"{audio_dur:.2f}",
            "data-track-index": "10",
            "data-volume": "1.0"
        })
        stage.append(audio_tag)

        cumulative_start += data_duration

    # ルートコンポジションの属性。hyperframes は data-composition-id をキーに
    # window.__timelines からタイムラインを取り出すため、欠けると何も動かない。
    stage["data-composition-id"] = video.id
    stage["data-start"] = "0"
    stage["data-duration"] = f"{cumulative_start:.2f}"
    stage["data-width"] = str(style.canvas_width)
    stage["data-height"] = str(style.canvas_height)
    # 背景モチーフ・装飾スタイル・タイポスケールはクラスで、
    # 切替トランジションは app.js が読む data 属性で伝える。
    stage["class"] = stage_classes(style)
    stage["data-transition"] = normalize_transition(style.transition)
    if fps:
        stage["data-fps"] = str(fps)

    video.duration_sec = cumulative_start

    html_output_path = output_dir / "index.html"
    html_output_path.write_text(str(soup), encoding="utf-8")

    # 旧 build_timeline.py 用のバックアップ (index.original.html) と
    # narration_durations.json は不要になったため、残っていれば削除する。
    # hyperframes はどちらも参照していない。
    for stale in ("index.original.html", "narration_durations.json"):
        (output_dir / stale).unlink(missing_ok=True)

    # index.html が読み込む JS と、style.css が読み込むフォントを同じディレクトリに揃える。
    # （分割レンダリングのチャンクや、テンプレート更新前に作られた動画への追従）
    sync_runtime_files(template_dir, output_dir)
    sync_font_dir(template_dir, output_dir)

    base_css_content = ""
    base_css_path = template_dir / "style.css"
    if base_css_path.exists():
        base_css_content = base_css_path.read_text(encoding="utf-8")

    # テンプレート CSS を先に置き、その後ろに動画ごとのテーマを注入する。
    # 順序が逆だとテンプレート側の :root（未注入時のフォールバック）が後勝ちして
    # ユーザーのスタイル設定が一切反映されなくなる。ここは入れ替えないこと。
    css_parts = [
        base_css_content,
        "\n/* ==========================================================================\n"
        "   動画ごとのテーマ（テンプレートの既定値を上書きする。必ず末尾に置くこと）\n"
        "   ========================================================================== */",
        build_theme_css(style, canvas_width=style.canvas_width, canvas_height=style.canvas_height),
    ]
    if style.custom_css:
        css_parts.append("\n/* 動画別カスタムCSS */\n" + style.custom_css)
    if scene_custom_css_blocks:
        css_parts.append("\n/* シーン別カスタムCSS */\n" + "\n".join(scene_custom_css_blocks))

    css_output_path = output_dir / "style.css"
    css_output_path.write_text("\n".join(css_parts), encoding="utf-8")

    meta_data = {
        "name": video.name,
        "description": video.name,
        "duration": round(cumulative_start, 2),
        "resolution": { "width": style.canvas_width, "height": style.canvas_height },
        "fps": fps or 30
    }
    meta_output_path = output_dir / "meta.json"
    meta_output_path.write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")


def _asset_to_html(soup, asset, data_start: float, slide_duration: float):
    """SceneAsset を HTML タグに変換して返す。"""
    import json as _json
    cfg_raw = asset.display_config_json or "{}"
    try:
        cfg = _json.loads(cfg_raw)
    except Exception:
        cfg = {}

    offset   = float(cfg.get("offset_sec", 0.5))
    duration = float(cfg.get("duration_sec") or max(0.1, slide_duration - 1.0))
    x        = cfg.get("x", "center")
    y        = cfg.get("y", "center")
    max_w    = cfg.get("max_width", "600px")
    max_h    = cfg.get("max_height", "500px")
    radius   = cfg.get("border_radius", "16px")

    elem_start = data_start + offset
    
    styles = [
        "position: absolute",
        f"max-width: {max_w}",
        f"max-height: {max_h}",
        f"border-radius: {radius}",
    ]
    
    # X軸
    if x == "left":
        styles.append("left: 5%")
    elif x == "right":
        styles.append("right: 5%")
    elif x == "center":
        styles.append("left: 50%")
    elif x:
        styles.append(f"left: {x}")
        
    # Y軸
    if y == "top":
        styles.append("top: 5%")
    elif y == "bottom":
        styles.append("bottom: 5%")
    elif y == "center":
        styles.append("top: 50%")
    elif y:
        styles.append(f"top: {y}")
        
    # center 時の transform 補正
    if x == "center" and y == "center":
        styles.append("transform: translate(-50%, -50%)")
    elif x == "center":
        styles.append("transform: translateX(-50%)")
    elif y == "center":
        styles.append("transform: translateY(-50%)")

    style_str = "; ".join(styles) + ";"

    if asset.asset_type == "svg" and not asset.file_path:
        # インライン SVG（手動登録時のみ想定）。file_path があれば下の img 分岐で読み込む
        wrapper = soup.new_tag("div", attrs={
            "class": f"clip asset-slot slot-{asset.slot}",
            "data-start": f"{elem_start:.2f}",
            "data-duration": f"{duration:.2f}",
            "style": style_str,
        })
        wrapper.append(BeautifulSoup(asset.svg_content or "", "html.parser"))
        return wrapper
    else:
        tag = "video" if asset.asset_type == "video" else "img"
        attrs = {
            "class": f"clip asset-slot slot-{asset.slot}",
            "data-start": f"{elem_start:.2f}",
            "data-duration": f"{duration:.2f}",
            "style": style_str,
            "src": asset.file_path or "",
        }
        if asset.asset_type == "video":
            attrs["loop"] = ""
            attrs["muted"] = ""
            attrs["autoplay"] = ""
            attrs["playsinline"] = ""
        return soup.new_tag(tag, attrs=attrs)
