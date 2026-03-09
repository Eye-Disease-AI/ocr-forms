import easyocr
import json
import numpy as np
import os
from datetime import date
from lib.parser import FormParser
from .common import *

_SCAN_DEFAULTS = {
    "upscaling_scale": 3,
    "bubble_pixel_threshold": 150,
    "bubble_fill_threshold": 0.5,
}


def _warp_image(image: np.ndarray, parser: FormParser, page_width, page_height, upscaling_scale) -> np.ndarray:
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(image)

    width_pixels = int(page_width * upscaling_scale)
    height_pixels = int(page_height * upscaling_scale)

    detected_centers = {}
    if ids is not None:
        for i, marker_id in enumerate(ids.flatten()):
            if int(marker_id) in range(4):
                detected_centers[int(marker_id)] = corners[i][0].mean(axis=0)

    if len(detected_centers) < 4:
        raise Exception(f"Error: only {len(detected_centers)}/4 markers detected.")

    expected_centers = parser.marker_coordinates(upscaling_scale)
    source_points = np.float32([detected_centers[i] for i in range(4)])
    destination_points = np.float32([expected_centers[i] for i in range(4)])

    transform = cv2.getPerspectiveTransform(source_points, destination_points)
    return cv2.warpPerspective(image, transform, (width_pixels, height_pixels))


def _bbox_to_coordinates(bbox, page_height_points, scale):
    x1_points, y1_points, x2_points, y2_points = bbox
    return (
        int(x1_points * scale),
        int((page_height_points - y2_points) * scale),
        int(x2_points * scale),
        int((page_height_points - y1_points) * scale),
    )


def _cutout_bbox(warped: np.ndarray, bbox, page_height_points, scale) -> np.ndarray:
    x1, y1, x2, y2 = _bbox_to_coordinates(bbox, page_height_points, scale)
    return warped[y1:y2, x1:x2]


def _bubble_fill_score(region: np.ndarray, darkness_threshold: int) -> float:
    _, thresholded = cv2.threshold(region, darkness_threshold, 255, cv2.THRESH_BINARY_INV)
    filled = np.sum(thresholded == 255)
    return filled / thresholded.size


def _parse_text(text: str) -> str:
    return text


def _parse_date(text: str) -> str:
    digits = ''.join(c for c in text if c.isdigit())
    try:
        if len(digits) == 7:   # d mm yyyy
            return date(int(digits[3:7]), int(digits[1:3]), int(digits[0])).isoformat()
        if len(digits) == 8:   # dd mm yyyy
            return date(int(digits[4:8]), int(digits[2:4]), int(digits[0:2])).isoformat()
    except ValueError:
        pass
    return text


def _parse_number(text: str) -> int | float | None:
    digits = ''.join(c for c in text if c.isdigit() or c in '.,-')
    normalized = digits.replace(',', '.')
    try:
        value = float(normalized)
        return int(value) if value == int(value) else value
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
        self._text_reader = easyocr.Reader(['en', 'pl'], gpu=False, verbose=False)

    def scan(self, image: np.ndarray, debug_logs_dir=None):
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        warped = _warp_image(grayscale, self.parser, self.page_width, self.page_height, self.scan_config["upscaling_scale"])

        if debug_logs_dir:
            cv2.imwrite(os.path.join(debug_logs_dir, "warped.png"), warped)

        annotated_debug_image: np.ndarray = cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR) if debug_logs_dir else None
        results = {}

        for field in self.layout:
            debug_logs_field_dir = os.path.join(debug_logs_dir, field["id"]) if debug_logs_dir else None
            if debug_logs_field_dir:
                os.makedirs(debug_logs_field_dir, exist_ok=True)

            if field["type"] == "text":
                region = _cutout_bbox(warped, field["bbox"], self.page_height, self.scan_config["upscaling_scale"])
                if debug_logs_field_dir:
                    cv2.imwrite(os.path.join(debug_logs_field_dir, "raw.png"), region)

                raw_text = ' '.join(self._text_reader.readtext(region, detail=0)).strip()
                if debug_logs_field_dir:
                    with open(os.path.join(debug_logs_field_dir, "raw_text.txt"), "w") as file:
                        file.write(raw_text)

                results[field["id"]] = {field["parse"]: _PARSERS[field["parse"]](raw_text)}

                if annotated_debug_image is not None:
                    x1, y1, x2, y2 = _bbox_to_coordinates(field["bbox"], self.page_height, self.scan_config["upscaling_scale"])
                    cv2.rectangle(annotated_debug_image, (x1, y1), (x2, y2), (255, 100, 0), 2)
                    cv2.putText(annotated_debug_image, f"{field['id']}: {_PARSERS[field['parse']](raw_text)}", (x1, y1 - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 0), 1)

            if field["type"] == "bubbles":
                scores = {}
                for option, box in field["options"].items():
                    region = _cutout_bbox(warped, box, self.page_height, self.scan_config["upscaling_scale"])
                    if debug_logs_field_dir:
                        cv2.imwrite(os.path.join(debug_logs_field_dir, f"{option}.png"), region)
                    scores[option] = _bubble_fill_score(region, self.scan_config["bubble_pixel_threshold"])

                if debug_logs_field_dir:
                    with open(os.path.join(debug_logs_field_dir, "scores.json"), "w") as file:
                        json.dump(scores, file, indent=2)

                marked_options = [option for option, score in scores.items() if score > self.scan_config["bubble_fill_threshold"]]

                results[field["id"]] = {"choice": marked_options}

                if annotated_debug_image is not None:
                    for option, box in field["options"].items():
                        x1, y1, x2, y2 = _bbox_to_coordinates(box, self.page_height, self.scan_config["upscaling_scale"])
                        color = (0, 210, 0) if option in marked_options else (200, 100, 0)
                        cv2.rectangle(annotated_debug_image, (x1, y1), (x2, y2), color, 2)

                    first_box = next(iter(field["options"].values()))
                    first_x1, first_y1, _, _ = _bbox_to_coordinates(first_box, self.page_height, self.scan_config["upscaling_scale"])
                    cv2.putText(annotated_debug_image, f"{field['id']}: {marked_options}", (first_x1, first_y1 - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 0), 1)

        if debug_logs_dir:
            cv2.imwrite(os.path.join(debug_logs_dir, "annotated.png"), annotated_debug_image)
            with open(os.path.join(debug_logs_dir, "results.json"), "w") as file:
                json.dump(results, file, indent=2)

        return results
