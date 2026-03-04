# XLSX – Excel Spreadsheet Processing

- name: xlsx
- description: Create, edit, and analyze Excel spreadsheets — research data, experimental results, statistical analysis, and data visualization.
- emoji: 📈

## Runtime Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| LibreOffice (`soffice`) | XLSX→PDF conversion, formula recalculation | `brew install --cask libreoffice` |

## Python Libraries

| Library | Purpose |
|---------|---------|
| `pandas` | Data analysis, import/export, statistics |
| `openpyxl` | Excel file creation with formatting, formulas, charts |
| `xlsxwriter` | High-performance Excel creation (write-only) |

## Workflows

### Read / Analyze
```python
import pandas as pd

# Read entire file
df = pd.read_excel('data.xlsx')
print(df.shape)
print(df.describe())
print(df.head(20))

# Read specific sheet
df = pd.read_excel('data.xlsx', sheet_name='Results')

# Read all sheets
dfs = pd.read_excel('data.xlsx', sheet_name=None)
for name, df in dfs.items():
    print(f"Sheet: {name}, Shape: {df.shape}")
```

### Create New Spreadsheet
```python
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Experimental Results"

# Headers
headers = ['Model', 'Dataset', 'Accuracy', 'Precision', 'Recall', 'F1']
header_font = Font(bold=True, size=12)
header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
header_font_white = Font(bold=True, size=12, color='FFFFFF')

for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.font = header_font_white
    cell.fill = header_fill
    cell.alignment = Alignment(horizontal='center')

# Data rows
data = [
    ['BERT', 'GLUE', 0.923, 0.915, 0.931, 0.923],
    ['GPT-4', 'GLUE', 0.957, 0.952, 0.961, 0.956],
    ['Our Model', 'GLUE', 0.968, 0.965, 0.971, 0.968],
]
for row_idx, row_data in enumerate(data, 2):
    for col_idx, value in enumerate(row_data, 1):
        cell = ws.cell(row=row_idx, column=col_idx, value=value)
        if isinstance(value, float):
            cell.number_format = '0.000'

# Auto-fit columns
for col in range(1, len(headers) + 1):
    ws.column_dimensions[get_column_letter(col)].width = 15

# Formulas
ws.cell(row=len(data) + 2, column=1, value='Average')
for col in range(3, len(headers) + 1):
    col_letter = get_column_letter(col)
    ws.cell(
        row=len(data) + 2,
        column=col,
        value=f'=AVERAGE({col_letter}2:{col_letter}{len(data)+1})'
    )

wb.save('results.xlsx')
```

### Create with Pandas
```python
import pandas as pd

df = pd.DataFrame({
    'Epoch': range(1, 101),
    'Train Loss': [...],
    'Val Loss': [...],
    'Train Acc': [...],
    'Val Acc': [...],
})

with pd.ExcelWriter('training_log.xlsx', engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Training', index=False)
    # Add summary sheet
    summary = df.describe()
    summary.to_excel(writer, sheet_name='Summary')
```

### Add Charts
```python
from openpyxl.chart import BarChart, LineChart, Reference

wb = openpyxl.load_workbook('results.xlsx')
ws = wb.active

# Bar chart for comparison
chart = BarChart()
chart.title = "Model Comparison"
chart.y_axis.title = "Score"
chart.x_axis.title = "Metric"
data_ref = Reference(ws, min_col=3, min_row=1, max_col=6, max_row=4)
cats_ref = Reference(ws, min_col=1, min_row=2, max_row=4)
chart.add_data(data_ref, titles_from_data=True)
chart.set_categories(cats_ref)
chart.shape = 4
ws.add_chart(chart, "A8")

wb.save('results_with_chart.xlsx')
```

### Force Recalculate Formulas
```bash
soffice --headless --calc --convert-to xlsx:"Calc MS Excel 2007 XML" input.xlsx --outdir /output/
```

## Research Data Best Practices

### Sheet Organization
| Sheet | Content |
|-------|---------|
| `Raw Data` | Original experimental measurements |
| `Processed` | Cleaned and normalized data |
| `Results` | Aggregated results and comparisons |
| `Statistics` | Statistical tests (t-test, ANOVA, etc.) |
| `Charts` | Visualizations |
| `Metadata` | Experiment parameters, environment info |

### Formatting Conventions
| Color | Meaning |
|-------|---------|
| Blue text | Hard-coded input values |
| Black text | Formulas / computed values |
| Green text | Cross-sheet references |
| Yellow background | Key assumptions / hyperparameters |
| Red text | Values needing attention |

### Number Formats
| Type | Format |
|------|--------|
| Accuracy / F1 | `0.000` or `0.0%` |
| Loss | `0.0000` |
| Runtime (seconds) | `#,##0.0` |
| Parameters | `#,##0` |
| p-value | `0.00E+00` |

## Rules

- **Always use Excel formulas** for computed values — never hard-code Python-computed results
- Use `scripts/recalc.py` to force formula recalculation after editing
- Verify formulas are correct before delivering
- Include units in column headers (e.g., "Runtime (s)", "Memory (GB)")
- Freeze the header row: `ws.freeze_panes = 'A2'`
- Add data validation for input cells where appropriate
- For large datasets (>100k rows), use `xlsxwriter` instead of `openpyxl`
- Always include a metadata sheet documenting the experiment setup
