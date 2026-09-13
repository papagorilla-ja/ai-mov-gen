"""レイアウト（見せ方）の登録・検索・自動差し替え。

1 レイアウト = 1 ディレクトリ。

    layouts/sequence_horizontal/
        spec.py        ← SPEC = LayoutSpec(...) を定義する
        template.html  ← Jinja2 テンプレート
        style.css      ← このレイアウト専用の CSS

ディレクトリを置くだけで
    - シーン編集の選択肢に出る
    - 編集フォームが自動生成される（型のスキーマから）
    - AI が選べるようになる
    - 動画に描画される
の全部が有効になる。他のファイルを触る必要は無い。

自動差し替え（設計方針の第 1 層）:
    レイアウトは「3〜4 件がちょうど良い」といった収容力を宣言する。
    LLM が 7 件生成したなら、同じ型の中で 7 件を収められるレイアウトへ
    resolve() が自動的に差し替える。テンプレートが想定外の件数で
    崩れることを、描画前に構造的に防ぐ。
"""

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from layouts._types import CONTENT_TYPES, count_of

LAYOUT_ROOT = Path(__file__).parent


# ==========================================================================
# 収容力
# ==========================================================================

@dataclass(frozen=True)
class Capacity:
    """このレイアウトが何件まで綺麗に収まるか。

    ideal は「最も収まりが良い件数の範囲」。min/max は「破綻しない範囲」。
    件数の概念を持たない型（statement / contrast）は any=True にする。
    """
    min: int = 0
    max: int = 99
    ideal: tuple[int, int] = (0, 99)
    any: bool = False

    def fits(self, n: int) -> bool:
        return True if self.any else self.min <= n <= self.max

    def distance(self, n: int) -> int:
        """ideal からどれだけ離れているか。小さいほど良い（差し替え先の選定に使う）。"""
        if self.any:
            return 0
        lo, hi = self.ideal
        if n < lo:
            return lo - n
        if n > hi:
            return n - hi
        return 0


ANY = Capacity(any=True)


# ==========================================================================
# レイアウトの定義
# ==========================================================================

@dataclass(frozen=True)
class LayoutSpec:
    id: str
    label: str                                  # 選択 UI に出す日本語（「横型フロー」）
    type_id: str                                # 属する型（"sequence"）
    when_to_use: str                            # AI に見せる「どんなときに使うか」1〜2 文
    capacity: Capacity = ANY
    aspect: tuple[str, ...] = ("16:9", "4:3")   # 成立するアスペクト比
    # 背景モチーフをどれだけ覆うか。0=背景を活かす / 1=完全に隠す。
    # style.css の .slide-layout-* { --veil } を置き換える。
    veil: float = 0.85
    # 背景の装飾オーブを何個出すか（0〜2）。composition.py が描く。
    orbs: int = 1
    phase: str = "P0"                           # カタログ上のフェーズ表示
    # 既定のサンプルを上書きしたいときだけ指定する（通常は型の sample を使う）
    sample: dict | None = None
    # そのレイアウトでしか起きない挙動を、編集フォームの該当項目に添える注記。
    #     {"lead": "数字を入れると 0 から増えていく演出が付きます"}
    # 型（_types.py）の hint は同じ型のレイアウト全部に出てしまうため、
    # 「このレイアウトのときだけ言いたいこと」はこちらに書く。
    # 例: 大きな数字はカウントアップするが、同じ statement 型の
    #     見出し・引用では起きない。
    field_notes: dict[str, str] | None = None
    # テンプレートに渡す追加の変数を組み立てるフック。
    # グラフの Chart.js スクリプトのように「テンプレートでは書けないが、
    # そのレイアウトにしか関係しない」処理をレイアウト側に閉じ込めるためのもの。
    #     def _prepare(content: dict, ctx: dict) -> dict: ...
    #     SPEC = LayoutSpec(..., prepare=_prepare)
    prepare: Callable[[dict, dict], dict] | None = None

    @property
    def dir(self) -> Path:
        return LAYOUT_ROOT / self.id

    @property
    def template_path(self) -> Path:
        return self.dir / "template.html"

    @property
    def css_path(self) -> Path:
        return self.dir / "style.css"

    def sample_content(self) -> dict:
        ct = CONTENT_TYPES.get(self.type_id)
        base = dict(ct.sample) if ct else {}
        if self.sample:
            base.update(self.sample)
        base.setdefault("title", self.label)
        return base


# ==========================================================================
# 探索
# ==========================================================================

_REGISTRY: dict[str, LayoutSpec] | None = None

# 旧 layout_hint 値からの後方互換（routers/scenario.py から移設）
LEGACY_LAYOUT_ALIASES = {
    "text_image": "text_left_image_right",
    "list": "bullet_list",
}

# どの型にも解決できなかったときの最終避難先。
# 動画生成を止めないことを最優先し、必ず存在するレイアウトを指す。
FALLBACK_LAYOUT = "text_only"


