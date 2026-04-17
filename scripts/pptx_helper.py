"""
Reusable PPTX primitives for building clean, modern presentations.

This module contains NO project-specific logic — only generic helpers
for creating slides, adding text, shapes, images, and layout utilities.

Do not modify this file to add project-specific slides.
Use build_pptx_slides.py for that.
"""

import logging
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_CONNECTOR_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Cm, Emu, Pt

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Design System — Color Palette
# ──────────────────────────────────────────────────────────────────────

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
NAVY_LIGHT = RGBColor(0x2D, 0x3E, 0x5E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BG = RGBColor(0xF7, 0xF8, 0xFA)
MUTED = RGBColor(0x88, 0x92, 0xA0)
DIVIDER = RGBColor(0xE1, 0xE5, 0xEB)
DARK_TEXT = RGBColor(0x1B, 0x2A, 0x4A)

# Accent colors per view kind
ORANGE = RGBColor(0xFF, 0x6B, 0x35)  # Detection
TEAL = RGBColor(0x2E, 0xC4, 0xB6)  # Classification
SKY_BLUE = RGBColor(0x5F, 0xA8, 0xD3)  # Tagging

# Good / Bad
GREEN = RGBColor(0x27, 0xAE, 0x60)
RED = RGBColor(0xE7, 0x4C, 0x3C)

# Placeholder background
PLACEHOLDER_BG = RGBColor(0xF0, 0xF1, 0xF3)

# ──────────────────────────────────────────────────────────────────────
# Design System — Typography
# ──────────────────────────────────────────────────────────────────────

FONT_FAMILY = "Calibri"
FONT_FAMILY_MONO = "Consolas"

FONT_SIZE_COVER_TITLE = Pt(40)
FONT_SIZE_COVER_SUBTITLE = Pt(18)
FONT_SIZE_SECTION_TITLE = Pt(36)
FONT_SIZE_SECTION_SUBTITLE = Pt(16)
FONT_SIZE_SLIDE_TITLE = Pt(24)
FONT_SIZE_BODY = Pt(14)
FONT_SIZE_BODY_SMALL = Pt(12)
FONT_SIZE_CAPTION = Pt(10)
FONT_SIZE_LABEL = Pt(9)
FONT_SIZE_BADGE = Pt(11)
FONT_SIZE_FOOTER = Pt(8)

# ──────────────────────────────────────────────────────────────────────
# Design System — Layout (16:9 widescreen)
# ──────────────────────────────────────────────────────────────────────

SLIDE_WIDTH = Cm(33.867)
SLIDE_HEIGHT = Cm(19.05)

MARGIN_LEFT = Cm(2.0)
MARGIN_RIGHT = Cm(2.0)
MARGIN_TOP = Cm(1.5)
MARGIN_BOTTOM = Cm(1.2)

CONTENT_LEFT = MARGIN_LEFT
CONTENT_TOP = Cm(4.0)  # below title area
CONTENT_WIDTH = SLIDE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
CONTENT_HEIGHT = SLIDE_HEIGHT - CONTENT_TOP - MARGIN_BOTTOM

TITLE_LEFT = MARGIN_LEFT
TITLE_TOP = Cm(1.2)
TITLE_WIDTH = SLIDE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
TITLE_HEIGHT = Cm(2.0)

ACCENT_BAR_WIDTH = Cm(0.4)
ACCENT_BAR_HEIGHT = Cm(3.0)

# ──────────────────────────────────────────────────────────────────────
# Presentation factory
# ──────────────────────────────────────────────────────────────────────


def create_presentation() -> Presentation:
    """Create a blank 16:9 Presentation with no template."""
    prs = Presentation()
    prs.slide_width = int(SLIDE_WIDTH)
    prs.slide_height = int(SLIDE_HEIGHT)
    return prs


def add_blank_slide(prs: Presentation):
    """Add a blank slide (layout index 6 = Blank in default theme)."""
    layout = prs.slide_layouts[6]
    return prs.slides.add_slide(layout)


# ──────────────────────────────────────────────────────────────────────
# Background helpers
# ──────────────────────────────────────────────────────────────────────


def set_slide_bg_solid(slide, color: RGBColor):
    """Set a solid background color on a slide."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def set_slide_bg_gradient(slide, color_start: RGBColor, color_end: RGBColor):
    """Set a two-stop linear gradient background on a slide."""
    bg = slide.background
    fill = bg.fill
    fill.gradient()
    fill.gradient_stops[0].color.rgb = color_start
    fill.gradient_stops[0].position = 0.0
    fill.gradient_stops[1].color.rgb = color_end
    fill.gradient_stops[1].position = 1.0


# ──────────────────────────────────────────────────────────────────────
# Text helpers
# ──────────────────────────────────────────────────────────────────────


def add_textbox(
    slide,
    left,
    top,
    width,
    height,
    text: str,
    *,
    font_size=FONT_SIZE_BODY,
    font_name=FONT_FAMILY,
    bold=False,
    italic=False,
    color: RGBColor = DARK_TEXT,
    alignment=PP_ALIGN.LEFT,
    word_wrap=True,
    vertical_anchor=MSO_ANCHOR.TOP,
):
    """Add a text box with a single styled run. Returns the shape."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = word_wrap
    tf.auto_size = None
    try:
        tf.vertical_anchor = vertical_anchor
    except Exception:
        pass

    para = tf.paragraphs[0]
    para.alignment = alignment
    run = para.add_run()
    run.text = text
    run.font.size = font_size
    run.font.name = font_name
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txBox


def add_rich_textbox(
    slide,
    left,
    top,
    width,
    height,
    runs: list[dict],
    *,
    alignment=PP_ALIGN.LEFT,
    word_wrap=True,
    line_spacing=None,
):
    """Add a textbox with multiple styled runs in a single paragraph.

    Each run dict: {"text": str, "bold": bool, "color": RGBColor, "size": Pt, "font": str}
    """
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = word_wrap
    para = tf.paragraphs[0]
    para.alignment = alignment
    if line_spacing is not None:
        para.line_spacing = line_spacing

    for r in runs:
        run = para.add_run()
        run.text = r.get("text", "")
        run.font.size = r.get("size", FONT_SIZE_BODY)
        run.font.name = r.get("font", FONT_FAMILY)
        run.font.bold = r.get("bold", False)
        run.font.italic = r.get("italic", False)
        run.font.color.rgb = r.get("color", DARK_TEXT)
    return txBox


def add_multiline_textbox(
    slide,
    left,
    top,
    width,
    height,
    lines: list[dict],
    *,
    word_wrap=True,
    para_spacing_pt=4,
):
    """Add a textbox with multiple paragraphs (one per line).

    Each line dict: {"text": str, "bold": bool, "color": RGBColor,
                     "size": Pt, "alignment": PP_ALIGN, "indent_level": int}
    """
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = word_wrap

    for i, line in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = line.get("alignment", PP_ALIGN.LEFT)
        para.space_after = Pt(para_spacing_pt)
        run = para.add_run()
        run.text = line.get("text", "")
        run.font.size = line.get("size", FONT_SIZE_BODY)
        run.font.name = line.get("font", FONT_FAMILY)
        run.font.bold = line.get("bold", False)
        run.font.italic = line.get("italic", False)
        run.font.color.rgb = line.get("color", DARK_TEXT)
    return txBox


def add_title(slide, text: str, *, color: RGBColor = DARK_TEXT, font_size=FONT_SIZE_SLIDE_TITLE):
    """Add a title textbox at the standard title position."""
    return add_textbox(
        slide,
        TITLE_LEFT,
        TITLE_TOP,
        TITLE_WIDTH,
        TITLE_HEIGHT,
        text,
        font_size=font_size,
        bold=True,
        color=color,
    )


def add_subtitle(slide, text: str, *, color: RGBColor = MUTED, font_size=FONT_SIZE_BODY):
    """Add subtitle text just below the standard title position."""
    return add_textbox(
        slide,
        TITLE_LEFT,
        TITLE_TOP + Cm(2.2),
        TITLE_WIDTH,
        Cm(1.2),
        text,
        font_size=font_size,
        color=color,
    )


# ──────────────────────────────────────────────────────────────────────
# Shape helpers
# ──────────────────────────────────────────────────────────────────────


def add_rounded_rect(
    slide,
    left,
    top,
    width,
    height,
    *,
    fill_color: RGBColor | None = WHITE,
    border_color: RGBColor | None = DIVIDER,
    border_width=Pt(1.5),
    text: str = "",
    text_color: RGBColor = DARK_TEXT,
    text_size=FONT_SIZE_BODY_SMALL,
    text_bold=False,
    text_align=PP_ALIGN.CENTER,
):
    """Add a rounded rectangle shape with optional text."""
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        left, top, width, height,
    )
    if fill_color is not None:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()

    if border_color is not None:
        shape.line.color.rgb = border_color
        shape.line.width = border_width
    else:
        shape.line.fill.background()

    if text:
        tf = shape.text_frame
        tf.word_wrap = True
        para = tf.paragraphs[0]
        para.alignment = text_align
        run = para.add_run()
        run.text = text
        run.font.size = text_size
        run.font.color.rgb = text_color
        run.font.bold = text_bold
        run.font.name = FONT_FAMILY

    return shape


