#!/usr/bin/env python
import json
import numpy as np
from pathlib import Path
import typer

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
PDF_EXTS   = {'.pdf'}

def main(
    template: Path = typer.Option(Path("config/form_template.json"), help="Form template JSON"),
    scan_config: Path = typer.Option(Path("config/scan_config.json"), help="Scan config JSON"),
    scans_dir: Path = typer.Option(Path("scans"), help="Directory containing scanned forms"),
    output: Path = typer.Option(Path("results.json"), help="Output JSON file"),
):
    import cv2
    from pdf2image import convert_from_path
    from lib.scanner import FormScanner

    with open(template) as f:
        cfg = json.load(f)
    with open(scan_config) as f:
        scan_cfg = json.load(f)

    scanner = FormScanner(cfg, scan_cfg)
    all_results = {}

    for path in sorted(scans_dir.iterdir()):
        ext = path.suffix.lower()

        if ext in IMAGE_EXTS:
            frames = [cv2.imread(str(path))]
            keys = [path.name]
        elif ext in PDF_EXTS:
            pages = convert_from_path(str(path))
            frames = [np.array(p) for p in pages]
            keys = [f"{path.name}_page{i+1}" if len(pages) > 1 else path.name for i in range(len(pages))]
        else:
            continue

        for key, img in zip(keys, frames):
            typer.echo(f"Scanning {key} ...", err=True)
            debug_dir = Path("debug") / key
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                all_results[key] = scanner.scan(img, debug_logs_dir=str(debug_dir))
            except Exception as e:
                typer.echo(f"Failure scanning {key}: {e}", err=True)

    with open(output, "w") as f:
        json.dump(all_results, f, indent=2)

    typer.echo(f"Processed {len(all_results)} form(s) → {output}")

if __name__ == "__main__":
    typer.run(main)
