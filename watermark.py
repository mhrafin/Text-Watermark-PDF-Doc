# watermark.py
import argparse
import io
import os
import sys
from pathlib import Path

import pikepdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def parse_page_ranges(ranges_str):
    """
    Parses a string of page ranges (1-based) into a set of 0-based indices.
    Example: "1-3, 5" -> {0, 1, 2, 4}
    """
    if not ranges_str:
        return None

    indices = set()
    parts = [p.strip() for p in ranges_str.split(",")]

    for part in parts:
        if "-" in part:
            try:
                start_str, end_str = part.split("-")
                start = int(start_str)
                end = int(end_str)
                # Convert 1-based to 0-based; inclusive end means range(start-1, end)
                for i in range(start - 1, end):
                    indices.add(i)
            except ValueError:
                print(f"Warning: Invalid range format '{part}'. Ignoring.")
        else:
            try:
                # Convert 1-based to 0-based
                indices.add(int(part) - 1)
            except ValueError:
                print(f"Warning: Invalid page number '{part}'. Ignoring.")

    return indices


def _opacity_type(value: str) -> float:
    try:
        f = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid opacity value: '{value}'")
    if not 0.0 <= f <= 1.0:
        raise argparse.ArgumentTypeError("opacity must be between 0.0 and 1.0")
    return f


def _margin_type(value: str) -> float:
    try:
        f = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid margin value: '{value}'")
    if f < 0:
        raise argparse.ArgumentTypeError("margin must be >= 0")
    return f


def _angle_type(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid angle value: '{value}'")


def _font_size_type(value: str) -> float:
    try:
        f = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid font-size value: '{value}'")
    if f <= 0:
        raise argparse.ArgumentTypeError("font-size must be > 0")
    return f


_STANDARD_FONTS = {
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
    "Symbol",
    "ZapfDingbats",
}


def _resolve_font(font_path: str | None) -> str:
    """Resolve font path to a registered font name, falling back to Helvetica."""
    if not font_path:
        return "Helvetica"
    p = Path(font_path)
    if not p.exists():
        print(f"Error: font file not found: {font_path}", file=sys.stderr)
        sys.exit(2)
    font_name = p.stem
    if font_name not in pdfmetrics.getRegisteredFontNames():
        try:
            pdfmetrics.registerFont(TTFont(font_name, str(p)))
        except Exception as e:
            print(f"Warning: Could not register font {font_name}: {e}", file=sys.stderr)
            print("Falling back to Helvetica.", file=sys.stderr)
            return "Helvetica"
    return font_name


def _get_version() -> str:
    try:
        from importlib.metadata import version as _get_ver

        return _get_ver("text-watermark-pdf-doc")
    except Exception:
        return "0.1.0"


def _placement_rect(
    page_width: float,
    page_height: float,
    ow: float,
    oh: float,
    position: str,
    margin: float,
):
    """Compute destination rect for non-tiled overlay. Returns (x0, y0, x1, y1) or None for tile."""
    if position == "lower-right":
        x0 = page_width - ow - margin
        y0 = margin
    elif position == "lower-left":
        x0 = margin
        y0 = margin
    elif position == "top-right":
        x0 = page_width - ow - margin
        y0 = page_height - oh - margin
    elif position == "top-left":
        x0 = margin
        y0 = page_height - oh - margin
    elif position == "center":
        x0 = (page_width - ow) / 2
        y0 = (page_height - oh) / 2
    elif position == "tile":
        return None
    else:
        raise ValueError(f"Unknown position: {position}")
    return (x0, y0, x0 + ow, y0 + oh)


def make_watermark_overlay(
    text: str,
    font_path: str | None,
    font_size: float,
    opacity: float,
    angle: float,
    position: str,
    margin: float,
) -> io.BytesIO:
    """
    Create a watermark overlay PDF in memory.
    For tiled position, creates a letter-sized tiled canvas.
    For others, creates a minimal canvas sized to text + padding.
    """
    font_name = _resolve_font(font_path)
    # Final fallback check: if font not standard and not registered, use Helvetica
    if (
        font_name not in _STANDARD_FONTS
        and font_name not in pdfmetrics.getRegisteredFontNames()
    ):
        print(
            f"Warning: Font '{font_name}' is not registered. Falling back to 'Helvetica'.",
            file=sys.stderr,
        )
        font_name = "Helvetica"

    if position == "tile":
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        c.setFont(font_name, font_size)
        # Use setFillGray with alpha if available, fallback to setFillAlpha
        try:
            c.setFillGray(0, alpha=opacity)
        except TypeError:
            c.setFillColorRGB(0, 0, 0)
            try:
                c.setFillAlpha(opacity)
            except Exception:
                pass
        width, height = letter
        text_width = pdfmetrics.stringWidth(text, font_name, font_size)
        # Grid steps: use text width + spacing and fixed vertical spacing
        step_x = text_width + 80
        step_y = 100
        # Avoid zero steps
        if step_x <= 0:
            step_x = 200
        if step_y <= 0:
            step_y = 100
        # Tile across a larger area than page to ensure coverage
        for x in range(int(-width), int(width * 2), int(step_x) if step_x else 200):
            for y in range(
                int(-height), int(height * 2), int(step_y) if step_y else 100
            ):
                c.saveState()
                c.translate(x, y)
                if angle:
                    c.rotate(angle)
                c.drawString(0, 0, text)
                c.restoreState()
        c.save()
        packet.seek(0)
        return packet
    else:
        pad = 2
        text_width = pdfmetrics.stringWidth(text, font_name, font_size)
        ow = text_width + 2 * pad
        oh = font_size + 2 * pad
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(ow, oh))
        c.setFont(font_name, font_size)
        try:
            c.setFillGray(0, alpha=opacity)
        except TypeError:
            c.setFillColorRGB(0, 0, 0)
            try:
                c.setFillAlpha(opacity)
            except Exception:
                pass
        # Rotate around center if angle provided
        if angle:
            c.saveState()
            c.translate(ow / 2, oh / 2)
            c.rotate(angle)
            c.translate(-ow / 2, -oh / 2)
            c.drawString(pad, pad, text)
            c.restoreState()
        else:
            c.drawString(pad, pad, text)
        c.save()
        packet.seek(0)
        return packet


