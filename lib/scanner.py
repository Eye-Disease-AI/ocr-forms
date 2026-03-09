import easyocr
import json
import numpy as np
import os
from datetime import date
from lib.parser import FormParser
from .common import *

_SCAN_DEFAULTS = {
    "scale": 3,
    "omr_pixel_threshold": 150,
    "omr_fill_threshold": 0.5,
}


def _warp_image(image: np.ndarray, parser: FormParser, page_width, page_height, upscaling_scale) -> np.ndarray:
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(image)

    W_px = int(page_width * upscaling_scale)
    H_px = int(page_height * upscaling_scale)

    src = {}
    if ids is not None:
        for i, mark_id in enumerate(ids.flatten()):
            if int(mark_id) in range(4):
                src[int(mark_id)] = corners[i][0].mean(axis=0)

    if len(src) < 4:
        raise Exception(f"Error: only {len(src)}/4 markers detected.")
        

    dst = parser.marker_coordinates(upscaling_scale)
    src_pts = np.float32([src[i] for i in range(4)])
    dst_pts = np.float32([dst[i] for i in range(4)])

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return cv2.warpPerspective(image, M, (W_px, H_px))


def _bbox_to_coordinates(bbox, H_pts, scale):
    x1_rl, y1_rl, x2_rl, y2_rl = bbox
    return (
        int(x1_rl * scale),
        int((H_pts - y2_rl) * scale),
        int(x2_rl * scale),
        int((H_pts - y1_rl) * scale),
    )


def _cutout_bbox(warped: np.ndarray, bbox, H_pts, scale) -> np.ndarray:
    x1, y1, x2, y2 = _bbox_to_coordinates(bbox, H_pts, scale)
    return warped[y1:y2, x1:x2]


def _omr_score(region: np.ndarray, pixel_threshold: int) -> float:
    _, th = cv2.threshold(region, pixel_threshold, 255, cv2.THRESH_BINARY_INV)
    filled = np.sum(th == 255)
    return filled / th.size


def _parse_text(txt: str) -> str:
    return txt


def _parse_date(txt: str) -> str:
    digits = ''.join(c for c in txt if c.isdigit())
    try:
        if len(digits) == 7:   # d mm yyyy
            return date(int(digits[3:7]), int(digits[1:3]), int(digits[0])).isoformat()
        if len(digits) == 8:   # dd mm yyyy
            return date(int(digits[4:8]), int(digits[2:4]), int(digits[0:2])).isoformat()
    except ValueError:
        pass
    return txt


def _parse_number(txt: str) -> int | float | None:
    digits = ''.join(c for c in txt if c.isdigit() or c in '.,-')
    normalized = digits.replace(',', '.')
    try:
        f = float(normalized)
        return int(f) if f == int(f) else f
    except ValueError:
        return None


_PARSERS = {
    "text":   _parse_text,
    "date":   _parse_date,
    "number": _parse_number,
}


class FormScanner:
    def __init__(self, form_config: dict, scan_config=None):
        self.scan_config = {**_SCAN_DEFAULTS, **(scan_config or {})}
        self.parser = FormParser(form_config)
        self.layout = self.parser.compute_field_coordinates()
        self.page_width, self.page_height = self.parser.page_size()
        self._ocr = easyocr.Reader(['en'], gpu=False, verbose=False)

    def scan(self, image: np.ndarray, debug_logs_dir=None):
        gray_image =  cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        warped = _warp_image(gray_image, self.parser, self.page_width, self.page_height, self.scan_config["upscaling_scale"])

        if debug_logs_dir:
            cv2.imwrite(os.path.join(debug_logs_dir, "warped.png"), warped)

        annotated_debug_image: np.ndarray = cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR) if debug_logs_dir else None
        results = {}

        for field in self.layout:
            debug_logs_field_dir = os.path.join(debug_logs_dir, field["id"]) if debug_logs_dir else None
            if debug_logs_field_dir:
                os.makedirs(debug_logs_field_dir, exist_ok=True)

            if field["type"] == "text":
                roi = _cutout_bbox(warped, field["bbox"], self.page_height, self.scan_config["upscaling_scale"])
                if debug_logs_field_dir:
                    cv2.imwrite(os.path.join(debug_logs_field_dir, "raw.png"), roi)

                raw_txt = ' '.join(self._ocr.readtext(roi, detail=0)).strip()
                if debug_logs_field_dir:
                    with open(os.path.join(debug_logs_field_dir, "raw_ocr.txt"), "w") as f:
                        f.write(raw_txt)

                results[field["id"]] = {field["parse"]: _PARSERS[field["parse"]](raw_txt)}

                if annotated_debug_image is not None:
                    x1, y1, x2, y2 = _bbox_to_coordinates(field["bbox"], self.page_height, self.scan_config["upscaling_scale"])
                    cv2.rectangle(annotated_debug_image, (x1, y1), (x2, y2), (255, 100, 0), 2)
                    cv2.putText(annotated_debug_image, f"{field['id']}: {_PARSERS[field['parse']](raw_txt)}", (x1, y1 - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 0), 1)

            if field["type"] == "omr":
                scores = {}
                for opt, box in field["options"].items():
                    roi = _cutout_bbox(warped, box, self.page_height, self.scan_config["upscaling_scale"])
                    if debug_logs_field_dir:
                        cv2.imwrite(os.path.join(debug_logs_field_dir, f"{opt}.png"), roi)
                    scores[opt] = _omr_score(roi, self.scan_config["omr_pixel_threshold"])

                if debug_logs_field_dir:
                    with open(os.path.join(debug_logs_field_dir, "scores.json"), "w") as f:
                        json.dump(scores, f, indent=2)

                selected = [opt for opt, s in scores.items() if s > self.scan_config["omr_fill_threshold"]]
            
                results[field["id"]] = {"choice": selected}

                if annotated_debug_image is not None:
                    for opt, box in field["options"].items():
                        x1, y1, x2, y2 = _bbox_to_coordinates(box, self.page_height, self.scan_config["upscaling_scale"])
                        if opt in selected:
                            color = (0, 210, 0)
                        else:
                            color = (200, 100, 0)
                        cv2.rectangle(annotated_debug_image, (x1, y1), (x2, y2), color, 2)

                    first_box = next(iter(field["options"].values()))
                    fx1, fy1, _, _ = _bbox_to_coordinates(first_box, self.page_height, self.scan_config["upscaling_scale"])
                    cv2.putText(annotated_debug_image, f"{field['id']}: {selected}", (fx1, fy1 - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 0), 1)

        if debug_logs_dir:
            cv2.imwrite(os.path.join(debug_logs_dir, "annotated.png"), annotated_debug_image)
            with open(os.path.join(debug_logs_dir, "results.json"), "w") as f:
                json.dump(results, f, indent=2)

        return results
