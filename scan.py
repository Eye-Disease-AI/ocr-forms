import cv2
import json
import os
import sys
from lib.scanner import FormScanner

TEMPLATE  = sys.argv[2] if len(sys.argv) > 2 else "config/form_template.json"
SCAN_CFG  = sys.argv[3] if len(sys.argv) > 3 else "config/scan_config.json"
IMAGE = sys.argv[1]

with open(TEMPLATE) as f:
    cfg = json.load(f)

with open(SCAN_CFG) as f:
    scan_cfg = json.load(f)

stem = os.path.splitext(os.path.basename(IMAGE))[0]
debug_dir = os.path.join("debug", stem)
os.makedirs(debug_dir, exist_ok=True)

img = cv2.imread(IMAGE)

results = FormScanner(cfg, scan_cfg).scan(img, debug_logs_dir=debug_dir)
print(json.dumps(results, indent=2))
