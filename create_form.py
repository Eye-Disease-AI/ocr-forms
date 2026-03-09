#!/usr/bin/env python
import json
from pathlib import Path
import typer

def main(
    template: Path = typer.Argument(help="Form template JSON"),
    output: Path = typer.Argument(help="Output PDF path"),
):
    from lib.renderer import FormRenderer

    with open(template) as f:
        cfg = json.load(f)

    renderer = FormRenderer(cfg)
    renderer.render()
    renderer.save_pdf(str(output))
    renderer.save_png(str(output.with_suffix(".png")))
    typer.echo(f"Saved {output}")

if __name__ == "__main__":
    typer.run(main)
