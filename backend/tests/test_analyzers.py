"""
Tests for all analyzers: completeness, pseudo_code, analysis_code.

Run with:
    cd lablens/backend
    python -m pytest tests/test_analyzers.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from section_extractor.section_extractor import SectionMap
from analyzers import completeness_analyzer, pseudo_code_analyzer, analysis_code_analyzer
from analyzers.models import Finding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_smap(sections: dict, page_map: dict | None = None) -> SectionMap:
    return SectionMap(
        filename="test.pdf",
        sections=sections,
        missing=[],
        page_map=page_map or {},
    )


SAMPLE_PDF = os.path.join(
    os.path.dirname(__file__), "..", "sample_pdfs", "020_pika_modul2_DGpraktik.pdf"
)
SAMPLE_AVAILABLE = os.path.isfile(SAMPLE_PDF)


# ===========================================================================
# completeness_analyzer
# ===========================================================================

class TestCompletenessAnalyzer:
    def test_no_findings_when_all_sections_present(self):
        sections = {
            "pendahuluan": "A" * 100,
            "flowchart":   "B" * 100,
            "pseudocode":  "C" * 100,
            "code":        "D" * 100,
            "analysis":    "E" * 100,
            "output":      "F" * 100,
            "conclusion":  "G" * 100,
        }
        smap = _make_smap(sections)
        findings = completeness_analyzer.analyze(smap)
        assert findings == []

    def test_missing_section_generates_high_finding(self):
        # analysis is absent entirely (not in sections, not in page_map)
        sections = {k: "x" * 100 for k in
                    ["pendahuluan","flowchart","pseudocode","code","output","conclusion"]}
        smap = _make_smap(sections, page_map={})
        findings = completeness_analyzer.analyze(smap)
        types = [f.type for f in findings]
        assert "missing_section" in types
        missing = [f for f in findings if f.type == "missing_section"]
        assert missing[0].section == "analysis"
        assert missing[0].severity == "HIGH"

    def test_empty_section_generates_high_finding(self):
        # analysis heading was found (in page_map) but content is empty
        sections = {k: "x" * 100 for k in
                    ["pendahuluan","flowchart","pseudocode","code","output","conclusion"]}
        smap = _make_smap(sections, page_map={"analysis": [11]})
        findings = completeness_analyzer.analyze(smap)
        empty = [f for f in findings if f.type == "empty_section"]
        assert len(empty) == 1
        assert empty[0].section == "analysis"
        assert empty[0].severity == "HIGH"

    def test_thin_section_generates_medium_finding(self):
        sections = {k: "x" * 100 for k in
                    ["pendahuluan","flowchart","pseudocode","code","output","conclusion"]}
        sections["analysis"] = "2.4.1 Sub A\n2.4.2 Sub B"   # < 80 chars
        smap = _make_smap(sections)
        findings = completeness_analyzer.analyze(smap)
        thin = [f for f in findings if f.type == "thin_section"]
        assert len(thin) == 1
        assert thin[0].severity == "MEDIUM"

    def test_finding_has_required_fields(self):
        smap = _make_smap({}, page_map={})
        findings = completeness_analyzer.analyze(smap)
        for f in findings:
            assert isinstance(f, Finding)
            assert f.type
            assert f.severity in ("LOW", "MEDIUM", "HIGH")
            assert f.title
            assert f.reason


# ===========================================================================
# pseudo_code_analyzer
# ===========================================================================

class TestPseudoCodeAnalyzer:
    def test_no_findings_when_no_sections(self):
        smap = _make_smap({})
        assert pseudo_code_analyzer.analyze(smap) == []

    def test_no_findings_when_pseudocode_missing(self):
        smap = _make_smap({"code": "if (x > 0) { y = 1; }"})
        assert pseudo_code_analyzer.analyze(smap) == []

    def test_threshold_mismatch_detected(self):
        pseudo = "if nilai >= 75 then\n    print Lulus\nelse\n    print Tidak Lulus"
        code   = "if (nilai >= 80) {\n    cout << \"Lulus\";\n} else {\n    cout << \"Tidak Lulus\";\n}"
        smap   = _make_smap({"pseudocode": pseudo, "code": code})
        findings = pseudo_code_analyzer.analyze(smap)
        types = [f.type for f in findings]
        assert "pseudo_code_threshold_mismatch" in types

    def test_no_threshold_mismatch_when_values_match(self):
        pseudo = "if nilai >= 80 then Lulus else Tidak Lulus"
        code   = "if (nilai >= 80) { cout << \"Lulus\"; } else { cout << \"Tidak Lulus\"; }"
        smap   = _make_smap({"pseudocode": pseudo, "code": code})
        findings = pseudo_code_analyzer.analyze(smap)
        types = [f.type for f in findings]
        assert "pseudo_code_threshold_mismatch" not in types

    def test_loop_in_pseudo_not_code_detected(self):
        pseudo = "for i = 1 to 10\n    print i\nend for"
        code   = "cout << \"hello\";"
        smap   = _make_smap({"pseudocode": pseudo, "code": code})
        findings = pseudo_code_analyzer.analyze(smap)
        types = [f.type for f in findings]
        assert "pseudo_code_loop_mismatch" in types
        match = [f for f in findings if f.type == "pseudo_code_loop_mismatch"][0]
        assert match.severity == "MEDIUM"

    def test_switch_case_mismatch_detected(self):
        pseudo = "SWITCH x\n    case 1: WRITE a\n    case 2: WRITE b\nEnd switch"
        code   = "switch(x) {\n    case 1: cout << a; break;\n    case 3: cout << c; break;\n}"
        smap   = _make_smap({"pseudocode": pseudo, "code": code})
        findings = pseudo_code_analyzer.analyze(smap)
        types = [f.type for f in findings]
        assert "pseudo_code_switch_case_mismatch" in types

    def test_internal_switch_inconsistency_detected(self):
        # Kategori is assigned 1 and 3 but case 2 is defined — case 2 unreachable
        pseudo = (
            "If angka >= 1 and angka <= 10 then\n"
            "    Kategori = 1\n"
            "Else if angka >= 11 and angka <= 50 then\n"
            "    Kategori = 3\n"           # bug: should be 2
            "Else\n"
            "    Kategori = 0\n"
            "End if\n"
            "SWITCH Kategori\n"
            "    case 1: WRITE small\n"
            "    case 2: WRITE medium\n"   # case 2 never reachable
            "    case 3: WRITE large\n"
            "End switch"
        )
        code = "switch(k) { case 1: break; case 2: break; case 3: break; }"
        smap = _make_smap({"pseudocode": pseudo, "code": code})
        findings = pseudo_code_analyzer.analyze(smap)
        types = [f.type for f in findings]
        assert "pseudo_internal_switch_inconsistency" in types
        inc = [f for f in findings if f.type == "pseudo_internal_switch_inconsistency"][0]
        assert inc.severity == "HIGH"
        assert "2" in str(inc.evidence["case_label_never_assigned"])


# ===========================================================================
# analysis_code_analyzer
# ===========================================================================

class TestAnalysisCodeAnalyzer:
    def test_no_findings_when_no_sections(self):
        smap = _make_smap({})
        assert analysis_code_analyzer.analyze(smap) == []

    def test_no_findings_when_analysis_too_short(self):
        # Short analysis is handled by completeness; this analyzer skips it
        smap = _make_smap({"code": "for(int i=0;i<10;i++){}", "analysis": "Short."})
        assert analysis_code_analyzer.analyze(smap) == []

    def test_unmentioned_for_loop_detected(self):
        code     = "for(int i = 0; i < 10; i++) { cout << i; }"
        analysis = "x" * 100 + " Program ini menggunakan variabel integer."
        smap     = _make_smap({"code": code, "analysis": analysis})
        findings = analysis_code_analyzer.analyze(smap)
        types = [f.type for f in findings]
        assert "analysis_missing_construct_mention" in types
        match = [f for f in findings if f.type == "analysis_missing_construct_mention"][0]
        assert match.evidence["construct"] == "for loop"

    def test_mentioned_construct_no_finding(self):
        code     = "for(int i = 0; i < 10; i++) { cout << i; }"
        analysis = "x" * 100 + " Program ini menggunakan perulangan for untuk iterasi."
        smap     = _make_smap({"code": code, "analysis": analysis})
        findings = analysis_code_analyzer.analyze(smap)
        # "for loop" should NOT be flagged because "perulangan" is in analysis
        loop_findings = [f for f in findings
                         if f.type == "analysis_missing_construct_mention"
                         and f.evidence.get("construct") == "for loop"]
        assert loop_findings == []

    def test_switch_not_mentioned_in_analysis_detected(self):
        code     = "switch(x) { case 1: cout << 1; break; }"
        analysis = "x" * 100 + " Program menggunakan if-else untuk memilih kondisi."
        smap     = _make_smap({"code": code, "analysis": analysis})
        findings = analysis_code_analyzer.analyze(smap)
        types = [f.type for f in findings]
        assert "analysis_missing_construct_mention" in types


# ===========================================================================
# Integration: real PDF
# ===========================================================================

@pytest.mark.skipif(not SAMPLE_AVAILABLE, reason="Sample PDF not available")
class TestRealPdfAnalyzers:
    @pytest.fixture(scope="class")
    def findings(self):
        from parser.pdf_parser import parse_pdf
        from section_extractor.section_extractor import extract_sections
        report = parse_pdf(SAMPLE_PDF)
        smap   = extract_sections(report)
        return (
            completeness_analyzer.analyze(smap) +
            pseudo_code_analyzer.analyze(smap) +
            analysis_code_analyzer.analyze(smap)
        )

    def test_at_least_four_findings(self, findings):
        assert len(findings) >= 4

    def test_flowchart_empty_section_found(self, findings):
        empty = [f for f in findings
                 if f.type == "empty_section" and f.section == "flowchart"]
        assert len(empty) == 1

    def test_output_empty_section_found(self, findings):
        empty = [f for f in findings
                 if f.type == "empty_section" and f.section == "output"]
        assert len(empty) == 1

    def test_analysis_thin_section_found(self, findings):
        thin = [f for f in findings
                if f.type == "thin_section" and f.section == "analysis"]
        assert len(thin) == 1

    def test_pseudo_internal_switch_found(self, findings):
        inc = [f for f in findings
               if f.type == "pseudo_internal_switch_inconsistency"]
        assert len(inc) == 1
        assert inc[0].severity == "HIGH"

    def test_all_findings_have_evidence_and_reason(self, findings):
        for f in findings:
            assert f.reason, f"Finding {f.type} has no reason"
            assert isinstance(f.evidence, dict), f"Finding {f.type} evidence is not a dict"

    def test_no_false_positive_on_pendahuluan(self, findings):
        # pendahuluan has real content in this report — should not be flagged
        flagged = [f for f in findings if f.section == "pendahuluan"]
        assert flagged == []
