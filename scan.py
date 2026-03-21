#!/usr/bin/env python
import json
from pathlib import Path
import typer

def main(
    image: Path = typer.Argument(help="Path to the scanned form image"),
    template: Path = typer.Option(Path("config/form_template.json"), help="Form template JSON"),
    scan_config: Path = typer.Option(Path("config/scan_config.json"), help="Scan config JSON"),
):
    import cv2
    from lib.scanner import FormScanner

    with open(template) as f:
        cfg = json.load(f)
    with open(scan_config) as f:
        scan_cfg = json.load(f)

    debug_dir = Path("debug") / image.stem
    debug_dir.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(str(image))
    try:
        results = FormScanner(cfg, scan_cfg).scan(img, debug_logs_dir=str(debug_dir))
        print(json.dumps(results, indent=2, ensure_ascii=False))
    except Exception as e:
        typer.echo(f"Failure scanning {image}: {e}", err=True)
        raise typer.Exit(1)

if __name__ == "__main__":
    typer.run(main)
