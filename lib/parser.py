from lib.common import *

class FormParser:
    def __init__(self, config: dict):
        self.cfg = config
        self.marker_config = {**MARKER_DEFAULTS, **config.get("markers", {})}
        self.text_box_config = {**TEXT_BOX_DEFAULTS, **config.get("text_box", {})}
        self.width, self.height = PAGE_SIZES[config["page"]["size"]]

        self.margin = config["page"]["margin_mm"] * units.mm
        self.row_spacing = config["layout"]["row_spacing_mm"] * units.mm
        self.label_spacing = config["layout"]["label_spacing_mm"] * units.mm
        self.bubble_diameter = config["layout"]["bubble_diameter_mm"] * units.mm
        self.option_spacing = config["layout"]["option_spacing_mm"] * units.mm

        self.marker_size = self.marker_config["size_mm"] * units.mm
        self.marker_pad  = self.marker_config["pad_mm"] * units.mm

    def compute_field_coordinates(self):
        fields = []
        y = self.height - self.margin
        for q in self.cfg["questions"]:
            y -= self.label_spacing

            if q["type"] in ("text", "date", "number"):
                fields.append({
                    "id": q["id"],
                    "type": "text",
                    "parse": q["type"],
                    "bbox": (
                        self.margin,
                        y,
                        self.margin + self.text_box_config["width"]*units.mm,
                        y + self.text_box_config["height"]*units.mm
                    )
                })

            if q["type"] == "choice":
                x = self.margin
                options = {}
                for opt in q["options"]:
                    options[opt] = (
                        x,
                        y - self.bubble_diameter / 2,
                        x + self.bubble_diameter,
                        y + self.bubble_diameter / 2
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

    def marker_coordinates(self, pixels_per_point):
        """Expected marker center positions in pixel coords (top-left origin) for a given pixels-per-point scale."""
        pad = self.marker_pad
        W, H = self.width, self.height
        half = self.marker_size / 2
        return {
            0: ((pad + half) * pixels_per_point,       (pad + half) * pixels_per_point),        # top-left
            1: ((W - pad - half) * pixels_per_point,   (pad + half) * pixels_per_point),        # top-right
            2: ((pad + half) * pixels_per_point,       (H - pad - half) * pixels_per_point),    # bottom-left
            3: ((W - pad - half) * pixels_per_point,   (H - pad - half) * pixels_per_point),    # bottom-right
        }