def add_accent_bar(slide, left, top, width, height, color: RGBColor):
    """Add a solid colored rectangle (accent bar / decorative element)."""
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        left, top, width, height,
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_line(slide, x1, y1, x2, y2, *, color: RGBColor = DIVIDER, width=Pt(1)):
    """Add a straight connector line."""
    conn = slide.shapes.add_connector(
        MSO_CONNECTOR_TYPE.STRAIGHT,
        x1, y1, x2, y2,
    )
    conn.line.color.rgb = color
    conn.line.width = width
    return conn


def add_badge(
    slide,
    left,
    top,
    text: str,
    *,
    bg_color: RGBColor,
    text_color: RGBColor = WHITE,
    font_size=FONT_SIZE_BADGE,
    padding_lr=Cm(0.6),
    height=Cm(1.0),
):
    """Add a pill-shaped badge (rounded rect with text)."""
    # Estimate width from text length
    char_width = int(font_size) * 0.7
    text_width = int(len(text) * char_width)
    width = max(text_width + 2 * int(padding_lr), int(Cm(2.5)))

    return add_rounded_rect(
        slide,
        left, top,
        width, height,
        fill_color=bg_color,
        border_color=None,
        text=text,
        text_color=text_color,
        text_size=font_size,
        text_bold=True,
    )


