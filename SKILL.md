---
name: hack-annotation-guide
description: Creates or modifies a PowerPoint annotation guide for a Deepomatic Studio project. Triggered when a user mentions "annotation guide". Can generate a new guide from scratch with custom options (number of examples, extra slides, colors, extra images) or modify an existing guide (add images, change colors, add/remove slides). Supports iterative refinement — ask clarifying questions and let the user adjust until they're happy.
---

# Annotation Guide Generator

Creates and customises `.pptx` annotation guides from Deepomatic Studio projects.

## Architecture

| File | Role | Stable? |
|------|------|---------|
| `scripts/pptx_helper.py` | Reusable PPTX primitives (shapes, text, images, grids, colors, layout) + image download helpers. **Never modify this file.** | ✅ |
| `scripts/studio_api.py` | Studio REST API client (`StudioClient`). **Never modify this file.** | ✅ |
| `scripts/build_pptx_slides.py` | Slide composition recipe — defines what slides appear and in what order. **This is the file you copy and edit to customise the guide.** | ❌ (template) |
| `scripts/generate_guide.py` | Thin CLI entry point. Accepts `--script` to use a custom build script. | ✅ |

## How the skill works

### Interaction style

- **Always ask clarifying questions** before generating. For example: "Do you want the default color scheme or something custom?", "Should I include all views or just a subset?", "How many example images per concept?".
- **Be prepared for iteration.** The user may say "looks good but change the colors" or "add an extra slide at the end". Apply incremental changes to the copied build script and re-run.
- **The user may provide extra images** (as file paths or chat attachments). When they do, ask for the local file path if not obvious, then incorporate those images into the appropriate slides.

### Mode 1: Create a new annotation guide

When the user asks to **create**, **generate**, or **build** an annotation guide:

1. **Copy the template**: Copy `scripts/build_pptx_slides.py` → `scripts/generated/build_pptx_slides_custom.py`
2. **Modify the copy** based on user preferences:
   - Number of example images per slide (change the slice limits in slide builder functions)
   - Add or remove slide types (e.g., skip bad examples, add a custom text slide)
   - Change accent colors (modify `kind_color()` or individual color constants)
   - Add extra slides by writing new `build_xxx()` functions and calling them from `build_all_slides()`
   - Incorporate user-provided extra images by adding logic to load them from the specified path
3. **Run the command**:
   ```bash
   cd /home/emma/Documents/skills/hack-annotation-guide
   source .env && export DEEPOMATIC_API_KEY
   uv run python scripts/generate_guide.py --org <ORG_SLUG> --project <PROJECT_SLUG> --output <OUTPUT_PATH> --cluster <CLUSTER> --script scripts/generated/build_pptx_slides_custom.py
   ```

### Mode 2: Modify an existing annotation guide

When the user asks to **modify**, **update**, or **change** an existing annotation guide:

1. **Copy the template**: Copy `scripts/build_pptx_slides.py` → `scripts/generated/build_pptx_slides_custom.py`
2. **Modify the copy** based on user requests:
   - Add images from a local folder: update `find_view_images()` or add logic to scan the user's specified folder
   - Change colors: modify color constants or `kind_color()`
   - Add/remove/reorder slides: edit `build_all_slides()`
   - Add specific content to slides (text, annotations, instructions)
3. **Run the command** with `--script` pointing to the modified copy (same as above)

### Step 3 — Iterate

If the user wants changes, edit `scripts/generated/build_pptx_slides_custom.py` and re-run. Don't re-copy from `scripts/build_pptx_slides.py` unless the user asks to start over.

### Important rules for modifying the build script

