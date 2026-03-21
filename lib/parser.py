from lib.common import *



class FormParser:
    def __init__(self, config: dict):
        self.config = config
        self.defaults = {**DEFAULTS, **config.get("defaults", {})}
        self.width, self.height = PAGE_SIZES[config["page"]["size"]]
        self.margin_x = config["page"]["margin_x_mm"] * units.mm
        self.margin_y = config["page"]["margin_y_mm"] * units.mm
        self.font, _, self.font_size = resolve_font(config["page"])

    def _question_style(self, question: dict) -> dict:
        overrides = {k: v for k, v in question.items() if k not in QUESTION_STRUCTURAL_KEYS}
        return {**self.defaults, **overrides}

    def compute_field_coordinates(self):
        fields = []
        y = self.height - self.margin_y
        for question in self.config["questions"]:
            style = self._question_style(question)
            y -= style["label_spacing_mm"] * units.mm

            if question["type"] == "text":
                tokens = parse_format_string(question["format"])
                box_size = style["char_box_size_mm"] * units.mm
                x = self.margin_x
                segments = []
                box_index = 0
                for token in tokens:
                    if token["kind"] == "box":
                        segments.append({
                            "kind": "box",
                            "bbox": (x, y, x + box_size, y + box_size),
                            "index": box_index,
                        })
                        box_index += 1
                        x += box_size
                    else:
                        segments.append({"kind": "literal", "char": token["char"]})
                        x += pdfmetrics.stringWidth(token["char"], self.font, self.font_size)
                fields.append({
                    "id": question["id"],
                    "type": "text",
                    "segments": segments,
                })

            if question["type"] == "choice":
                diameter = style["bubble_diameter_mm"] * units.mm
                options = {}
                if question.get("direction", "horizontal") == "vertical":
                    for i, option in enumerate(question["options"]):
                        options[option] = (
                            self.margin_x,
                            y - diameter / 2,
                            self.margin_x + diameter,
                            y + diameter / 2
                        )
                        if i < len(question["options"]) - 1:
                            y -= style["option_spacing_mm"] * units.mm
                else:
                    x = self.margin_x
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

                fields.append({
                    "id": question["id"],
                    "type": "bubbles",
                    "options": options
                })
                y -= diameter / 2  # align to bubble bottom edge before gap
                y -= style["question_spacing_mm"] * units.mm
                continue

            y -= style["question_spacing_mm"] * units.mm

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
