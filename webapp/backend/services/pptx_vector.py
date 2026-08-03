"""LibreOffice (soffice) + pdftocairo を使って PPTX の各スライドを SVG 化するラッパ。

図解（チャート/SmartArt/オートシェイプ群/EMF・WMF）をベクタのまま切り出すために使う。
グリフをパス化した SVG が得られるため、レンダラー側にフォントが無くても文字が崩れない。

FIX-15 (docs/antigravity_fix15_pptx_per_slide_import.md) 参照。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from pathlib import Path

CONVERT_TIMEOUT_SEC = 180
EMU_PER_PT = 12700
PAD_PT = 8.0


def is_available() -> bool:
    return shutil.which("soffice") is not None and shutil.which("pdftocairo") is not None


def pptx_to_page_svgs(pptx_path: Path, workdir: Path, page_count: int) -> dict[int, str]:
    """PPTX をページごとの SVG 文字列に変換して返す（キー: 1始まりのページ番号）。

    """
    workdir.mkdir(parents=True, exist_ok=True)
    profile_dir = workdir / f"lo_profile_{uuid.uuid4().hex}"

    convert_cmd = [
        "soffice", "--headless", "--norestore",
        f"-env:UserInstallation=file://{profile_dir}",
        "--convert-to", "pdf", "--outdir", str(workdir), str(pptx_path),
    ]
    subprocess.run(convert_cmd, timeout=CONVERT_TIMEOUT_SEC, capture_output=True, check=True)

    pdf_path = workdir / (pptx_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"PDF変換に失敗しました: {pdf_path} が生成されませんでした")

    result: dict[int, str] = {}
    for page in range(1, page_count + 1):
        svg_path = workdir / f"page_{page}.svg"
        cmd = ["pdftocairo", "-svg", "-f", str(page), "-l", str(page), str(pdf_path), str(svg_path)]
        proc = subprocess.run(cmd, timeout=60, capture_output=True)
        if proc.returncode != 0 or not svg_path.exists():
            continue
        result[page] = svg_path.read_text(encoding="utf-8")

    return result


def crop_svg(page_svg: str, bbox_emu: tuple[int, int, int, int], slide_size_emu: tuple[int, int], pad_pt: float = PAD_PT) -> str:
    """ページ全体の SVG から、指定バウンディングボックス（EMU）の領域だけを見せる SVG に切り出す。

    子要素は一切変更せず、ルート <svg> の viewBox/width/height だけを書き換える。
    """
    left, top, width, height = bbox_emu
    slide_w_emu, slide_h_emu = slide_size_emu

    x_pt = left / EMU_PER_PT - pad_pt
    y_pt = top / EMU_PER_PT - pad_pt
    w_pt = width / EMU_PER_PT + pad_pt * 2
    h_pt = height / EMU_PER_PT + pad_pt * 2

    slide_w_pt = slide_w_emu / EMU_PER_PT
    slide_h_pt = slide_h_emu / EMU_PER_PT
    x_pt = max(0.0, x_pt)
    y_pt = max(0.0, y_pt)
    w_pt = min(w_pt, slide_w_pt - x_pt)
    h_pt = min(h_pt, slide_h_pt - y_pt)

    view_box = f"{x_pt:.2f} {y_pt:.2f} {w_pt:.2f} {h_pt:.2f}"

    def _replace_root_attrs(match: re.Match) -> str:
        tag = match.group(0)
        tag = re.sub(r'viewBox="[^"]*"', f'viewBox="{view_box}"', tag)
        if "viewBox=" not in tag:
            tag = tag[:-1] + f' viewBox="{view_box}">'
        tag = re.sub(r'\swidth="[^"]*"', f' width="{w_pt:.2f}pt"', tag, count=1)
        tag = re.sub(r'\sheight="[^"]*"', f' height="{h_pt:.2f}pt"', tag, count=1)
        if 'preserveAspectRatio' not in tag:
            tag = tag[:-1] + ' preserveAspectRatio="xMidYMid meet">'
        return tag

    svg_out = re.sub(r"<svg\b[^>]*>", _replace_root_attrs, page_svg, count=1)
    return svg_out
