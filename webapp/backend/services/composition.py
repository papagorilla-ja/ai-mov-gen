import json
import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
from models.video import Video
from models.scene import Scene
from models.video_style import VideoStyle
from layouts import _registry as layouts
from layouts import _render, _types
from services.design_tokens import (
    build_theme_css,
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


def aspect_of(style) -> str:
    """キャンバスの縦横比を "16:9" / "4:3" の文字列にする。

    レイアウトはこの値で「自分が成立するか」を判断し、CSS は
    [data-aspect="4:3"] で横並びの密度を一段詰める。
    """
    width = getattr(style, "canvas_width", 1920) or 1920
    height = getattr(style, "canvas_height", 1080) or 1080
    return "4:3" if (width / height) < 1.5 else "16:9"


def resolve_scene(scene: Scene, assets_map: dict | None = None):
    """シーンから (レイアウト, 正規化済みの内容, 件数) を取り出す。

    DB の slide_content_json は旧キー（bullet_points / cards / left_text …）の
    ことがあるが、_types.normalize() が読み込み時に吸収する。
    レイアウト別の分岐はここには書かない（全て layouts/ 配下が持つ）。
    """
    raw: dict = {}
    if scene.slide_content_json:
        try:
            parsed = json.loads(scene.slide_content_json)
            if isinstance(parsed, dict):
                raw = parsed
        except Exception:
            pass

    spec = layouts.get(scene.layout_type) or layouts.get(layouts.FALLBACK_LAYOUT)
    content = _types.normalize(spec.type_id, raw)

    # タイトルはシーン一覧で編集される scene.title を控えとして使う。
    # 以前は最後の手段として "Scene 03" を出していたが、内容と無関係な
    # 文字を毎スライドに出すのは読み取りコストを増やすだけなので出さない。
    if not content.get("title"):
        content["title"] = scene.title or ""

    # 固有の内容がまだ生成されていないシーンは、あらすじで場をつなぐ
    _types.fill_from_summary(spec.type_id, content, scene.outline_summary or "")

    # 画像は media 型のレイアウトだけが内容として受け取る。
    # それ以外のレイアウトでは、従来どおり絶対配置のアセットとして重ねる
    # （generate_composition 側で処理する）。
    if assets_map and spec.type_id == "media":
        scene_assets = sorted(assets_map.get(scene.id, []), key=lambda a: a.slot)
        from_assets = [{"src": a.file_path, "caption": ""} for a in scene_assets if a.file_path]
        if from_assets:
            limit = spec.capacity.max if not spec.capacity.any else len(from_assets)
            content["images"] = from_assets[:limit]

    return spec, content, _types.count_of(spec.type_id, content)


def render_scene_fragment(
    scene: Scene,
    style: VideoStyle | None = None,
    assets_map: dict | None = None,
    *,
    scene_start: float = 0.0,
    scene_duration: float | None = None,
):
    """1 シーン分の HTML 断片を (レイアウト, HTML) で返す。"""
    spec, content, count = resolve_scene(scene, assets_map)
    duration = scene_duration if scene_duration is not None else (scene.data_duration or 10.0)
    html = _render.render(
        spec, content,
        scene_start=scene_start,
        scene_duration=duration,
        aspect=aspect_of(style),
        count=count,
        extra={"style": style, "scene_index": scene.index},
    )
    return spec, html


def render_scene_preview_html(scene: Scene, style: VideoStyle | None = None) -> str:
    """1シーン分の「現在の実効 HTML」を文字列で返す。
    custom_html が設定されていればそれを、なければ自動生成結果を返す。"""
    if scene.custom_html:
        return scene.custom_html
    _, html = render_scene_fragment(scene, style, scene_start=0.0)
    return html


def render_layout_sample_html(layout_id: str, style: VideoStyle | None = None) -> str:
    """レイアウト選択ギャラリーのサムネイル用に、サンプル内容で描画する。

    サムネイル画像を手で用意せず、実際のレイアウトビルダーに流して実物を作る。
    こうしておけば、実装を直したときにサムネイルだけ古いまま、という
    ずれが原理的に起きない。
    """
    spec = layouts.get(layout_id)
    if not spec:
        return ""
    content = _types.normalize(spec.type_id, spec.sample_content())
    return _render.render(
        spec, content,
        scene_start=0.0, scene_duration=10.0,
        aspect=aspect_of(style),
        count=_types.count_of(spec.type_id, content),
        extra={"style": style, "scene_index": 0},
    )


# サムネイル用の文書で参照するフォントの配信先（main.py の StaticFiles マウントと対）。
TEMPLATE_ASSET_URL = "/template-assets"


def render_layout_sample_document(layout_id: str, style: VideoStyle | None = None,
                                  template_dir: Path | None = None) -> str:
    """レイアウトのサムネイルを iframe に流し込むための、完結した HTML 文書。

    スライドの CSS は :root や #stage を書き換える強い指定を含むため、
    編集画面へ直接埋め込むと画面全体の見た目を壊す。iframe に閉じ込める。
    """
    spec = layouts.get(layout_id)
    if not spec:
        return ""

    template_dir = template_dir or Path("/app/templates/blank")
    base_css = ""
    css_path = template_dir / "style.css"
    if css_path.exists():
        base_css = css_path.read_text(encoding="utf-8")

    style = style or VideoStyle()
    width = getattr(style, "canvas_width", None) or 1920
    height = getattr(style, "canvas_height", None) or 1080
    orbs = "".join(f'<div class="deco-orb deco-orb-{i + 1}"></div>' for i in range(spec.orbs))

    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
{base_css}
{layouts.collect_css([spec.id])}
{build_theme_css(style, canvas_width=width, canvas_height=height)}
/* ---- サムネイル専用 ----
   GSAP を動かさないので、全要素を表示済みの状態に固定する。
   #stage を箱の幅に合わせて縮小し、原寸のレイアウトをそのまま縮めて見せる。 */
@font-face {{ font-family: 'BIZ UDPGothic'; font-weight: 400;
  src: url('{TEMPLATE_ASSET_URL}/fonts/BIZUDPGothic-Regular.woff2') format('woff2'); }}
@font-face {{ font-family: 'BIZ UDPGothic'; font-weight: 700;
  src: url('{TEMPLATE_ASSET_URL}/fonts/BIZUDPGothic-Bold.woff2') format('woff2'); }}
html, body {{ margin: 0; padding: 0; overflow: hidden; background: var(--bg-main); }}
#stage {{
  position: absolute; left: 0; top: 0;
  width: {width}px; height: {height}px;
  transform: scale(var(--thumb-scale, 1));
  transform-origin: top left;
  overflow: hidden;
}}
.slide {{ opacity: 1 !important; pointer-events: none; }}
.clip {{ opacity: 1 !important; }}
</style>
<!-- グラフのレイアウトは Chart.js で canvas に描く。読み込まないと
     サムネイルだけ「グラフが消えた空のスライド」になる。 -->
