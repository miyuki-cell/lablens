"""
Tests for the PDF parser.

Run with:
    cd lablens/backend
    python -m pytest tests/test_pdf_parser.py -v
"""

import io
import os
import sys
import pytest

# Allow importing from parent package without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parser.pdf_parser import parse_pdf, ParsedReport, ParsedPage, _normalize_whitespace


# ---------------------------------------------------------------------------
# Helpers — build a minimal in-memory PDF using fitz
# ---------------------------------------------------------------------------

def _make_test_pdf(pages: list[str]) -> bytes:
    """Create a minimal PDF in memory with the given page texts."""
    import fitz
    doc = fitz.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 100), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNormalizeWhitespace:
    def test_strips_trailing_spaces(self):
        result = _normalize_whitespace("hello   \nworld  ")
        assert result == "hello\nworld"

    def test_collapses_blank_lines(self):
        result = _normalize_whitespace("a\n\n\n\nb")
        assert result == "a\n\nb"

    def test_empty_input(self):
        assert _normalize_whitespace("") == ""

    def test_only_whitespace(self):
        assert _normalize_whitespace("   \n   \n  ") == ""


class TestParsePdfFromBytes:
    def test_single_page(self):
        pdf_bytes = _make_test_pdf(["Hello, LabLens!"])
        report = parse_pdf(pdf_bytes)
        assert isinstance(report, ParsedReport)
        assert report.filename == "<bytes>"
        assert len(report.pages) == 1
        assert report.pages[0].page_number == 1
        assert "Hello" in report.pages[0].text

    def test_multi_page(self):
        pdf_bytes = _make_test_pdf(["Page one text", "Page two text", "Page three text"])
        report = parse_pdf(pdf_bytes)
        assert len(report.pages) == 3
        assert report.pages[0].page_number == 1
        assert report.pages[2].page_number == 3

    def test_blank_page_skipped(self):
        """A page with only whitespace should be omitted from output."""
        pdf_bytes = _make_test_pdf(["Real content", "   \n  "])
        report = parse_pdf(pdf_bytes)
        # The blank page may or may not yield whitespace depending on fitz internals,
        # but any truly blank-after-normalization page must be skipped.
        for p in report.pages:
            assert p.text.strip() != ""

    def test_to_dict_schema(self):
        pdf_bytes = _make_test_pdf(["Test page"])
        report = parse_pdf(pdf_bytes)
        d = report.to_dict()
        assert "filename" in d
        assert "pages" in d
        assert isinstance(d["pages"], list)
        assert "page_number" in d["pages"][0]
        assert "text" in d["pages"][0]

    def test_full_text_separator(self):
        pdf_bytes = _make_test_pdf(["Alpha", "Beta"])
        report = parse_pdf(pdf_bytes)
        full = report.full_text
        assert "\f" in full  # pages joined by form-feed
        assert "Alpha" in full
        assert "Beta" in full


class TestParsePdfFromPath:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_pdf(tmp_path / "nonexistent.pdf")

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            parse_pdf(12345)  # type: ignore[arg-type]

    def test_from_path(self, tmp_path):
        pdf_bytes = _make_test_pdf(["Path-based test"])
        pdf_path = tmp_path / "sample.pdf"
        pdf_path.write_bytes(pdf_bytes)

        report = parse_pdf(pdf_path)
        assert report.filename == "sample.pdf"
        assert len(report.pages) >= 1
        assert "Path" in report.pages[0].text
