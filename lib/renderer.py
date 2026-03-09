import io
from pdf2image import convert_from_bytes
from PIL import Image
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader
from .common import *



def _marker_image_reader(marker_id: int):
    img = cv2.aruco.generateImageMarker(ARUCO_DICT, marker_id, 200)
    buffer = io.BytesIO()
    Image.fromarray(img).save(buffer, format='PNG')
    buffer.seek(0)
    return ImageReader(buffer)


class FormRenderer:
    def __init__(self, form_config: dict):
        self.config = form_config
        self.defaults = {**DEFAULTS, **form_config.get("defaults", {})}
        self.width, self.height = PAGE_SIZES[self.config["page"]["size"]]
        self.margin = self.config["page"]["margin_mm"] * units.mm
        self.font, self.font_size = resolve_font(self.config["page"])

        self.canvas = None

    def _question_style(self, question: dict) -> dict:
        overrides = {k: v for k, v in question.items() if k not in QUESTION_STRUCTURAL_KEYS}
        return {**self.defaults, **overrides}

    def render(self):
        self.canvas = io.BytesIO() if self.canvas is None else self.canvas
        self._render_to_canvas(self.canvas)

    def save_pdf(self, output: str):
        if self.canvas is None:
            self.render()
        with open(output, 'wb') as file:
            file.write(self.canvas.getvalue())

    def save_png(self, output: str, dpi: int=150):
        if self.canvas is None:
            self.render()
        pages = convert_from_bytes(self.canvas.getvalue(), dpi=dpi)
        pages[0].save(output, 'PNG')

    def _render_to_canvas(self, dest):
        canvas = pdf_canvas.Canvas(dest, pagesize=(self.width, self.height))
        canvas.setFont(self.font, self.font_size)
        self._draw_markers_on_canvas(canvas)

        y = self.height - self.margin

        for question in self.config["questions"]:
            style = self._question_style(question)
            canvas.drawString(self.margin, y, question["label"])
            y -= style["label_spacing_mm"] * units.mm
            if question["type"] in ("text", "date", "number"):
                canvas.rect(self.margin, y,
                            style["text_box_width_mm"] * units.mm,
                            style["text_box_height_mm"] * units.mm)
            if question["type"] == "choice":
                radius = style["bubble_diameter_mm"] * units.mm / 2
                if question.get("direction", "horizontal") == "vertical":
                    for option in question["options"]:
                        canvas.circle(self.margin + radius, y, radius)
                        canvas.drawString(self.margin + style["bubble_diameter_mm"] * units.mm + 2*units.mm, y-2, option)
                        y -= style["option_spacing_mm"] * units.mm
                    y -= style["row_spacing_mm"] * units.mm
                else:
                    x = self.margin
                    for option in question["options"]:
                        canvas.circle(x + radius, y, radius)
                        canvas.drawString(x + style["bubble_diameter_mm"] * units.mm + 2*units.mm, y-2, option)
                        x += horizontal_option_spacing(option, style["bubble_diameter_mm"] * units.mm,
                                                       style["option_spacing_mm"] * units.mm,
                                                       self.font, self.font_size)
                    y -= style["row_spacing_mm"] * units.mm * 2
                continue
            y -= style["row_spacing_mm"] * units.mm * 2
        canvas.save()

    def _draw_markers_on_canvas(self, canvas):
        size = self.defaults["marker_size_mm"] * units.mm
        pad  = self.defaults["marker_pad_mm"] * units.mm
        width, height = self.width, self.height
        for marker_id, (x, y) in {
            0: (pad,             height - pad - size),  # top left
            1: (width - pad - size, height - pad - size),  # top right
            2: (pad,             pad),                   # bottom left
            3: (width - pad - size, pad),                # bottom right
        }.items():
            canvas.drawImage(_marker_image_reader(marker_id), x, y, width=size, height=size)
