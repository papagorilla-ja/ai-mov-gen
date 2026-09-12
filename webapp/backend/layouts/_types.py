"""コンテンツ・スキーマ（型）の定義 — このモジュールが「唯一の正」。

設計の中心にある考え方:
    見せ方（レイアウト）は 40 種類あるが、**データの形は 14 種類しかない**。

        型 sequence (steps[])  ─┬→ 横型フロー
                                ├→ 縦型フロー
                                ├→ 階段
                                └→ 年表

    同じ型に属するレイアウト同士は、入力内容をそのまま保って差し替えられる。
    これにより
      - AI は「14 型のどれか」を選ぶだけで済む（40 択にしない）
      - 編集フォームは 14 種類作れば足りる（40 種類作らない）
      - レイアウトを変えても入力内容が消えない
    という 3 つが同時に成立する。

このモジュールが提供するもの:
    1. 型ごとのフィールド定義     … 編集フォームの自動生成と LLM プロンプト生成に使う
    2. normalize()                … 任意の dict を型のスキーマへ丸める（旧キーも吸収）
    3. count_of()                 … 件数を数える（レイアウト自動差し替えの判定に使う）
    4. convert()                  … 型をまたいだ変換（情報が落ちる件数も返す）

旧データの扱い:
    DB に保存済みの slide_content_json は旧キー（bullet_points / cards /
    left_text …）を持つ。DB 移行はせず、normalize() が読み込み時に吸収する。
    新しい編集画面から保存すると新しい形に置き換わる。どちらの形でも動く。
"""

from dataclasses import dataclass, field


# ==========================================================================
# フィールド定義
# ==========================================================================

# kind の一覧。フロントエンドの汎用フォームはこの値でレンダラーを切り替える。
#   text      … 1 行入力
#   textarea  … 複数行入力
#   choice    … 選択肢（options を持つ）
#   group     … 入れ子オブジェクト（children でその形を定義）
#   items     … オブジェクトの配列（children で 1 件の形を定義）
#   tree      … 階層構造（専用コンポーネント）
#   table     … 見出し行＋データ行（専用コンポーネント）
#   chart     … グラフ設定（専用コンポーネント）
#   images    … 画像スロットの配列（専用コンポーネント）
FIELD_KINDS = frozenset({
    "text", "textarea", "choice", "group", "items", "tree", "table", "chart", "images",
})

# 専用エディタが必要な kind。フロント側はこれ以外を汎用レンダラーで描く。
DEDICATED_KINDS = frozenset({"tree", "table", "chart", "images"})


@dataclass(frozen=True)
class FieldSpec:
    """1 フィールドの定義。

    hint は「人間への入力の手引き」と「LLM への書き方の指示」を兼ねる。
    同じ文言を 2 箇所に書くと必ず片方が腐るため、意図的に 1 本にしている。
    """
    name: str
    kind: str
    label: str                                  # 編集画面に出る日本語ラベル
    hint: str = ""                              # 書き方の指針（人間と LLM の両方が読む）
    max_chars: int | None = None                # 目安の上限文字数
    options: tuple[str, ...] = ()               # kind="choice" の選択肢
    children: tuple["FieldSpec", ...] = ()      # kind="group" / "items" の中身
    fixed_count: int | None = None              # kind="items" で件数が固定のもの（象限=4 など）

    def __post_init__(self):
        if self.kind not in FIELD_KINDS:
            raise ValueError(f"未知の kind: {self.kind}（{self.name}）")


@dataclass(frozen=True)
class ContentType:
    """コンテンツ・スキーマ 1 種類ぶんの定義。"""
    id: str
    label: str                                  # 「順序」など、選択 UI に出す短い日本語
    description: str                            # LLM に見せる「どんな内容のときこの型か」
    fields: tuple[FieldSpec, ...]
    # 件数を数えるフィールド名。None なら「件数」という概念を持たない型。
    # レイアウトの自動差し替え（capacity 判定）はこの値を見る。
    collection: str | None = None
    min_count: int = 0
    max_count: int = 0
    sample: dict = field(default_factory=dict)  # ギャラリーのサムネイル生成に使う


# ==========================================================================
# 共通フィールド（全 14 型が持つ）
# ==========================================================================

