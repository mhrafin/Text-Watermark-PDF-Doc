# Text-Watermark-PDF-Doc

Add text watermarks to PDF files via a proper CLI. No more editing source constants — pass flags per run.

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

This installs the `watermark` command (from `pyproject.toml` `[project.scripts]`) alongside `python watermark.py` and `python -m watermark`:

```bash
.venv/bin/watermark --help
# or
uv run watermark --help
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
python watermark.py <input.pdf> [output.pdf] [options]
# or after uv sync:
watermark <input.pdf> [output.pdf] [options]
```

- `input` — required input PDF path.
- `output` — optional output path. Defaults to `<input>_watermarked.pdf` beside the input (e.g., `my.pdf` → `my_watermarked.pdf`).

Basic examples:

```bash
# Simple: default text, all pages, lower-right corner
python watermark.py my_document.pdf

# Custom text and output
python watermark.py my_document.pdf watermarked_doc.pdf --text "Draft"

# Page ranges, position, tiled diagonal, opacity
python watermark.py book.pdf --text "Personal use only" --pages "2-10,127-132" --position center --angle 45 --opacity 0.35
python watermark.py book.pdf --position tile --angle 30 --text "Confidential"
python watermark.py book.pdf --position top-left --margin 24 --font Amiri-Regular.ttf --font-size 12

# Dry-run preview (no file written)
python watermark.py book.pdf --pages "1-3,5" --dry-run

# My Usecases
watermark "/media/raf/Personal/Books/English/How-to-Make-Notes-and-Write---Allosso-Dan-jzdq8.pdf" output.pdf --font-size 8 --margin 20
```

Use `--help` for full flag list and defaults, `--version` for the package version.

```bash
python watermark.py --help
watermark --version   # 0.1.0
```

## Configuration (flags)

All former source constants are now flags with validated defaults:


| Flag                                                                 | Default                                        | Description                                                                                                                                      |
| -------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--text TEXT`                                                        | `"Personal use only. No commercial printing."` | Watermark text                                                                                                                                   |
| `--font PATH`                                                        | `Helvetica`                                    | Path to a`.ttf` file. Name derived from file stem; falls back to Helvetica with a warning if registration fails. Omit to use standard PDF fonts. |
| `--font-size FLOAT`                                                  | `9`                                            | Font size in points (`>0`)                                                                                                                       |
| `--opacity FLOAT`                                                    | `0.5`                                          | Opacity`0.0`–`1.0`                                                                                                                              |
| `--pages RANGES`                                                     | all pages                                      | 1-based ranges, e.g.`"2-10,127-132"`, `"1-3, 5, 10-12"`                                                                                          |
| `--position {lower-right,lower-left,top-right,top-left,center,tile}` | `lower-right`                                  | Placement.`tile` repeats diagonally across the page and ignores `--margin`.                                                                      |
| `--angle FLOAT`                                                      | `0.0`                                          | Rotation in degrees (around text center; per-tile for`tile`)                                                                                     |
| `--margin FLOAT`                                                     | `36.0`                                         | Margin in points for corner/center (`≥0`, ignored for `tile`)                                                                                   |
| `--dry-run`                                                          | off                                            | Preview targeted pages and output path without writing                                                                                           |
| `output` positional                                                  | `<input>_watermarked.pdf`                      | Output path when omitted                                                                                                                         |

### Page range examples

`--pages "2-31, 55, 77, 100-110"` → pages 2–31, 55, 77, 100–110 (1-based inclusive). Invalid tokens are warned and ignored; out-of-range indices are silently skipped.

### Fonts

**Standard PDF fonts** — omit `--font` to use `Helvetica` (or other built-ins are available if you pass a standard name via `--font` without a file — fallback logic will warn and use Helvetica).

**Custom TTF** — place your `.ttf` in the project root (or any path) and pass it:

```bash
python watermark.py in.pdf --font Amiri-Regular.ttf --text "مثال"
```

A bundled Arabic-style font (`Amiri-Regular.ttf`) is included. The font name is derived from the file stem (`Amiri-Regular`).

### Placement

Corner positions are placed via a minimal overlay sized to the text (`stringWidth` + padding) and `pikepdf.Page.add_overlay(..., rect)` in real page coordinates, so the same `--margin` works on letter, A4, and mixed-size PDFs. `center` is centered; `tile` draws a rotated grid on a letter-sized canvas and stretches uniformly (density-based).

## How it works

1. **argparse** parses `input`/`output` and all flags (with validation).
2. **ReportLab** generates a watermark PDF overlay — minimal rect for corners/center, or a tiled letter-sized grid for `tile`.
3. **pikepdf** opens the input, adds the overlay via `page.add_overlay()` with a per-page `rect` (from page `MediaBox`, `--margin`, and text-measured size) on pages matching `--pages`, and saves to the output path.

No background rectangle is drawn — opacity is via `setFillGray(0, alpha=…)` so the page shows through.

## Project structure

```
Text-Watermark-PDF-Doc/
├── watermark.py           # CLI + placement engine
├── tests/
│   └── test_watermark.py  # unit tests for parsing, placement, and CLI validation
├── Amiri-Regular.ttf      # Bundled custom font (optional)
├── pyproject.toml         # Project metadata, pinned deps, and [project.scripts] entry point
├── uv.lock                # Lockfile (uv)
└── .gitignore
```

## Testing

```bash
.venv/bin/python -m unittest tests.test_watermark -v
# or with pytest if installed:
uv run pytest -q
```

## Dependencies

- [pikepdf](https://github.com/pikepdf/pikepdf) — PDF reading/writing
- [reportlab](https://www.reportlab.com/) — PDF generation for the watermark overlay
- `argparse` (stdlib) — CLI