def _derive_output_path(input_path: str) -> str:
    p = Path(input_path)
    return str(p.with_name(f"{p.stem}_watermarked.pdf"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watermark",
        description="Add text watermarks to PDF files.",
        epilog='Example: python watermark.py input.pdf --text "Draft" --pages "2-10,127-132" --position lower-right --margin 36',
    )
    parser.add_argument("input", help="Input PDF path")
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output PDF path (default: <input>_watermarked.pdf)",
    )
    parser.add_argument(
        "--text",
        default="Personal use only. No commercial printing.",
        help="Watermark text (default: %(default)s)",
    )
    parser.add_argument(
        "--font", default=None, help="Path to a .ttf font file (default: Helvetica)"
    )
    parser.add_argument(
        "--font-size",
        type=_font_size_type,
        default=9,
        help="Font size in points (default: %(default)s)",
    )
    parser.add_argument(
        "--opacity",
        type=_opacity_type,
        default=0.5,
        help="Opacity 0.0-1.0 (default: %(default)s)",
    )
    parser.add_argument(
        "--pages",
        default=None,
        help='Pages to watermark, 1-based ranges e.g. "2-10,127-132" (default: all pages)',
    )
    parser.add_argument(
        "--position",
        choices=[
            "lower-right",
            "lower-left",
            "top-right",
            "top-left",
            "center",
            "tile",
        ],
        default="lower-right",
        help="Watermark position (default: %(default)s)",
    )
    parser.add_argument(
        "--angle",
        type=_angle_type,
        default=0.0,
        help="Rotation angle in degrees (default: %(default)s)",
    )
    parser.add_argument(
        "--margin",
        type=_margin_type,
        default=36.0,
        help="Margin in points for corner/center positions (default: %(default)s, ignored for tile)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which pages would be watermarked without writing output",
    )
    parser.add_argument("--version", action="version", version=_get_version())
    return parser


