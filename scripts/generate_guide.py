#!/usr/bin/env python
"""
Annotation Guide Generator — CLI entry point.

Fetches the view architecture from a Deepomatic Studio project and
generates a .pptx annotation guide.

Usage:
    source .env && export DEEPOMATIC_API_KEY
    uv run scripts/generate_guide.py --org <ORG_SLUG> --project <PROJECT_SLUG>
"""

import argparse
import importlib.util
import logging
import sys
from pathlib import Path

from pptx_helper import create_presentation, download_sample_images
from studio_api import StudioClient

logger = logging.getLogger(__name__)


def _load_build_module(script_path: str | None):
    """Dynamically import a build script and return its build_all_slides function.

    If *script_path* is None, uses the default build_pptx_slides module.
    This allows the skill to point to a modified copy of the build script.
    """
    if script_path is None:
        from build_pptx_slides import build_all_slides
        return build_all_slides

    path = Path(script_path).resolve()
    if not path.is_file():
        logger.error("Build script not found: %s", path)
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("custom_build", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "build_all_slides"):
        logger.error("Build script %s has no build_all_slides() function.", path)
        sys.exit(1)

    return mod.build_all_slides


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a .pptx annotation guide from a Deepomatic Studio project."
    )
    parser.add_argument(
        "--org", required=True, metavar="ORG_SLUG",
        help="Studio organisation slug (e.g. sandbox).",
    )
    parser.add_argument(
        "--project", required=True, metavar="PROJECT_SLUG",
        help="Studio project slug (e.g. hackatono).",
    )
    parser.add_argument(
        "--cluster", default="eu", choices=["eu", "us"],
        help="Studio cluster: 'eu' (default) or 'us'.",
    )
    parser.add_argument(
        "--output", default="annotation_guide.pptx", metavar="OUTPUT_PPTX",
        help="Destination .pptx file (default: annotation_guide.pptx).",
    )
    parser.add_argument(
        "--script", default=None, metavar="BUILD_SCRIPT",
        help="Path to a custom build script (default: build_pptx_slides.py). "
             "Used by the skill to point to a modified copy.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    args = _parse_args(argv)

    # 1. Fetch project map from Studio API
    client = StudioClient(
        org_slug=args.org,
        project_slug=args.project,
        cluster=args.cluster,
    )
    project_map = client.fetch_project_map()

    # 2. Download sample images
    images_dir = Path("images") / args.project
    download_sample_images(client, project_map, images_dir)

    # 3. Load the build script (default or custom)
    build_all_slides = _load_build_module(args.script)

    # 4. Generate the PPTX
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prs = create_presentation()
    build_all_slides(
        prs,
        project_map,
        images_dir=images_dir,
        org_slug=args.org,
        project_slug=args.project,
    )
    prs.save(str(output_path))
    print(f"\u2705 Done \u2192 {output_path}  ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
