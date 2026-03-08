import json
import os
from lib.engine import FormRenderer
import sys

TEMPLATE = sys.argv[1] if len(sys.argv)>2 else "config/form_template.json"
OUTPUT = sys.argv[2] if len(sys.argv)>3 else "config/form.pdf"

with open(TEMPLATE) as f:
    cfg = json.load(f)

renderer = FormRenderer(cfg)
renderer.render(OUTPUT)
renderer.render_png(os.path.splitext(OUTPUT)[0] + ".png")