<script src="{TEMPLATE_ASSET_URL}/chart.min.js"></script>
</head><body>
<div id="stage" class="{stage_classes(style)}" data-aspect="{aspect_of(style)}">
  <div class="stage-bg-motif"></div><div class="stage-bg-glow"></div>
  <div class="slide slide-layout-{spec.id}" style="--veil: {spec.veil}">
    {orbs}{render_layout_sample_html(spec.id, style)}
  </div>
</div>
<script>
// 原寸 {width}px のスライドを、埋め込み先の幅に合わせて縮小する。
// CSS だけでは書けない。calc(100vw / {width}) は「長さ ÷ 数値 = 長さ」になり、
// 無単位の数値を要求する scale() では無効な値として無視されてしまう。
(function () {{
  function fit() {{
    document.documentElement.style.setProperty(
      '--thumb-scale', (document.documentElement.clientWidth / {width}).toFixed(4));
  }}
  fit();
  window.addEventListener('resize', fit);
}})();
</script>
</body></html>"""


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
    # この動画で実際に使われたレイアウト。CSS はここにあるものだけ連結する。
    used_layouts: list[str] = []

    for scene in scenes:
        audio_dur = scene.narration_audio_duration if scene.narration_audio_duration is not None else 10.0
        data_duration = audio_dur + TRANSITION_BUFFER
        data_start = cumulative_start

        scene.data_start = data_start
        scene.data_duration = data_duration

        spec = layouts.get(scene.layout_type) or layouts.get(layouts.FALLBACK_LAYOUT)
        used_layouts.append(spec.id)

        slide_div = soup.new_tag("div", attrs={
            "id": f"scene-{scene.id}",
            "class": f"slide slide-layout-{spec.id} clip",
            "data-start": f"{data_start:.2f}",
            "data-duration": f"{data_duration:.2f}",
            # 背景モチーフをどれだけ覆うかはレイアウトごとに違う。
            # CSS に一覧を持たず、レジストリの値をそのまま書き出す。
            "style": f"--veil: {spec.veil}",
        })

        # 背景の装飾オーブ。枚数はレイアウトが宣言する（全面画像は 0）。
        for i in range(spec.orbs):
            slide_div.append(soup.new_tag("div", attrs={"class": f"deco-orb deco-orb-{i + 1}"}))

        if scene.custom_html:
            # AI/手動編集済みのカスタム HTML を優先使用（自動生成をスキップ）
            custom_frag = BeautifulSoup(scene.custom_html, "html.parser")
            for child in list(custom_frag.contents):
                slide_div.append(child)
        else:
            _, fragment = render_scene_fragment(
                scene, style, assets_map,
                scene_start=data_start, scene_duration=data_duration,
            )
            for child in list(BeautifulSoup(fragment, "html.parser").contents):
                slide_div.append(child)

        if scene.custom_css:
            scene_custom_css_blocks.append(scene.custom_css)

        # media 型のレイアウトは画像を内容として受け取り済みなので重ねない。
        # それ以外（手動アップロードの添え物）は従来どおり絶対配置で重ねる。
        if assets_map and spec.type_id != "media":
            for asset in sorted(assets_map.get(scene.id, []), key=lambda a: a.slot):
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
    # 横並びのレイアウトは 4:3 で一段詰める必要がある。CSS が
    # [data-aspect="4:3"] で拾えるよう、ここで比率を書き出す。
    stage["data-aspect"] = aspect_of(style)
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
        "   この動画で使われたレイアウトの CSS（layouts/<id>/style.css）\n"
        "   使っていないレイアウトは出さない。生成物を読めるサイズに保つため。\n"
        "   ========================================================================== */",
        layouts.collect_css(used_layouts),
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