def apply_watermark(args: argparse.Namespace) -> None:
    input_pdf = args.input
    output_pdf = args.output
    if not output_pdf:
        output_pdf = _derive_output_path(input_pdf)

    # Validate input exists
    if not os.path.exists(input_pdf):
        print(f"Error: input file not found: {input_pdf}", file=sys.stderr)
        sys.exit(2)

    # Validate font file exists early (before opening PDF)
    if args.font and not os.path.exists(args.font):
        print(f"Error: font file not found: {args.font}", file=sys.stderr)
        sys.exit(2)

    # Dry-run preview before any PDF work
    if args.dry_run:
        # Use parse_page_ranges to resolve pages for preview
        pages_to_process = None
        if args.pages:
            pages_to_process = parse_page_ranges(args.pages)
        try:
            pdf = pikepdf.Pdf.open(input_pdf)
            total = len(pdf.pages)
        except Exception as e:
            print(f"Error: could not open input PDF: {e}", file=sys.stderr)
            sys.exit(2)
        if pages_to_process is None:
            targeted = list(range(1, total + 1))
            print(f"Dry-run: would watermark all {total} pages: {targeted}")
        else:
            # Filter to valid page numbers within total
            targeted = sorted([p + 1 for p in pages_to_process if 0 <= p < total])
            invalid = sorted([p + 1 for p in pages_to_process if not (0 <= p < total)])
            print(
                f"Dry-run: would watermark {len(targeted)} of {total} pages: {targeted}"
            )
            if invalid:
                print(
                    f"  Note: {len(invalid)} page(s) out of range and would be skipped: {invalid}"
                )
            print(
                f"  Resolved 0-based indices: {sorted([p for p in pages_to_process if 0 <= p < total])}"
            )
        print(f"  Input:  {input_pdf}")
        print(f"  Output: {output_pdf} (not written)")
        print(
            f"  Text: '{args.text}' | Position: {args.position} | Angle: {args.angle} | Margin: {args.margin} | Opacity: {args.opacity}"
        )
        return

    print(f"Opening input file: {input_pdf}")
    try:
        pdf = pikepdf.Pdf.open(input_pdf)
    except Exception as e:
        print(f"Error: could not open input PDF: {e}", file=sys.stderr)
        sys.exit(2)

    # Generate overlay
    watermark_stream = make_watermark_overlay(
        text=args.text,
        font_path=args.font,
        font_size=args.font_size,
        opacity=args.opacity,
        angle=args.angle,
        position=args.position,
        margin=args.margin,
    )
    watermark_pdf = pikepdf.Pdf.open(watermark_stream)
    watermark_page = watermark_pdf.pages[0]

    # Determine pages to watermark
    pages_to_process = None
    if args.pages:
        pages_to_process = parse_page_ranges(args.pages)
        if pages_to_process is not None:
            print(f"Parsed page ranges: {sorted(list(pages_to_process))}")
        else:
            print("Parsed page ranges: None (all pages)")

    # Precompute overlay dimensions for non-tiled placement
    # For non-tile, overlay size is small; for tile, we use mediabox stretch
    is_tiled = args.position == "tile"
    if not is_tiled:
        # Get overlay dimensions from its mediabox
        try:
            ow = float(watermark_page.mediabox[2]) - float(watermark_page.mediabox[0])
            oh = float(watermark_page.mediabox[3]) - float(watermark_page.mediabox[1])
        except Exception:
            # Fallback to text measurement
            font_name = _resolve_font(args.font)
            text_width = pdfmetrics.stringWidth(args.text, font_name, args.font_size)
            ow = text_width + 4
            oh = args.font_size + 4
    else:
        ow = oh = None  # not used

    print("Applying watermarks...")
    for i, page in enumerate(pdf.pages):
        if (pages_to_process is None) or (i in pages_to_process):
            if is_tiled:
                page.add_overlay(watermark_page, pikepdf.Rectangle(page.mediabox))
            else:
                # Compute per-page rect
                try:
                    pw = float(page.mediabox[2]) - float(page.mediabox[0])
                    ph = float(page.mediabox[3]) - float(page.mediabox[1])
                except Exception:
                    # Fallback to letter if mediabox unusual
                    pw, ph = letter
                rect = _placement_rect(pw, ph, ow, oh, args.position, args.margin)
                if rect is None:
                    rect = pikepdf.Rectangle(page.mediabox)
                else:
                    rect = pikepdf.Rectangle(*rect)
                page.add_overlay(watermark_page, rect)

    print(f"Saving to: {output_pdf}")
    try:
        pdf.save(output_pdf)
    except Exception as e:
        print(f"Error: could not save output PDF: {e}", file=sys.stderr)
        sys.exit(2)
    print("Done.")


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_watermark(args)


if __name__ == "__main__":
    main()