COMMON_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        name="title", kind="text", label="スライドタイトル",
        hint="このスライドで伝える一番のことを 10〜28 文字で。体言止め可。",
        max_chars=28,
    ),
    FieldSpec(
        name="eyebrow", kind="text", label="アイブロウ（小見出し）",
        hint=(
            "タイトルの上に出す 4〜10 文字の日本語。内容に紐づく語だけを入れる"
            "（例:「3つの手法」「前年比較」「導入の流れ」）。"
            "適切な語が無ければ空文字にする。空なら表示されない。"
        ),
        max_chars=10,
    ),
)


# ==========================================================================
# 部品（複数の型で使い回すフィールド）
# ==========================================================================

def _labeled_item(label_max: int, text_max: int, *, with_icon: bool = True) -> tuple[FieldSpec, ...]:
    """「見出し＋説明（＋アイコン）」という最頻出の 1 件の形。

    list / sequence / cycle がこの形を共有しているため、型をまたいでも
    内容を保ったまま差し替えられる（convert() が無変換で通す根拠）。
    """
    children = [
        FieldSpec(name="label", kind="text", label="見出し",
                  hint=f"{label_max} 文字以内の短い見出し。体言止め可。", max_chars=label_max),
        FieldSpec(name="text", kind="textarea", label="説明",
                  hint=f"{text_max} 文字以内。丁寧語で 1〜2 文。", max_chars=text_max),
    ]
    if with_icon:
        children.append(FieldSpec(
            name="icon", kind="text", label="アイコン",
            hint="内容を表す日本語 1 語（例: 成長 / 注意 / 人 / 時間）。無ければ空文字。",
            max_chars=8,
        ))
    return tuple(children)


_SIDE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(name="title", kind="text", label="見出し",
              hint="比較対象の名前。4〜16 文字。", max_chars=16),
    FieldSpec(name="text", kind="textarea", label="説明",
              hint="60〜100 文字。もう一方と同じ観点で書く。", max_chars=100),
)


# ==========================================================================
# 14 型の定義
# ==========================================================================

CONTENT_TYPES: dict[str, ContentType] = {}


def _register(ct: ContentType) -> ContentType:
    CONTENT_TYPES[ct.id] = ct
    return ct


STATEMENT = _register(ContentType(
    id="statement",
    label="宣言",
    description="伝えたいことが 1 つだけで、分解も比較もしない内容。導入・結論・キーメッセージ。",
    fields=(
        FieldSpec(name="lead", kind="text", label="主文",
                  hint="一番伝えたい一文。40 文字以内。", max_chars=40),
        FieldSpec(name="body", kind="textarea", label="本文",
                  hint="80〜150 文字。1〜3 文。丁寧語。", max_chars=150),
        FieldSpec(name="note", kind="text", label="補足",
                  hint="出典や前提など。不要なら空文字。", max_chars=40),
    ),
    sample={"lead": "理解は「覚える」ことではありません",
            "body": "研修で学んだことを行動に変えるには、知識を自分の業務に翻訳する時間が必要です。",
            "note": ""},
))

LIST = _register(ContentType(
    id="list",
    label="並列",
    description="同じ階層の複数の情報を並べる。要点の列挙、機能紹介、観点の提示。順序に意味は無い。",
    fields=(
        FieldSpec(name="items", kind="items", label="項目",
                  hint="2〜6 件。粒度（抽象度）を揃える。無理に数を増やさない。",
                  children=_labeled_item(16, 70)),
    ),
    collection="items", min_count=2, max_count=6,
    sample={"items": [
        {"label": "年代測定", "text": "遺物がいつのものかを高い精度で特定します。", "icon": "時間"},
        {"label": "残留物分析", "text": "土器に残る有機物から当時の食生活を復元します。", "icon": "調査"},
        {"label": "同位体分析", "text": "人骨から集団の移動経路を追跡します。", "icon": "地図"},
    ]},
))

SEQUENCE = _register(ContentType(
    id="sequence",
    label="順序",
    description="時系列・手順・段階など、並び順そのものに意味がある内容。フロー、ステップ、年表。",
    fields=(
        FieldSpec(name="steps", kind="items", label="ステップ",
                  hint="2〜7 件。前から後ろへ進む順に並べる。各ステップは 1 動作に絞る。",
                  children=_labeled_item(14, 60)),
    ),
    collection="steps", min_count=2, max_count=7,
    sample={"steps": [
        {"label": "課題の把握", "text": "現場で何が起きているかを観察します。", "icon": "調査"},
        {"label": "原因の特定", "text": "データを集めて仮説を検証します。", "icon": "分析"},
        {"label": "対策の実行", "text": "小さく試してから展開します。", "icon": "実行"},
    ]},
))

