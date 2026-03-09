from reportlab.lib import pagesizes
from reportlab.lib import units
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
