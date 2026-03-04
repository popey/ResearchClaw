# PDF – Full PDF Processing

- name: pdf
- description: Read, create, edit, merge, split, and analyze PDF documents — with special focus on academic papers, forms, and research reports.
- emoji: 📑

## Python Libraries

| Library | Purpose |
|---------|---------|
| `pypdf` | Basic operations: merge, split, rotate, encrypt, metadata |
| `pdfplumber` | Text extraction, table extraction |
| `reportlab` | Create new PDFs programmatically |
| `pymupdf` (fitz) | Advanced text/image extraction, rendering |

## CLI Tools

| Tool | Purpose | Install |
|------|---------|---------|
| `pdftotext` | High-quality text extraction | `brew install poppler` |
| `qpdf` | Structural operations, repair | `brew install qpdf` |
| `pdftk` | Form filling, stamp, burst | `brew install pdftk-java` |
| `pdftoppm` | PDF to image conversion | `brew install poppler` |

## Core Operations

### Read / Extract Text
```python
import pdfplumber
with pdfplumber.open("paper.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
```

Or via CLI for better quality:
```bash
pdftotext -layout paper.pdf -
```

### Extract Tables
```python
import pdfplumber
with pdfplumber.open("paper.pdf") as pdf:
    page = pdf.pages[3]  # table on page 4
    tables = page.extract_tables()
```

### Merge PDFs
```python
from pypdf import PdfMerger
merger = PdfMerger()
merger.append("part1.pdf")
merger.append("part2.pdf")
merger.write("combined.pdf")
merger.close()
```

### Split PDF
```python
from pypdf import PdfReader, PdfWriter
reader = PdfReader("document.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(f"page_{i+1}.pdf")
```

### PDF to Images
```bash
pdftoppm -png -r 200 document.pdf output_prefix
```

Or with Python:
```python
import fitz  # pymupdf
doc = fitz.open("document.pdf")
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=200)
    pix.save(f"page_{i+1}.png")
```

### Create PDF (ReportLab)
```python
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("output.pdf", pagesize=A4)
styles = getSampleStyleSheet()
story = [Paragraph("Hello World", styles['Title'])]
doc.build(story)
```

### Encrypt / Decrypt
```python
from pypdf import PdfReader, PdfWriter
reader = PdfReader("input.pdf")
writer = PdfWriter()
for page in reader.pages:
    writer.add_page(page)
writer.encrypt("password")
writer.write("encrypted.pdf")
```

### Extract Images
```python
import fitz
doc = fitz.open("paper.pdf")
for page_num, page in enumerate(doc):
    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        ext = base_image["ext"]
        with open(f"img_p{page_num}_{img_index}.{ext}", "wb") as f:
            f.write(image_bytes)
```

### Form Operations
```bash
# List form fields
pdftk form.pdf dump_data_fields

# Fill form
pdftk form.pdf fill_form data.fdf output filled.pdf flatten
```

## Research-Specific Features

### Academic Paper Parsing
For academic papers (arxiv, conference, journal), extract:
1. **Title and Authors** — usually on first page
2. **Abstract** — typically between "Abstract" and "Introduction"
3. **References** — parse bibliography section
4. **Figures and Tables** — extract with captions
5. **Equations** — note page/location for reference

### Citation Extraction
```python
import re
# Simple regex for common citation formats
refs = re.findall(r'\[(\d+)\]', text)  # [1], [2] style
refs = re.findall(r'\(([A-Z][a-z]+ et al\., \d{4})\)', text)  # (Author et al., 2024)
```

## Scripts

Helper scripts in `scripts/`:

| Script | Purpose |
|--------|---------|
| `convert_pdf_to_images.py` | Batch convert PDF pages to images |
| `extract_form_structure.py` | Analyze and report form field structure |
| `fill_pdf_form.py` | Programmatic form filling |
| `check_bounding_boxes.py` | Validate annotation positions |

## Rules

- **ReportLab**: NEVER use Unicode superscript/subscript characters (ⁿ, ₂, etc.) — they render as black boxes. Use `<super>` and `<sub>` markup tags instead.
- Always verify PDF output by converting to images and inspecting
- For encrypted PDFs, ask the user for the password
- When extracting text, check if the PDF is scanned (image-based) — if so, suggest OCR
- Prefer `pdftotext -layout` for text extraction from papers (preserves columns)
- For large PDFs (>100 pages), process page ranges rather than the whole file