CONTRAST = _register(ContentType(
    id="contrast",
    label="対比",
    description="2 つのものを同じ観点で比べる。従来と新方式、AとB、ビフォーアフター。",
    fields=(
        FieldSpec(name="left", kind="group", label="左", children=_SIDE_FIELDS),
        FieldSpec(name="right", kind="group", label="右", children=_SIDE_FIELDS),
        FieldSpec(name="verdict", kind="text", label="結論",
                  hint="対比から言えることを 40 文字以内で。不要なら空文字。", max_chars=40),
    ),
    sample={
        "left": {"title": "従来の進め方", "text": "全体を設計し切ってから着手するため、前提が変わると手戻りが大きくなります。"},
        "right": {"title": "新しい進め方", "text": "小さく作って確かめながら進めるため、前提の変化を早く織り込めます。"},
        "verdict": "不確実性が高いほど後者が有利になります",
    },
))

HIERARCHY = _register(ContentType(
    id="hierarchy",
    label="階層",
    description="上下関係・包含関係・分解構造。ピラミッド、ツリー、組織図、目的と手段の分解。",
    fields=(
        FieldSpec(name="root", kind="group", label="頂点",
                  children=(
                      FieldSpec(name="label", kind="text", label="見出し", max_chars=16),
                      FieldSpec(name="text", kind="textarea", label="説明", max_chars=60),
                  )),
        FieldSpec(name="children", kind="tree", label="階層",
                  hint="深さは最大 3 まで。同じ階層の項目は粒度を揃える。"),
    ),
    collection="children", min_count=2, max_count=5,
    sample={
        "root": {"label": "理念", "text": "組織が何のために存在するか"},
        "children": [
            {"label": "戦略", "text": "理念を実現する道筋", "children": []},
            {"label": "施策", "text": "戦略を具体化した打ち手", "children": []},
            {"label": "業務", "text": "施策を日々回す手順", "children": []},
        ],
    },
))

CYCLE = _register(ContentType(
    id="cycle",
    label="循環",
    description="終わりが始まりに戻る反復構造。PDCA、改善サイクル、相互に影響し合う関係。",
    fields=(
        FieldSpec(name="nodes", kind="items", label="ノード",
                  hint="3〜6 件。一巡して最初に戻る流れになるように書く。",
                  children=_labeled_item(12, 50)),
    ),
    collection="nodes", min_count=3, max_count=6,
    sample={"nodes": [
        {"label": "計画", "text": "目標と手順を決めます。", "icon": "計画"},
        {"label": "実行", "text": "決めた通りに動かします。", "icon": "実行"},
        {"label": "評価", "text": "結果を測定します。", "icon": "分析"},
        {"label": "改善", "text": "次の計画に反映します。", "icon": "改善"},
    ]},
))

