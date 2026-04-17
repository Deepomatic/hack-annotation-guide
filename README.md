# Annotation Guide Generator

Generate a skeleton `.pptx` annotation guide from a Deepomatic Studio project.

Connects to the Studio API, fetches the project's view tree (views, concepts, conditions), downloads sample images from Studio annotations, and produces a PowerPoint presentation.

## What it generates

The output `.pptx` contains:

1. **Intro slide** — an overview of the full view hierarchy (all views listed with their type)
2. **Info slide per view** — showing parent view, activation conditions, child views, and the full list of concepts
3. **Concept slides per view** — up to 3 concepts per slide, with:
   - A **sample image** for each concept, fetched directly from the project's Studio annotations
   - The **concept name** displayed as a legend below each image
   - If a concept has no annotated image yet, the space is left blank with a "missing image" placeholder and the concept name still shown

For views that are children of a **detection** view, the images are **cropped to the detection bounding box** from the parent view, so you see only the detected region.

Image download strategy:
- **Tagging / Classification views**: 1 image per concept, filtered by tag
- **Detection views**: 1 image that covers as many concepts as possible

If a view has more than 3 concepts (e.g. 9), it will span multiple slides (3 slides of 3 concepts each). The slide title always shows the view name.

## Setup

```bash
# Install dependencies
uv sync

# Set your Studio API key
echo 'DEEPOMATIC_API_KEY=your_key_here' > .env
```

## Usage

```bash
source .env && export DEEPOMATIC_API_KEY
uv run python scripts/main.py --org <ORG_SLUG> --project <PROJECT_SLUG>
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--org` | Studio organisation slug | required* |
| `--project` | Studio project slug | required* |
| `--cluster` | Studio cluster: `eu` or `us` | `eu` |
| `--map` | Path to local project map JSON (alternative to --org/--project) | — |
| `--output` | Output `.pptx` file path | `annotation_guide.pptx` |

### Example

```bash
source .env && export DEEPOMATIC_API_KEY
uv run python scripts/main.py --org sandbox --project hackatono
```

## Skill integration

This project works as a skill for both **GitHub Copilot** (via `.github/copilot-instructions.md`) and **Claude Code** (via `SKILL.md`).

Trigger phrase: *"Create an annotation guide for the X org and the Y project"*
