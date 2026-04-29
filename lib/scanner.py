import json
import numpy as np
import os
from lib.parser import FormParser
from .common import *
import cv2

_SCAN_DEFAULTS = {
    "upscaling_scale": 3,
    "bubble_pixel_threshold": 150,
    "bubble_fill_threshold": 0.5,
    "ocr_engine": "pytesseract",  # "pytesseract" | "easyocr"
}

def _prepare_aruco() -> cv2.aruco.ArucoDetector:
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    params = cv2.aruco.DetectorParameters()

    # Adaptive threshold sweep, try multiple window sizes
    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 23
    params.adaptiveThreshWinSizeStep = 4

    # More lenient quad fitting for ragged toner edges
    params.polygonalApproxAccuracyRate = 0.05
    params.minMarkerPerimeterRate = 0.02

    # Bit extraction, the big wins for noisy laser prints
    params.perspectiveRemovePixelPerCell = 8
    params.perspectiveRemoveIgnoredMarginPerCell = 0.33
    params.maxErroneousBitsInBorderRate = 0.5
    params.errorCorrectionRate = 1.0

    # Robust corner refinement
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_APRILTAG

    return cv2.aruco.ArucoDetector(aruco_dict, params)


def _warp_image(image: np.ndarray, parser: FormParser, page_width, page_height, upscaling_scale, debug_logs_field_dir) -> np.ndarray:
    detector = _prepare_aruco()
    image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))

    detected_centers = {}
    expected_centers = parser.marker_coordinates(upscaling_scale)
    
    if debug_logs_field_dir is not None:
        markers_dir = os.path.join(debug_logs_field_dir, "markers")
        os.makedirs(markers_dir, exist_ok=True)
    for ds in [1, 2, 4, 8, 10, 12]:
        target_h = int(image.shape[0] / ds)
        downsampled = cv2.resize(image, (int(image.shape[1]/ds), target_h), interpolation=cv2.INTER_AREA)
        corners, ids, rejected = detector.detectMarkers(downsampled)

        if debug_logs_field_dir is not None:
            markers_debug = cv2.cvtColor(downsampled, cv2.COLOR_GRAY2BGR)
            cv2.aruco.drawDetectedMarkers(markers_debug, corners, ids)
            cv2.aruco.drawDetectedMarkers(markers_debug, rejected, borderColor=(0,0,255))
            cv2.imwrite(os.path.join(markers_dir, f"scale={ds}.png"), markers_debug)

        if ids is not None:
            for i, mid in enumerate(ids.flatten()):
                mid = int(mid)
                if mid not in expected_centers:
                    continue
                if mid not in detected_centers:
                    detected_centers[mid] = corners[i][0].mean(axis=0) * ds
        if len(detected_centers) >= 4:
            break   # that's enough


    if len(detected_centers) < 4:
        raise Exception(f"Error: only {len(detected_centers)}/4 markers detected.")

    width_pixels = int(page_width * upscaling_scale)
    height_pixels = int(page_height * upscaling_scale)

    common_ids = sorted(set(detected_centers) & set(expected_centers))

    source_points = np.float32([detected_centers[i] for i in common_ids])
    destination_points = np.float32([expected_centers[i] for i in common_ids])

    transform = cv2.getPerspectiveTransform(source_points[:4], destination_points[:4])
    warped = cv2.warpPerspective(image, transform, (width_pixels, height_pixels))
    return warped


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


