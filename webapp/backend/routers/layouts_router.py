"""レイアウトカタログの API。

フロントエンドがレイアウトの定義を二重に持たないための入口。
選択肢・編集フォームの項目・件数の制約・サムネイルまで、すべてここから配る。
（services/design_tokens.py の STYLE_OPTIONS と同じ考え方）
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from models.video_style import VideoStyle
from layouts import _registry as layouts
from layouts import _types
from services.composition import render_layout_sample_document

router = APIRouter(tags=["layouts"])


def _field_dict(f) -> dict:
    """FieldSpec を素の dict にする（フロントの汎用フォームがこれを読む）。"""
    return {
        "name": f.name,
        "kind": f.kind,
        "label": f.label,
        "hint": f.hint,
        "max_chars": f.max_chars,
        "options": list(f.options),
        "fixed_count": f.fixed_count,
        "children": [_field_dict(c) for c in f.children],
    }


@router.get("/layouts")
async def list_layouts():
    """型ごとにまとめたレイアウト一覧と、型ごとの編集フォーム定義を返す。"""
    return {
        "types": [
            {
                "id": ct.id,
                "label": ct.label,
                "description": ct.description,
                "min_count": ct.min_count,
                "max_count": ct.max_count,
                "collection": ct.collection,
                "fields": [_field_dict(f) for f in _types.COMMON_FIELDS]
                          + [_field_dict(f) for f in ct.fields],
            }
            for ct in _types.CONTENT_TYPES.values()
        ],
        "catalog": layouts.catalog(),
        "breadth_levels": [
            {k: (list(v) if isinstance(v, tuple) else v) for k, v in level.items()}
            for level in layouts.BREADTH_LEVELS
        ],
        "default_breadth": layouts.DEFAULT_BREADTH,
        "dedicated_kinds": sorted(_types.DEDICATED_KINDS),
    }


@router.get("/layouts/{layout_id}/sample")
async def layout_sample(layout_id: str, video_id: str | None = None,
                        db: AsyncSession = Depends(get_db)):
    """レイアウト選択ギャラリーのサムネイル用 HTML。

    サムネイル画像は持たない。実際のレイアウトビルダーにサンプル内容を流して
    実物を描き、画面側で縮小表示する。こうすれば実装を直したときに
    サムネイルだけ古いまま、というずれが起きない。
    video_id を渡すと、その動画のテーマ（配色・書体・キャンバス比）で描く。
    """
    spec = layouts.get(layout_id)
    if not spec or spec.id != layouts.normalize_layout_id(layout_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "レイアウトが見つかりません")

    style = None
    if video_id:
        stmt = select(VideoStyle).where(VideoStyle.video_id == video_id)
        style = (await db.execute(stmt)).scalars().first()

    return {
        "id": spec.id,
        "label": spec.label,
        "type": spec.type_id,
        # iframe の srcdoc にそのまま入れられる完結した HTML 文書。
        # 断片で返すと、スライドの CSS が編集画面側に漏れて見た目を壊す。
        "document": render_layout_sample_document(spec.id, style),
    }


@router.post("/layouts/convert")
async def convert_content(payload: dict):
    """レイアウトを変えたときの内容の移し替え。

    同じ型のあいだは無変換で通る。型をまたぐときは拾える範囲だけ移し、
    落ちた件数を返す（画面側はこれを見て確認ダイアログを出す）。
    """
    from_layout = layouts.normalize_layout_id(payload.get("from_layout"))
    to_layout = layouts.normalize_layout_id(payload.get("to_layout"))
    content = payload.get("content") if isinstance(payload.get("content"), dict) else {}

    converted, lost = _types.convert(
        layouts.type_of(from_layout), layouts.type_of(to_layout), content
    )
    return {
        "layout": to_layout,
        "type": layouts.type_of(to_layout),
        "content": converted,
        "lost_count": lost,
    }
