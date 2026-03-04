# -*- coding: utf-8 -*-
"""Extract form structure from a non-fillable PDF.

Analyses text labels, horizontal lines, and checkbox-like rectangles to
produce a JSON description of the form layout.

Usage:
    python extract_form_structure.py <input.pdf> <output.json>
"""
import json
import sys


def extract_form_structure(pdf_path: str) -> dict:
    try:
        import pdfplumber
    except ImportError:
        print("pdfplumber not installed. Run: pip install pdfplumber")
        sys.exit(1)

    structure: dict = {
        "pages": [],
        "labels": [],
        "lines": [],
        "checkboxes": [],
        "row_boundaries": [],
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            pw, ph = float(page.width), float(page.height)
            structure["pages"].append(
                {"page": page_num, "width": pw, "height": ph}
            )

            # Text labels with bounding boxes
            for word in page.extract_words():
                structure["labels"].append(
                    {
                        "page": page_num,
                        "text": word["text"],
                        "x0": word["x0"],
                        "top": word["top"],
                        "x1": word["x1"],
                        "bottom": word["bottom"],
                    }
                )

            # Horizontal lines (>50% page width)
            for line in page.lines:
                x0, x1 = float(line["x0"]), float(line["x1"])
                if abs(x1 - x0) > pw * 0.5:
                    structure["lines"].append(
                        {
                            "page": page_num,
                            "x0": x0,
                            "x1": x1,
                            "y": float(line["top"]),
                        }
                    )

            # Checkbox-like small squares (5–15pt side)
            for rect in page.rects:
                w = abs(float(rect["x1"]) - float(rect["x0"]))
                h = abs(float(rect["bottom"]) - float(rect["top"]))
                if 5 <= w <= 15 and 5 <= h <= 15 and abs(w - h) < 3:
                    cx = (float(rect["x0"]) + float(rect["x1"])) / 2
                    cy = (float(rect["top"]) + float(rect["bottom"])) / 2
                    structure["checkboxes"].append(
                        {"page": page_num, "center_x": cx, "center_y": cy}
                    )

            # Row boundaries from sorted line y-coords
            page_lines = [
                l for l in structure["lines"] if l["page"] == page_num
            ]
            ys = sorted(set(l["y"] for l in page_lines))
            for i in range(len(ys) - 1):
                structure["row_boundaries"].append(
                    {"page": page_num, "top": ys[i], "bottom": ys[i + 1]}
                )

    return structure


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: extract_form_structure.py <input.pdf> <output.json>")
        sys.exit(1)
    result = extract_form_structure(sys.argv[1])
    with open(sys.argv[2], "w") as f:
        json.dump(result, f, indent=2)
    print(f"Form structure saved to {sys.argv[2]}")