def _discover() -> dict[str, LayoutSpec]:
    """layouts/*/spec.py を読み込んで SPEC を集める。

    import は遅延させている。モジュール読み込み時に走らせると、
    spec.py 側の `from layouts._registry import LayoutSpec` と循環するため。
    """
    found: dict[str, LayoutSpec] = {}
    # pkgutil.iter_modules は __init__.py を持たないディレクトリを列挙しないため、
    # ファイルシステムを直接見る。レイアウトを増やすたびに __init__.py を
    # 置き忘れて「静かに 1 つ足りない」事故を避けたい。
    # 並び順は sorted で固定する（カタログの並びと、差し替え先の同点判定に効く）。
    for entry in sorted(LAYOUT_ROOT.iterdir(), key=lambda p: p.name):
        name = entry.name
        if not entry.is_dir() or name.startswith("_") or not (entry / "spec.py").exists():
            continue
        try:
            module = importlib.import_module(f"layouts.{name}.spec")
        except Exception as e:  # noqa: BLE001 — 1 つ壊れても他を生かす
            print(f"[layouts] {name}/spec.py の読み込みに失敗: {e}")
            continue
        spec = getattr(module, "SPEC", None)
        if not isinstance(spec, LayoutSpec):
            print(f"[layouts] {name}/spec.py に SPEC が定義されていません")
            continue
        if spec.id != name:
            print(f"[layouts] id とディレクトリ名が不一致: {spec.id} != {name}")
            continue
        if spec.type_id not in CONTENT_TYPES:
            print(f"[layouts] {spec.id} の type_id が未知: {spec.type_id}")
            continue
        found[spec.id] = spec
    return found


def registry() -> dict[str, LayoutSpec]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _discover()
    return _REGISTRY


def reload_registry() -> dict[str, LayoutSpec]:
    """開発時にレイアウトを追加した後、再起動せずに読み直すためのもの。"""
    global _REGISTRY
    _REGISTRY = None
    return registry()


def get(layout_id: str | None) -> LayoutSpec | None:
    return registry().get(normalize_layout_id(layout_id))


def normalize_layout_id(raw: str | None) -> str:
    """DB / LLM から来た値を実在するレイアウト ID に丸める。"""
    value = (raw or "").strip()
    value = LEGACY_LAYOUT_ALIASES.get(value, value)
    return value if value in registry() else FALLBACK_LAYOUT


def layouts_for_type(type_id: str) -> list[LayoutSpec]:
    return [s for s in registry().values() if s.type_id == type_id]


def type_of(layout_id: str | None) -> str:
    spec = get(layout_id)
    return spec.type_id if spec else "statement"


# ==========================================================================
# レイアウトの幅（動画単位で使う型を絞る）
# ==========================================================================

# 40 種を用意しても、1 本の動画で毎シーン違う図解が出ると
# 「新しい図の読み方」を毎回学ばされ、認知負荷が上がる。
# 動画ごとにここで型を絞る。
BREADTH_LEVELS = [
    {
        "value": "minimal", "label": "控えめ",
        "description": "見慣れた型だけを使う。社内研修・安全教育向け",
        "types": ("statement", "list", "sequence", "contrast", "cover"),
    },
    {
        "value": "standard", "label": "標準",
        "description": "図表と画像まで使う。既定値",
        "types": ("statement", "list", "sequence", "contrast", "cover",
                  "table", "chart", "media", "dialog"),
    },
    {
        "value": "rich", "label": "豊富",
        "description": "階層・循環・2軸・集合・数式まで使う。提案資料向け",
        "types": tuple(CONTENT_TYPES.keys()),
    },
]

DEFAULT_BREADTH = "standard"

# 許可されていない型が来たときの寄せ先。情報構造が最も近い型を選んでいる。
TYPE_FALLBACKS = {
    "hierarchy": "list",
    "cycle": "sequence",
    "matrix": "list",
    "sets": "contrast",
    "formula": "list",
    "dialog": "list",
    "media": "statement",
    "chart": "table",
    "table": "list",
}


def normalize_breadth(value: str | None) -> str | None:
    """UI / LLM から来た値を許可された「レイアウトの幅」に丸める。

    None はそのまま返す（＝未設定。DEFAULT_BREADTH が使われる）。
    ここで既定値を書き込んでしまうと、既定を変えたときに
    「未設定のまま使い続けていた動画」が追従しなくなる。
    """
    if value is None:
        return None
    valid = {level["value"] for level in BREADTH_LEVELS}
    return value if value in valid else DEFAULT_BREADTH


def allowed_types(breadth: str | None) -> tuple[str, ...]:
    for level in BREADTH_LEVELS:
        if level["value"] == (breadth or DEFAULT_BREADTH):
            return level["types"]
    return next(x["types"] for x in BREADTH_LEVELS if x["value"] == DEFAULT_BREADTH)


def coerce_type(type_id: str, breadth: str | None) -> str:
    """型を「レイアウトの幅」設定の範囲内に寄せる。"""
    allowed = allowed_types(breadth)
    seen = set()
    current = type_id if type_id in CONTENT_TYPES else "statement"
    while current not in allowed and current not in seen:
        seen.add(current)
        current = TYPE_FALLBACKS.get(current, "statement")
    return current if current in allowed else "statement"


