import cv2
import json
import numpy as np
import os
import sys
from pdf2image import convert_from_path
from lib.scanner import FormScanner

TEMPLATE  = sys.argv[1] if len(sys.argv) > 1 else "config/form_template.json"
SCAN_CFG  = sys.argv[2] if len(sys.argv) > 2 else "config/scan_config.json"
SCANS_DIR = sys.argv[3] if len(sys.argv) > 3 else "scans"
OUTPUT    = sys.argv[4] if len(sys.argv) > 4 else "results.json"

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
PDF_EXTS   = {'.pdf'}

with open(TEMPLATE) as f:
    cfg = json.load(f)

with open(SCAN_CFG) as f:
    scan_cfg = json.load(f)

scanner = FormScanner(cfg, scan_cfg)
all_results = {}

for filename in sorted(os.listdir(SCANS_DIR)):
    stem, ext = os.path.splitext(filename)
    ext = ext.lower()
    path = os.path.join(SCANS_DIR, filename)

    if ext in IMAGE_EXTS:
        img = cv2.imread(path)
        frames = [cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)]
        keys = [stem]

    elif ext in PDF_EXTS:
        pages = convert_from_path(path)
        frames = [cv2.cvtColor(np.array(p), cv2.COLOR_RGB2GRAY) for p in pages]
        keys = [f"{stem}_p{i+1}" if len(pages) > 1 else stem for i in range(len(pages))]

    else:
        continue

    for key, gray in zip(keys, frames):
        print(f"Scanning {key} ...", file=sys.stderr)
        debug_dir = os.path.join("debug", key)
        os.makedirs(debug_dir, exist_ok=True)
        all_results[key] = scanner.scan(gray, debug_logs_dir=debug_dir)

with open(OUTPUT, "w") as f:
    json.dump(all_results, f, indent=2)

print(f"Processed {len(all_results)} form(s) → {OUTPUT}")