MATRIX = _register(ContentType(
    id="matrix",
    label="2軸",
    description="2 つの軸で 4 象限に分ける。ポジショニング、優先度の仕分け、緊急度と重要度。",
    fields=(
        FieldSpec(name="x_axis", kind="group", label="横軸",
                  children=(
                      FieldSpec(name="label", kind="text", label="軸の名前", max_chars=12),
                      FieldSpec(name="low", kind="text", label="左端", max_chars=8),
                      FieldSpec(name="high", kind="text", label="右端", max_chars=8),
                  )),
        FieldSpec(name="y_axis", kind="group", label="縦軸",
                  children=(
                      FieldSpec(name="label", kind="text", label="軸の名前", max_chars=12),
                      FieldSpec(name="low", kind="text", label="下端", max_chars=8),
                      FieldSpec(name="high", kind="text", label="上端", max_chars=8),
                  )),
        FieldSpec(name="quadrants", kind="items", label="象限", fixed_count=4,
                  hint="左上・右上・左下・右下の順に 4 件。必ず 4 件にする。",
                  children=(
                      FieldSpec(name="label", kind="text", label="見出し", max_chars=14),
                      FieldSpec(name="text", kind="textarea", label="説明", max_chars=45),
                  )),
        # 象限そのものではなく「その中のどこに位置するか」を打つための任意項目。
        # ポジショニングマップ（matrix_plot）だけが使い、四象限は無視する。
        FieldSpec(name="plots", kind="items", label="配置する点",
                  hint=("任意。地図上に置きたいものがあるときだけ書く。"
                        "x は横軸の位置、y は縦軸の位置を 0〜100 の数値で（0 が左/下、100 が右/上）。"),
                  children=(
                      FieldSpec(name="label", kind="text", label="名前", max_chars=14),
                      FieldSpec(name="x", kind="text", label="横位置(0〜100)", max_chars=5),
                      FieldSpec(name="y", kind="text", label="縦位置(0〜100)", max_chars=5),
                  )),
    ),
    collection="quadrants", min_count=4, max_count=4,
    sample={
        "x_axis": {"label": "緊急度", "low": "低い", "high": "高い"},
        "y_axis": {"label": "重要度", "low": "低い", "high": "高い"},
        "quadrants": [
            {"label": "計画して取り組む", "text": "重要だが急がない。先に時間を確保します。"},
            {"label": "すぐ着手する", "text": "重要かつ急ぐ。最優先で処理します。"},
            {"label": "やらない", "text": "重要でも急ぎでもない。整理して外します。"},
            {"label": "任せる", "text": "急ぐが重要度は低い。仕組みで処理します。"},
        ],
        "plots": [
            {"label": "手順書の整備", "x": "25", "y": "80"},
            {"label": "障害対応", "x": "85", "y": "88"},
            {"label": "定例の議事録", "x": "70", "y": "25"},
            {"label": "過去資料の整理", "x": "20", "y": "18"},
        ],
    },
))

SETS = _register(ContentType(
    id="sets",
    label="集合",
    description="複数の集合の重なりや包含。共通点と相違点、2 つの条件を満たす領域。",
    fields=(
        FieldSpec(name="sets", kind="items", label="集合",
                  hint="2〜3 件。円として描かれる。",
                  children=(
                      FieldSpec(name="label", kind="text", label="名前", max_chars=14),
                      FieldSpec(name="text", kind="textarea", label="説明", max_chars=45),
                  )),
        FieldSpec(name="overlaps", kind="items", label="重なり",
                  hint="重なる部分に置く文言。members は重なる集合の番号（0 始まり）。",
                  children=(
                      FieldSpec(name="members", kind="text", label="対象",
                                hint="重なる集合の番号をカンマ区切りで（例: 0,1）。", max_chars=12),
                      FieldSpec(name="label", kind="text", label="見出し", max_chars=14),
                      FieldSpec(name="text", kind="textarea", label="説明", max_chars=40),
                  )),
    ),
    collection="sets", min_count=2, max_count=3,
    sample={
        "sets": [
            {"label": "できること", "text": "自分の得意や技術がある領域"},
            {"label": "求められること", "text": "市場や組織が必要としている領域"},
        ],
        "overlaps": [{"members": "0,1", "label": "価値になる仕事", "text": "技術と需要が重なる場所"}],
    },
))

TABLE = _register(ContentType(
    id="table",
    label="表",
    description="複数の項目を複数の観点で整理する。比較表、料金表、一覧。",
    fields=(
        FieldSpec(name="headers", kind="table", label="表",
                  hint="2〜4 列 / 2〜6 行。各セルは 20 文字以内。長文は入れない。"),
    ),
    collection="rows", min_count=2, max_count=6,
    sample={
        "headers": ["遺跡", "時期", "特徴"],
        "rows": [
            ["三内丸山", "前期〜中期", "大型掘立柱建物と長期定住"],
            ["大湯環状列石", "後期", "祭祀空間としての配石遺構"],
            ["亀ヶ岡", "晩期", "洗練された遮光器土偶"],
        ],
    },
))

CHART = _register(ContentType(
    id="chart",
    label="グラフ",
    description="数値そのものを見せる。推移、構成比、大小の比較、ランキング。",
    fields=(
        FieldSpec(name="chart", kind="chart", label="グラフ",
                  hint="labels と values は必ず同じ個数（3〜6）。values は数値のみ。"),
    ),
    collection="chart.labels", min_count=2, max_count=8,
    sample={"chart": {"type": "bar", "labels": ["前期", "中期", "後期", "晩期"],
                      "values": [120, 260, 180, 90], "unit": "遺跡数（概数）"}},
))

