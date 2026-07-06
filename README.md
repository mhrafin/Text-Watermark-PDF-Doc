# Text-Watermark-PDF-Doc

Add text watermarks to PDF files using Python. Configure the text, font, opacity, and page ranges, then run from the command line.

## Requirements

- **Python ≥ 3.12**
- **uv** (recommended) or **pip**

## Setup

### Using uv (recommended)

```bash
git clone <repo-url>
cd Text-Watermark-PDF-Doc
uv sync
```

### Using pip

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install pikepdf==10.1.0 reportlab==4.4.7
```

Activate the environment before running:

```bash
source .venv/bin/activate
```

## Usage

```bash
python watermark.py <input.pdf> <output.pdf>
```

Example:

```bash
python watermark.py my_document.pdf watermarked_doc.pdf
```

## Configuration

All settings live at the top of `watermark.py` (lines 12–38). Edit the file to change them.

| Setting | Default | Description |
|---|---|---|
| `WATERMARK_TEXT` | `"Personal use only..."` | Watermark text content |
| `FONT_SIZE` | `9` | Font size in points |
| `FONT_NAME` | `"Amiri-Regular"` | Font family name |
| `CUSTOM_FONT_PATH` | `"Amiri-Regular.ttf"` | Path to a `.ttf` font file, or `None` to use standard fonts |
| `CUSTOM_FONT_NAME` | `"Amiri-Regular"` | Name used when registering the custom font |
| `OPACITY` | `0.35` | Opacity from `0.0` (invisible) to `1.0` (solid) |
| `PAGES_TO_WATERMARK` | `"2-31, 574-695"` | Pages to watermark. Accepts three types of values (see below) |

### Page range values

Set `PAGES_TO_WATERMARK` to one of:

- `None` — watermarks **every** page.
- A **list** of 0-based indices, e.g. `[0, 2, 4]`.
- A **string** of 1-based ranges, e.g. `"1-3, 5, 10-12"` (inclusive).

### Standard fonts

Set `CUSTOM_FONT_PATH = None` and `FONT_NAME` to any standard PDF font:

`"Helvetica"`, `"Times-Roman"`, `"Courier"`, `"Helvetica-Bold"`, `"Times-BoldItalic"`, etc.

### Custom TTF fonts

Place your `.ttf` file in the project root and set:

```python
CUSTOM_FONT_PATH = "YourFont.ttf"
CUSTOM_FONT_NAME = "YourFont"
FONT_NAME = "YourFont"
```

A bundled Arabic-style font (`Amiri-Regular.ttf`) is included.

## How it works

1. **pikepdf** reads the input PDF.
2. **ReportLab** generates a single-page PDF overlay with the watermark text.
3. Each page in the input that matches `PAGES_TO_WATERMARK` gets the overlay applied via `page.add_overlay()`.
4. The result is saved to the output path.

The watermark is placed in the lower-right corner (40 pt from the right edge, 30 pt from the bottom), right-aligned.

## Project structure

```
Text-Watermark-PDF-Doc/
├── watermark.py           # Main script
├── Amiri-Regular.ttf      # Bundled custom font (optional)
├── pyproject.toml         # Project metadata & pinned deps
├── uv.lock                # Lockfile (uv)
└── .gitignore
```

## Dependencies

- [pikepdf](https://github.com/pikepdf/pikepdf) — PDF reading/writing
- [reportlab](https://www.reportlab.com/) — PDF generation for the watermark overlay
