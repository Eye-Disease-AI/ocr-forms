import cv2
import easyocr
import numpy as np
import json
import os
import sys
from datetime import date
from lib.engine import FormParser

TEMPLATE = sys.argv[2] if len(sys.argv)>3 else "config/form_template.json"
IMAGE = sys.argv[1]

_stem = os.path.splitext(os.path.basename(IMAGE))[0]
DEBUG_DIR = os.path.join("debug", _stem)
os.makedirs(DEBUG_DIR, exist_ok=True)

with open(TEMPLATE) as f:
    cfg = json.load(f)

parser = FormParser(cfg)
layout = parser.compute()
W_pts, H_pts = parser.page_size()

img = cv2.imread(IMAGE)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

SCALE = 3  # output pixels per ReportLab point (~216 DPI for A4)


def warp_to_page(gray):

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)

    W_px = int(W_pts * SCALE)
    H_px = int(H_pts * SCALE)

    src = {}
    if ids is not None:
        for i, mid in enumerate(ids.flatten()):
            if int(mid) in (0, 1, 2, 3):
                src[int(mid)] = corners[i][0].mean(axis=0)

    if len(src) < 4:
        print(f"Warning: {len(src)}/4 markers detected; skipping perspective correction", file=sys.stderr)
        return cv2.resize(gray, (W_px, H_px)), SCALE

    dst = parser.marker_dst_px(SCALE)
    src_pts = np.float32([src[i] for i in [0, 1, 2, 3]])
    dst_pts = np.float32([dst[i] for i in [0, 1, 2, 3]])

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return cv2.warpPerspective(gray, M, (W_px, H_px)), SCALE


warped, scale = warp_to_page(gray)
cv2.imwrite(os.path.join(DEBUG_DIR, "warped.png"), warped)
annotated = cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR)

_ocr = easyocr.Reader(['en'], gpu=False, verbose=False)


def bbox_px(bbox):
    # Convert ReportLab points (bottom-left origin) to pixels (top-left origin)
    x1_rl, y1_rl, x2_rl, y2_rl = bbox
    return (
        int(x1_rl * scale),
        int((H_pts - y2_rl) * scale),
        int(x2_rl * scale),
        int((H_pts - y1_rl) * scale),
    )


def crop(bbox):
    x1, y1, x2, y2 = bbox_px(bbox)
    return warped[y1:y2, x1:x2]


def omr_score(region):

    _,th = cv2.threshold(region,150,255,cv2.THRESH_BINARY_INV)
    filled = np.sum(th==255)
    return filled / th.size


def parse_date(txt):
    digits = ''.join(c for c in txt if c.isdigit())
    try:
        if len(digits) == 7:   # d mm yyyy
            return date(int(digits[3:7]), int(digits[1:3]), int(digits[0])).isoformat()
        if len(digits) == 8:   # dd mm yyyy
            return date(int(digits[4:8]), int(digits[2:4]), int(digits[0:2])).isoformat()
    except ValueError:
        pass
    return txt  # fallback: return raw OCR text


results = {}

for field in layout:

    field_dir = os.path.join(DEBUG_DIR, field["id"])
    os.makedirs(field_dir, exist_ok=True)

    if field["type"] == "ocr":

        roi = crop(field["bbox"])
        cv2.imwrite(os.path.join(field_dir, "raw.png"), roi)

        raw_txt = ' '.join(_ocr.readtext(roi, detail=0)).strip()
        with open(os.path.join(field_dir, "raw_ocr.txt"), "w") as f:
            f.write(raw_txt)

        results[field["id"]] = parse_date(raw_txt)

        x1, y1, x2, y2 = bbox_px(field["bbox"])
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 100, 0), 2)
        cv2.putText(annotated, f"{field['id']}: {results[field['id']]}", (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 0), 1)

    if field["type"] == "omr":

        best = None
        best_score = 0

        for opt,box in field["options"].items():

            roi = crop(box)
            cv2.imwrite(os.path.join(field_dir, f"{opt}.png"), roi)
            score = omr_score(roi)

            if score > best_score:
                best_score = score
                best = opt

        results[field["id"]] = best

        for opt, box in field["options"].items():
            x1, y1, x2, y2 = bbox_px(box)
            color = (0, 210, 0) if opt == best else (200, 100, 0)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        first_box = next(iter(field["options"].values()))
        fx1, fy1, _, _ = bbox_px(first_box)
        cv2.putText(annotated, f"{field['id']}: {best}", (fx1, fy1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 0), 1)

cv2.imwrite(os.path.join(DEBUG_DIR, "annotated.png"), annotated)

with open(os.path.join(DEBUG_DIR, "results.json"), "w") as f:
    json.dump(results, f, indent=2)

print(json.dumps(results,indent=2))
