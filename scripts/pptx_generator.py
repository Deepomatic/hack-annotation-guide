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


def _sanitize(name: str) -> str:
    """Turn a label into a safe directory/filename component."""
    return name.replace(" ", "_").replace("/", "-").replace("\\", "-")

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


def _find_view_images(view_label: str, images_dir) -> dict[str, Path | None]:
    """Return a dict {concept_name: image_path_or_None} for a view.

    Images are expected at  images_dir/<sanitized_view>/<view>__<concept>.ext
    """
    if images_dir is None:
        return {}
    view_dir = Path(images_dir) / _sanitize(view_label)
    if not view_dir.is_dir():
        return {}
    exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}
    result: dict[str, Path] = {}
    for p in sorted(view_dir.iterdir()):
        if p.suffix.lower() not in exts:
            continue
        stem = p.stem
        if "__" in stem:
            concept = stem.split("__", 1)[1].replace("_", " ")
        else:
            concept = stem
        result[concept] = p
    return result


def _add_concept_to_slide(
    slide, concept_name: str, img_path: Path | None,
    x, y, col_w, img_area_h, box_colour, slide_w, slide_h,
):
    """Place one concept (image + legend) in a column on the slide."""
    from PIL import Image as PILImage

    legend_h = Cm(1.2)

    if img_path and img_path.exists():
        try:
            with PILImage.open(img_path) as im:
                iw, ih = im.size
        except Exception:
            iw, ih = 0, 0

        if iw > 0 and ih > 0:
            # Size constraints: max 1/3, min 1/4 of max(slide_w, slide_h)
            max_dim = max(slide_w, slide_h)
            size_max = max_dim // 3
            size_min = max_dim // 4

            # Fit within column and image area
            max_w = min(col_w, size_max)
            max_h = min(img_area_h - legend_h, size_max)

            scale = min(max_w / iw, max_h / ih)
            pic_w = int(iw * scale)
            pic_h = int(ih * scale)

            # Enforce minimum size
            if max(pic_w, pic_h) < size_min:
                upscale = size_min / max(pic_w, pic_h)
                pic_w = int(pic_w * upscale)
                pic_h = int(pic_h * upscale)

            # Centre horizontally in column
            x_off = (col_w - pic_w) // 2
            # Place image vertically centred in the available area
            y_off = (img_area_h - legend_h - pic_h) // 2

            try:
                slide.shapes.add_picture(
                    str(img_path), x + x_off, y + max(y_off, 0), pic_w, pic_h,
                )
            except Exception as exc:
                logger.warning("Could not embed %s: %s", img_path.name, exc)
    else:
        # No image — draw a light placeholder rectangle
        margin = Cm(1)
        placeholder_w = col_w - 2 * margin
        placeholder_h = img_area_h - legend_h - 2 * margin
        if placeholder_w > 0 and placeholder_h > 0:
            shape = slide.shapes.add_shape(
                1, x + margin, y + margin, placeholder_w, placeholder_h,
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = COLOUR_PLACEHOLDER_BG
            shape.line.color.rgb = box_colour
            shape.line.width = Pt(1)
            shape.line.dash_style = 2  # dash
            tf = shape.text_frame
            tf.word_wrap = True
            para = tf.paragraphs[0]
            para.alignment = PP_ALIGN.CENTER
            run = para.add_run()
            run.text = "[ image missing ]"
            run.font.size = Pt(10)
            run.font.color.rgb = box_colour

    # Legend — concept name centred below the image area
    _add_text_box(
        slide, x, y + img_area_h - legend_h, col_w, legend_h,
        concept_name, bold=True, size_pt=12, colour=box_colour, align=PP_ALIGN.CENTER,
    )


def _slides_for_view(prs, node, nodes, concept_map, images_dir=None):
    """Create one info slide + concept slides (max 3 concepts each) for a view."""
    kind = node["kind"]
    kind_label = KIND_LABELS.get(kind, kind)
    box_colour = _kind_colour(kind)

    slide_w = prs.slide_width
    slide_h = prs.slide_height

    # --- Info slide (always) ---
    layout = prs.slide_layouts[LAYOUT_TITLE_ONLY]
    slide = prs.slides.add_slide(layout)

    title = slide.shapes.title
    title.text = f"{node['label']}  –  {kind_label}"
    title.text_frame.paragraphs[0].runs[0].font.color.rgb = COLOUR_TITLE
    title.text_frame.paragraphs[0].runs[0].font.size = Pt(24)

    info_left = Cm(0.5)
    info_top = Cm(3.5)
    info_w = Cm(11)

    lines = []
    parent_label = ""
    if node["parent"] and node["parent"] in nodes:
        parent_label = nodes[node["parent"]]["label"]
    lines.append(("Parent view:", parent_label or "— (root)"))

    cond_str = _resolve_conditions(node["conditions"], concept_map)
    lines.append(("Activated by:", cond_str or "—"))

    child_labels = [nodes[c]["label"] for c in node["children"] if c in nodes]
    lines.append(("Child views:", ", ".join(child_labels) if child_labels else "—"))

    tag_names = node.get("tag_names", [])
    if tag_names:
        lines.append(("Concepts:", ", ".join(tag_names)))

    y_offset = info_top
    row_h = Cm(1.1)
    for label, value in lines:
        _add_text_box(slide, info_left, y_offset, info_w, row_h, label, bold=True, size_pt=11, colour=COLOUR_TITLE)
        _add_text_box(slide, info_left, y_offset + Cm(0.55), info_w, row_h, value or "—", bold=False, size_pt=11)
        y_offset += Cm(1.7)

    # --- Concept slides (max 3 per slide) ---
    view_images = _find_view_images(node["label"], images_dir)

    # Build the list of concepts to show
    concepts: list[str] = list(tag_names) if tag_names else []

    # If no concepts defined but we have images, use image names
    if not concepts and view_images:
        concepts = list(view_images.keys())

    # If still nothing, no concept slides needed (info slide is enough)
    if not concepts:
        return

    # Chunk concepts into groups of 3
    CONCEPTS_PER_SLIDE = 3
    chunks = [concepts[i:i + CONCEPTS_PER_SLIDE] for i in range(0, len(concepts), CONCEPTS_PER_SLIDE)]

    content_top = Cm(3.5)
    content_h = slide_h - content_top - Cm(1)
    margin = Cm(0.5)

    for chunk_idx, chunk in enumerate(chunks):
        slide = prs.slides.add_slide(layout)

        title = slide.shapes.title
        if len(chunks) > 1:
            title.text = f"{node['label']}  ({chunk_idx + 1}/{len(chunks)})"
        else:
            title.text = node["label"]
        title.text_frame.paragraphs[0].runs[0].font.color.rgb = COLOUR_TITLE
        title.text_frame.paragraphs[0].runs[0].font.size = Pt(22)

        n_cols = len(chunk)
        total_content_w = slide_w - 2 * margin
        col_w = total_content_w // n_cols

        for col_idx, concept_name in enumerate(chunk):
            # Try to find the image — match by concept name
            img_path = view_images.get(concept_name)
            # Also try sanitized matching
            if img_path is None:
                sanitized = _sanitize(concept_name).replace("_", " ")
                for k, v in view_images.items():
                    if k == sanitized or k.lower() == concept_name.lower():
                        img_path = v
                        break
            # Also try if image key contains the concept (partial match for "sample" names)
            if img_path is None:
                cn_lower = concept_name.lower().replace(" ", "_")
                for k, v in view_images.items():
                    if cn_lower in k.lower().replace(" ", "_"):
                        img_path = v
                        break

            x = margin + col_idx * col_w
            _add_concept_to_slide(
                slide, concept_name, img_path,
                x, content_top, col_w, content_h,
                box_colour, slide_w, slide_h,
            )


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


# _slide_for_view replaced by _slides_for_view above


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------


def generate_pptx(project_map: dict, output_path: str | Path, *, images_dir: Path | None = None) -> Path:
    """
    Build the annotation guide .pptx from a project map and write it.

    Parameters
    ----------
    project_map : dict
        Parsed JSON project map containing "nodes", "edges", "concepts".
    output_path : str | Path
        Destination file path.
    images_dir : Path | None
        Directory containing downloaded sample images (one sub-folder per view).
    """
    nodes, roots = _build_tree(project_map)
    concept_map = _build_concept_map(project_map)
    ordered = _dfs_order(nodes, roots)

    prs = Presentation()
    prs.slide_width = Cm(33.87)
    prs.slide_height = Cm(19.05)

    _slide_intro(prs, nodes, roots, concept_map)

    for nid in ordered:
        _slides_for_view(prs, nodes[nid], nodes, concept_map, images_dir=images_dir)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    logger.info("Saved annotation guide to %s  (%d slides)", output_path, len(prs.slides))
    return output_path
