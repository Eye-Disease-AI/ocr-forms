import os
from reportlab.lib import pagesizes
from reportlab.lib import units
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import IO

import cv2


DEFAULTS = {
    "marker_size_mm":       15,
    "marker_pad_mm":         5,
    "char_box_size_mm":      8,
    "question_spacing_mm":  12,
    "label_spacing_mm":      6,
    "bubble_diameter_mm":    6,
    "option_spacing_mm":    10,
}

PAGE_SIZES = {
    "A4": pagesizes.A4
}

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

QUESTION_STRUCTURAL_KEYS = {"type", "id", "label", "options", "direction", "format"}


def parse_format_string(fmt: str) -> list[dict]:
    """Parse format string like '[2]-[2]-[4]' into box/literal tokens.

    [N] expands to N consecutive input boxes. Any other character is a literal.
    Example: '[2]-[2]-[4]' -> box, box, literal('-'), box, box, literal('-'), box x4
    """
    import re
    tokens = []
    i = 0
    while i < len(fmt):
        m = re.match(r'\[(\d+)\]', fmt[i:])
        if m:
            count = int(m.group(1))
            tokens.extend([{"kind": "box"}] * count)
            i += m.end()
        else:
            tokens.append({"kind": "literal", "char": fmt[i]})
            i += 1
    return tokens


def resolve_font(page_config: dict) -> tuple[str, str, int]:
    """Register fonts and return (regular_name, bold_name, font_size)."""
    font_setting = page_config.get("font", "Helvetica")
    font_size = page_config.get("font_size", 11)

    if os.path.isfile(font_setting):
        if "FormFont" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("FormFont", font_setting))

        base, ext = os.path.splitext(font_setting)
        bold_candidates = [
            base + "-Bold" + ext,
            base + "Bold" + ext,
            base.replace("Regular", "Bold") + ext,
        ]
        bold_path = next((p for p in bold_candidates if os.path.isfile(p)), None)
        if bold_path and "FormFontBold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("FormFontBold", bold_path))
        bold_name = "FormFontBold" if bold_path else "FormFont"
        return "FormFont", bold_name, font_size

    # Built-in ReportLab font — bold variant follows standard naming
    bold_name = font_setting + "-Bold" if font_setting in ("Helvetica", "Times-Roman", "Courier") else font_setting
    return font_setting, bold_name, font_size


def horizontal_option_spacing(option: str, bubble_diameter: float, min_spacing: float,
                              font_name: str, font_size: int) -> float:
    """Space needed for one horizontal bubble+label, at least min_spacing."""
    label_width = pdfmetrics.stringWidth(option, font_name, font_size)
    return max(min_spacing, bubble_diameter + label_width + 4 * units.mm)
