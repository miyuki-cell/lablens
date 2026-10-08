"""
Tests for the Section Extractor.

Run with:
    cd lablens/backend
    python -m pytest tests/test_section_extractor.py -v
"""

import io
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parser.pdf_parser import parse_pdf
from section_extractor.section_extractor import (
    extract_sections,
    SectionMap,
    SECTION_KEYS,
    _detect_toc_pages,
    _match_heading,
    _clean_section_text,
)
from parser.pdf_parser import ParsedPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf(pages: list[str]) -> bytes:
    import fitz
    doc = fitz.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 100), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


SAMPLE_PDF = os.path.join(
    os.path.dirname(__file__), "..", "sample_pdfs", "020_pika_modul2_DGpraktik.pdf"
)
SAMPLE_AVAILABLE = os.path.isfile(SAMPLE_PDF)


# ---------------------------------------------------------------------------
# Unit: _detect_toc_pages
# ---------------------------------------------------------------------------

class TestDetectTocPages:
    def _make_page(self, num: int, text: str) -> ParsedPage:
        return ParsedPage(page_number=num, text=text)

    def test_page_with_many_dot_leaders_is_toc(self):
        toc_text = (
            "DAFTAR ISI\n"
            "BAB I PENDAHULUAN .......... 2\n"
            "1.1 Tujuan ................. 2\n"
            "2.1 Flowchart .............. 3\n"
            "2.2 Pseudocode ............. 4\n"
        )
        page = self._make_page(2, toc_text)
        result = _detect_toc_pages([page])
        assert 2 in result

    def test_regular_page_is_not_toc(self):
        regular_text = "BAB I\nPENDAHULUAN\n1.1 Tujuan\nMahasiswa memahami konsep."
        page = self._make_page(3, regular_text)
        result = _detect_toc_pages([page])
        assert 3 not in result

    def test_two_dot_leaders_below_threshold(self):
        text = "Some text\nA .... 1\nB .... 2\nOther content here"
        page = self._make_page(1, text)
        result = _detect_toc_pages([page])
        assert 1 not in result  # only 2 dot-leader lines, threshold is 3


# ---------------------------------------------------------------------------
# Unit: _match_heading
# ---------------------------------------------------------------------------

class TestMatchHeading:
    def test_numbered_pseudocode_heading(self):
        assert _match_heading("2.2 Pseudocode") == "pseudocode"

    def test_numbered_code_heading(self):
        assert _match_heading("2.3 Kode Program") == "code"

    def test_numbered_analysis_heading(self):
        assert _match_heading("2.4 Analisis Program") == "analysis"

    def test_numbered_flowchart_heading(self):
        assert _match_heading("2.1 Diagram Flowchart") == "flowchart"

    def test_conclusion_heading(self):
        assert _match_heading("3.4 Kesimpulan") == "conclusion"

    def test_bab_i_is_pendahuluan(self):
        assert _match_heading("BAB I") == "pendahuluan"

    def test_daftar_pustaka(self):
        assert _match_heading("DAFTAR PUSTAKA") == "references"

    def test_toc_line_dot_leader_rejected(self):
        # This is a ToC entry — must NOT match
        assert _match_heading("2.2 Pseudocode ............. 4") is None

    def test_empty_line_returns_none(self):
        assert _match_heading("") is None

    def test_regular_content_line_returns_none(self):
        assert _match_heading("Program menggunakan perulangan for.") is None

    def test_case_insensitive_bab(self):
        assert _match_heading("BAB i") == "pendahuluan"


# ---------------------------------------------------------------------------
# Unit: _clean_section_text
# ---------------------------------------------------------------------------