def _preprocess_char_region(region: np.ndarray) -> np.ndarray:
    """Inset to remove box borders, upscale, binarize with adaptive threshold, add padding."""
    inset = max(2, region.shape[0] // 10)
    if region.shape[0] > inset * 2 and region.shape[1] > inset * 2:
        region = region[inset:-inset, inset:-inset]
    upscaled = cv2.resize(region, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    block = max(11, (upscaled.shape[0] // 4) | 1)  # must be odd
    binary = cv2.adaptiveThreshold(upscaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, block, 10)
    return cv2.copyMakeBorder(binary, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def _ocr_char_pytesseract(region: np.ndarray) -> str:
    import pytesseract
    processed = _preprocess_char_region(region)
    # PSM 8 = single word — more robust than PSM 10 (single char),
    # returns empty string when unreadable instead of random garbage
    text = pytesseract.image_to_string(processed, config='--psm 8 --oem 3').strip()
    return text[0] if text else ""


def _ocr_char_easyocr(region: np.ndarray, reader) -> str:
    processed = _preprocess_char_region(region)
    raw = ' '.join(reader.readtext(processed, detail=0)).strip()
    return raw[0] if raw else ""


class FormScanner:
    def __init__(self, form_config: dict, scan_config=None):
        self.scan_config = {**_SCAN_DEFAULTS, **(scan_config or {})}
        self.parser = FormParser(form_config)
        self.layout = self.parser.compute_field_coordinates()
        self.page_width, self.page_height = self.parser.page_size()

        if self.scan_config["ocr_engine"] == "easyocr":
            import easyocr
            self._easyocr_reader = easyocr.Reader(['en', 'pl'], gpu=False, verbose=False)
        else:
            self._easyocr_reader = None

    def _ocr_char(self, region: np.ndarray) -> str:
        if self.scan_config["ocr_engine"] == "easyocr":
            return _ocr_char_easyocr(region, self._easyocr_reader)
        return _ocr_char_pytesseract(region)

    def scan(self, image: np.ndarray, debug_logs_dir=None):
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        #grayscale = cv2.convertScaleAbs(grayscale, alpha=2.0, beta=0)
        #grayscale = cv2.morphologyEx(grayscale, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        grayscale = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(grayscale)

        if debug_logs_dir:
            cv2.imwrite(os.path.join(debug_logs_dir, "grayscale.png"), grayscale)

        warped = _warp_image(grayscale, self.parser, self.page_width, self.page_height, self.scan_config["upscaling_scale"], debug_logs_dir)

        if debug_logs_dir:
            cv2.imwrite(os.path.join(debug_logs_dir, "warped.png"), warped)

        annotated_debug_image: np.ndarray = cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR) if debug_logs_dir else None
        results = {}

        for field in self.layout:
            debug_logs_field_dir = os.path.join(debug_logs_dir, field["id"]) if debug_logs_dir else None
            if debug_logs_field_dir:
                os.makedirs(debug_logs_field_dir, exist_ok=True)

            if field["type"] == "text":
                scale = self.scan_config["upscaling_scale"]
                parts = []
                char_results = []  # (seg, detected_char)
                for seg in field["segments"]:
                    if seg["kind"] == "literal":
                        parts.append(seg["char"])
                        char_results.append((seg, seg["char"]))
                    else:
                        region = _cutout_bbox(warped, seg["bbox"], self.page_height, scale)
                        if debug_logs_field_dir:
                            cv2.imwrite(os.path.join(debug_logs_field_dir, f"char_{seg['index']}.png"), region)
                        char = self._ocr_char(region)
                        parts.append(char)
                        char_results.append((seg, char))

                assembled = "".join(parts)
                results[field["id"]] = assembled

                if debug_logs_field_dir:
                    with open(os.path.join(debug_logs_field_dir, "assembled.txt"), "w") as f:
                        f.write(assembled)

                if annotated_debug_image is not None:
                    for seg, char in char_results:
                        if seg["kind"] == "box":
                            x1, y1, x2, y2 = _bbox_to_coordinates(seg["bbox"], self.page_height, scale)
                            cv2.rectangle(annotated_debug_image, (x1, y1), (x2, y2), (255, 100, 0), 2)
                            cv2.putText(annotated_debug_image, char, (x1 + 2, y1 - 4),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 0), 1)
                    first_box_seg = next((s for s, _ in char_results if s["kind"] == "box"), None)
                    if first_box_seg:
                        x1, y1, _, _ = _bbox_to_coordinates(first_box_seg["bbox"], self.page_height, scale)
                        cv2.putText(annotated_debug_image, f"{field['id']}: {assembled}", (x1, y1 - 16),
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
                json.dump(results, file, indent=2, ensure_ascii=False)

        return results
