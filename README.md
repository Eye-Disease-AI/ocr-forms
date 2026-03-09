# magi-ocr

A two-stage paper form pipeline: generate printable PDF forms from a JSON template, then scan and extract answers from filled/photographed forms.

## Requirements

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) for dependency management
- poppler (for PDF scanning): `sudo pacman -S poppler` / `sudo apt install poppler-utils`

```bash
uv sync
```

---

## Create a form

```bash
uv run python create_form.py [TEMPLATE] [OUTPUT]
```

| Argument | Default | Description |
|---|---|---|
| `TEMPLATE` | `config/form_template.json` | Form template JSON |
| `OUTPUT` | `config/form.pdf` | Output PDF path (PNG saved alongside) |

```bash
uv run python create_form.py --help
uv run python create_form.py config/form_template.json outputs/myform.pdf
```

---

## Scan a single form

```bash
uv run python scan.py IMAGE [OPTIONS]
```

| Argument / Option | Default | Description |
|---|---|---|
| `IMAGE` | *(required)* | Path to the scanned form image |
| `--template` | `config/form_template.json` | Form template JSON |
| `--scan-config` | `config/scan_config.json` | Scan config JSON |

```bash
uv run python scan.py scans/form1.png
uv run python scan.py scans/form1.png --template config/form_template.json
```

Output is printed to stdout:

```json
{
  "date":         {"date": "2026-03-08"},
  "q1":           {"choice": ["B"]},
  "satisfaction": {"choice": ["7"]}
}
```

A `debug/<image_stem>/` directory is also written with:
- `warped.png` — perspective-corrected scan
- `annotated.png` — bounding boxes and detected answers overlaid
- `<field_id>/raw.png` — cropped region per field
- `<field_id>/scores.json` — fill scores per bubble
- `results.json` — same as stdout

---

## Batch scan a directory

```bash
uv run python batch_scan.py [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--template` | `config/form_template.json` | Form template JSON |
| `--scan-config` | `config/scan_config.json` | Scan config JSON |
| `--scans-dir` | `scans/` | Directory of forms to scan |
| `--output` | `results.json` | Output JSON file |

```bash
uv run python batch_scan.py
uv run python batch_scan.py --scans-dir scans/ --output results.json
```

Supported formats: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.pdf` (multi-page PDFs produce one entry per page).

---

## Configuration

### `config/form_template.json`

```json
{
  "page": {
    "size": "A4",
    "margin_x_mm": 25,
    "margin_y_mm": 25,
    "font": "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "font_size": 11
  },
  "defaults": {
    "marker_size_mm": 15,
    "marker_pad_mm": 5,
    "text_box_width_mm": 60,
    "text_box_height_mm": 8,
    "question_spacing_mm": 12,
    "label_spacing_mm": 6,
    "bubble_diameter_mm": 6,
    "option_spacing_mm": 10
  },
  "questions": [
    { "type": "date",   "id": "date", "label": "Date" },
    { "type": "text",   "id": "name", "label": "Name", "text_box_width_mm": 120 },
    { "type": "number", "id": "age",  "label": "Age",  "text_box_width_mm": 30 },
    { "type": "choice", "id": "q1",   "label": "Question 1", "options": ["A", "B", "C", "D"] },
    { "type": "choice", "id": "q2",   "label": "Question 2", "options": ["Yes", "No", "Maybe"],
      "direction": "vertical" },
    { "type": "choice", "id": "sat",  "label": "Satisfaction",
      "options": ["1","2","3","4","5","6","7","8","9","10"] }
  ]
}
```

**`page`**

| Key | Description |
|---|---|
| `size` | Page size (`"A4"`) |
| `margin_x_mm` | Left margin |
| `margin_y_mm` | Top margin |
| `font` | Path to a TTF font file, or a built-in ReportLab font name (`"Helvetica"`) |
| `font_size` | Font size in points |

**`defaults`** — applied to all questions; any key can be overridden per question by adding it directly to the question object.

| Key | Description |
|---|---|
| `marker_size_mm` | ArUco marker size |
| `marker_pad_mm` | Padding between marker and page edge |
| `text_box_width_mm` | Width of text input boxes |
| `text_box_height_mm` | Height of text input boxes |
| `question_spacing_mm` | Gap from bottom of one question's input to the next question's label |
| `label_spacing_mm` | Gap from question label down to its input |
| `bubble_diameter_mm` | Diameter of OMR bubbles |
| `option_spacing_mm` | Spacing between bubbles (horizontal: min spacing; vertical: between centres) |

**Question types:**

| Type | Input | Output |
|---|---|---|
| `text` | Freehand text box | Raw OCR string |
| `date` | Text box | ISO date `yyyy-mm-dd`, falls back to raw string |
| `number` | Text box | `int` or `float`, `null` on failure |
| `choice` | Bubbles; `"options": [...]`; add `"direction": "vertical"` for stacked layout | List of selected labels |

---

### `config/scan_config.json`

```json
{
  "upscaling_scale": 3,
  "bubble_pixel_threshold": 150,
  "bubble_fill_threshold": 0.25
}
```

| Parameter | Description |
|---|---|
| `upscaling_scale` | Pixels per ReportLab point for the warped output (~216 DPI at 3) |
| `bubble_pixel_threshold` | Grayscale cutoff for dark-pixel counting (0–255) |
| `bubble_fill_threshold` | Minimum dark-pixel ratio to count a bubble as marked |

---

## How scanning works

1. **Perspective correction** — four ArUco markers (DICT_4X4_50) at the corners are detected and used to warp the photo to the exact page dimensions.
2. **Choice fields (OMR)** — each bubble region is thresholded; dark-pixel ratio is the fill score; all options above `bubble_fill_threshold` are returned as a list.
3. **Text fields (OCR)** — EasyOCR reads the handwritten box and returns the raw string, then a type-specific parser (`date`, `number`, or `text`) post-processes it.