- **Always import from `pptx_helper`** — never use raw `python-pptx` directly in the build script
- **Always keep the `build_all_slides(prs, project_map, *, images_dir, org_slug, project_slug)` signature** — `generate_guide.py` calls this function
- The copy goes in `scripts/generated/` to keep the workspace clean
- Available helpers from `pptx_helper`: `add_blank_slide`, `set_slide_bg_solid`, `set_slide_bg_gradient`, `add_textbox`, `add_rich_textbox`, `add_multiline_textbox`, `add_title`, `add_subtitle`, `add_rounded_rect`, `add_accent_bar`, `add_line`, `add_badge`, `add_image`, `add_image_placeholder`, `grid_positions`, `add_tree_connector`, `add_footer`, `add_bottom_strip`, `add_top_line`, `create_presentation`
- Available color constants: `NAVY`, `NAVY_LIGHT`, `WHITE`, `LIGHT_BG`, `MUTED`, `DIVIDER`, `DARK_TEXT`, `ORANGE`, `TEAL`, `SKY_BLUE`, `GREEN`, `RED`, `PLACEHOLDER_BG`
- Available layout constants: `SLIDE_WIDTH`, `SLIDE_HEIGHT`, `MARGIN_LEFT`, `MARGIN_RIGHT`, `MARGIN_TOP`, `MARGIN_BOTTOM`, `CONTENT_LEFT`, `CONTENT_TOP`, `CONTENT_WIDTH`, `CONTENT_HEIGHT`, `TITLE_LEFT`, `TITLE_TOP`, `TITLE_WIDTH`, `TITLE_HEIGHT`

## Default CLI usage

```bash
cd /home/emma/Documents/skills/hack-annotation-guide
source .env && export DEEPOMATIC_API_KEY
uv run python scripts/generate_guide.py --org <ORG_SLUG> --project <PROJECT_SLUG> --output <OUTPUT_PATH> --cluster <CLUSTER>
```

### Parameters
- `--org` (required): Studio organisation slug (e.g. `sandbox`)
- `--project` (required): Studio project slug (e.g. `hackatono`)
- `--cluster` (optional): Studio cluster — `eu` (default) or `us`
- `--output` (optional): Output file path (default: `annotation_guide.pptx`)
- `--script` (optional): Path to a custom build script (default: `build_pptx_slides.py`)

### Environment
- `DEEPOMATIC_API_KEY`: Studio API key (stored in `.env` file)

## Available helpers from `pptx_helper`

### Primitives
`create_presentation`, `add_blank_slide`, `set_slide_bg_solid`, `set_slide_bg_gradient`, `add_textbox`, `add_rich_textbox`, `add_multiline_textbox`, `add_title`, `add_subtitle`, `add_rounded_rect`, `add_accent_bar`, `add_line`, `add_badge`, `add_image`, `add_image_placeholder`, `grid_positions`, `add_tree_connector`, `add_footer`, `add_bottom_strip`, `add_top_line`, `add_card`, `add_vertical_divider`

### Data helpers
`build_tree`, `build_concept_map`, `resolve_conditions`, `dfs_order`, `find_view_images`, `match_images`, `compute_tree_positions`, `kind_color`, `sanitize_name`

### High-level slide builders
`build_cover_slide`, `build_toc_slide`, `build_overview_slide`, `build_section_slide`, `build_info_slide`, `build_concept_recap_slide`, `build_concept_detail_slide`

All slide builders accept keyword color overrides (e.g. `bg_color=`, `accent_color=`, `title_color=`).

### Color constants
`NAVY`, `NAVY_LIGHT`, `WHITE`, `LIGHT_BG`, `MUTED`, `DIVIDER`, `DARK_TEXT`, `ORANGE`, `TEAL`, `SKY_BLUE`, `GREEN`, `RED`, `PLACEHOLDER_BG`

### Layout constants
`SLIDE_WIDTH`, `SLIDE_HEIGHT`, `MARGIN_LEFT`, `MARGIN_RIGHT`, `MARGIN_TOP`, `MARGIN_BOTTOM`, `CONTENT_LEFT`, `CONTENT_TOP`, `CONTENT_WIDTH`, `CONTENT_HEIGHT`, `TITLE_LEFT`, `TITLE_TOP`, `TITLE_WIDTH`, `TITLE_HEIGHT`

## Examples

Generate default guide:
```bash
uv run python scripts/generate_guide.py --org sandbox --project hackatono
```

Generate with custom build script:
```bash
uv run python scripts/generate_guide.py --org sandbox --project hackatono --script scripts/generated/build_pptx_slides_custom.py
```

Generate for US cluster:
```bash
uv run python scripts/generate_guide.py --org sandbox --project hackatono --cluster us
```
