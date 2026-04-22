# Annotation Guide Generator

Generate a `.pptx` annotation guide from a Deepomatic Studio project.

Connects to the Studio API, fetches the project's view tree (views, concepts, conditions), downloads sample images from Studio annotations, and produces a PowerPoint presentation.

## What it generates

The output `.pptx` contains:

1. **Cover slide** — project name with gradient background and accent bars
2. **Table of Contents** — lists all root views with kind badges (Detection / Classification / Tagging)
3. **Views Overview** — tree diagram of the full view hierarchy
4. **Per-view slides**:
   - **Section divider** (for root views) — navy gradient with kind badge
   - **Info slide** — key-value metadata card (parent, activation conditions, children, concepts)
   - **Concept recap** — grid overview of all concepts in the view with sample images
   - **Concept detail** — split slide with good examples (left) and bad examples (right) per concept

View types are color-coded: **Detection** (orange), **Classification** (teal), **Tagging** (sky blue).

For views that are children of a **detection** view, sample images are **cropped to the detection bounding box**.

## Project structure

```
scripts/
├── main.py                 # CLI entry point (arg parsing, image download, orchestration)
├── build_pptx_slides.py    # Slide composition recipe (what slides, in what order)
├── pptx_helper.py          # PPTX primitives, layout constants, colors, slide builders
└── studio_api.py           # Studio REST API client
```

## Setup

```bash
# Install dependencies
uv sync

# Set your Studio API keys (one per cluster you use)
cat > .env <<EOF
DEEPOMATIC_API_KEY_EU=your_eu_key_here
DEEPOMATIC_API_KEY_US=your_us_key_here
EOF
```

The correct key is picked automatically based on `--cluster` (defaults to `eu`). A generic `DEEPOMATIC_API_KEY` is still honoured as a fallback.

## Usage

All commands are run from the project root:

```bash
uv run --env-file .env scripts/main.py --org <ORG_SLUG> --project <PROJECT_SLUG>
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--org` | Studio organisation slug | required* |
| `--project` | Studio project slug | required with `--org` |
| `--map` | Path to local project map JSON (alternative to `--org`/`--project`) | — |
| `--cluster` | Studio cluster: `eu` or `us` | `eu` |
| `--output` | Output `.pptx` file path | `annotation_guide.pptx` |
| `--token` | Studio Bearer token (or set `DEEPOMATIC_TOKEN_EU` / `DEEPOMATIC_TOKEN_US`) | — |
| `--api-key` | Studio API key (or set `DEEPOMATIC_API_KEY_EU` / `DEEPOMATIC_API_KEY_US`) | — |

\* Either `--org` + `--project` or `--map` is required.

### Examples

```bash
# Default guide
uv run --env-file .env scripts/main.py --org sandbox --project hackatono

# Custom output path
uv run --env-file .env scripts/main.py --org sandbox --project hackatono --output /tmp/guide.pptx

# US cluster
uv run --env-file .env scripts/main.py --org sandbox --project hackatono --cluster us

# From a local map JSON
uv run --env-file .env scripts/main.py --map project_map.json
```

## Skill integration

This project works as an AI coding assistant skill (via `SKILL.md`).

Trigger phrase: *"Create an annotation guide for the X org and the Y project"*

The skill supports customisation (colors, slides, extra images) and iterative refinement.