class TestCleanSectionText:
    def test_strips_curly_quote_instructions(self):
        text = "\u201cSetiap soal wajib memiliki diagram flowchart\u201d\nReal content here"
        result = _clean_section_text(text)
        assert "Setiap soal" not in result
        assert "Real content here" in result

    def test_strips_multiline_curly_quote_instructions(self):
        text = "\u201cFormat pseudocode bebas dengan ketentuan jelas\ndan sesuai dengan flowchart\u201d\nPROGRAM Start"
        result = _clean_section_text(text)
        assert "Format pseudocode" not in result
        assert "PROGRAM Start" in result

    def test_removes_lone_page_numbers(self):
        text = "Some content\n4\nMore content\n12"
        result = _clean_section_text(text)
        assert "\n4\n" not in result
        assert "\n12" not in result
        assert "Some content" in result
        assert "More content" in result

    def test_preserves_real_code(self):
        code = "#include<iostream>\nusing namespace std;\nint main(){\n    return 0;\n}"
        result = _clean_section_text(code)
        assert "#include" in result
        assert "int main" in result

    def test_collapses_blank_lines(self):
        text = "line1\n\n\n\nline2"
        result = _clean_section_text(text)
        assert "\n\n\n" not in result

    def test_empty_input_returns_empty(self):
        assert _clean_section_text("") == ""

    def test_only_placeholder_returns_empty(self):
        text = "\u201cCantumkan analisis program atau deskripsi program\nsesuai dengan perintah pada subbab 1.3\u201d"
        result = _clean_section_text(text)
        assert result.strip() == ""


# ---------------------------------------------------------------------------
# Integration: real PDF
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not SAMPLE_AVAILABLE, reason="Sample PDF not available")
class TestRealPdf:
    @pytest.fixture(scope="class")
    def smap(self):
        report = parse_pdf(SAMPLE_PDF)
        return extract_sections(report)

    def test_returns_section_map(self, smap):
        assert isinstance(smap, SectionMap)
        assert smap.filename == "020_pika_modul2_DGpraktik.pdf"

    def test_pendahuluan_has_content(self, smap):
        text = smap.sections.get("pendahuluan", "")
        assert len(text) > 100
        # Should contain educational content
        assert "percabangan" in text.lower() or "tujuan" in text.lower()

    def test_pseudocode_has_content(self, smap):
        text = smap.sections.get("pseudocode", "")
        assert len(text) > 50
        # Should contain pseudocode keywords
        assert any(kw in text for kw in ["READ", "WRITE", "ALGORITMA", "if", "PROGRAM"])

    def test_code_has_cpp_content(self, smap):
        text = smap.sections.get("code", "")
        assert len(text) > 50
        assert "#include" in text
        assert "int main" in text

    def test_analysis_is_near_empty(self, smap):
        """This student left analysis nearly empty — only sub-headings remain."""
        text = smap.sections.get("analysis", "")
        # After placeholder stripping, only the sub-headings remain
        # It should be short (< 100 chars) or missing entirely
        assert len(text) < 120

    def test_conclusion_has_real_text(self, smap):
        text = smap.sections.get("conclusion", "")
        assert len(text) > 50
        assert "switch" in text.lower() or "kendala" in text.lower()

    def test_toc_content_not_in_sections(self, smap):
        """Section text must not contain dot-leader ToC entries."""
        for key, text in smap.sections.items():
            assert "............" not in text, (
                f"Section '{key}' appears to contain ToC dot-leaders"
            )

    def test_page_map_populated(self, smap):
        assert len(smap.page_map) > 0
        # Pseudocode is on pages 7-8, code on 9-10
        if "pseudocode" in smap.page_map:
            assert min(smap.page_map["pseudocode"]) >= 7
        if "code" in smap.page_map:
            assert min(smap.page_map["code"]) >= 9

    def test_placeholder_text_stripped(self, smap):
        """Template instruction text (curly-quoted) must be gone from all sections."""
        placeholder_markers = [
            "Setiap soal wajib",
            "Format pseudocode bebas",
            "Cantumkan analisis",
            "Berikan screenshot",
            "Kesimpulan laporan, dapat diisi",
        ]
        for key, text in smap.sections.items():
            for marker in placeholder_markers:
                assert marker not in text, (
                    f"Section '{key}' still contains placeholder: '{marker}'"
                )
