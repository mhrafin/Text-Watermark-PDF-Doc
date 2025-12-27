# watermark.py
import pikepdf
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import sys
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Configuration ---
# The text you want to appear as the watermark.
WATERMARK_TEXT = "Personal use only. No commercial printing."

# Font size of the watermark text.
FONT_SIZE = 9

# Font name to use for the watermark.
# You can use standard fonts like "Helvetica", "Times-Roman", "Courier"
# Or the custom font registered below.
FONT_NAME = "Amiri-Regular"

# Path to a custom TTF font file (Google Font).
# Set to None to use standard fonts.
CUSTOM_FONT_PATH = "Amiri-Regular.ttf"
CUSTOM_FONT_NAME = "Amiri-Regular"

# Opacity of the watermark (0.0 to 1.0).
# Lower values make it more transparent (fainter).
OPACITY = 0.35

# Which pages to watermark.
# Set to None to watermark ALL pages.
# Set to a list of page indices (0-based) to watermark only specific pages.
# OR set to a string to define ranges (1-based, inclusive):
# Example: "2-31, 55, 77, 100-110"
# This will watermark pages 2 through 31, page 55, page 77, and pages 100 through 110.
PAGES_TO_WATERMARK = "2-31, 574-695" 
# ---------------------

def parse_page_ranges(ranges_str):
    """
    Parses a string of page ranges (1-based) into a set of 0-based indices.
    Example: "1-3, 5" -> {0, 1, 2, 4}
    """
    if not ranges_str:
        return None
    
    indices = set()
    parts = [p.strip() for p in ranges_str.split(',')]
    
    for part in parts:
        if '-' in part:
            try:
                start_str, end_str = part.split('-')
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

def make_watermark_pdf(text):
    """
    Creates a temporary PDF in memory containing the watermark text.
    Uses ReportLab to draw the text.
    """
    packet = io.BytesIO()
    # Create a new PDF canvas
    c = canvas.Canvas(packet, pagesize=letter)
    
    # Register custom font if provided
    if CUSTOM_FONT_PATH and os.path.exists(CUSTOM_FONT_PATH):
        try:
            pdfmetrics.registerFont(TTFont(CUSTOM_FONT_NAME, CUSTOM_FONT_PATH))
        except Exception as e:
            print(f"Warning: Could not register font {CUSTOM_FONT_NAME}: {e}")
            print("Falling back to default font.")
    
    # Set font and transparency
    c.setFont(FONT_NAME, FONT_SIZE)
    c.setFillGray(0, alpha=OPACITY)
    
    # Calculate position: Lower-right corner with a small margin
    width, height = letter
    x = width - 40  # 40 points from the right edge
    y = 30          # 30 points from the bottom edge
    
    # Draw the text aligned to the right at the specified position
    c.drawRightString(x, y, text)
    
    # Finalize the PDF page and save it to the buffer
    c.save()
    packet.seek(0)
    return packet

def apply_watermark(input_pdf, output_pdf):
    """
    Opens the input PDF, creates a watermark, overlays it on the specified pages,
    and saves the result to the output PDF.
    """
    print(f"Opening input file: {input_pdf}")
    # Load the input PDF using pikepdf
    pdf = pikepdf.Pdf.open(input_pdf)
    
    # Generate the watermark PDF stream in memory
    watermark_stream = make_watermark_pdf(WATERMARK_TEXT)
    
    # Open the generated watermark PDF
    watermark_pdf = pikepdf.Pdf.open(watermark_stream)
    watermark_page = watermark_pdf.pages[0]

    # Determine which pages to watermark
    pages_to_process = PAGES_TO_WATERMARK
    if isinstance(pages_to_process, str):
        pages_to_process = parse_page_ranges(pages_to_process)
        print(f"Parsed page ranges: {sorted(list(pages_to_process)) if pages_to_process else 'None'}")

    # Iterate over all pages in the input PDF
    print("Applying watermarks...")
    for i, page in enumerate(pdf.pages):
        # Check if this page should be watermarked based on the configuration
        if (pages_to_process is None) or (i in pages_to_process):
            # Apply the watermark page as an overlay to the current page
            # We use the page's own MediaBox to ensure correct scaling/positioning
            page.add_overlay(watermark_page, pikepdf.Rectangle(page.mediabox))

    # Save the modified PDF to the output file
    print(f"Saving to: {output_pdf}")
    pdf.save(output_pdf)
    print("Done.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python watermark.py <input_pdf_path> <output_pdf_path>")
        print("Example: python watermark.py my_document.pdf watermarked_doc.pdf")
    else:
        apply_watermark(sys.argv[1], sys.argv[2])