FORMULA = _register(ContentType(
    id="formula",
    label="数式",
    description="要素の組み合わせで結果が決まる関係。掛け算・足し算による定義、相乗効果。",
    fields=(
        FieldSpec(name="terms", kind="items", label="項",
                  hint="2〜4 件。演算子でつながれて並ぶ。",
                  children=(
                      FieldSpec(name="label", kind="text", label="項の名前", max_chars=12),
                      FieldSpec(name="note", kind="text", label="補足", max_chars=30),
                  )),
        FieldSpec(name="operator", kind="choice", label="演算子",
                  options=("×", "＋", "→"), hint="項の関係。相乗なら ×、積み上げなら ＋、帰結なら →。"),
        FieldSpec(name="result", kind="group", label="結果",
                  children=(
                      FieldSpec(name="label", kind="text", label="結果の名前", max_chars=14),
                      FieldSpec(name="note", kind="text", label="補足", max_chars=30),
                  )),
    ),
    collection="terms", min_count=2, max_count=4,
    sample={
        "terms": [{"label": "頻度", "note": "どれだけ繰り返すか"},
                  {"label": "深さ", "note": "どこまで掘り下げるか"}],
        "operator": "×",
        "result": {"label": "定着度", "note": "研修が行動に変わる度合い"},
    },
))

MEDIA = _register(ContentType(
    id="media",
    label="画像",
    description="写真・図版・画面キャプチャが主役。実物を見せる、事例を示す。",
    fields=(
        FieldSpec(name="images", kind="images", label="画像",
                  hint="1〜4 枚。各画像に短いキャプションを付けられる。"),
        FieldSpec(name="body", kind="textarea", label="本文",
                  hint="画像に添える説明。40〜120 文字。", max_chars=120),
        FieldSpec(name="image_description", kind="textarea", label="推奨画像の内容",
                  hint="どんな画像を置くべきかを日本語 30〜60 文字で。画像生成 AI への指示の元になる。",
                  max_chars=60),
    ),
    collection="images", min_count=1, max_count=4,
    sample={"images": [{"src": "", "caption": ""}],
            "body": "実際の現場では、こうした手順が紙の帳票で運用されています。",
            "image_description": "作業現場で帳票に記入している手元の写真。横長。"},
))

DIALOG = _register(ContentType(
    id="dialog",
    label="対話",
    description="2 人のやり取りで進める。素朴な疑問への回答、Q&A、掛け合いによる解説。",
    fields=(
        FieldSpec(name="lines", kind="items", label="発言",
                  hint="2〜8 発言。A が質問・進行、B が回答・解説。交互に並べる。",
                  children=(
                      FieldSpec(name="speaker", kind="choice", label="話者", options=("A", "B")),
                      FieldSpec(name="text", kind="textarea", label="セリフ",
                                hint="20〜60 文字。話し言葉で自然に。", max_chars=60),
                  )),
    ),
    collection="lines", min_count=2, max_count=8,
    sample={"lines": [
        {"speaker": "A", "text": "この手順、なぜ毎回ダブルチェックが要るんですか？"},
        {"speaker": "B", "text": "一人だと見落とす箇所が統計的にほぼ決まっているからです。"},
    ]},
))

COVER = _register(ContentType(
    id="cover",
    label="扉",
    description="内容そのものではなく、区切りを示す。表紙、章扉、目次、まとめ。",
    fields=(
        FieldSpec(name="subtitle", kind="text", label="サブタイトル",
                  hint="この章で何を扱うかを 30〜60 文字で。詳細は書かない。", max_chars=60),
        FieldSpec(name="chapters", kind="items", label="項目",
                  hint="目次・まとめで使う。不要なら空にする。",
                  children=(FieldSpec(name="label", kind="text", label="項目", max_chars=30),)),
    ),
    collection="chapters", min_count=0, max_count=8,
    sample={"subtitle": "考古学がどのように過去を復元しているかを見ていきます", "chapters": []},
))


# ==========================================================================
# 旧キーの吸収
# ==========================================================================

