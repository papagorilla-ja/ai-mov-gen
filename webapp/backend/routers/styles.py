from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from models.style_template import StyleTemplate
from models.video_style import VideoStyle
from schemas.style import (
    ApplyPromptRequest,
    StyleTemplateCreate,
    StyleTemplateRead,
    VideoStyleRead,
    VideoStyleUpdate,
)
from services.design_tokens import (
    STYLE_OPTIONS,
    build_theme_css,
    normalize_decor,
    normalize_font,
    normalize_motif,
    normalize_transition,
    normalize_type_scale,
    stage_classes,
)
from services.llm_service import apply_style_prompt as apply_style_prompt_llm

router = APIRouter(tags=["styles"])

# 単純に代入してよいフィールド（値の妥当性を問わないもの）
_PLAIN_FIELDS = (
    "template_id",
    "color_primary",
    "color_secondary",
    "color_accent",
    "color_bg",
    "color_text_primary",
    "style_prompt",
    "custom_css",
    "default_speaker_id",   # null 送信でクリア可
    "default_speaker_b_id",  # null 送信でクリア可
    "bgm_volume",
    "canvas_width",
    "canvas_height",
)

# 保存前に許可された値へ丸めるフィールド。
# 廃止したフォント名や、UI/LLM が送ってきた未知の値をここで吸収する。
_NORMALIZED_FIELDS = {
    "font_heading": normalize_font,
    "font_body": normalize_font,
    "background_motif": normalize_motif,
    "decor_style": normalize_decor,
    "type_scale": normalize_type_scale,
    "transition": normalize_transition,
}


def _apply_updates(style: VideoStyle, payload: VideoStyleUpdate) -> None:
    """送信されたフィールドだけを VideoStyle に反映する。

    model_fields_set を見ることで「未送信」と「null を明示送信（クリア）」を
    区別している。null を送って既定話者をクリアする操作があるため区別は必須。
    """
    sent = payload.model_fields_set
    for field in _PLAIN_FIELDS:
        if field in sent:
            setattr(style, field, getattr(payload, field))
    for field, normalize in _NORMALIZED_FIELDS.items():
        if field in sent:
            value = getattr(payload, field)
            # 明示的な null はクリア（既定値にフォールバックさせる）とみなす
            setattr(style, field, normalize(value) if value is not None else None)


async def _get_or_create_style(video_id: str, db: AsyncSession) -> VideoStyle:
    stmt = select(VideoStyle).where(VideoStyle.video_id == video_id)
    style = (await db.execute(stmt)).scalars().first()
    if not style:
        style = VideoStyle(video_id=video_id)
        db.add(style)
        await db.flush()
    return style


def _to_response(style: VideoStyle) -> VideoStyleRead:
    """保存済みの値に、プレビュー用の算出 CSS を添えて返す。

    画面側は返ってきた theme_css を iframe に流し込むだけでよく、
    派生色の計算を再実装せずに済む（再実装すると必ず本番のレンダリングとずれる）。
    """
    resp = VideoStyleRead.model_validate(style, from_attributes=True)
    resp.theme_css = build_theme_css(
        style, canvas_width=style.canvas_width, canvas_height=style.canvas_height
    )
    resp.stage_classes = stage_classes(style)
    return resp


@router.get("/style-options")
async def get_style_options():
    """背景モチーフ・装飾スタイル・組版・切替・フォントの選択肢を返す。

    フロントエンドはこの結果だけを見て UI を組み立てる。
    選択肢を画面側にも書くと必ず定義が二重化して片方が腐るため、
    design_tokens.py を唯一の正としている。
    """
    return STYLE_OPTIONS


