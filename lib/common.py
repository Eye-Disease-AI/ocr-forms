from reportlab.lib import pagesizes
from reportlab.lib import units
from typing import IO

import cv2


MARKER_DEFAULTS = {"size_mm": 15, "pad_mm": 5}
TEXT_BOX_DEFAULTS = {"width": 60, "height": 8}
PAGE_SIZES = {
    "A4": pagesizes.A4
}
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
