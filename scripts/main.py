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
import json
import logging
import sys
from pathlib import Path

from pptx_generator import generate_pptx
from studio_api import StudioClient

logger = logging.getLogger(__name__)


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
    else:
        client = StudioClient(
            org_slug=args.org,
            project_slug=args.project,
            token=args.token,
            api_key=args.api_key,
        )
        project_map = client.fetch_project_map()

    # Generate the PPTX
    output = generate_pptx(project_map, args.output)
    print(f"✅ Done → {output}")


if __name__ == "__main__":
    main()
