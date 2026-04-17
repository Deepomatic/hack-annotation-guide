# Annotation Guide Generator

Generate a skeleton `.pptx` annotation guide from a Deepomatic Studio project.

Connects to the Studio API, fetches the project's view tree (views, concepts, conditions), and produces a PowerPoint with:
- An **intro slide** showing the full view hierarchy
- **One slide per view** with parent, conditions, child views, all concepts, and a color-coded image placeholder (Detection=orange, Classification=green, Tagging=blue)

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
