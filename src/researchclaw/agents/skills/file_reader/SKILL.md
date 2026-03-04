# File Reader

- name: file_reader
- description: Read, preview, and summarize text-based files — source code, configs, logs, data files, and plain text documents.
- emoji: 📄
- requires: []

## Supported Formats

| Category | Extensions |
|----------|-----------|
| Plain text | `.txt`, `.md`, `.rst`, `.text` |
| Data | `.json`, `.yaml`, `.yml`, `.csv`, `.tsv`, `.xml` |
| Config | `.ini`, `.toml`, `.cfg`, `.conf`, `.env` |
| Logs | `.log` |
| Source code | `.py`, `.js`, `.ts`, `.java`, `.c`, `.cpp`, `.go`, `.rs`, `.r`, `.m`, `.jl`, `.sh`, `.sql` |
| Research | `.bib`, `.tex`, `.sty`, `.cls` |

## Excluded Formats

Do NOT use this skill for:
- **PDF files** → use the `pdf` skill
- **Office files** (`.docx`, `.pptx`, `.xlsx`) → use the respective skill
- **Images** (`.png`, `.jpg`, `.gif`) → these are binary files
- **Audio/Video** (`.mp3`, `.mp4`, `.wav`) → these are binary files

## How to Use

1. **Check file type** before reading:
   ```bash
   file -b --mime-type /path/to/file
   ```

2. **Read the file** with the `read_file` tool:
   ```json
   {"path": "/path/to/file.txt"}
   ```

3. For large files, read specific sections or use `head`/`tail`:
   ```bash
   head -n 100 /path/to/large_file.csv
   wc -l /path/to/large_file.csv
   ```

## Research Context

- `.bib` files: Parse BibTeX entries and summarize references
- `.tex` files: Understand LaTeX document structure
- `.csv`/`.tsv` files: Preview data tables, report shape and column info
- `.json` files: Parse structured research metadata

## Rules

- Always check MIME type before reading unknown files
- For files > 10,000 lines, preview head + tail + report line count
- Never attempt to read binary files as text
- Report encoding issues gracefully (try UTF-8 first, then latin-1)