# DB に保存済みの slide_content_json は、レイアウトごとに別のキーを使っていた。
# DB 移行はせず、normalize() が読み込み時にここで吸収する。
# 値の形も違う（bullet_points は文字列の配列、cards はオブジェクトの配列）ため、
# 単純なキー名の付け替えでは足りず、_coerce_items() で形も揃える。
LEGACY_COLLECTION_KEYS: dict[str, tuple[str, ...]] = {
    "items": ("items", "bullet_points", "cards"),
    "steps": ("steps", "bullet_points", "cards", "items"),
    "nodes": ("nodes", "bullet_points", "cards", "items"),
    "terms": ("terms", "items"),
    "lines": ("lines",),
    "chapters": ("chapters", "bullet_points"),
    "quadrants": ("quadrants",),
    "sets": ("sets",),
    "overlaps": ("overlaps",),
    "images": ("images",),
}


def _as_list(value) -> list:
    """配列でない値を配列に均す。改行区切りの文字列は 1 行 1 件として扱う。"""
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.split("\n") if line.strip()]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _coerce_items(raw, children: tuple[FieldSpec, ...]) -> list[dict]:
    """項目配列を children の形に揃える。

    受け取りうる形:
      ["文字列", ...]                     … 旧 bullet_points
      [{"title": ..., "text": ...}, ...]  … 旧 cards
      [{"label": ..., "text": ...}, ...]  … 現行
    いずれも children の先頭 2 フィールド（見出し・説明）にマップする。
    """
    names = [c.name for c in children]
    # 「説明」に相当するフィールド名。text が無い型（terms は note）にも対応する。
    text_key = "text" if "text" in names else ("note" if "note" in names else names[-1])
    head_key = names[0]

    entries = _as_list(raw)

    # 素の文字列の行き先は「リスト単位で 1 回だけ」決める。
    # 1 件ごとに文字数で判定すると、同じリストの中で片方が見出し・片方が説明に
    # 入ってしまい、表示の高さも字送りも揃わなくなる。
    # 一番長い行に合わせて全件を同じフィールドへ入れる。
    longest = max((len(e) for e in entries if isinstance(e, str)), default=0)
    string_key = head_key if (longest <= 16 and head_key != text_key) else text_key

    out: list[dict] = []
    for entry in entries:
        if isinstance(entry, str):
            item = {n: "" for n in names}
            item[string_key] = entry
            out.append(item)
            continue
        if not isinstance(entry, dict):
            continue
        item = {}
        for n in names:
            value = entry.get(n)
            if value is None and n == head_key:
                # 旧 cards の "title" を見出しとして拾う
                value = entry.get("title") or entry.get("label") or entry.get("name")
            if value is None and n == text_key:
                value = entry.get("text") or entry.get("body") or entry.get("note")
            item[n] = value if value is not None else ""
        out.append(item)
    return out


def _coerce_group(raw, children: tuple[FieldSpec, ...], legacy_prefix: str = "", source: dict | None = None) -> dict:
    """入れ子オブジェクトを children の形に揃える。

    旧 contrast は left_title / left_text のようにフラットな別キーだったため、
    legacy_prefix を渡すと親 dict 側からも拾う。
    """
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for c in children:
        value = raw.get(c.name)
        if not value and legacy_prefix and source:
            value = source.get(f"{legacy_prefix}_{c.name}")
        out[c.name] = value if value is not None else ""
    return out


def _coerce_tree(raw, depth: int = 0) -> list[dict]:
    """階層を {label, text, children[]} の再帰構造に揃える。深さは 3 まで。"""
    if depth >= 3:
        return []
    out = []
    for entry in _as_list(raw):
        if isinstance(entry, str):
            out.append({"label": entry[:16], "text": "", "children": []})
            continue
        if not isinstance(entry, dict):
            continue
        out.append({
            "label": str(entry.get("label") or entry.get("title") or ""),
            "text": str(entry.get("text") or entry.get("body") or ""),
            "children": _coerce_tree(entry.get("children"), depth + 1),
        })
    return out


# ==========================================================================
# 正規化
# ==========================================================================

