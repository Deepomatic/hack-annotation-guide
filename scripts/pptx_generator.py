"""
Generate a skeleton .pptx annotation guide from a Deepomatic project map.

Adapted from Brieuc's PR #317 in deepomatic-tools.

The project map JSON has the following structure:
  {
    "nodes": [ { "id": ..., "label": ..., "data": { "parent": ..., "kind": ..., "conditions": ... } } ],
    "edges": [ { "source": ..., "target": ..., "data": {} } ],
    "concepts": [ { "id": ..., "concept_name": ... } ]
  }

View kinds:
  CLA  – Classification
  DET  – Detection  (bounding-box based)
  TAG  – Tagging
"""

import logging
from collections import defaultdict
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Cm, Pt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slide-layout indices (default Office Theme)
# ---------------------------------------------------------------------------
LAYOUT_TITLE_SLIDE = 0
LAYOUT_TITLE_CONTENT = 1
LAYOUT_TITLE_ONLY = 2
LAYOUT_BLANK = 5

# Kind labels
KIND_LABELS = {
    "CLA": "Classification",
    "DET": "Detection",
    "TAG": "Tagging",
}

# Colours
COLOUR_TITLE = RGBColor(0x1F, 0x49, 0x7D)  # dark blue
COLOUR_DET_BOX = RGBColor(0xFF, 0x6F, 0x00)  # orange
COLOUR_CLA_BOX = RGBColor(0x70, 0xAD, 0x47)  # green
COLOUR_TAG_BOX = RGBColor(0x5B, 0x9B, 0xD5)  # blue
COLOUR_PLACEHOLDER_BG = RGBColor(0xF2, 0xF2, 0xF2)  # light grey


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_text(tf, text, bold=False, size_pt=14, colour=None, align=PP_ALIGN.LEFT):
    """Replace all text in a text-frame with a single run."""
    tf.clear()
    para = tf.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = text
    run.font.bold = bold
    run.font.size = Pt(size_pt)
    if colour:
        run.font.color.rgb = colour


def _add_text_box(slide, left, top, width, height, text, bold=False, size_pt=12, colour=None, align=PP_ALIGN.LEFT):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    _set_text(tf, text, bold=bold, size_pt=size_pt, colour=colour, align=align)
    return txBox


def _add_placeholder_image(slide, left, top, width, height, label, box_colour):
    """Draw a labelled rectangle that acts as a picture placeholder."""
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        left, top, width, height,
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOUR_PLACEHOLDER_BG
    shape.line.color.rgb = box_colour
    shape.line.width = Pt(1.5)

    tf = shape.text_frame
    tf.word_wrap = True
    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    run = para.add_run()
    run.text = label
    run.font.size = Pt(11)
    run.font.color.rgb = box_colour
    run.font.bold = True
    return shape


def _add_bbox_overlay(slide, parent_left, parent_top, parent_width, parent_height, box_colour):
    """Draw a small bounding-box overlay inside the image placeholder."""
    margin_w = parent_width * 0.15
    margin_h = parent_height * 0.15
    box = slide.shapes.add_shape(
        1,
        parent_left + margin_w,
        parent_top + margin_h,
        parent_width - 2 * margin_w,
        parent_height - 2 * margin_h,
    )
    box.fill.background()
    box.line.color.rgb = box_colour
    box.line.width = Pt(2)
    return box


# ---------------------------------------------------------------------------
# Map parsing
# ---------------------------------------------------------------------------


def _build_tree(project_map):
    """
    Return (nodes_dict, roots_list) from a project map.
    Each node: { "id", "label", "kind", "parent", "conditions", "children" }
    """
    nodes = {}
    for n in project_map["nodes"]:
        nodes[n["id"]] = {
            "id": n["id"],
            "label": n["label"],
            "kind": n["data"].get("kind", ""),
            "parent": n["data"].get("parent", ""),
            "conditions": n["data"].get("conditions") or [],
            "tag_names": n["data"].get("tag_names", []),
            "children": [],
        }

    for edge in project_map["edges"]:
        src, tgt = edge["source"], edge["target"]
        if src and src in nodes and tgt in nodes:
            nodes[src]["children"].append(tgt)

    roots = [nid for nid, n in nodes.items() if not n["parent"]]
    return nodes, roots


def _build_concept_map(project_map):
    """Return dict {concept_id: concept_name}."""
    return {c["id"]: c["concept_name"] for c in project_map.get("concepts", [])}


def _resolve_conditions(conditions, concept_map):
    """Turn condition lists into a human-readable string."""
    if not conditions:
        return ""
    groups = []
    for group in conditions:
        names = [concept_map.get(cid, str(cid)) for cid in group]
        groups.append(" & ".join(names))
    return "  |  ".join(groups)


def _dfs_order(nodes, roots):
    """Return node IDs in DFS order starting from roots."""
    order = []
    visited = set()

    def dfs(nid):
        if nid in visited:
            return
        visited.add(nid)
        order.append(nid)
        for child_id in nodes[nid]["children"]:
            dfs(child_id)

    for r in roots:
        dfs(r)
    for nid in nodes:
        if nid not in visited:
            order.append(nid)
    return order


# ---------------------------------------------------------------------------
# Slide builders
# ---------------------------------------------------------------------------


def _kind_colour(kind):
    if kind == "DET":
        return COLOUR_DET_BOX
    if kind == "CLA":
        return COLOUR_CLA_BOX
    return COLOUR_TAG_BOX


