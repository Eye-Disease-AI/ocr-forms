# magi-ocr

A two-stage paper form pipeline: generate printable PDF forms from a JSON template, then scan and extract answers from filled/photographed forms.

## Requirements

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) for dependency management


Install Python dependencies:

```bash
uv sync
```

---

## Create a form

Generate a PDF (and PNG preview) from a JSON template:

```bash
uv run python create_form.py [template.json] [output.pdf]
```

Defaults:
- template: `config/form_template.json`
- output: `config/form.pdf` (PNG saved alongside as `config/form.png`)

Example:

```bash
uv run python create_form.py config/form_template.json outputs/myform.pdf
```

Print the PDF, distribute, and collect filled forms.

---

## Scan a single form

Scan one filled form image and print extracted answers as JSON:

```bash
uv run python scan.py <image_path> [template.json] [scan_config.json]
```

Example:

```bash
uv run python scan.py scans/form1.png
```

Output is printed to stdout:

```json
{
  "date": "8.03.2026",
  "q1": ["B"],
  "q2": [],
  "satisfaction": ["7"]
}
```

Text fields return the raw OCR string. Choice fields return a list of selected option labels (empty list if nothing marked).

A `debug/<image_stem>/` directory is created with:
- `warped.png` - perspective-corrected scan
- `annotated.png` - bounding boxes and detected answers overlaid
- `<field_id>/raw.png` - cropped region per field
- `<field_id>/scores.json` - OMR fill scores per bubble
- `results.json` - same JSON as stdout

---

## Batch scan a directory

Process all images and PDFs in the `scans/` directory:

```bash
uv run python batch_scan.py [template.json] [scan_config.json] [scans_dir] [output.json]
```

Defaults:
- template: `config/form_template.json`
- scan config: `config/scan_config.json`
- scans dir: `scans/`
- output: `results.json`

Supported input formats: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.pdf` (multi-page PDFs produce one entry per page).

Results are saved to `results.json`:

```json
{
  "form1.png": { "date": "8.03.2026", "q1": ["B"], ... },
  "form2.pdf_page1": { ... },
  "form2.pdf_page2": { ... }
}
```

---

## Configuration

### `config/form_template.json` - form appearance

```json
{
  "page": { "size": "A4", "margin_mm": 20 },
  "markers": { "size_mm": 15, "pad_mm": 5 },
  "text_box": { "width": 60, "height": 8 },
  "layout": { "row_spacing_mm": 12, "bubble_diameter_mm": 6, "option_spacing_mm": 12 },
  "questions": [
    { "type": "text",   "id": "date", "label": "Date" },
    { "type": "choice", "id": "q1",   "label": "Question 1", "options": ["A", "B", "C", "D"] },
    { "type": "choice", "id": "sat",  "label": "Satisfaction", "options": ["1","2","3","4","5","6","7","8","9","10"] }
  ]
}
```

**Question types:**
- `text` — freehand text box; returns raw OCR string
- `date` — text box; OCR output parsed to ISO date (`yyyy-mm-dd`), falls back to raw string on failure
- `number` — text box; OCR output parsed to `int` or `float`, returns `null` on failure
- `choice` — bubble selection (OMR); specify `"options": [...]`; returns a list of selected labels

### `config/scan_config.json` - scanning parameters

```json
{
  "upscaling_scale": 3,
  "omr_pixel_threshold": 150,
  "omr_fill_threshold": 0.25
}
```

| Parameter | Description |
|---|---|
| `upscaling_scale` | Output pixels per ReportLab point (~216 DPI at 3) |
| `omr_pixel_threshold` | Grayscale cutoff for counting dark pixels (0–255) |
| `omr_fill_threshold` | Minimum dark-pixel ratio to count a bubble as marked |

---

## How scanning works

1. **Perspective correction** — four ArUco markers (DICT_4X4_50) printed at the corners are detected and used to warp the image to the expected page dimensions.
2. **OMR (choice fields)** — each bubble region is thresholded; the ratio of dark pixels determines fill score; all options above the threshold are returned as a list.
3. **OCR (text fields)** — EasyOCR reads the handwritten box and returns the raw string. Any further interpretation (e.g. parsing a date) is left to the caller.
