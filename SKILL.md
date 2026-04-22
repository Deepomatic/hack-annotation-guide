---
name: hack-annotation-guide
description: Creates or modifies a PowerPoint annotation guide for a Deepomatic Studio project. Triggered when a user mentions "annotation guide". Can generate a new guide from scratch with custom options (number of examples, extra slides, colors, extra images) or modify an existing guide (add images, change colors, add/remove slides). Supports iterative refinement — ask clarifying questions and let the user adjust until they're happy.
---

# Annotation Guide Generator

Creates and customises `.pptx` annotation guides from Deepomatic Studio projects.

## Architecture

| File | Role |
|------|------|
| `scripts/pptx_helper.py` | Reusable PPTX primitives (shapes, text, images, grids, colors, layout) + image download helpers + high-level slide builders. |
| `scripts/studio_api.py` | Studio REST API client (`StudioClient`). |
| `scripts/build_pptx_slides.py` | Slide composition recipe — defines what slides appear and in what order. Imports builders from `pptx_helper`. |
| `scripts/main.py` | CLI entry point. Parses args, downloads images, calls `build_all_slides()` from the build script. |

## How the skill works

### Interaction style


- **Give the user an overview of what will be shown in the powerpoint** Before generating, tell the user what you will do. E.g. "I will fetch the views and concepts from your organization and project and create a powerpoint with an intro slide to each view and then one slide for each concept with N examples, based on the already existing annotated images in your project."
- **ALWAYS ASK CLARIFYING QUESTIONS** before generating. For example: "Do you want the default color scheme or something custom?", "Should I include all views or just a subset?", "How many example images per concept?".
- **Be prepared for iteration.** The user may say "looks good but change the colors" or "add an extra slide at the end". Apply incremental changes to the copied scripts and re-run.
- **The user may provide extra images** (as file paths or chat attachments). When they do, ask for the local file path if not obvious, then incorporate those images into the appropriate slides.

### Step 0 — Copy the scripts folder

**Every time** the user asks to create or modify an annotation guide, always start by copying the scripts into `scripts/generated/`:

```bash
mkdir -p scripts/generated
cp scripts/*.py scripts/generated/
```

All subsequent edits happen **only inside `scripts/generated/`**. DO NOT modify the original `scripts/` folder under any circomstances!

### Step 1 — Make changes (prefer minimal edits)

Apply changes in this order of preference:

1. **`build_pptx_slides.py`** — change slide order, add/remove slides, pass different color overrides to builders, add extra image slides. This is the primary file to edit.
2. **`main.py`** — change image download logic, add CLI flags, change how `build_all_slides()` is called.
3. **`pptx_helper.py`** — only if the user needs a new primitive or layout that doesn't exist yet (new shape type, new slide builder). Avoid if possible.
4. **`studio_api.py`** — only if the user needs a new API call. Almost never needed.

### Step 2 — Run the generation

Always run from the **project root** (where `pyproject.toml` lives). All paths below are relative to the project root. Use `uv run` with `--env-file` to load credentials automatically — no manual venv activation needed:

```bash
uv run --env-file .env scripts/generated/main.py --org <ORG_SLUG> --project <PROJECT_SLUG> --output <OUTPUT_PATH>
```

### Step 3 — Iterate

If the user wants changes, edit the files in `scripts/generated/` and re-run. Don't re-copy from `scripts/` unless the user asks to start over.

## Default CLI usage

```bash
uv run --env-file .env scripts/main.py --org <ORG_SLUG> --project <PROJECT_SLUG> --output <OUTPUT_PATH>
```

### Parameters
- `--org` (required): Studio organisation slug (e.g. `sandbox`)
- `--project` (required): Studio project slug (e.g. `hackatono`)
- `--cluster` (optional): Studio cluster — `eu` (default) or `us`
- `--output` (optional): Output file path (default: `annotation_guide.pptx`)
- `--views` (optional): Comma-separated list of view labels (case-insensitive) to include. When set, **only images for those views are downloaded** and only their slides are generated. This dramatically speeds up generation for partial guides. Example: `--views "Bottle,Label"`.
- `--api-key` (optional): Studio API key (or set `DEEPOMATIC_API_KEY` / `DEEPOMATIC_API_KEY_US` env var)

### Environment
The API key is selected based on `--cluster`:
- `DEEPOMATIC_API_KEY`: Studio API key for the **EU** cluster (default)
- `DEEPOMATIC_API_KEY_US`: Studio API key for the **US** cluster

Both are stored in `.env` at the project root. Example:

```dotenv
DEEPOMATIC_API_KEY=your_eu_key_here
DEEPOMATIC_API_KEY_US=your_us_key_here
```

## Available helpers from `pptx_helper`

### Primitives
`create_presentation`, `add_blank_slide`, `set_slide_bg_solid`, `set_slide_bg_gradient`, `add_textbox`, `add_rich_textbox`, `add_multiline_textbox`, `add_title`, `add_subtitle`, `add_rounded_rect`, `add_accent_bar`, `add_line`, `add_badge`, `add_image`, `add_image_placeholder`, `grid_positions`, `add_tree_connector`, `add_footer`, `add_bottom_strip`, `add_top_line`, `add_card`, `add_vertical_divider`

### Data helpers
`build_tree`, `build_concept_map`, `resolve_conditions`, `dfs_order`, `find_view_images`, `match_images`, `compute_tree_positions`, `kind_color`, `sanitize_name`

### Studio URL helper
`build_view_url(org_slug, project_slug, view_id, cluster="eu")` from `studio_api` — returns the Studio web UI URL for a view. Used by `build_info_slide` (via `build_all_slides`) to render a clickable "Open in Studio" link on every view description slide.

### High-level slide builders
`build_cover_slide`, `build_toc_slide`, `build_overview_slide`, `build_section_slide`, `build_info_slide`, `build_concept_recap_slide`, `build_concept_detail_slide`

All slide builders accept keyword color overrides (e.g. `bg_color=`, `accent_color=`, `title_color=`).
`build_info_slide` additionally accepts `view_url=` to render a clickable Studio link at the bottom of the slide. `build_all_slides` fills this in automatically for every view using `org_slug`, `project_slug` and `cluster`.

### Color constants
`NAVY`, `NAVY_LIGHT`, `WHITE`, `LIGHT_BG`, `MUTED`, `DIVIDER`, `DARK_TEXT`, `ORANGE`, `TEAL`, `SKY_BLUE`, `GREEN`, `RED`, `PLACEHOLDER_BG`

### Layout constants
`SLIDE_WIDTH`, `SLIDE_HEIGHT`, `MARGIN_LEFT`, `MARGIN_RIGHT`, `MARGIN_TOP`, `MARGIN_BOTTOM`, `CONTENT_LEFT`, `CONTENT_TOP`, `CONTENT_WIDTH`, `CONTENT_HEIGHT`, `TITLE_LEFT`, `TITLE_TOP`, `TITLE_WIDTH`, `TITLE_HEIGHT`

## Examples

Generate default guide:
```bash
uv run --env-file .env scripts/main.py --org sandbox --project hackatono
```

Generate for US cluster:
```bash
uv run --env-file .env scripts/main.py --org sandbox --project hackatono --cluster us
```

Generate only for specific views (skips image downloads for other views — much faster):
```bash
uv run --env-file .env scripts/main.py --org sandbox --project hackatono --views "Bottle,Label"
```

> **Tip for the agent:** when the user says they only want certain views, pass them via `--views` instead of editing `build_pptx_slides.py`. This avoids downloading images for excluded views.