def normalize(type_id: str, raw: dict | None) -> dict:
    """任意の dict を型のスキーマに丸める。

    routers/scenes.py の normalize_slide_content() を置き換えるもの。
    LLM の出鱈目・旧データ・手入力の揺れを、ここ 1 箇所で吸収する。
    """
    ct = CONTENT_TYPES.get(type_id) or STATEMENT
    src = raw if isinstance(raw, dict) else {}
    out: dict = {}

    # 共通フィールド
    for f in COMMON_FIELDS:
        out[f.name] = str(src.get(f.name) or "")

    for f in ct.fields:
        if f.kind == "items":
            keys = LEGACY_COLLECTION_KEYS.get(f.name, (f.name,))
            value = next((src[k] for k in keys if src.get(k)), None)
            items = _coerce_items(value, f.children)
            if f.fixed_count:
                # 象限のように件数が固定のものは、足りなければ空で埋め、多ければ切る
                blank = {c.name: "" for c in f.children}
                items = (items + [dict(blank) for _ in range(f.fixed_count)])[:f.fixed_count]
            out[f.name] = items
        elif f.kind == "group":
            out[f.name] = _coerce_group(src.get(f.name), f.children, legacy_prefix=f.name, source=src)
        elif f.kind == "tree":
            out[f.name] = _coerce_tree(src.get(f.name))
        elif f.kind == "table":
            headers = [str(h) for h in _as_list(src.get("headers"))]
            rows = []
            for row in _as_list(src.get("rows")):
                cells = _as_list(row) if not isinstance(row, str) else [c.strip() for c in row.split(",")]
                # 列数を見出しに合わせる（過不足はここで吸収する。テンプレート側で崩れるため）
                cells = [str(c) for c in cells][:len(headers) or None]
                if headers:
                    cells += [""] * (len(headers) - len(cells))
                rows.append(cells)
            out["headers"] = headers
            out["rows"] = rows
        elif f.kind == "chart":
            cfg = src.get("chart") if isinstance(src.get("chart"), dict) else {}
            labels = [str(x) for x in _as_list(cfg.get("labels"))]
            values = []
            for v in _as_list(cfg.get("values")):
                try:
                    values.append(float(str(v).replace(",", "")))
                except (TypeError, ValueError):
                    values.append(0.0)
            # ラベルと数値の個数が違うと Chart.js が黙って片方を落とすため、短い方に揃える
            n = min(len(labels), len(values)) if labels and values else 0
            out["chart"] = {
                "type": cfg.get("type") if cfg.get("type") in ("bar", "line", "pie", "doughnut") else "bar",
                "labels": labels[:n],
                "values": values[:n],
                "unit": str(cfg.get("unit") or ""),
            }
        elif f.kind == "images":
            images = []
            for entry in _as_list(src.get("images")):
                if isinstance(entry, str):
                    images.append({"src": entry, "caption": ""})
                elif isinstance(entry, dict):
                    images.append({"src": str(entry.get("src") or ""),
                                   "caption": str(entry.get("caption") or "")})
            if not images and src.get("image_src"):
                # 旧 media 系は image_src を単独キーで持っていた
                images = [{"src": str(src["image_src"]), "caption": ""}]
            out["images"] = images
            # 画像の左右位置は旧データを引き継ぐ（レイアウト側が参照する）
            pos = src.get("image_position")
            out["image_position"] = pos if pos in ("left", "right") else "right"
        elif f.kind == "choice":
            value = src.get(f.name)
            out[f.name] = value if value in f.options else (f.options[0] if f.options else "")
        else:
            out[f.name] = str(src.get(f.name) or "")

    return out


# ==========================================================================
# 件数
# ==========================================================================

def count_of(type_id: str, content: dict) -> int:
    """レイアウトの自動差し替え判定に使う「件数」を返す。

    collection が "chart.labels" のようなドット記法のときは辿る。
    件数の概念を持たない型（statement / contrast）は 0 を返す。
    """
    ct = CONTENT_TYPES.get(type_id)
    if not ct or not ct.collection:
        return 0
    node = content
    for part in ct.collection.split("."):
        if not isinstance(node, dict):
            return 0
        node = node.get(part)
    return len(node) if isinstance(node, (list, tuple)) else 0


# ==========================================================================
# 型の変換
# ==========================================================================

# 「見出し＋説明」という同じ形を共有する型。互いに無変換で行き来できる。
_LABELED_FAMILY = {
    "list": "items",
    "sequence": "steps",
    "cycle": "nodes",
    "hierarchy": "children",
    "formula": "terms",
    "cover": "chapters",
}


