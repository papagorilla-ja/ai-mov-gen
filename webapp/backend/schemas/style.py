from datetime import datetime
from pydantic import BaseModel, ConfigDict

from services.design_tokens import DEFAULTS


class StyleTemplateBase(BaseModel):
    name: str
    is_system: bool = False
    preview_image_path: str | None = None
    base_css: str
    color_primary: str = DEFAULTS["color_primary"]
    color_secondary: str = DEFAULTS["color_secondary"]
    color_accent: str = DEFAULTS["color_accent"]
    color_bg: str = DEFAULTS["color_bg"]
    color_text_primary: str = DEFAULTS["color_text_primary"]
    font_heading: str = DEFAULTS["font_heading"]
    font_body: str = DEFAULTS["font_body"]
    # 配色だけでなくデザイン要素一式を運ぶ
    background_motif: str = DEFAULTS["background_motif"]
    decor_style: str = DEFAULTS["decor_style"]
    type_scale: str = DEFAULTS["type_scale"]
    transition: str = DEFAULTS["transition"]


class StyleTemplateCreate(StyleTemplateBase):
    pass


class StyleTemplateRead(StyleTemplateBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VideoStyleRead(BaseModel):
    id: str
    video_id: str
    template_id: str | None = None
    color_primary: str | None = None
    color_secondary: str | None = None
    color_accent: str | None = None
    color_bg: str | None = None
    color_text_primary: str | None = None
    font_heading: str | None = None
    font_body: str | None = None
    background_motif: str | None = None
    decor_style: str | None = None
    type_scale: str | None = None
    transition: str | None = None
    style_prompt: str | None = None
    custom_css: str | None = None
    default_speaker_id: str | None = None
    default_speaker_b_id: str | None = None
    bgm_path: str | None = None
    bgm_volume: float = 0.3
    canvas_width: int = 1920
    canvas_height: int = 1080

    # ---- 以下は保存されない算出値 ----
    # プレビュー用。派生色（文字副色・境界線・影など）の計算はサーバー側にしかない。
    # 画面側で同じ計算を書くと必ず実際のレンダリング結果とずれるため、
    # 算出済みの CSS をそのまま返して iframe に流し込ませる。
    theme_css: str | None = None
    stage_classes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VideoStyleUpdate(BaseModel):
    template_id: str | None = None
    color_primary: str | None = None
    color_secondary: str | None = None
    color_accent: str | None = None
    color_bg: str | None = None
    color_text_primary: str | None = None
    font_heading: str | None = None
    font_body: str | None = None
    background_motif: str | None = None
    decor_style: str | None = None
    type_scale: str | None = None
    transition: str | None = None
    style_prompt: str | None = None
    custom_css: str | None = None
    default_speaker_id: str | None = None
    default_speaker_b_id: str | None = None
    bgm_volume: float | None = None
    canvas_width: int | None = None
    canvas_height: int | None = None


class ApplyPromptRequest(BaseModel):
    prompt: str
