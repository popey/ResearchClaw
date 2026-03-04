# -*- coding: utf-8 -*-
"""Fill fillable PDF form fields from a JSON specification.

Usage:
    python fill_pdf_form.py <input.pdf> <fields.json> <output.pdf>

The JSON file should contain a list of field entries:
[
    {"field_id": "/FieldName", "value": "John Doe", "page": 0},
    {"field_id": "/CheckBox1", "value": "/Yes", "page": 0}
]
"""
import json
import sys


def fill_pdf_fields(
    input_path: str, fields_json_path: str, output_path: str
) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        print("pypdf not installed. Run: pip install pypdf")
        sys.exit(1)

    with open(fields_json_path, "r") as f:
        fields = json.load(f)

    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.append(reader)

    # Group fields by page
    page_fields: dict = {}
    for entry in fields:
        page = entry.get("page", 0)
        page_fields.setdefault(page, {})[entry["field_id"]] = entry["value"]

    # Apply fields per page
    for page_num, field_values in page_fields.items():
        if page_num < len(writer.pages):
            writer.update_page_form_field_values(
                writer.pages[page_num], field_values
            )
            print(
                f"Page {page_num}: updated {len(field_values)} field(s)"
            )

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"Filled PDF saved to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Usage: fill_pdf_form.py <input.pdf> <fields.json> <output.pdf>"
        )
        sys.exit(1)
    fill_pdf_fields(sys.argv[1], sys.argv[2], sys.argv[3])
