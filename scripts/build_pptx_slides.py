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
    view_filter: set[str] | None = None,
):
    """Build the complete annotation guide slide deck (French).

    Per-view structure:
      1. Section divider (root views only)
      2. Info slide (metadata)
      3. Concept recap (grid overview of all concepts)
      4. Per-concept detail slides (4 good examples, no bad examples, with explanation)

    If *view_filter* (lowercase view labels) is provided, only those views
    generate per-view slides. Cover / TOC / Overview still list the full tree.
    """
    nodes, roots = build_tree(project_map)
    concept_map = build_concept_map(project_map)
    ordered = dfs_order(nodes, roots)

    # ── Cover ──
    project_name = " — ".join(filter(None, [org_slug.upper(), project_slug.upper()]))
    build_cover_slide(prs, project_name=project_name, title="Guide d'Annotation")

    # ── Table of Contents ──
    build_toc_slide(prs, nodes, roots, title="Table des Matières")

    # ── Views Overview (tree diagram) ──
    build_overview_slide(prs, nodes, roots, concept_map, title="Vue d'Ensemble")

    # ── Per-view slides ──
    for nid in ordered:
        node = nodes[nid]
        if view_filter is not None and node["label"].lower() not in view_filter:
            continue
        is_root = not node["parent"] or node["parent"] not in nodes

        if is_root:
            build_section_slide(prs, node["label"], node["kind"])

        build_info_slide(prs, node, nodes, concept_map,
                         instruction_text="Ajoutez ici les instructions d'annotation pour cette vue.")

        tag_names = node.get("tag_names", [])
        if tag_names:
            build_concept_recap_slide(prs, node, images_dir=images_dir,
                                      title=f"{node['label']}  —  Vue d'Ensemble des Concepts")

            for concept_name in tag_names:
                build_concept_detail_slide(
                    prs, node, concept_name, images_dir=images_dir,
                    n_good=4,
                    examples_label="✓  Exemples",
                )

    logger.info("Built %d slides total.", len(prs.slides))
