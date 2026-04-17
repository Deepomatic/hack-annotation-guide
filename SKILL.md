---
name: hack-annotation-guide
description: Generates an annotation guide PowerPoint (.pptx) from a Deepomatic Studio project. Use when user asks to create, generate, or build an annotation guide for a Studio project. Requires an org slug and project slug (e.g. "create annotation guide for the sandbox org and the hackatono project").
---

# Annotation Guide Generator

Generates a skeleton `.pptx` annotation guide from a Deepomatic Studio project's view architecture.

## What it does

1. Connects to the Studio API and fetches the project's view tree (root views, child views, concepts/tags per view)
2. Generates a PowerPoint with:
   - An **intro slide** showing the full view hierarchy as a tree
   - **One slide per view** with: parent view, activation conditions, child views, all concepts/tags, and an image placeholder (color-coded by view type)
3. View types are color-coded: **Detection** (orange), **Classification** (green), **Tagging** (blue)

## Usage

```bash
cd /home/emma/Documents/skills/hack-annotation-guide
source .env && export DEEPOMATIC_API_KEY
uv run python scripts/main.py --org <ORG_SLUG> --project <PROJECT_SLUG> --output <OUTPUT_PATH>
```

### Parameters
- `--org` (required): Studio organisation slug (e.g. `sandbox`)
- `--project` (required): Studio project slug (e.g. `hackatono`)
- `--cluster` (optional): Studio cluster — `eu` (default) or `us` (for US projects on studio.us1.deepomatic.com)
- `--output` (optional): Output file path (default: `annotation_guide.pptx`)
- `--map` (alternative to --org/--project): Path to a local project map JSON file

### Environment
- `DEEPOMATIC_API_KEY`: Studio API key (stored in `.env` file)

## Examples

Generate guide for the hackatono project:
```bash
uv run python scripts/main.py --org sandbox --project hackatono
```

Generate guide with custom output path:
```bash
uv run python scripts/main.py --org sandbox --project hackatono --output /tmp/hackatono_guide.pptx
```
