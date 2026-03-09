from lib.common import *



class FormParser:
    def __init__(self, config: dict):
        self.config = config
        self.defaults = {**DEFAULTS, **config.get("defaults", {})}
        self.width, self.height = PAGE_SIZES[config["page"]["size"]]
        self.margin = config["page"]["margin_mm"] * units.mm
        self.font, self.font_size = resolve_font(config["page"])

    def _question_style(self, question: dict) -> dict:
        overrides = {k: v for k, v in question.items() if k not in QUESTION_STRUCTURAL_KEYS}
        return {**self.defaults, **overrides}

    def compute_field_coordinates(self):
        fields = []
        y = self.height - self.margin
        for question in self.config["questions"]:
            style = self._question_style(question)
            y -= style["label_spacing_mm"] * units.mm

            if question["type"] in ("text", "date", "number"):
                fields.append({
                    "id": question["id"],
                    "type": "text",
                    "parse": question["type"],
                    "bbox": (
                        self.margin,
                        y,
                        self.margin + style["text_box_width_mm"] * units.mm,
                        y + style["text_box_height_mm"] * units.mm
                    )
                })

            if question["type"] == "choice":
                diameter = style["bubble_diameter_mm"] * units.mm
                options = {}
                if question.get("direction", "horizontal") == "vertical":
                    for option in question["options"]:
                        options[option] = (
                            self.margin,
                            y - diameter / 2,
                            self.margin + diameter,
                            y + diameter / 2
                        )
                        y -= style["option_spacing_mm"] * units.mm
                    y -= style["row_spacing_mm"] * units.mm
                else:
                    x = self.margin
                    for option in question["options"]:
                        options[option] = (
                            x,
                            y - diameter / 2,
                            x + diameter,
                            y + diameter / 2
                        )
                        x += horizontal_option_spacing(option, diameter,
                                                       style["option_spacing_mm"] * units.mm,
                                                       self.font, self.font_size)
                    y -= style["row_spacing_mm"] * units.mm * 2

                fields.append({
                    "id": question["id"],
                    "type": "bubbles",
                    "options": options
                })
                continue

            y -= style["row_spacing_mm"] * units.mm * 2

        return fields

    def page_size(self):
        return self.width, self.height

    def marker_coordinates(self, pixels_per_point):
        size = self.defaults["marker_size_mm"] * units.mm
        pad  = self.defaults["marker_pad_mm"] * units.mm
        width, height = self.width, self.height
        half = size / 2
        return {
            0: ((pad + half) * pixels_per_point,          (pad + half) * pixels_per_point),          # top-left
            1: ((width - pad - half) * pixels_per_point,  (pad + half) * pixels_per_point),          # top-right
            2: ((pad + half) * pixels_per_point,          (height - pad - half) * pixels_per_point), # bottom-left
            3: ((width - pad - half) * pixels_per_point,  (height - pad - half) * pixels_per_point), # bottom-right
        }
