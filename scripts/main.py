"""
Annotation Guide Generator

Fetches the view architecture from a Deepomatic Studio project
and generates a skeleton .pptx annotation guide.

Usage
-----
  # From Studio API (requires DEEPOMATIC_TOKEN or DEEPOMATIC_API_KEY env var):
  python main.py --org sandbox --project hackatono

  # From a local map JSON file (e.g. exported from /views/map/):
  python main.py --map project_map.json

  # Custom output path:
  python main.py --org sandbox --project hackatono --output my_guide.pptx
"""

import argparse
import io
import json
import logging
import sys
from pathlib import Path

from PIL import Image

from build_pptx_slides import build_all_slides
from pptx_helper import create_presentation
from studio_api import StudioClient

logger = logging.getLogger(__name__)


def _sanitize(name: str) -> str:
    """Turn a label into a safe filename component."""
    return name.replace(" ", "_").replace("/", "-").replace("\\", "-")


def _draw_bboxes(img: Image.Image, bboxes: list[dict], color=(255, 107, 53), thickness: int = 3) -> Image.Image:
    """Draw normalized bboxes on a PIL image. Returns a copy with overlays."""
    from PIL import ImageDraw
    img = img.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for bbox in bboxes:
        x0 = int(bbox["xmin"] * w)
        y0 = int(bbox["ymin"] * h)
        x1 = int(bbox["xmax"] * w)
        y1 = int(bbox["ymax"] * h)
        for i in range(thickness):
            draw.rectangle([x0 - i, y0 - i, x1 + i, y1 + i], outline=color)
    return img