def convert(from_type: str, to_type: str, content: dict) -> tuple[dict, int]:
    """型をまたいで内容を移し替える。(変換後の内容, 失われた件数) を返す。

    _LABELED_FAMILY 同士は無変換で通る。それ以外は拾える範囲だけ移し、
    落ちた件数を呼び出し側に返す（UI が確認ダイアログを出すのに使う）。
    """
    if from_type == to_type:
        return normalize(to_type, content), 0

    target = CONTENT_TYPES.get(to_type)
    if not target:
        return normalize(to_type, content), 0

    carried = dict(content)

    src_key = _LABELED_FAMILY.get(from_type)
    dst_key = _LABELED_FAMILY.get(to_type)
    if src_key and dst_key:
        # 同じ形の家族同士。キー名を付け替えるだけで内容は保たれる。
        carried[dst_key] = content.get(src_key) or []

    result = normalize(to_type, carried)

    # 落ちた件数を数える。件数の概念が無い型へ移したときは、
    # 元の件数がそのまま「表示されなくなった件数」になる。
    before = count_of(from_type, normalize(from_type, content))
    after = count_of(to_type, result)
    lost = max(0, before - after) if before else 0
    return result, lost


def list_types() -> list[dict]:
    """API / LLM プロンプト向けに、型の一覧を素の dict で返す。"""
    return [
        {"id": ct.id, "label": ct.label, "description": ct.description,
         "min_count": ct.min_count, "max_count": ct.max_count}
        for ct in CONTENT_TYPES.values()
    ]


# ==========================================================================
# あらすじからの穴埋め
# ==========================================================================

# チャットのアウトラインだけ決まっていて、シーンの内容がまだ生成されていない
# 段階でも、真っ白なスライドにはしない。あらすじ（outline_summary）を
# 「その型で一番自然な場所」に流し込む。
#   - 文章を置ける型 … その本文欄へそのまま
#   - 項目を並べる型 … 1 件だけの項目として
_SUMMARY_TARGET: dict[str, str] = {
    "statement": "body",
    "cover": "subtitle",
    "media": "body",
    "contrast": "left.text",
}
_SUMMARY_COLLECTION: dict[str, str] = {
    "list": "items", "sequence": "steps", "cycle": "nodes",
    "hierarchy": "children", "formula": "terms", "dialog": "lines",
}


def is_blank(type_id: str, content: dict) -> bool:
    """固有の内容がまだ何も入っていないか（タイトルとアイブロウは数えない）。"""
    ct = CONTENT_TYPES.get(type_id)
    if not ct:
        return True

    def _has_text(value) -> bool:
        """入れ子の dict / list の中に、空でない文字列が 1 つでもあるか。"""
        if isinstance(value, dict):
            return any(_has_text(v) for v in value.values())
        if isinstance(value, (list, tuple)):
            return any(_has_text(v) for v in value)
        return bool(str(value or "").strip())

    # count_of() は使えない。matrix のように件数が固定の型は、中身が空でも
    # 常に 4 件返るため「空ではない」と誤判定してしまう。
    for f in ct.fields:
        if f.kind in ("items", "tree") and _has_text(content.get(f.name)):
            return False
    for f in ct.fields:
        value = content.get(f.name)
        if f.kind == "group":
            if any(str(v).strip() for v in (value or {}).values()):
                return False
        elif f.kind in ("table", "chart", "images"):
            if content.get("rows") or (content.get("chart") or {}).get("values") or content.get("images"):
                return False
        elif f.kind not in ("items", "tree") and str(value or "").strip():
            return False
    return True


def fill_from_summary(type_id: str, content: dict, summary: str) -> dict:
    """あらすじを型に合う形で流し込む。content は破壊的に更新して返す。"""
    text = (summary or "").strip()
    if not text or not is_blank(type_id, content):
        return content

    key = _SUMMARY_TARGET.get(type_id)
    if key:
        if "." in key:
            outer, inner = key.split(".", 1)
            content.setdefault(outer, {})[inner] = text
        else:
            content[key] = text
        return content

    field = _SUMMARY_COLLECTION.get(type_id)
    if field:
        if type_id == "dialog":
            content[field] = [{"speaker": "A", "text": text}]
        elif type_id == "formula":
            content[field] = [{"label": text[:12], "note": ""}]
        else:
            content[field] = [{"label": "", "text": text, "icon": ""}]
        return content

    # 表・グラフ・2軸・集合は、あらすじから機械的に作れる形が無い。
    # 無理に数字や象限をでっち上げると誤情報になるため、空のままにする。
    return content
