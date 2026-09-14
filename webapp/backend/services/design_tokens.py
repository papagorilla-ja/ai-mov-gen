"""デザインシステムの中核 — 選択肢の定義と CSS カスタムプロパティの生成。

このモジュールが「唯一の正」となるように設計している。
選択肢 (背景モチーフ・装飾スタイル・タイポスケール・トランジション・フォント) は
ここだけで定義し、API・シード・LLM プロンプト・フロントエンドの全てが
ここから配られた値を使う。定義が二重化すると必ず片方が腐るため。

配色の考え方:
  ユーザーが指定するのは「主要 5 色 + フォント 2 種」だけに留める。
  文字の副色・境界線・カード地・影といった大量の派生色は、
  背景色の明るさ (相対輝度) から自動的に導出する。
  こうしないと「背景を白にしたら白文字で読めない」という破綻が必ず起きる。
"""

# ==========================================================================
# 選択肢の定義
# ==========================================================================

# 背景モチーフ。値はそのまま CSS のクラス名 (motif-<value>) になる。
BACKGROUND_MOTIFS = [
    {"value": "grid", "label": "グリッド", "description": "細かい方眼。情報密度の高い資料に馴染む"},
    {"value": "mesh", "label": "メッシュ", "description": "色玉をぼかして重ねた柔らかいグラデーション"},
    {"value": "dots", "label": "ドット", "description": "等間隔の点。軽快で親しみやすい"},
    {"value": "waves", "label": "ウェーブ", "description": "斜めの帯。動きと奥行きが出る"},
    {"value": "noise", "label": "ノイズ", "description": "微細な粒状の質感。落ち着いた紙のような印象"},
    {"value": "plain", "label": "無地", "description": "装飾なし。内容に集中させたいとき"},
]

# 装飾スタイル (カードや枠の質感)。値は CSS のクラス名 (decor-<value>) になる。
DECOR_STYLES = [
    {"value": "glass", "label": "グラス", "description": "半透明＋ぼかし。奥行きのある現代的な印象"},
    {"value": "flat", "label": "フラット", "description": "影も透過もない塗り。すっきりと軽い"},
    {"value": "outline", "label": "アウトライン", "description": "線画中心。余白が生きる知的な印象"},
    {"value": "solid", "label": "ソリッド", "description": "不透明＋強い影。要素が明確に浮き立つ"},
]

# タイポグラフィスケール。値は CSS のクラス名 (type-<value>) になる。
TYPE_SCALES = [
    {"value": "compact", "label": "密", "description": "文字を小さめに。情報量の多いスライド向け"},
    {"value": "normal", "label": "標準", "description": "バランス重視の既定値"},
    {"value": "relaxed", "label": "ゆったり", "description": "文字を大きく行間も広く。要点を絞ったスライド向け"},
]

# シーン切替トランジション。app.js が #stage の data-transition を読んで適用する。
TRANSITIONS = [
    {"value": "none", "label": "なし", "description": "瞬時に切り替わる。要素側のアニメーションのみ"},
    {"value": "fade", "label": "フェード", "description": "背景を挟んで穏やかに入れ替わる"},
    {"value": "slide", "label": "スライド", "description": "横方向に滑り込む。テンポが出る"},
    {"value": "zoom", "label": "ズーム", "description": "奥から迫り出す。印象が強い"},
    {"value": "wipe", "label": "ワイプ", "description": "下から拭うように現れる"},
]