# ==========================================================================
# 自動差し替え（設計方針の第 1 層）
# ==========================================================================

@dataclass
class Resolution:
    """resolve() の結果。reason は「なぜ差し替えたか」の日本語（ログと UI に出す）。"""
    layout_id: str
    changed: bool = False
    reason: str = ""


def resolve(
    type_id: str,
    content: dict,
    proposed: str | None = None,
    *,
    aspect: str = "16:9",
    avoid: tuple[str, ...] = (),
) -> Resolution:
    """内容の実データを見て、実際に使うレイアウトを決める。

    引数:
        type_id   … 型（AI が段階 1 で決めたもの）
        content   … 正規化済みの内容。件数はここから数える
        proposed  … AI が段階 2 で選んだ見せ方。妥当ならそのまま採用する
        aspect    … "16:9" / "4:3"
        avoid     … 直前のシーンで使ったレイアウト（連続を避ける）
    """
    candidates = [s for s in layouts_for_type(type_id) if aspect in s.aspect]
    if not candidates:
        return Resolution(FALLBACK_LAYOUT, changed=True,
                          reason=f"型 {type_id} に {aspect} 対応のレイアウトが無いため既定へ")

    n = count_of(type_id, content)
    fitting = [s for s in candidates if s.capacity.fits(n)]

    proposed_id = (proposed or "").strip()
    proposed_spec = registry().get(proposed_id)

    # 提案どおりで問題なければ、それを尊重する
    if proposed_spec and proposed_spec in fitting and proposed_spec.id not in avoid:
        return Resolution(proposed_spec.id)

    def rank(s: LayoutSpec) -> tuple:
        # ideal に近い / 連続を避ける / 定義順（カタログの並び）を優先する
        return (s.capacity.distance(n), 1 if s.id in avoid else 0, s.id)

    pool = fitting or candidates
    # 連続回避は「他に選べるものがあるとき」だけ効かせる。
    # 1 つしかないのに避けると、型に合わないレイアウトへ落ちてしまう。
    non_avoided = [s for s in pool if s.id not in avoid]
    best = sorted(non_avoided or pool, key=rank)[0]

    if proposed_spec and proposed_spec.id == best.id:
        return Resolution(best.id)

    if proposed_spec and proposed_spec.type_id != type_id:
        reason = f"「{proposed_spec.label}」は型 {type_id} ではないため「{best.label}」へ"
    elif proposed_spec and not proposed_spec.capacity.fits(n):
        reason = (f"「{proposed_spec.label}」は {proposed_spec.capacity.min}〜"
                  f"{proposed_spec.capacity.max} 件までのため、{n} 件を収められる"
                  f"「{best.label}」へ")
    elif proposed_spec and aspect not in proposed_spec.aspect:
        reason = f"「{proposed_spec.label}」は {aspect} に非対応のため「{best.label}」へ"
    elif proposed_spec and proposed_spec.id in avoid:
        reason = f"直前のシーンと同じ「{proposed_spec.label}」が続くため「{best.label}」へ"
    elif proposed_id:
        reason = f"未知のレイアウト「{proposed_id}」のため「{best.label}」へ"
    else:
        reason = f"{n} 件に最も適した「{best.label}」を選択"

    return Resolution(best.id, changed=True, reason=reason)


# ==========================================================================
# CSS の収集
# ==========================================================================

def collect_css(layout_ids) -> str:
    """動画で実際に使われたレイアウトの CSS だけを連結する。

    40 種ぶんを常に連結すると、生成物の style.css が読みにくくなり
    デバッグの邪魔になる。使ったものだけを、使った順に出す。
    """
    parts: list[str] = []
    for lid in dict.fromkeys(layout_ids):          # 重複を除いて順序は保つ
        spec = registry().get(lid)
        if not spec or not spec.css_path.exists():
            continue
        parts.append(f"/* ---- layout: {spec.id}（{spec.label}） ---- */")
        parts.append(spec.css_path.read_text(encoding="utf-8").strip())
    return "\n".join(parts)


# ==========================================================================
# カタログ（API / LLM プロンプト向け）
# ==========================================================================

def catalog() -> list[dict]:
    """型ごとにまとめたレイアウト一覧を返す。"""
    out = []
    for type_id, ct in CONTENT_TYPES.items():
        specs = sorted(layouts_for_type(type_id), key=lambda s: (s.phase, s.id))
        out.append({
            "type": type_id,
            "label": ct.label,
            "description": ct.description,
            "min_count": ct.min_count,
            "max_count": ct.max_count,
            "layouts": [
                {
                    "id": s.id, "label": s.label, "when_to_use": s.when_to_use,
                    "min": s.capacity.min, "max": s.capacity.max,
                    "ideal": list(s.capacity.ideal), "any_count": s.capacity.any,
                    "aspect": list(s.aspect), "phase": s.phase,
                    "field_notes": s.field_notes or {},
                }
                for s in specs
            ],
        })
    return out