def _slide_intro(prs, nodes, roots, concept_map):
    """Title / introduction slide listing all views."""
    layout = prs.slide_layouts[LAYOUT_TITLE_SLIDE]
    slide = prs.slides.add_slide(layout)

    title = slide.shapes.title
    title.text = "Annotation Guide"
    title.text_frame.paragraphs[0].runs[0].font.color.rgb = COLOUR_TITLE

    subtitle = slide.placeholders[1]
    tf = subtitle.text_frame
    tf.clear()

    def add_line(text, indent=0, bold=False, size_pt=12, colour=None):
        para = tf.add_paragraph()
        para.level = indent
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size_pt)
        run.font.bold = bold
        if colour:
            run.font.color.rgb = colour

    # First paragraph
    tf.paragraphs[0].clear()
    first_run = tf.paragraphs[0].add_run()
    first_run.text = "Views overview:"
    first_run.font.bold = True
    first_run.font.size = Pt(13)
    first_run.font.color.rgb = COLOUR_TITLE

    ordered = _dfs_order(nodes, roots)
    for nid in ordered:
        n = nodes[nid]
        depth = 0
        pid = n["parent"]
        while pid and pid in nodes:
            depth += 1
            pid = nodes[pid]["parent"]
        kind = KIND_LABELS.get(n["kind"], n["kind"])
        prefix = "  " * depth + ("└ " if depth else "• ")
        add_line(f"{prefix}{n['label']}  [{kind}]", indent=min(depth, 4), size_pt=11)

    return slide


def _slide_for_view(prs, node, nodes, concept_map):
    """One slide per view."""
    kind = node["kind"]
    layout = prs.slide_layouts[LAYOUT_TITLE_ONLY]
    slide = prs.slides.add_slide(layout)

    # Title
    title = slide.shapes.title
    kind_label = KIND_LABELS.get(kind, kind)
    title.text = f"{node['label']}  –  {kind_label}"
    title.text_frame.paragraphs[0].runs[0].font.color.rgb = COLOUR_TITLE
    title.text_frame.paragraphs[0].runs[0].font.size = Pt(24)

    slide_w = prs.slide_width
    slide_h = prs.slide_height

    # Info panel (left column)
    info_left = Cm(0.5)
    info_top = Cm(3.5)
    info_w = Cm(11)

    lines = []

    # Parent
    parent_label = ""
    if node["parent"] and node["parent"] in nodes:
        parent_label = nodes[node["parent"]]["label"]
    lines.append(("Parent view:", parent_label or "— (root)"))

    # Conditions
    cond_str = _resolve_conditions(node["conditions"], concept_map)
    lines.append(("Activated by:", cond_str or "—"))

    # Children
    child_labels = [nodes[c]["label"] for c in node["children"] if c in nodes]
    lines.append(("Child views:", ", ".join(child_labels) if child_labels else "—"))

    # Concepts (actual tags on this view)
    tag_names = node.get("tag_names", [])
    if tag_names:
        lines.append(("Concepts:", ", ".join(tag_names)))

    # Draw info block
    y_offset = info_top
    row_h = Cm(1.1)
    for label, value in lines:
        _add_text_box(slide, info_left, y_offset, info_w, row_h, label, bold=True, size_pt=11, colour=COLOUR_TITLE)
        _add_text_box(slide, info_left, y_offset + Cm(0.55), info_w, row_h, value or "—", bold=False, size_pt=11)
        y_offset += Cm(1.7)

    # Image placeholder (right column)
    img_left = Cm(12)
    img_top = Cm(3.5)
    img_w = slide_w - img_left - Cm(0.5)
    img_h = Cm(10)

    box_colour = _kind_colour(kind)
    placeholder_label = f"[ {kind_label} example image ]"
    _add_placeholder_image(slide, img_left, img_top, img_w, img_h, placeholder_label, box_colour)

    if kind == "DET":
        _add_bbox_overlay(slide, img_left, img_top, img_w, img_h, COLOUR_DET_BOX)
        _add_text_box(
            slide, img_left, img_top + img_h + Cm(0.3), img_w, Cm(0.8),
            "↑ Replace with an annotated image showing bounding boxes",
            size_pt=9, colour=COLOUR_DET_BOX,
        )
    else:
        _add_text_box(
            slide, img_left, img_top + img_h + Cm(0.3), img_w, Cm(0.8),
            "↑ Replace with a representative example image",
            size_pt=9, colour=box_colour,
        )

    return slide


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------


def generate_pptx(project_map: dict, output_path: str | Path) -> Path:
    """
    Build the annotation guide .pptx from a project map and write it.

    Parameters
    ----------
    project_map : dict
        Parsed JSON project map containing "nodes", "edges", "concepts".
    output_path : str | Path
        Destination file path.
    """
    nodes, roots = _build_tree(project_map)
    concept_map = _build_concept_map(project_map)
    ordered = _dfs_order(nodes, roots)

    prs = Presentation()
    prs.slide_width = Cm(33.87)
    prs.slide_height = Cm(19.05)

    _slide_intro(prs, nodes, roots, concept_map)

    for nid in ordered:
        _slide_for_view(prs, nodes[nid], nodes, concept_map)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    logger.info("Saved annotation guide to %s  (%d slides)", output_path, len(prs.slides))
    return output_path