# ──────────────────────────────────────────────────────────────────────
# Image helpers
# ──────────────────────────────────────────────────────────────────────


def add_image(slide, img_path, left, top, max_width, max_height):
    """Add an image auto-scaled to fit within max_width × max_height.

    Preserves aspect ratio. Centers within the given area.
    Returns the picture shape, or None if image can't be loaded.
    """
    from PIL import Image as PILImage

    img_path = Path(img_path)
    if not img_path.exists():
        return None

    try:
        with PILImage.open(img_path) as im:
            iw, ih = im.size
    except Exception:
        return None

    if iw <= 0 or ih <= 0:
        return None

    scale = min(int(max_width) / iw, int(max_height) / ih)
    pic_w = int(iw * scale)
    pic_h = int(ih * scale)

    # Center in area
    x_off = (int(max_width) - pic_w) // 2
    y_off = (int(max_height) - pic_h) // 2

    try:
        pic = slide.shapes.add_picture(
            str(img_path),
            left + x_off,
            top + y_off,
            pic_w,
            pic_h,
        )
        return pic
    except Exception as exc:
        logger.warning("Could not embed %s: %s", img_path.name, exc)
        return None


def add_image_placeholder(
    slide,
    left,
    top,
    width,
    height,
    label: str = "",
    *,
    border_color: RGBColor = DIVIDER,
    bg_color: RGBColor = PLACEHOLDER_BG,
    label_color: RGBColor | None = None,
    dash=True,
):
    """Draw a labeled rectangle as an image placeholder."""
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        left, top, width, height,
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.5)
    if dash:
        shape.line.dash_style = 2  # dashed

    if label:
        tf = shape.text_frame
        tf.word_wrap = True
        try:
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        except Exception:
            pass
        para = tf.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER
        run = para.add_run()
        run.text = label
        run.font.size = FONT_SIZE_CAPTION
        run.font.color.rgb = label_color or border_color
        run.font.bold = True
        run.font.name = FONT_FAMILY

    return shape


