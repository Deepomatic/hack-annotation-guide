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

from pptx_generator import generate_pptx
from studio_api import StudioClient

logger = logging.getLogger(__name__)


def _sanitize(name: str) -> str:
    """Turn a label into a safe filename component."""
    return name.replace(" ", "_").replace("/", "-").replace("\\", "-")


def _download_sample_images(client: StudioClient, project_map: dict, images_dir: Path):
    """Download sample images for each view, organised by view name.

    Strategy per view kind:
    - TAG / CLA: 1 image per concept, each named after the concept.
    - DET: 1 image that contains as many concepts as possible.
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
            _download_one_per_concept(client, view_id, view_label, tag_ids, concept_map, view_dir, crop=is_child_of_det)
        elif kind == "DET":
            _download_best_det_image(client, view_id, view_label, tag_ids, concept_map, view_dir)
        else:
            # Unknown kind – just grab one sample
            _download_fallback(client, view_id, view_label, view_dir, count=1)

    logger.info("Images saved to %s", images_dir)


def _img_ext(region: dict) -> str:
    """Extract image extension from a region dict, defaulting to .jpg."""
    orig = region.get("image", {}).get("data", {}).get("filename", "")
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


def _download_one_per_concept(
    client: StudioClient,
    view_id: str,
    view_label: str,
    tag_ids: list[int],
    concept_map: dict[int, str],
    view_dir: Path,
    *,
    crop: bool = False,
):
    """TAG/CLA: fetch 1 image per concept tag.

    If *crop* is True the view is a child of a DET view, so each region
    carries a bounding-box from the parent detection.  We download the
    full image and crop to that bbox.
    """
    downloaded = 0
    for tag_id in tag_ids:
        concept_name = _sanitize(concept_map.get(tag_id, str(tag_id)))
        try:
            regions = client.get_regions(view_id, page_size=1, tag=tag_id)
        except Exception as exc:
            logger.warning("  Could not fetch regions for %s / %s: %s", view_label, concept_name, exc)
            continue
        if not regions:
            logger.info("  No image found for %s / %s", view_label, concept_name)
            continue
        region = regions[0]
        img_url = region.get("image", {}).get("original_signed_url")
        if not img_url:
            continue

        bbox = region.get("region", {}).get("bbox") if crop else None
        ext = _img_ext(region)
        filepath = view_dir / f"{view_label}__{concept_name}{ext}"

        if bbox:
            ok = _save_cropped_image(client, img_url, bbox, filepath)
        else:
            ok = _save_image(client, img_url, filepath)
        if ok:
            downloaded += 1

    if downloaded == 0:
        _download_fallback(client, view_id, view_label, view_dir, count=1)


def _download_best_det_image(
    client: StudioClient,
    view_id: str,
    view_label: str,
    tag_ids: list[int],
    concept_map: dict[int, str],
    view_dir: Path,
):
    """DET: fetch one image that covers as many concepts as possible.

    Strategy: fetch a batch of regions, score each by how many distinct
    concept tags its annotations contain, and pick the best one.
    """
    try:
        regions = client.get_regions(view_id, page_size=50)
    except Exception as exc:
        logger.warning("  Could not fetch regions for %s: %s", view_label, exc)
        return

    if not regions:
        logger.info("  No regions for DET view %s", view_label)
        return

    tag_set = set(tag_ids)
    best_region = None
    best_score = -1

    for region in regions:
        # Each region has a list of annotations with tag IDs
        annotations = region.get("annotations", [])
        region_tags: set[int] = set()
        for ann in annotations:
            for t in ann.get("tags", []):
                tid = t if isinstance(t, int) else t.get("id")
                if tid is not None:
                    region_tags.add(tid)

        score = len(region_tags & tag_set)
        if score > best_score:
            best_score = score
            best_region = region
        if score == len(tag_set):
            break  # perfect match

    if best_region is None:
        _download_fallback(client, view_id, view_label, view_dir, count=1)
        return

    img_url = best_region.get("image", {}).get("original_signed_url")
    if not img_url:
        _download_fallback(client, view_id, view_label, view_dir, count=1)
        return

    # Name the file with the concepts it covers
    covered = []
    for ann in best_region.get("annotations", []):
        for t in ann.get("tags", []):
            tid = t if isinstance(t, int) else t.get("id")
            if tid in tag_set:
                covered.append(_sanitize(concept_map.get(tid, str(tid))))
    suffix = "_".join(covered[:4]) if covered else "sample"
    ext = _img_ext(best_region)
    filepath = view_dir / f"{view_label}__{suffix}{ext}"
    _save_image(client, img_url, filepath)

    logger.info("  DET %s: best image covers %d/%d concepts", view_label, best_score, len(tag_set))


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
        help="Studio API key (or set DEEPOMATIC_API_KEY env var).",
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
        client = StudioClient(
            org_slug=args.org,
            project_slug=args.project,
            token=args.token,
            api_key=args.api_key,
            cluster=args.cluster,
        )
        project_map = client.fetch_project_map()

        # Download sample images for each view
        images_dir = Path("images") / args.project
        _download_sample_images(client, project_map, images_dir)

    # Generate the PPTX
    output = generate_pptx(project_map, args.output, images_dir=images_dir)
    print(f"✅ Done → {output}")


if __name__ == "__main__":
    main()
