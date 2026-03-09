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
  "date": "2026-03-08",
  "q1": "B",
  "q2": null,
  "satisfaction": "7"
}
```

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
  "form1": { "date": "2026-03-08", "q1": "B", ... },
  "form2_p1": { ... },
  "form2_p2": { ... }
}
```

---

## Configuration

### `config/form_template.json` - form appearance

```json
{
  "page": {
    "size": "A4",
    "margin_mm": 20
  },
  "markers": {
    "size_mm": 15,
    "pad_mm": 5
  },
  "layout": {
    "row_spacing_mm": 12,
    "bubble_diameter_mm": 6,
    "option_spacing_mm": 12
  },
  "questions": [
    { "type": "date",   "id": "date", "label": "Date" },
    { "type": "choice", "id": "q1",   "label": "Question 1", "options": ["A", "B", "C", "D"] },
    { "type": "scale",  "id": "sat",  "label": "Satisfaction", "range": [1, 10] }
  ]
}
```

**Question types:**
- `date` - handwritten date field (OCR), expected format: `d.mm.yyyy` or `dd.mm.yyyy`
- `choice` - multiple-choice bubbles (OMR), specify `"options"` list
- `scale` - numeric range bubbles (OMR), specify `"range": [start, end]`

### `config/scan_config.json` - scanning parameters

```json
{
  "scale": 3,
  "omr_pixel_threshold": 150,
  "omr_fill_threshold": 0.25,
  "omr_fill_threshold_choice": 0.5
}
```

| Parameter | Description |
|---|---|
| `scale` | Output pixels per ReportLab point (~216 DPI at 3) |
| `omr_pixel_threshold` | Grayscale cutoff for counting dark pixels (0-255) |
| `omr_fill_threshold` | Minimum fill ratio to count a bubble as marked (scale questions) |
| `omr_fill_threshold_choice` | Minimum fill ratio for choice questions (higher = stricter) |

---

## How scanning works

1. **Perspective correction** - four ArUco markers (DICT_4X4_50) printed at the
   corners are detected and used to warp the image to the expected page dimensions.
2. **OMR (bubbles)** - each bubble region is thresholded. The ratio of dark
   pixels determines fill score. Results: list of selected answers.
3. **OCR (dates)** - EasyOCR reads the handwritten date box. Digits are
   extracted and parsed to ISO format (`yyyy-mm-dd`).