# ──────────────────────────────────────────────────────────────────────
# Layout helpers
# ──────────────────────────────────────────────────────────────────────


def grid_positions(
    n_items: int,
    area_left,
    area_top,
    area_width,
    area_height,
    *,
    cols: int | None = None,
    h_padding=Cm(0.5),
    v_padding=Cm(0.5),
) -> list[tuple[int, int, int, int]]:
    """Compute (left, top, width, height) for N items in a grid layout.

    Returns list of (left, top, cell_width, cell_height).
    If cols is None, auto-picks: 1 for 1 item, 2 for 2, 3 for 3-6, 4 for 7+.
    """
    if n_items == 0:
        return []

    if cols is None:
        if n_items <= 1:
            cols = 1
        elif n_items <= 2:
            cols = 2
        elif n_items <= 6:
            cols = 3
        else:
            cols = 4

    import math
    rows = math.ceil(n_items / cols)

    cell_w = (int(area_width) - (cols - 1) * int(h_padding)) // cols
    cell_h = (int(area_height) - (rows - 1) * int(v_padding)) // rows

    positions = []
    for i in range(n_items):
        row = i // cols
        col = i % cols
        x = int(area_left) + col * (cell_w + int(h_padding))
        y = int(area_top) + row * (cell_h + int(v_padding))
        positions.append((x, y, cell_w, cell_h))

    return positions


# ──────────────────────────────────────────────────────────────────────
# Connector helpers (for tree/graph diagrams)
# ──────────────────────────────────────────────────────────────────────


def add_tree_connector(slide, parent_cx, parent_bottom_y, child_cx, child_top_y, *, color=DIVIDER, width=Pt(1.5)):
    """Draw a connector from parent bottom-center to child top-center."""
    return add_line(slide, parent_cx, parent_bottom_y, child_cx, child_top_y, color=color, width=width)


# ──────────────────────────────────────────────────────────────────────
# Footer / page number
# ──────────────────────────────────────────────────────────────────────


def add_footer(slide, text: str, *, include_page_number=False, page_number: int | None = None):
    """Add a small footer text at the bottom-right of the slide."""
    footer_text = text
    if include_page_number and page_number is not None:
        footer_text = f"{text}  |  {page_number}"

    return add_textbox(
        slide,
        SLIDE_WIDTH - Cm(8),
        SLIDE_HEIGHT - Cm(1.0),
        Cm(7),
        Cm(0.8),
        footer_text,
        font_size=FONT_SIZE_FOOTER,
        color=MUTED,
        alignment=PP_ALIGN.RIGHT,
    )


# ──────────────────────────────────────────────────────────────────────
# Decorative helpers
# ──────────────────────────────────────────────────────────────────────


def add_bottom_strip(slide, color: RGBColor, height=Cm(0.3)):
    """Add a thin colored strip at the bottom of a slide."""
    return add_accent_bar(
        slide,
        0, SLIDE_HEIGHT - height,
        SLIDE_WIDTH, height,
        color,
    )


def add_top_line(slide, *, color: RGBColor = DIVIDER, y=None):
    """Add a thin horizontal line below the title area (visual separator)."""
    if y is None:
        y = TITLE_TOP + TITLE_HEIGHT + Cm(0.3)
    return add_line(
        slide,
        MARGIN_LEFT, y,
        SLIDE_WIDTH - MARGIN_RIGHT, y,
        color=color,
        width=Pt(0.75),
    )
