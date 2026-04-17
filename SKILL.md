---
name: hack-annotation-guide
description: Creates or modifies a PowerPoint annotation guide for a Deepomatic Studio project. Triggered when a user mentions "annotation guide". Can generate a new guide from scratch with custom options (number of examples, extra slides, colors) or modify an existing guide (add images, change colors, add/remove slides).
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

### Mode 1: Create a new annotation guide

When the user asks to **create**, **generate**, or **build** an annotation guide:

1. **Copy the template**: Copy `scripts/build_pptx_slides.py` → `scripts/generated/build_pptx_slides_custom.py`
2. **Modify the copy** based on user preferences:
   - Number of example images per slide (change the slice limits in slide builder functions)
   - Add or remove slide types (e.g., skip bad examples, add a custom text slide)
   - Change accent colors (modify `kind_color()` or individual color constants)
   - Add extra slides by writing new `build_xxx()` functions and calling them from `build_all_slides()`
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