def _download_sample_images(client: StudioClient, project_map: dict, images_dir: Path):
    """Download sample images for each view, organised by view name.

    Strategy per view kind:
    - TAG / CLA: 2 images per concept.
    - DET: 2 images per concept with bbox overlays.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    concept_map = {c["id"]: c["concept_name"] for c in project_map.get("concepts", [])}

    # Build a lookup: node_id → parent node's kind (DET, CLA, TAG, …)
    node_map = {n["id"]: n for n in project_map["nodes"]}
    parent_kind: dict[str, str] = {}
    for edge in project_map.get("edges", []):
        src = node_map.get(edge["source"], {})
        parent_kind[edge["target"]] = src.get("data", {}).get("kind", "").upper()

    for node in project_map["nodes"]:
        view_id = node["id"]
        view_label = _sanitize(node["label"])
        kind = node["data"].get("kind", "").upper()
        tag_ids: list[int] = node["data"].get("tag_ids", [])
        is_child_of_det = parent_kind.get(view_id) == "DET"

        view_dir = images_dir / view_label
        view_dir.mkdir(parents=True, exist_ok=True)

        if kind in ("TAG", "CLA"):
            _download_n_per_concept(client, view_id, view_label, tag_ids,
                                    concept_map, view_dir, n=4, crop=is_child_of_det)
        elif kind == "DET":
            _download_det_per_concept(client, view_id, view_label, tag_ids,
                                      concept_map, view_dir, n=4)
        else:
            # Unknown kind – just grab one sample
            _download_fallback(client, view_id, view_label, view_dir, count=2)

    logger.info("Images saved to %s", images_dir)


def _img_ext(region: dict) -> str:
    """Extract image extension from a region dict, defaulting to .jpg."""
    image = region.get("image", {})
    data = image.get("data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            data = {}
    orig = data.get("filename", "") if isinstance(data, dict) else ""
    if not orig:
        # Try to infer from the location field
        orig = image.get("location", "")
    ext = Path(orig).suffix if orig else ".jpg"
    return ext or ".jpg"


def _save_image(client: StudioClient, url: str, filepath: Path) -> bool:
    """Download and save an image. Returns True on success."""
    if filepath.exists():
        logger.info("  Already exists: %s", filepath)
        return True
    try:
        filepath.write_bytes(client.download_image(url))
        logger.info("  Downloaded: %s", filepath)
        return True
    except Exception as exc:
        logger.warning("  Failed to download %s: %s", filepath.name, exc)
        return False


def _save_cropped_image(client: StudioClient, url: str, bbox: dict, filepath: Path) -> bool:
    """Download a full image, crop it to *bbox*, and save the crop.

    bbox is expected to have normalised keys: xmin, ymin, xmax, ymax (0‒1).
    """
    if filepath.exists():
        logger.info("  Already exists: %s", filepath)
        return True
    try:
        img_data = client.download_image(url)
        img = Image.open(io.BytesIO(img_data))
        w, h = img.size
        left = int(bbox["xmin"] * w)
        upper = int(bbox["ymin"] * h)
        right = int(bbox["xmax"] * w)
        lower = int(bbox["ymax"] * h)
        crop = img.crop((left, upper, right, lower))
        # Save as PNG to avoid JPEG re-compression artefacts on small crops
        filepath = filepath.with_suffix(".png")
        crop.save(filepath)
        logger.info("  Cropped & saved: %s (%dx%d)", filepath, right - left, lower - upper)
        return True
    except Exception as exc:
        logger.warning("  Failed to crop %s: %s", filepath.name, exc)
        return False


def _download_n_per_concept(
    client: StudioClient,
    view_id: str,
    view_label: str,
    tag_ids: list[int],
    concept_map: dict[int, str],
    view_dir: Path,
    *,
    n: int = 2,
    crop: bool = False,
):
    """TAG/CLA: fetch N images per concept tag.

    Files are named {view}__{concept}__{idx}.ext (idx = 1, 2, …)
    If *crop* is True the view is a child of a DET view, so each region
    carries a bounding-box from the parent detection.
    """
    downloaded = 0
    for tag_id in tag_ids:
        concept_name = _sanitize(concept_map.get(tag_id, str(tag_id)))
        try:
            regions = client.get_regions(view_id, page_size=n, tag=tag_id)
        except Exception as exc:
            logger.warning("  Could not fetch regions for %s / %s: %s", view_label, concept_name, exc)
            continue
        if not regions:
            logger.info("  No image found for %s / %s", view_label, concept_name)
            continue
        for idx, region in enumerate(regions[:n], 1):
            img_url = region.get("image", {}).get("original_signed_url")
            if not img_url:
                continue

            bbox = region.get("region", {}).get("bbox") if crop else None
            ext = _img_ext(region)
            filepath = view_dir / f"{view_label}__{concept_name}__{idx}{ext}"

            if bbox:
                ok = _save_cropped_image(client, img_url, bbox, filepath)
            else:
                ok = _save_image(client, img_url, filepath)
            if ok:
                downloaded += 1

    if downloaded == 0:
        _download_fallback(client, view_id, view_label, view_dir, count=1)


def _download_det_per_concept(
    client: StudioClient,
    view_id: str,
    view_label: str,
    tag_ids: list[int],
    concept_map: dict[int, str],
    view_dir: Path,
    *,
    n: int = 2,
):
    """DET: fetch N images per concept with bbox overlays.

    For each concept tag:
      1. Fetch N regions filtered by that tag
      2. For each region, fetch annotations to get detection bboxes
      3. Draw the bboxes for that concept onto the image
      4. Save as PNG
    """
    # Map kind color per tag for consistent bbox colors
    DET_BBOX_COLOR = (255, 107, 53)  # orange — matches the DET accent

    downloaded = 0
    for tag_id in tag_ids:
        concept_name = _sanitize(concept_map.get(tag_id, str(tag_id)))
        try:
            regions = client.get_regions(view_id, page_size=n, tag=tag_id)
        except Exception as exc:
            logger.warning("  Could not fetch regions for DET %s / %s: %s", view_label, concept_name, exc)
            continue
        if not regions:
            logger.info("  No regions for DET %s / %s", view_label, concept_name)
            continue

        for idx, region in enumerate(regions[:n], 1):
            img_url = region.get("image", {}).get("original_signed_url")
            region_id = region.get("region", {}).get("id")
            if not img_url or not region_id:
                continue

            filepath = view_dir / f"{view_label}__{concept_name}__{idx}.png"
            if filepath.exists():
                logger.info("  Already exists: %s", filepath)
                downloaded += 1
                continue

            # Fetch annotations for this region to get per-concept bboxes
            try:
                annotations = client.get_annotations(view_id, region_id)
            except Exception as exc:
                logger.warning("  Could not fetch annotations for region %s: %s", region_id, exc)
                # Fall back to saving without bbox
                _save_image(client, img_url, filepath)
                downloaded += 1
                continue

            # Collect bboxes for the target tag
            bboxes = []
            for ann in annotations:
                ann_tags = ann.get("tags", [])
                tag_match = any(
                    (t if isinstance(t, int) else t.get("id")) == tag_id
                    for t in ann_tags
                )
                if tag_match:
                    bbox = ann.get("region", {}).get("bbox")
                    if bbox:
                        bboxes.append(bbox)

            # Download image and draw bboxes
            try:
                img_data = client.download_image(img_url)
                img = Image.open(io.BytesIO(img_data))
                if bboxes:
                    img = _draw_bboxes(img, bboxes, color=DET_BBOX_COLOR, thickness=4)
                img.save(filepath)
                logger.info("  DET saved: %s (%d bboxes)", filepath, len(bboxes))
                downloaded += 1
            except Exception as exc:
                logger.warning("  Failed to save DET image %s: %s", filepath.name, exc)

    if downloaded == 0:
        _download_fallback(client, view_id, view_label, view_dir, count=1)


def _download_fallback(client: StudioClient, view_id: str, view_label: str, view_dir: Path, count: int = 1):
    """Download generic sample images when no tag-specific strategy works."""
    try:
        regions = client.get_regions(view_id, page_size=count)
    except Exception:
        return
    for i, region in enumerate(regions[:count]):
        img_url = region.get("image", {}).get("original_signed_url")
        if not img_url:
            continue
        ext = _img_ext(region)
        filepath = view_dir / f"{view_label}__sample_{i + 1}{ext}"
        _save_image(client, img_url, filepath)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a .pptx annotation guide from a Deepomatic Studio project."
    )

    # Source: either API or local file
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--map",
        metavar="MAP_JSON",
        help="Path to a local project map JSON file.",
    )
    source.add_argument(
        "--org",
        metavar="ORG_SLUG",
        help="Studio organisation slug (requires --project too).",
    )

    parser.add_argument(
        "--project",
        metavar="PROJECT_SLUG",
        help="Studio project slug.",
    )
    parser.add_argument(
        "--token",
        metavar="TOKEN",
        help="Studio Bearer token (or set DEEPOMATIC_TOKEN env var).",
    )
    parser.add_argument(
        "--api-key",
        metavar="API_KEY",
        help="Studio API key (or set DEEPOMATIC_API_KEY_EU env var for EU cluster, DEEPOMATIC_API_KEY_US for US cluster).",
    )
    parser.add_argument(
        "--cluster",
        default="eu",
        choices=["eu", "us"],
        help="Studio cluster: 'eu' (default) or 'us' (studio.us1.deepomatic.com).",
    )
    parser.add_argument(
        "--output",
        default="annotation_guide.pptx",
        metavar="OUTPUT_PPTX",
        help="Destination .pptx file (default: annotation_guide.pptx).",
    )

    args = parser.parse_args(argv)

    if args.org and not args.project:
        parser.error("--project is required when using --org")

    return args


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    args = _parse_args(argv)

    # Get the project map
    if args.map:
        map_path = Path(args.map)
        if not map_path.is_file():
            logger.error("Map file not found: %s", map_path)
            sys.exit(1)
        with map_path.open(encoding="utf-8") as fh:
            project_map = json.load(fh)
        logger.info("Loaded project map from %s", map_path)
        images_dir = None
    else:
        org = args.org.lower()
        project = args.project.lower()
        client = StudioClient(
            org_slug=org,
            project_slug=project,
            token=args.token,
            api_key=args.api_key,
            cluster=args.cluster,
        )
        project_map = client.fetch_project_map()

        # Download sample images for each view
        images_dir = Path("images") / project
        _download_sample_images(client, project_map, images_dir)

    # Generate the PPTX
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prs = create_presentation()
    build_all_slides(
        prs,
        project_map,
        images_dir=images_dir,
        org_slug=getattr(args, "org", "") or "",
        project_slug=getattr(args, "project", "") or "",
    )
    prs.save(str(output_path))
    print(f"✅ Done → {output_path}  ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
