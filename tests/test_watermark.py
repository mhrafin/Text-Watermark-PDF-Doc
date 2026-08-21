import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pikepdf
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4

# Import from watermark.py
import watermark
from watermark import (
    parse_page_ranges,
    _placement_rect,
    make_watermark_overlay,
    build_parser,
    _derive_output_path,
    _resolve_font,
)


class TestParsePageRanges(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(parse_page_ranges(""))
        self.assertIsNone(parse_page_ranges(None))

    def test_single_page(self):
        self.assertEqual(parse_page_ranges("1"), {0})
        self.assertEqual(parse_page_ranges("5"), {4})

    def test_range(self):
        self.assertEqual(parse_page_ranges("1-3"), {0, 1, 2})
        self.assertEqual(parse_page_ranges("2-10"), set(range(1, 10)))

    def test_mixed_ranges(self):
        self.assertEqual(parse_page_ranges("1-3, 5"), {0, 1, 2, 4})
        self.assertEqual(parse_page_ranges("2-10,127-132"), set(list(range(1, 10)) + list(range(126, 132))))

    def test_spaces_and_commas(self):
        self.assertEqual(parse_page_ranges("1-3, 5, 10-12"), {0, 1, 2, 4, 9, 10, 11})

    def test_invalid_tokens_warn(self):
        with patch("builtins.print") as mock_print:
            result = parse_page_ranges("foo,1-3,bar")
            self.assertEqual(result, {0, 1, 2})
            # Should have warned twice
            self.assertTrue(mock_print.called)

    def test_invalid_range_format(self):
        with patch("builtins.print"):
            result = parse_page_ranges("1-foo")
            # Invalid range ignored, returns empty set
            self.assertEqual(result, set())


class TestPlacementRect(unittest.TestCase):
    def test_lower_right(self):
        rect = _placement_rect(612, 792, 100, 20, "lower-right", 36)
        self.assertEqual(rect, (612 - 100 - 36, 36, 612 - 36, 36 + 20))

    def test_lower_left(self):
        rect = _placement_rect(612, 792, 100, 20, "lower-left", 24)
        self.assertEqual(rect, (24, 24, 124, 44))

    def test_top_right(self):
        rect = _placement_rect(612, 792, 100, 20, "top-right", 10)
        self.assertEqual(rect, (502, 762, 602, 782))

    def test_top_left(self):
        rect = _placement_rect(612, 792, 100, 20, "top-left", 24)
        self.assertEqual(rect, (24, 748, 124, 768))

    def test_center(self):
        rect = _placement_rect(612, 792, 100, 20, "center", 36)
        self.assertEqual(rect, ((612 - 100) / 2, (792 - 20) / 2, (612 + 100) / 2, (792 + 20) / 2))

    def test_center_ignores_margin(self):
        r1 = _placement_rect(612, 792, 100, 20, "center", 36)
        r2 = _placement_rect(612, 792, 100, 20, "center", 100)
        self.assertEqual(r1, r2)

    def test_tile_returns_none(self):
        self.assertIsNone(_placement_rect(612, 792, 100, 20, "tile", 36))
        self.assertIsNone(_placement_rect(612, 792, 100, 20, "tile", 100))

    def test_consistent_across_page_sizes(self):
        # Same margin on letter and A4 should produce same offset from edges
        for pos in ["lower-right", "lower-left", "top-right", "top-left"]:
            rect_letter = _placement_rect(letter[0], letter[1], 100, 20, pos, 36)
            rect_a4 = _placement_rect(A4[0], A4[1], 100, 20, pos, 36)
            # Check that margin is respected: x0 or x1 distance to edge equals margin
            if pos == "lower-right":
                self.assertAlmostEqual(letter[0] - rect_letter[2], 36)
                self.assertAlmostEqual(A4[0] - rect_a4[2], 36)
                self.assertAlmostEqual(rect_letter[1], 36)
            elif pos == "top-left":
                self.assertAlmostEqual(rect_letter[0], 36)
                self.assertAlmostEqual(rect_a4[0], 36)


class TestOverlaySizing(unittest.TestCase):
    def test_overlay_sized_to_text(self):
        text = "Draft"
        font_size = 12
        overlay = make_watermark_overlay(text, None, font_size, 0.5, 0, "lower-right", 36)
        pdf = pikepdf.Pdf.open(overlay)
        page = pdf.pages[0]
        ow = float(page.mediabox[2]) - float(page.mediabox[0])
        oh = float(page.mediabox[3]) - float(page.mediabox[1])
        expected_w = pdfmetrics.stringWidth(text, "Helvetica", font_size) + 4  # 2*pad
        expected_h = font_size + 4
        self.assertAlmostEqual(ow, expected_w, places=1)
        self.assertAlmostEqual(oh, expected_h, places=1)

    def test_different_fonts_different_widths(self):
        text = "Hello"
        size = 12
        # Helvetica vs Times-Roman should differ
        overlay_h = make_watermark_overlay(text, None, size, 0.5, 0, "lower-right", 36)
        # For custom font, use Amiri if available, otherwise skip
        if Path("Amiri-Regular.ttf").exists():
            overlay_a = make_watermark_overlay(text, "Amiri-Regular.ttf", size, 0.5, 0, "lower-right", 36)
            pdf_h = pikepdf.Pdf.open(overlay_h)
            pdf_a = pikepdf.Pdf.open(overlay_a)
            ow_h = float(pdf_h.pages[0].mediabox[2]) - float(pdf_h.pages[0].mediabox[0])
            ow_a = float(pdf_a.pages[0].mediabox[2]) - float(pdf_a.pages[0].mediabox[0])
            self.assertNotEqual(ow_h, ow_a)

    def test_tile_overlay_is_letter_sized(self):
        overlay = make_watermark_overlay("TILE", None, 9, 0.5, 45, "tile", 36)
        pdf = pikepdf.Pdf.open(overlay)
        page = pdf.pages[0]
        ow = float(page.mediabox[2]) - float(page.mediabox[0])
        oh = float(page.mediabox[3]) - float(page.mediabox[1])
        self.assertAlmostEqual(ow, letter[0], places=0)
        self.assertAlmostEqual(oh, letter[1], places=0)

    def test_opacity_and_angle_do_not_crash(self):
        # Just verify it creates a valid PDF
        for angle in [0, 30, 45, 90]:
            overlay = make_watermark_overlay("Test", None, 9, 0.3, angle, "lower-right", 36)
            pdf = pikepdf.Pdf.open(overlay)
            self.assertEqual(len(pdf.pages), 1)


class TestDeriveOutputPath(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(_derive_output_path("input.pdf"), "input_watermarked.pdf")
        self.assertEqual(_derive_output_path("/tmp/foo/bar.pdf"), "/tmp/foo/bar_watermarked.pdf")

    def test_with_spaces(self):
        self.assertEqual(_derive_output_path("/tmp/test with spaces.pdf"), "/tmp/test with spaces_watermarked.pdf")


class TestResolveFont(unittest.TestCase):
    def test_none_returns_helvetica(self):
        self.assertEqual(_resolve_font(None), "Helvetica")

    def test_valid_ttf(self):
        if Path("Amiri-Regular.ttf").exists():
            name = _resolve_font("Amiri-Regular.ttf")
            self.assertEqual(name, "Amiri-Regular")
            self.assertIn("Amiri-Regular", pdfmetrics.getRegisteredFontNames())

    def test_missing_exits(self):
        with self.assertRaises(SystemExit) as cm:
            _resolve_font("/tmp/nonexistent_font_xyz.ttf")
        self.assertEqual(cm.exception.code, 2)


class TestBuildParser(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    def test_defaults(self):
        # Create a dummy input file for parsing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(b"%PDF-1.4\n%%EOF")
            fname = tf.name
        try:
            args = self.parser.parse_args([fname])
            self.assertEqual(args.text, "Personal use only. No commercial printing.")
            self.assertEqual(args.font_size, 9)
            self.assertEqual(args.opacity, 0.5)
            self.assertIsNone(args.pages)
            self.assertEqual(args.position, "lower-right")
            self.assertEqual(args.angle, 0.0)
            self.assertEqual(args.margin, 36.0)
            self.assertFalse(args.dry_run)
            self.assertEqual(args.input, fname)
            self.assertIsNone(args.output)
        finally:
            os.unlink(fname)

    def test_custom_values(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(b"%PDF-1.4\n%%EOF")
            fname = tf.name
        try:
            args = self.parser.parse_args([fname, "/tmp/out.pdf", "--text", "Hi", "--font-size", "12", "--opacity", "0.3", "--pages", "1-2", "--position", "center", "--angle", "45", "--margin", "24"])
            self.assertEqual(args.text, "Hi")
            self.assertEqual(args.font_size, 12)
            self.assertEqual(args.opacity, 0.3)
            self.assertEqual(args.pages, "1-2")
            self.assertEqual(args.position, "center")
            self.assertEqual(args.angle, 45)
            self.assertEqual(args.margin, 24)
            self.assertEqual(args.output, "/tmp/out.pdf")
        finally:
            os.unlink(fname)

    def test_opacity_validation(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            fname = tf.name
            tf.write(b"%PDF")
        try:
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--opacity", "1.5"])
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--opacity", "-0.1"])
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--opacity", "foo"])
        finally:
            os.unlink(fname)

    def test_margin_validation(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            fname = tf.name
            tf.write(b"%PDF")
        try:
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--margin", "-5"])
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--margin", "abc"])
        finally:
            os.unlink(fname)

    def test_position_choices(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            fname = tf.name
            tf.write(b"%PDF")
        try:
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--position", "invalid"])
            for pos in ["lower-right", "lower-left", "top-right", "top-left", "center", "tile"]:
                args = self.parser.parse_args([fname, "--position", pos])
                self.assertEqual(args.position, pos)
        finally:
            os.unlink(fname)

    def test_font_size_validation(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            fname = tf.name
            tf.write(b"%PDF")
        try:
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--font-size", "-1"])
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--font-size", "0"])
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--font-size", "abc"])
        finally:
            os.unlink(fname)

    def test_angle_validation(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            fname = tf.name
            tf.write(b"%PDF")
        try:
            with self.assertRaises(SystemExit):
                self.parser.parse_args([fname, "--angle", "notanumber"])
        finally:
            os.unlink(fname)

    def test_missing_input(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])

    def test_output_derivation_via_main(self):
        # Test that main derives output when not provided
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            # Create a valid 1-page PDF via reportlab
            c = canvas.Canvas(tf.name, pagesize=letter)
            c.drawString(100, 700, "hello")
            c.save()
            fname = tf.name
        derived = _derive_output_path(fname)
        # Ensure dry-run doesn't create file
        args = self.parser.parse_args([fname, "--dry-run"])
        # Simulate apply_watermark dry-run path
        from watermark import apply_watermark

        # Capture stdout
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            apply_watermark(args)
            out = fake_out.getvalue()
            self.assertIn("Dry-run", out)
            self.assertIn(derived, out)
        self.assertFalse(os.path.exists(derived))
        os.unlink(fname)
        if os.path.exists(derived):
            os.unlink(derived)

    def test_dry_run_with_pages(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            c = canvas.Canvas(tf.name, pagesize=letter)
            for i in range(3):
                c.drawString(100, 700, f"page {i}")
                c.showPage()
            c.save()
            fname = tf.name
        try:
            args = self.parser.parse_args([fname, "--pages", "1-2", "--dry-run"])
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                from watermark import apply_watermark

                apply_watermark(args)
                out = fake_out.getvalue()
                self.assertIn("would watermark 2 of 3", out)
        finally:
            os.unlink(fname)


class TestApplyWatermarkIntegration(unittest.TestCase):
    def _create_pdf(self, pages=3, pagesize=letter):
        tf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        c = canvas.Canvas(tf.name, pagesize=pagesize)
        for i in range(pages):
            c.drawString(100, 700, f"page {i+1}")
            c.showPage()
        c.save()
        return tf.name

    def test_watermark_all_pages(self):
        inp = self._create_pdf(3)
        out = inp.replace(".pdf", "_out.pdf")
        try:
            parser = build_parser()
            args = parser.parse_args([inp, out, "--text", "Test"])
            from watermark import apply_watermark

            apply_watermark(args)
            self.assertTrue(os.path.exists(out))
            pdf = pikepdf.Pdf.open(out)
            self.assertEqual(len(pdf.pages), 3)
        finally:
            for f in [inp, out]:
                if os.path.exists(f):
                    os.unlink(f)

    def test_pages_filter(self):
        inp = self._create_pdf(5)
        out = inp.replace(".pdf", "_out.pdf")
        try:
            parser = build_parser()
            args = parser.parse_args([inp, out, "--pages", "1-2,5", "--text", "Filtered"])
            from watermark import apply_watermark

            # Should not crash, and output should exist
            apply_watermark(args)
            self.assertTrue(os.path.exists(out))
        finally:
            for f in [inp, out]:
                if os.path.exists(f):
                    os.unlink(f)

    def test_mixed_page_sizes(self):
        tf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        c = canvas.Canvas(tf.name, pagesize=letter)
        c.drawString(100, 700, "letter")
        c.showPage()
        c.setPageSize(A4)
        c.drawString(100, 700, "A4")
        c.showPage()
        c.save()
        inp = tf.name
        out = inp.replace(".pdf", "_out.pdf")
        try:
            parser = build_parser()
            for pos in ["lower-right", "center", "top-left"]:
                args = parser.parse_args([inp, out, "--position", pos, "--margin", "24", "--text", "Mixed"])
                from watermark import apply_watermark

                apply_watermark(args)
                self.assertTrue(os.path.exists(out))
        finally:
            for f in [inp, out]:
                if os.path.exists(f):
                    os.unlink(f)

    def test_tile_and_angle(self):
        inp = self._create_pdf(2)
        out = inp.replace(".pdf", "_out.pdf")
        try:
            parser = build_parser()
            args = parser.parse_args([inp, out, "--position", "tile", "--angle", "30", "--text", "TILE"])
            from watermark import apply_watermark

            apply_watermark(args)
            self.assertTrue(os.path.exists(out))
            # Tile should ignore margin, but still succeed with large margin
            args2 = parser.parse_args([inp, out, "--position", "tile", "--margin", "100", "--text", "TILE"])
            apply_watermark(args2)
            self.assertTrue(os.path.exists(out))
        finally:
            for f in [inp, out]:
                if os.path.exists(f):
                    os.unlink(f)


if __name__ == "__main__":
    unittest.main()
