# DOCX – Word Document Processing

- name: docx
- description: Create, read, and edit Word documents — research papers, reports, proposals, and manuscripts.
- emoji: 📝

## Runtime Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| LibreOffice (`soffice`) | DOCX↔PDF conversion, preview | `brew install --cask libreoffice` |
| Poppler (`pdftoppm`) | PDF→image for visual QA | `brew install poppler` |
| pandoc | DOCX→text extraction | `brew install pandoc` |

## Workflows

### Read / Extract Text
```bash
# Quick text extraction
pandoc document.docx -t plain

# Or with formatting preserved
pandoc document.docx -t markdown
```

### Create New Document (python-docx)
```python
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# Title
title = doc.add_heading('Research Report', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# Abstract
doc.add_heading('Abstract', level=1)
doc.add_paragraph('This paper presents...', style='Normal')

# Body with formatting
para = doc.add_paragraph()
run = para.add_run('Important finding: ')
run.bold = True
para.add_run('The results show significant improvement.')

# Table
table = doc.add_table(rows=3, cols=3)
table.style = 'Table Grid'
table.cell(0, 0).text = 'Method'
table.cell(0, 1).text = 'Accuracy'
table.cell(0, 2).text = 'F1 Score'

# Figure
doc.add_picture('figure1.png', width=Inches(5))
doc.add_paragraph('Figure 1: Model Architecture', style='Caption')

doc.save('research_report.docx')
```

### Edit Existing Document
```python
from docx import Document

doc = Document('existing.docx')

# Find and replace text
for para in doc.paragraphs:
    if 'old_text' in para.text:
        for run in para.runs:
            run.text = run.text.replace('old_text', 'new_text')

# Add content at the end
doc.add_heading('Additional Results', level=1)
doc.add_paragraph('New experimental results...')

doc.save('updated.docx')
```

### Convert to PDF
```bash
soffice --headless --convert-to pdf document.docx --outdir /output/dir/
```

### Visual QA (verify output)
```bash
# Convert to PDF first
soffice --headless --convert-to pdf document.docx
# Then to images
pdftoppm -png -r 200 document.pdf preview
```

## Research Document Templates

### Paper Structure
1. Title, Authors, Affiliations
2. Abstract
3. Introduction
4. Related Work
5. Methodology
6. Experiments & Results
7. Discussion
8. Conclusion
9. References
10. Appendix

### Report Structure
1. Title Page
2. Executive Summary
3. Table of Contents
4. Introduction
5. Findings
6. Analysis
7. Recommendations
8. References
9. Appendices

## Page Setup

```python
from docx.shared import Inches, Cm

section = doc.sections[0]
section.page_width = Inches(8.5)   # Letter: 8.5 x 11
section.page_height = Inches(11)
section.top_margin = Inches(1)
section.bottom_margin = Inches(1)
section.left_margin = Inches(1.25)
section.right_margin = Inches(1.25)
```

## Styles

```python
from docx.shared import Pt, RGBColor

style = doc.styles['Normal']
font = style.font
font.name = 'Times New Roman'
font.size = Pt(12)
font.color.rgb = RGBColor(0, 0, 0)

# Line spacing
from docx.shared import Pt
style.paragraph_format.line_spacing = Pt(24)  # double-spaced
```

## Rules

- Always use `python-docx` for programmatic document creation (never raw XML unless editing existing)
- For editing complex documents, prefer targeted edits over full rewrites
- Always convert to PDF + images to verify visual output before delivering
- Use appropriate heading levels (max depth 3 for most documents)
- Include page numbers for documents > 2 pages
- For academic papers, follow the target venue's formatting guidelines
- Never use Unicode bullet characters (use Word's built-in list styles)
- Tables must have explicit column widths for consistent rendering