# フォント。macOS に実在するものと、リポジトリに同梱した BIZ UDPGothic のみを扱う。
# stack は実際に font-family へ書き出す文字列。日本語名も併記して解決漏れを防ぐ。
FONT_CHOICES = [
    {
        "value": "BIZ UDPGothic",
        "label": "BIZ UDPゴシック",
        "description": "同梱。読みやすさに配慮したユニバーサルデザイン書体",
        "stack": "'BIZ UDPGothic', 'Hiragino Sans', sans-serif",
    },
    {
        "value": "Hiragino Sans",
        "label": "ヒラギノ角ゴシック",
        "description": "標準的なゴシック。癖がなく万能",
        "stack": "'Hiragino Sans', 'ヒラギノ角ゴシック', 'BIZ UDPGothic', sans-serif",
    },
    {
        "value": "Hiragino Mincho ProN",
        "label": "ヒラギノ明朝",
        "description": "明朝体。格調と信頼感を出したいとき",
        "stack": "'Hiragino Mincho ProN', 'ヒラギノ明朝 ProN', serif",
    },
    {
        "value": "Hiragino Maru Gothic ProN",
        "label": "ヒラギノ丸ゴ",
        "description": "丸ゴシック。柔らかく親しみやすい",
        "stack": "'Hiragino Maru Gothic ProN', 'ヒラギノ丸ゴ ProN', sans-serif",
    },
    {
        "value": "YuGothic",
        "label": "游ゴシック体",
        "description": "モダンで引き締まった印象。ビジネス資料向け",
        "stack": "'YuGothic', '游ゴシック体', 'Hiragino Sans', sans-serif",
    },
    {
        "value": "YuMincho",
        "label": "游明朝体",
        "description": "上品で線の細い明朝。文化・教養系の題材に",
        "stack": "'YuMincho', '游明朝体', 'Hiragino Mincho ProN', serif",
    },
    {
        "value": "Klee",
        "label": "クレー",
        "description": "手書き風の楷書。教育・研修の温かみを出す",
        "stack": "'Klee', 'クレー', 'Hiragino Mincho ProN', serif",
    },
    {
        "value": "Toppan Bunkyu Midashi Mincho",
        "label": "凸版文久見出し明朝",
        "description": "見出し専用の力強い明朝。タイトルに映える",
        "stack": "'Toppan Bunkyu Midashi Mincho', '凸版文久見出し明朝', 'Hiragino Mincho ProN', serif",
    },
]

# 動きの性格。動画 1 本の中で「動きの作法」を揃えるための唯一のつまみ。
#
# レイアウトごと・要素ごとにパラメータを開放しない理由:
#   50 レイアウト × 各要素 × 複数パラメータをユーザーに委ねると、1 本の動画の中で
#   動きの性格がバラバラになり、視聴者は毎シーン「この動画の作法」を学び直すことになる。
#   レイアウトの幅（layout_breadth）を絞っているのと同じ考え方。
#
# duration_scale は「動きにかける時間の倍率」。1 より大きいほどゆっくりになる。
# 登場・退場・シーン切替だけでなく、背景モチーフの周期と Ken Burns の寄りにも
# 同じ倍率が掛かる（app.js が #stage の属性から読む）。
#
# ease は「自分で ease を宣言していない語彙」にだけ適用される既定値。
# clip-path やぼかしを動かす語彙は back 系で行き過ぎると値が不正になるため、
# app.js 側で自前の ease を持たせて性格の影響を受けないようにしている。
MOTION_CHARACTERS = [
    {"value": "calm", "label": "落ち着き",
     "description": "ゆっくり動く。説明が主役で、映像に気を取られたくないとき",
     "duration_scale": 1.35, "ease": "power2.out"},
    {"value": "standard", "label": "標準",
     "description": "研修動画で扱いやすい速さ。迷ったらこれ",
     "duration_scale": 1.0, "ease": "power2.out"},
    {"value": "lively", "label": "躍動",
     "description": "速く、弾んで動く。提案資料や短い告知向け",
     "duration_scale": 0.72, "ease": "back.out(1.7)"},
]

# 読み上げ速度。生成した音声に後から掛ける倍率で、値がそのまま ffmpeg の atempo になる。
# 換算の根拠: 生成済み 67 シーンの実測で、等倍は中央値 5.96 文字/秒（約 358 字/分）。
BASE_CHARS_PER_SEC = 5.96
NARRATION_SPEEDS = [
    {"value": 0.9, "label": "ゆっくり", "description": "約 5.4 文字/秒。専門用語が多い内容や、初学者向けに"},
    {"value": 1.0, "label": "標準", "description": "約 6.0 文字/秒。ニュース番組と同じくらいの速さ"},
    {"value": 1.1, "label": "やや速め", "description": "約 6.6 文字/秒。聞き取りやすさを保ちつつ短くなる"},
    {"value": 1.2, "label": "速め", "description": "約 7.2 文字/秒。既知の内容の復習や、尺を詰めたいときに"},
    {"value": 1.3, "label": "かなり速め", "description": "約 7.7 文字/秒。早口に感じる人もいる速さ"},
]

# 既定値。「既存動画の見た目を変えない」ことを最優先に選んでいる。
DEFAULTS = {
    "color_primary": "#6366f1",
    "color_secondary": "#8b5cf6",
    "color_accent": "#22d3ee",
    "color_bg": "#0f0f1a",
    "color_text_primary": "#f8fafc",
    "font_heading": "BIZ UDPGothic",
    "font_body": "BIZ UDPGothic",
    "background_motif": "grid",
    "decor_style": "glass",
    "type_scale": "normal",
    "transition": "none",
    "motion_character": "standard",
    "narration_speed": 1.0,
}

