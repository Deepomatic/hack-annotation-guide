"""
Slide composition for the Annotation Guide — Black & White theme.
"""

import logging

from pptx.dml.color import RGBColor

from pathlib import Path

from pptx_helper import (
    build_tree, build_concept_map, dfs_order,
    build_cover_slide, build_toc_slide, build_overview_slide,
    build_section_slide, build_info_slide,
    build_concept_recap_slide, build_concept_detail_slide,
    add_blank_slide, set_slide_bg_solid, add_title, add_top_line,
    add_bottom_strip, add_image, add_textbox,
    SLIDE_WIDTH, SLIDE_HEIGHT, MARGIN_LEFT, MARGIN_RIGHT,
    CONTENT_TOP, CONTENT_WIDTH, TITLE_LEFT, TITLE_TOP, TITLE_HEIGHT,
    LIGHT_BG, WHITE, DARK_TEXT, MUTED,
)
from pptx.util import Cm, Pt

POWERMETER_IMG = Path("/home/emma/Documents/skills/hack-annotation-guide/4d12c9f3-4ef6-4d89-bed7-8842e16e0ca5.jpg")

# ── Black & White palette ──
BLACK = RGBColor(0x00, 0x00, 0x00)
DARK_GRAY = RGBColor(0x33, 0x33, 0x33)
MID_GRAY = RGBColor(0x88, 0x88, 0x88)
LIGHT_GRAY = RGBColor(0xDD, 0xDD, 0xDD)
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)

logger = logging.getLogger(__name__)


def build_all_slides(
    prs,
    project_map: dict,
    *,
    images_dir=None,
    org_slug: str = "",
    project_slug: str = "",
):
    """Build the complete annotation guide slide deck.

    Per-view structure:
      1. Section divider (root views only)
      2. Info slide (metadata)
      3. Concept recap (grid overview of all concepts)
      4. Per-concept detail slides (good/bad split)
    """
    nodes, roots = build_tree(project_map)
    concept_map = build_concept_map(project_map)
    ordered = dfs_order(nodes, roots)

    # ── Cover ──
    project_name = " — ".join(filter(None, [org_slug.upper(), project_slug.upper()]))
    build_cover_slide(
        prs, project_name=project_name,
        bg_start=BLACK, bg_end=DARK_GRAY,
        accent_color=_WHITE, title_color=_WHITE, subtitle_color=LIGHT_GRAY,
    )

    # ── Table of Contents ──
    build_toc_slide(
        prs, nodes, roots,
        bg_color=_WHITE, header_line_color=BLACK, strip_color=BLACK,
    )

    # ── Views Overview (tree diagram) ──
    build_overview_slide(
        prs, nodes, roots, concept_map,
        bg_color=_WHITE, header_line_color=BLACK,
        connector_color=MID_GRAY, strip_color=BLACK,
    )

    # ── Per-view slides ──
    for nid in ordered:
        node = nodes[nid]
        is_root = not node["parent"] or node["parent"] not in nodes

        if is_root:
            build_section_slide(
                prs, node["label"], node["kind"],
                accent_color=_WHITE, bg_start=BLACK, bg_end=DARK_GRAY,
                title_color=_WHITE,
            )

        build_info_slide(
            prs, node, nodes, concept_map,
            bg_color=_WHITE, accent_color=BLACK,
        )

        # Add powermeter reference image for classification & tagging views
        if node["kind"] in ("CLA", "TAG"):
            slide = add_blank_slide(prs)
            set_slide_bg_solid(slide, _WHITE)
            add_title(slide, f"{node['label']} — Reference")
            add_top_line(slide, color=BLACK)
            add_image(slide, str(POWERMETER_IMG),
                      MARGIN_LEFT + Cm(5), CONTENT_TOP + Cm(0.5),
                      Cm(14), Cm(12))
            add_bottom_strip(slide, BLACK)

        tag_names = node.get("tag_names", [])
        if tag_names:
            build_concept_recap_slide(
                prs, node, images_dir=images_dir,
                accent_color=BLACK, bg_color=_WHITE,
            )

            for concept_name in tag_names:
                build_concept_detail_slide(
                    prs, node, concept_name, images_dir=images_dir,
                    accent_color=BLACK, bg_color=_WHITE,
                    good_color=DARK_GRAY, bad_color=MID_GRAY,
                )

    logger.info("Built %d slides total.", len(prs.slides))
