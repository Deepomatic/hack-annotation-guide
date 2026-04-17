# Annotation Guide Generator Skill

This workspace contains a skill that generates annotation guide PowerPoint files from Deepomatic Studio projects.

## When to use

When a user asks to **create**, **generate**, or **build** an annotation guide for a Deepomatic Studio project.

## How to run

```bash
cd /home/emma/Documents/skills/hack-annotation-guide
source .env && export DEEPOMATIC_API_KEY
uv run python scripts/main.py --org <ORG_SLUG> --project <PROJECT_SLUG>
```

### Parameters
- `--org`: Studio organisation slug (e.g. `sandbox`)
- `--project`: Studio project slug (e.g. `hackatono`)
- `--output`: Output .pptx file path (default: `annotation_guide.pptx`)
- `--map`: Alternative — path to a local project map JSON instead of fetching from API

### Environment variable
- `DEEPOMATIC_API_KEY` must be set (loaded from `.env` file in the skill directory)

## Example

User says: *"Create an annotation guide for the sandbox org and the hackatono project"*

Run:
```bash
cd /home/emma/Documents/skills/hack-annotation-guide
source .env && export DEEPOMATIC_API_KEY
uv run python scripts/main.py --org sandbox --project hackatono
```

Output: `annotation_guide.pptx` — a PowerPoint with one intro slide + one slide per view showing concepts, conditions, and image placeholders.
