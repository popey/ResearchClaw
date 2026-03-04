# -*- coding: utf-8 -*-
"""Convert PDF pages to PNG images.

Usage:
    python convert_pdf_to_images.py <input.pdf> <output_dir> [max_dim]
"""
import os
import sys


def convert(pdf_path: str, output_dir: str, max_dim: int = 1000) -> None:
    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("pdf2image not installed. Run: pip install pdf2image")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    images = convert_from_path(pdf_path, dpi=200)
    for i, image in enumerate(images):
        w, h = image.size
        if w > max_dim or h > max_dim:
            scale = min(max_dim / w, max_dim / h)
            image = image.resize((int(w * scale), int(h * scale)))
        out_path = os.path.join(output_dir, f"page_{i + 1}.png")
        image.save(out_path)
        print(f"Saved page {i + 1} → {out_path} ({image.size})")
    print(f"Converted {len(images)} pages")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: convert_pdf_to_images.py <input.pdf> <output_dir> [max_dim]")
        sys.exit(1)
    _max = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    convert(sys.argv[1], sys.argv[2], _max)