# 廃止したフォント名から現行の選択肢への読み替え。
# 過去に保存された 'Noto Sans JP' 等は実体が存在しないため、必ずここで吸収する。
LEGACY_FONT_ALIASES = {
    "Noto Sans JP": "BIZ UDPGothic",
    "Noto Serif JP": "Hiragino Mincho ProN",
    "M PLUS Rounded 1c": "Hiragino Maru Gothic ProN",
    "BIZ UDPGothic": "BIZ UDPGothic",
    "Inter": "YuGothic",
    "Roboto": "YuGothic",
}

_MOTIF_VALUES = {o["value"] for o in BACKGROUND_MOTIFS}
_DECOR_VALUES = {o["value"] for o in DECOR_STYLES}
_TYPE_VALUES = {o["value"] for o in TYPE_SCALES}
_TRANSITION_VALUES = {o["value"] for o in TRANSITIONS}
_FONT_STACKS = {o["value"]: o["stack"] for o in FONT_CHOICES}
_SPEED_VALUES = tuple(o["value"] for o in NARRATION_SPEEDS)
_MOTION_VALUES = {o["value"] for o in MOTION_CHARACTERS}
_MOTION_BY_VALUE = {o["value"]: o for o in MOTION_CHARACTERS}

# API / フロントエンドへまとめて渡すためのカタログ
STYLE_OPTIONS = {
    "background_motifs": BACKGROUND_MOTIFS,
    "decor_styles": DECOR_STYLES,
    "type_scales": TYPE_SCALES,
    "transitions": TRANSITIONS,
    # stack も渡す。画面側でフォント名をその書体自身で描いて見せるのに使う。
    "fonts": FONT_CHOICES,
    "narration_speeds": NARRATION_SPEEDS,
    "motion_characters": MOTION_CHARACTERS,
    "defaults": DEFAULTS,
}


# ==========================================================================
# 値の正規化
# ==========================================================================

def normalize_choice(value: str | None, allowed: set[str], fallback: str) -> str:
    """許可された選択肢に丸める。DB の NULL・古い値・LLM の出鱈目を一箇所で吸収する。"""
    if value and value in allowed:
        return value
    return fallback


def normalize_motion_character(value: str | None) -> str:
    return normalize_choice(value, _MOTION_VALUES, DEFAULTS["motion_character"])


def motion_character(style) -> dict:
    """スタイルから動きの性格の定義（倍率と ease を含む）を引く。

    app.js には倍率と ease を数値・文字列として渡す。
    向こうに同じ表をもう 1 つ置くと必ず片方が腐るため、定義はここだけに持つ。
    """
    value = normalize_motion_character(getattr(style, "motion_character", None) if style else None)
    return _MOTION_BY_VALUE[value]


def normalize_narration_speed(value) -> float:
    """読み上げ速度を許可された段階に丸める。

    そのまま ffmpeg の atempo に渡す値なので、範囲外や数値でないものを
    通すと音声処理そのものが落ちる。段階の中で一番近いものへ寄せる。
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return DEFAULTS["narration_speed"]
    return min(_SPEED_VALUES, key=lambda allowed: abs(allowed - v))


def normalize_motif(value: str | None) -> str:
    return normalize_choice(value, _MOTIF_VALUES, DEFAULTS["background_motif"])


def normalize_decor(value: str | None) -> str:
    return normalize_choice(value, _DECOR_VALUES, DEFAULTS["decor_style"])


def normalize_type_scale(value: str | None) -> str:
    return normalize_choice(value, _TYPE_VALUES, DEFAULTS["type_scale"])


def normalize_transition(value: str | None) -> str:
    return normalize_choice(value, _TRANSITION_VALUES, DEFAULTS["transition"])


def normalize_font(value: str | None, fallback: str = "BIZ UDPGothic") -> str:
    """フォント名を現行の選択肢に丸める（廃止名のエイリアスも解決する）。"""
    if not value:
        return fallback
    if value in _FONT_STACKS:
        return value
    return LEGACY_FONT_ALIASES.get(value, fallback)


def font_stack(value: str | None) -> str:
    """フォント名から font-family に書き出す文字列を得る。"""
    return _FONT_STACKS[normalize_font(value)]


# ==========================================================================
# 色の計算
# ==========================================================================

def parse_hex(value: str | None, fallback: str) -> tuple[int, int, int]:
    """#rgb / #rrggbb を (r, g, b) に変換する。壊れた値は fallback に落とす。"""
    for candidate in (value, fallback):
        if not candidate:
            continue
        text = candidate.strip().lstrip("#")
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) == 6:
            try:
                return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
            except ValueError:
                continue
    return (0, 0, 0)


