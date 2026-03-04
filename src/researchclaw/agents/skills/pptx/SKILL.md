# PPTX – PowerPoint Presentations

- name: pptx
- description: Create, edit, and analyze PowerPoint presentations — research talks, conference presentations, lecture slides, and poster summaries.
- emoji: 📊

## Runtime Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| LibreOffice (`soffice`) | PPTX→PDF conversion | `brew install --cask libreoffice` |
| Poppler (`pdftoppm`) | PDF→image for visual QA | `brew install poppler` |

## Workflows

### Read / Analyze Existing
```bash
# Extract text content
python -m markitdown presentation.pptx
```

Or with python-pptx:
```python
from pptx import Presentation
prs = Presentation('presentation.pptx')
for slide_num, slide in enumerate(prs.slides, 1):
    print(f"--- Slide {slide_num} ---")
    for shape in slide.shapes:
        if shape.has_text_frame:
            print(shape.text_frame.text)
```

### Create New Presentation (python-pptx)
```python
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

prs = Presentation()

# Title slide
slide = prs.slides.add_slide(prs.slide_layouts[0])
title = slide.shapes.title
title.text = "Neural Architecture Search"
subtitle = slide.placeholders[1]
subtitle.text = "A Comprehensive Survey\nAuthor Name — University"

# Content slide
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "Key Contributions"
body = slide.placeholders[1]
tf = body.text_frame
tf.text = "Contribution 1: Novel search space design"
p = tf.add_paragraph()
p.text = "Contribution 2: Efficient evaluation strategy"
p.level = 0

# Image slide
slide = prs.slides.add_slide(prs.slide_layouts[5])  # blank
slide.shapes.title.text = "Model Architecture"
slide.shapes.add_picture('architecture.png',
    Inches(1.5), Inches(2), Inches(7), Inches(4))

# Table slide
slide = prs.slides.add_slide(prs.slide_layouts[5])
slide.shapes.title.text = "Experimental Results"
rows, cols = 4, 4
table = slide.shapes.add_table(rows, cols,
    Inches(1), Inches(2), Inches(8), Inches(3)).table
headers = ['Method', 'Accuracy', 'Params', 'FLOPs']
for i, h in enumerate(headers):
    table.cell(0, i).text = h

prs.save('research_talk.pptx')
```

### Edit Existing Presentation
```python
from pptx import Presentation
prs = Presentation('existing.pptx')

# Modify specific slide
slide = prs.slides[2]  # 3rd slide
for shape in slide.shapes:
    if shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                if 'old_value' in run.text:
                    run.text = run.text.replace('old_value', 'new_value')

prs.save('updated.pptx')
```

### Visual QA (verify output)
```bash
soffice --headless --convert-to pdf presentation.pptx
pdftoppm -png -r 200 presentation.pdf slide_preview
```

## Design Guidelines for Research Presentations

### Color Schemes (pick one per presentation)

| Theme | Primary | Secondary | Accent | Background |
|-------|---------|-----------|--------|------------|
| Academic Blue | #1B365D | #5B8DB8 | #E8B54D | #FFFFFF |
| Nature Green | #2D5016 | #7BA05B | #D4A574 | #F5F5F0 |
| Modern Dark | #1A1A2E | #16213E | #0F3460 | #E4E4E4 |
| Clean Minimal | #333333 | #666666 | #0066CC | #FFFFFF |

### Typography

| Element | Font | Size | Style |
|---------|------|------|-------|
| Title slide title | Arial/Helvetica Bold | 36-44pt | Bold |
| Slide title | Arial/Helvetica | 28-32pt | Bold |
| Body text | Arial/Calibri | 18-24pt | Regular |
| Caption/footnote | Arial/Calibri | 12-14pt | Italic |

### Layout Rules

- **Max 6 bullet points** per slide
- **Max 8 words** per bullet point
- One key idea per slide
- Every slide should have a visual element (chart, image, diagram, or table)
- Use consistent margins: 0.5" from edges minimum

### Slide Types for Research Talks

1. **Title Slide** — Title, authors, affiliations, date
2. **Outline** — Talk structure overview
3. **Motivation** — Why this problem matters
4. **Background** — Prior work (brief)
5. **Method** — Your approach (with diagrams!)
6. **Experiments** — Setup, datasets, baselines
7. **Results** — Tables, charts, visualizations
8. **Ablation** — What contributes to performance
9. **Qualitative** — Visual examples
10. **Conclusion** — Summary + future work
11. **Thank You / Q&A** — Contact info

## Rules

- NEVER create text-only slides — every slide needs a visual element
- NEVER underline titles (it's an AI-generated look)
- Always verify output by converting to images
- Use high-contrast colors for readability
- Limit animations — they rarely work across platforms
- For charts, prefer clean, simple designs with clear labels
- Include slide numbers
- Keep total slides to ~1 per minute of talk time