@router.get("/style-templates", response_model=list[StyleTemplateRead])
async def list_style_templates(db: AsyncSession = Depends(get_db)):
    stmt = select(StyleTemplate)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/style-templates", response_model=StyleTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_style_template(payload: StyleTemplateCreate, db: AsyncSession = Depends(get_db)):
    tpl = StyleTemplate(
        name=payload.name,
        is_system=payload.is_system,
        preview_image_path=payload.preview_image_path,
        base_css=payload.base_css,
        color_primary=payload.color_primary,
        color_secondary=payload.color_secondary,
        color_accent=payload.color_accent,
        color_bg=payload.color_bg,
        color_text_primary=payload.color_text_primary,
        font_heading=normalize_font(payload.font_heading),
        font_body=normalize_font(payload.font_body),
        background_motif=normalize_motif(payload.background_motif),
        decor_style=normalize_decor(payload.decor_style),
        type_scale=normalize_type_scale(payload.type_scale),
        transition=normalize_transition(payload.transition),
    )
    db.add(tpl)
    await db.flush()
    return tpl


@router.delete("/style-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_style_template(template_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(StyleTemplate).where(StyleTemplate.id == template_id)
    tpl = (await db.execute(stmt)).scalars().first()
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    await db.delete(tpl)
    await db.flush()


@router.get("/videos/{video_id}/style", response_model=VideoStyleRead)
async def get_video_style(video_id: str, db: AsyncSession = Depends(get_db)):
    return _to_response(await _get_or_create_style(video_id, db))


@router.patch("/videos/{video_id}/style", response_model=VideoStyleRead)
async def update_video_style(video_id: str, payload: VideoStyleUpdate, db: AsyncSession = Depends(get_db)):
    style = await _get_or_create_style(video_id, db)
    _apply_updates(style, payload)
    await db.flush()
    return _to_response(style)


@router.post("/videos/{video_id}/style/apply-template/{template_id}", response_model=VideoStyleRead)
async def apply_style_template(video_id: str, template_id: str, db: AsyncSession = Depends(get_db)):
    """テンプレートの内容を動画のスタイルへ丸ごと写す。

    配色・書体だけでなく背景モチーフや装飾スタイルまで運ぶ必要があるため、
    フロントエンドで項目を1つずつ写す方式はやめてサーバー側に集約した。
    項目が増えたときにコピー漏れが起きるのを防ぐ狙いもある。
    """
    tpl = (await db.execute(select(StyleTemplate).where(StyleTemplate.id == template_id))).scalars().first()
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")

    style = await _get_or_create_style(video_id, db)
    style.template_id = tpl.id
    for field in (
        "color_primary", "color_secondary", "color_accent", "color_bg", "color_text_primary",
        "font_heading", "font_body", "background_motif", "decor_style", "type_scale", "transition",
    ):
        setattr(style, field, getattr(tpl, field))
    await db.flush()
    return _to_response(style)


@router.post("/videos/{video_id}/style/apply-prompt", response_model=VideoStyleRead)
async def apply_style_prompt(video_id: str, payload: ApplyPromptRequest, db: AsyncSession = Depends(get_db)):
    style = await _get_or_create_style(video_id, db)

    current_style_dict = {
        "color_primary": style.color_primary,
        "color_secondary": style.color_secondary,
        "color_accent": style.color_accent,
        "color_bg": style.color_bg,
        "color_text_primary": style.color_text_primary,
        "font_heading": style.font_heading,
        "font_body": style.font_body,
        "background_motif": style.background_motif,
        "decor_style": style.decor_style,
        "type_scale": style.type_scale,
        "transition": style.transition,
    }

    parsed = await apply_style_prompt_llm(current_style_dict, payload.prompt)

    # LLM の出力は信用せず、色はそのまま・選択肢は必ず許可された値へ丸める
    for field in ("color_primary", "color_secondary", "color_accent", "color_bg", "color_text_primary"):
        if field in parsed:
            setattr(style, field, parsed[field])
    for field, normalize in _NORMALIZED_FIELDS.items():
        if field in parsed:
            setattr(style, field, normalize(parsed[field]))

    style.style_prompt = payload.prompt
    await db.flush()
    return _to_response(style)
