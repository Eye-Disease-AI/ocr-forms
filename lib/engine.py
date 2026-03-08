import io
import cv2
from pdf2image import convert_from_bytes
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

PAGE_SIZES = {
    "A4": A4
}

MARKER_SIZE_MM = 15
MARKER_PAD_MM = 5

# Marker corner IDs: 0=TL, 1=TR, 2=BL, 3=BR
_ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def _marker_image_reader(marker_id):
    img = cv2.aruco.generateImageMarker(_ARUCO_DICT, marker_id, 200)
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)


class FormRenderer:

    def __init__(self, config):
        self.cfg = config

        page_size = PAGE_SIZES[self.cfg["page"]["size"]]
        self.width, self.height = page_size

        self.margin = self.cfg["page"]["margin_mm"] * mm
        self.row_spacing = self.cfg["layout"]["row_spacing_mm"] * mm
        self.bubble = self.cfg["layout"]["bubble_diameter_mm"] * mm
        self.option_spacing = self.cfg["layout"]["option_spacing_mm"] * mm

    def render(self, output):
        buf = io.BytesIO()
        self._draw_to_canvas(buf)
        data = buf.getvalue()
        with open(output, 'wb') as f:
            f.write(data)

    def render_png(self, output, dpi=150):
        buf = io.BytesIO()
        self._draw_to_canvas(buf)
        pages = convert_from_bytes(buf.getvalue(), dpi=dpi)
        pages[0].save(output, 'PNG')

    def _draw_to_canvas(self, dest):

        c = canvas.Canvas(dest, pagesize=(self.width, self.height))

        self._draw_markers(c)

        y = self.height - self.margin

        for q in self.cfg["questions"]:

            c.drawString(self.margin, y, q["label"])

            y -= self.row_spacing

            if q["type"] == "date":
                c.rect(self.margin, y, 60*mm, 8*mm)

            if q["type"] == "choice":

                x = self.margin

                for opt in q["options"]:

                    r = self.bubble / 2
                    c.circle(x + r, y, r)
                    c.drawString(x + self.bubble + 2*mm, y-2, opt)

                    x += self.option_spacing

            if q["type"] == "scale":

                start, end = q["range"]
                x = self.margin

                for v in range(start, end+1):

                    r = self.bubble / 2
                    c.circle(x + r, y, r)
                    c.drawString(x + self.bubble + 2*mm, y-2, str(v))

                    x += self.option_spacing

            y -= self.row_spacing * 2

        c.save()

    def _draw_markers(self, c):

        size = MARKER_SIZE_MM * mm
        pad = MARKER_PAD_MM * mm
        W, H = self.width, self.height

        for marker_id, (x, y) in {
            0: (pad,          H - pad - size),  # TL
            1: (W - pad - size, H - pad - size),  # TR
            2: (pad,          pad),               # BL
            3: (W - pad - size, pad),              # BR
        }.items():
            c.drawImage(_marker_image_reader(marker_id), x, y, width=size, height=size)


class FormParser:

    def __init__(self, config):

        self.cfg = config

        self.width, self.height = PAGE_SIZES[config["page"]["size"]]

        self.margin = config["page"]["margin_mm"] * mm
        self.row_spacing = config["layout"]["row_spacing_mm"] * mm
        self.bubble = config["layout"]["bubble_diameter_mm"] * mm
        self.option_spacing = config["layout"]["option_spacing_mm"] * mm

    def compute(self):

        fields = []

        y = self.height - self.margin

        for q in self.cfg["questions"]:

            y -= self.row_spacing

            if q["type"] == "date":

                fields.append({
                    "id": q["id"],
                    "type": "ocr",
                    "bbox": (
                        self.margin,
                        y,
                        self.margin + 60*mm,
                        y + 8*mm
                    )
                })

            if q["type"] == "choice":

                x = self.margin
                options = {}

                for opt in q["options"]:

                    options[opt] = (
                        x,
                        y - self.bubble / 2,
                        x + self.bubble,
                        y + self.bubble / 2
                    )

                    x += self.option_spacing

                fields.append({
                    "id": q["id"],
                    "type": "omr",
                    "options": options
                })

            if q["type"] == "scale":

                start,end = q["range"]
                x = self.margin
                options = {}

                for v in range(start,end+1):

                    options[str(v)] = (
                        x,
                        y - self.bubble / 2,
                        x + self.bubble,
                        y + self.bubble / 2
                    )

                    x += self.option_spacing

                fields.append({
                    "id": q["id"],
                    "type": "omr",
                    "options": options
                })

            y -= self.row_spacing * 2

        return fields

    def page_size(self):
        return self.width, self.height

    def marker_dst_px(self, scale):
        """Expected marker center positions in pixel coords (top-left origin) for a given pixels-per-point scale."""
        size = MARKER_SIZE_MM * mm
        pad = MARKER_PAD_MM * mm
        W, H = self.width, self.height
        half = size / 2
        return {
            0: ((pad + half) * scale,       (pad + half) * scale),        # TL
            1: ((W - pad - half) * scale,   (pad + half) * scale),        # TR
            2: ((pad + half) * scale,       (H - pad - half) * scale),    # BL
            3: ((W - pad - half) * scale,   (H - pad - half) * scale),    # BR
        }
