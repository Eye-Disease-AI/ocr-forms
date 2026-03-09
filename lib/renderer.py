import io
from pdf2image import convert_from_bytes
from PIL import Image
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader
from .common import *

def _marker_image_reader(marker_id: int):
    img = cv2.aruco.generateImageMarker(ARUCO_DICT, marker_id, 200)
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)

class FormRenderer:
    def __init__(self, form_config: dict):
        self.cfg = form_config
        self.markers_config = {**MARKER_DEFAULTS, **form_config.get("markers", {})}
        self.dates_config = {**DATES_DEFAULTS, **form_config.get("dates", {})}
        self.width, self.height = PAGE_SIZES[self.cfg["page"]["size"]]

        self.margin = self.cfg["page"]["margin_mm"] * units.mm
        self.row_spacing = self.cfg["layout"]["row_spacing_mm"] * units.mm
        self.bubble_diameter = self.cfg["layout"]["bubble_diameter_mm"] * units.mm
        self.option_spacing = self.cfg["layout"]["option_spacing_mm"] * units.mm

        self.marker_size = self.markers_config["size_mm"] * units.mm
        self.marker_pad  = self.markers_config["pad_mm"] * units.mm
        self.canvas = None

    def render(self):
        self.canvas = io.BytesIO() if self.canvas is None else self.canvas
        self._render_to_canvas(self.canvas)
    
    def save_pdf(self, output: str):
        if self.canvas is None:
            self.render()
        with open(output, 'wb') as f:
            f.write(self.canvas.getvalue())

    def save_png(self, output: str, dpi: int=150):
        if self.canvas is None:
            self.render()
        pages = convert_from_bytes(self.canvas.getvalue(), dpi=dpi)
        pages[0].save(output, 'PNG')

    def _render_to_canvas(self, dest: IO[bytes]):
        canvas = pdf_canvas.Canvas(dest, pagesize=(self.width, self.height))
        self._draw_markers_on_canvas(canvas)

        y = self.height - self.margin

        for q in self.cfg["questions"]:
            canvas.drawString(self.margin, y, q["label"])
            y -= self.row_spacing
            if q["type"] == "date":
                canvas.rect(self.margin, y, self.dates_config["width"]*units.mm, self.dates_config["height"]*units.mm)
            if q["type"] == "choice":
                x = self.margin
                for opt in q["options"]:
                    r = self.bubble_diameter / 2
                    canvas.circle(x + r, y, r)
                    canvas.drawString(x + self.bubble_diameter + 2*units.mm, y-2, opt)
                    x += self.option_spacing
            if q["type"] == "scale":
                start, end = q["range"]
                x = self.margin
                for v in range(start, end+1):
                    r = self.bubble_diameter / 2
                    canvas.circle(x + r, y, r)
                    canvas.drawString(x + self.bubble_diameter + 2*units.mm, y-2, str(v))
                    x += self.option_spacing
            y -= self.row_spacing * 2
        canvas.save()

    def _draw_markers_on_canvas(self, canvas):
        size = self.marker_size
        pad = self.marker_pad
        W, H = self.width, self.height
        for marker_id, (x, y) in {
            0: (pad,          H - pad - size),  # top left
            1: (W - pad - size, H - pad - size),  # top right
            2: (pad,          pad),               # bottom left
            3: (W - pad - size, pad),              # bottom right
        }.items():
            canvas.drawImage(_marker_image_reader(marker_id), x, y, width=size, height=size)
