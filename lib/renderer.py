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
        self.margin_x = self.config["page"]["margin_x_mm"] * units.mm
        self.margin_y = self.config["page"]["margin_y_mm"] * units.mm
        self.font, self.bold_font, self.font_size = resolve_font(self.config["page"])

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

        y = self.height - self.margin_y

        for question in self.config["questions"]:
            style = self._question_style(question)
            canvas.setFont(self.bold_font, self.font_size)
            for line in question["label"].splitlines():
                canvas.drawString(self.margin_x, y, line)
                y -= style["label_spacing_mm"] * units.mm
            canvas.setFont(self.font, self.font_size)

            if question["type"] == "text":
                tokens = parse_format_string(question["format"])
                box_size = style["char_box_size_mm"] * units.mm
                x = self.margin_x
                for token in tokens:
                    if token["kind"] == "box":
                        canvas.rect(x, y, box_size, box_size)
                        x += box_size
                    else:
                        canvas.drawString(x, y + 2, token["char"])
                        x += pdfmetrics.stringWidth(token["char"], self.font, self.font_size)

            elif question["type"] == "choice":
                diameter = style["bubble_diameter_mm"] * units.mm
                radius = diameter / 2
                shape = style.get("bubble_shape", "circle")
                if question.get("direction", "horizontal") == "vertical":
                    for i, option in enumerate(question["options"]):
                        if shape == "square":
                            canvas.rect(self.margin_x, y - radius, diameter, diameter)
                        else:
                            canvas.circle(self.margin_x + radius, y, radius)
                        canvas.drawString(self.margin_x + diameter + 2*units.mm, y-2, option)
                        if i < len(question["options"]) - 1:
                            y -= style["option_spacing_mm"] * units.mm
                else:
                    x = self.margin_x
                    for option in question["options"]:
                        if shape == "square":
                            canvas.rect(x, y - radius, diameter, diameter)
                        else:
                            canvas.circle(x + radius, y, radius)
                        canvas.drawString(x + diameter + 2*units.mm, y-2, option)
                        x += horizontal_option_spacing(option, diameter,
                                                       style["option_spacing_mm"] * units.mm,
                                                       self.font, self.font_size)
                y -= radius  # align to bubble bottom edge before gap
                y -= style["question_spacing_mm"] * units.mm
                continue

            y -= style["question_spacing_mm"] * units.mm
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