def to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(round(c)))) for c in rgb))


def rgb_triplet(rgb: tuple[int, int, int]) -> str:
    """rgba(var(--x-rgb), 0.3) の形で使えるよう "r, g, b" を返す。"""
    return ", ".join(str(max(0, min(255, int(round(c))))) for c in rgb)


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG の相対輝度。0 (黒) 〜 1 (白)。"""
    channels = []
    for c in rgb:
        srgb = c / 255.0
        channels.append(srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """WCAG のコントラスト比。1.0 (同色) 〜 21.0 (黒と白)。"""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    """a を b の方向へ ratio (0.0〜1.0) だけ寄せた色。"""
    ratio = max(0.0, min(1.0, ratio))
    return tuple(a[i] + (b[i] - a[i]) * ratio for i in range(3))


_WHITE = (255, 255, 255)
_BLACK = (17, 17, 17)


# ==========================================================================
# トークンの生成
# ==========================================================================

def build_theme_css(style, *, canvas_width: int, canvas_height: int) -> str:
    """VideoStyle から :root の CSS カスタムプロパティ定義を組み立てる。

    ここで生成した :root は「テンプレート CSS より後ろ」に連結すること。
    先に置くとテンプレート側の :root（未注入時のフォールバック）に上書きされ、
    ユーザーの設定が一切効かなくなる。
    """
    primary = parse_hex(getattr(style, "color_primary", None), DEFAULTS["color_primary"])
    secondary = parse_hex(getattr(style, "color_secondary", None), DEFAULTS["color_secondary"])
    accent = parse_hex(getattr(style, "color_accent", None), DEFAULTS["color_accent"])
    bg = parse_hex(getattr(style, "color_bg", None), DEFAULTS["color_bg"])
    text = parse_hex(getattr(style, "color_text_primary", None), DEFAULTS["color_text_primary"])

    # 背景の明るさでテーマを決める。以降の派生色はすべてこの判定に従う。
    is_light = relative_luminance(bg) > 0.5

    # 文字色と背景色のコントラストが不足している組み合わせ（暗いテーマの文字色を
    # 残したまま背景だけ白にした等）は、そのままだと本文が読めない。
    # ユーザー指定を尊重しつつ、破綻している場合に限り安全な色へ差し替える。
    if contrast_ratio(text, bg) < 3.0:
        text = _BLACK if is_light else _WHITE

    # 前景を背景側へ寄せて副次的な文字色を作る（明暗どちらでも自然に沈む）
    text_secondary = mix(text, bg, 0.32)
    text_muted = mix(text, bg, 0.55)

    # カードなどの「一段持ち上がった面」。明るいテーマでは暗く、暗いテーマでは明るく。
    elevated = mix(bg, _BLACK if is_light else _WHITE, 0.05 if is_light else 0.07)
    elevated_strong = mix(bg, _BLACK if is_light else _WHITE, 0.10 if is_light else 0.14)

    # 境界線・罫線・影は明暗で反転させる
    if is_light:
        border = "rgba(15, 23, 42, 0.12)"
        border_strong = "rgba(15, 23, 42, 0.24)"
        grid_line = "rgba(15, 23, 42, 0.05)"
        surface_glass = f"rgba({rgb_triplet(_WHITE)}, 0.72)"
        shadow_soft = "0 18px 40px -18px rgba(15, 23, 42, 0.22)"
        shadow_strong = "0 26px 60px -20px rgba(15, 23, 42, 0.32)"
    else:
        border = "rgba(255, 255, 255, 0.09)"
        border_strong = "rgba(255, 255, 255, 0.20)"
        grid_line = "rgba(255, 255, 255, 0.025)"
        surface_glass = f"rgba({rgb_triplet(elevated)}, 0.68)"
        shadow_soft = "0 18px 40px -18px rgba(0, 0, 0, 0.55)"
        shadow_strong = "0 26px 60px -20px rgba(0, 0, 0, 0.70)"

    # 主要色の上に乗せる文字色（バッジやボタンの中身）
    on_primary = to_hex(_BLACK if relative_luminance(primary) > 0.55 else _WHITE)
    on_accent = to_hex(_BLACK if relative_luminance(accent) > 0.55 else _WHITE)

    # 見出しのグラデーション。文字色からアクセント寄りへ滑らかに振る。
    title_from = to_hex(text)
    title_to = to_hex(mix(text, accent, 0.45))
    section_to = to_hex(mix(text, accent, 0.85))

    # full_image レイアウトのタイトルを読ませるための覆い（常に背景色ベース）
    overlay_rgb = rgb_triplet(bg)

    heading_stack = font_stack(getattr(style, "font_heading", None))
    body_stack = font_stack(getattr(style, "font_body", None))

    return f""":root {{
  /* ---- ユーザー指定色 ---- */
  --color-primary: {to_hex(primary)};
  --color-secondary: {to_hex(secondary)};
  --color-accent: {to_hex(accent)};
  --color-primary-rgb: {rgb_triplet(primary)};
  --color-secondary-rgb: {rgb_triplet(secondary)};
  --color-accent-rgb: {rgb_triplet(accent)};
  --color-primary-glow: rgba({rgb_triplet(primary)}, 0.16);
  --color-accent-glow: rgba({rgb_triplet(accent)}, 0.14);
  --on-primary: {on_primary};
  --on-accent: {on_accent};

  /* ---- 背景と面 ---- */
  --bg-main: {to_hex(bg)};
  --bg-main-rgb: {overlay_rgb};
  --bg-elevated: {to_hex(elevated)};
  --bg-elevated-strong: {to_hex(elevated_strong)};
  --surface-glass: {surface_glass};

  /* ---- 文字 ---- */
  --text-primary: {to_hex(text)};
  --text-secondary: {to_hex(text_secondary)};
  --text-muted: {to_hex(text_muted)};
  --title-grad-from: {title_from};
  --title-grad-to: {title_to};
  --section-grad-to: {section_to};

  /* ---- 罫線と影 ---- */
  --border-glass: {border};
  --border-glass-hover: {border_strong};
  --border-strong: {border_strong};
  --grid-line: {grid_line};
  --shadow-soft: {shadow_soft};
  --shadow-strong: {shadow_strong};

  /* ---- 書体 ---- */
  --font-heading: {heading_stack};
  --font-body: {body_stack};

  /* ---- キャンバス ---- */
  --canvas-width: {canvas_width}px;
  --canvas-height: {canvas_height}px;
}}
"""


def chart_palette(style) -> dict:
    """Chart.js に渡す配色を組み立てる。

    Chart.js は canvas に描くため CSS 変数が使えず、確定した色を JS 側へ
    埋め込む必要がある。グラフだけ配色から浮かないよう、ここでも
    ユーザー指定色から系列色・目盛り色・凡例色を導出する。
    """
    primary = parse_hex(getattr(style, "color_primary", None), DEFAULTS["color_primary"])
    secondary = parse_hex(getattr(style, "color_secondary", None), DEFAULTS["color_secondary"])
    accent = parse_hex(getattr(style, "color_accent", None), DEFAULTS["color_accent"])
    bg = parse_hex(getattr(style, "color_bg", None), DEFAULTS["color_bg"])
    text = parse_hex(getattr(style, "color_text_primary", None), DEFAULTS["color_text_primary"])

    is_light = relative_luminance(bg) > 0.5
    if contrast_ratio(text, bg) < 3.0:
        text = _BLACK if is_light else _WHITE

    # 主要3色に加え、その中間色を挟んで6系列ぶんを作る。
    # 系列数がこれを超える場合は Chart.js 側で循環利用される。
    series = [
        primary,
        accent,
        secondary,
        mix(primary, accent, 0.5),
        mix(accent, secondary, 0.5),
        mix(secondary, primary, 0.5),
    ]
    return {
        "series": [to_hex(c) for c in series],
        "border": to_hex(primary),
        "tick": to_hex(mix(text, bg, 0.35)),
        "legend": to_hex(text),
        "grid": f"rgba({rgb_triplet(mix(text, bg, 0.65))}, 0.45)",
    }


def stage_classes(style) -> str:
    """#stage に付与するデザイン系クラス（背景モチーフ・装飾・タイポ）を組み立てる。"""
    motif = normalize_motif(getattr(style, "background_motif", None))
    decor = normalize_decor(getattr(style, "decor_style", None))
    scale = normalize_type_scale(getattr(style, "type_scale", None))
    return f"motif-{motif} decor-{decor} type-{scale}"
