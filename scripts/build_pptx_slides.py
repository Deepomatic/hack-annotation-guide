"""
Slide composition for the Annotation Guide.

Edit this file to change which slides appear and in what order.
All slide builders and primitives live in pptx_helper.
"""

import logging

from pptx_helper import (
    build_tree, build_concept_map, dfs_order,
    build_cover_slide, build_toc_slide, build_overview_slide,
    build_section_slide, build_info_slide,
    build_concept_recap_slide, build_concept_detail_slide,
)

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
    build_cover_slide(prs, project_name=project_name)

    # ── Table of Contents ──
    build_toc_slide(prs, nodes, roots)

    # ── Views Overview (tree diagram) ──
    build_overview_slide(prs, nodes, roots, concept_map)

    # ── Per-view slides ──
    for nid in ordered:
        node = nodes[nid]
        is_root = not node["parent"] or node["parent"] not in nodes

        if is_root:
            build_section_slide(prs, node["label"], node["kind"])

        build_info_slide(prs, node, nodes, concept_map)

        tag_names = node.get("tag_names", [])
        if tag_names:
            build_concept_recap_slide(prs, node, images_dir=images_dir)

            for concept_name in tag_names:
                build_concept_detail_slide(prs, node, concept_name, images_dir=images_dir)

    logger.info("Built %d slides total.", len(prs.slides))
