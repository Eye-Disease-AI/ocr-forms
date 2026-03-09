import os
from reportlab.lib import pagesizes
from reportlab.lib import units
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import IO

import cv2


DEFAULTS = {
    "marker_size_mm":     15,
    "marker_pad_mm":       5,
    "text_box_width_mm":  60,
    "text_box_height_mm":  8,
    "row_spacing_mm":     10,
    "label_spacing_mm":    6,
    "bubble_diameter_mm":  6,
    "option_spacing_mm":  12,
}

PAGE_SIZES = {
    "A4": pagesizes.A4
}

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

QUESTION_STRUCTURAL_KEYS = {"type", "id", "label", "options", "direction"}


def resolve_font(page_config: dict) -> tuple[str, int]:
    """Register a TTF font if a file path is given, return (font_name, font_size)."""
    font_setting = page_config.get("font", "Helvetica")
    font_size = page_config.get("font_size", 11)
    if os.path.isfile(font_setting):
        if "FormFont" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("FormFont", font_setting))
        return "FormFont", font_size
    return font_setting, font_size


def horizontal_option_spacing(option: str, bubble_diameter: float, min_spacing: float,
                              font_name: str, font_size: int) -> float:
    """Space needed for one horizontal bubble+label, at least min_spacing."""
    label_width = pdfmetrics.stringWidth(option, font_name, font_size)
    return max(min_spacing, bubble_diameter + label_width + 4 * units.mm)
