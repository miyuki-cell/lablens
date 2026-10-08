"""
Tests for anomaly_scorer and pipeline (end-to-end).

Run with:
    cd lablens/backend
    python -m pytest tests/test_scorer_pipeline.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzers.models import Finding
from scorer.anomaly_scorer import score, ScoreResult


SAMPLE_PDF = os.path.join(
    os.path.dirname(__file__), "..", "sample_pdfs", "020_pika_modul2_DGpraktik.pdf"
)
SAMPLE_AVAILABLE = os.path.isfile(SAMPLE_PDF)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(type_: str, severity: str) -> Finding:
    return Finding(type=type_, severity=severity, title="t", reason="r")


# ===========================================================================
# anomaly_scorer unit tests
# ===========================================================================

class TestAnomalyScorer:
    def test_empty_findings_gives_zero_score(self):
        result = score([])
        assert result.score == 0.0
        assert result.priority == "LOW"

    def test_single_high_missing_section(self):
        result = score([_f("missing_section", "HIGH")])
        assert result.score == 0.30
        assert result.priority == "LOW"   # 0.30 is below MEDIUM threshold (0.36)

    def test_two_high_empty_sections_hit_cap(self):
        findings = [
            _f("empty_section", "HIGH"),
            _f("empty_section", "HIGH"),
            _f("empty_section", "HIGH"),  # third should be capped
        ]
        result = score(findings)
        # Cap for empty_section is 0.50; 3 × 0.25 = 0.75 but capped at 0.50
        assert result.score == 0.50
        assert result.priority == "MEDIUM"

    def test_high_priority_threshold(self):
        findings = [
            _f("empty_section", "HIGH"),
            _f("empty_section", "HIGH"),
            _f("pseudo_internal_switch_inconsistency", "HIGH"),
        ]
        result = score(findings)
        assert result.score >= 0.66
        assert result.priority == "HIGH"

    def test_medium_priority_threshold(self):
        findings = [_f("thin_section", "HIGH")]   # 0.12 alone
        # Add a second to push past 0.36
        findings += [_f("pseudo_code_threshold_mismatch", "HIGH")]  # +0.20 → 0.32 still LOW
        findings += [_f("pseudo_code_loop_mismatch", "HIGH")]       # +0.15 → 0.47 MEDIUM
        result = score(findings)
        assert 0.36 <= result.score <= 0.65
        assert result.priority == "MEDIUM"

    def test_score_clamped_at_one(self):
        # Many high-weight findings should not exceed 1.0
        findings = [_f("missing_section", "HIGH")] * 10
        result = score(findings)
        assert result.score <= 1.0

    def test_severity_scaling(self):
        high   = score([_f("missing_section", "HIGH")])
        medium = score([_f("missing_section", "MEDIUM")])
        low    = score([_f("missing_section", "LOW")])
        assert high.score > medium.score > low.score

    def test_breakdown_keys_match_finding_types(self):
        findings = [
            _f("empty_section", "HIGH"),
            _f("thin_section", "MEDIUM"),
        ]
        result = score(findings)
        assert "empty_section" in result.breakdown
        assert "thin_section" in result.breakdown

    def test_finding_counts_populated(self):
        findings = [
            _f("empty_section", "HIGH"),
            _f("thin_section", "MEDIUM"),
            _f("pseudo_code_branch_count_mismatch", "LOW"),
        ]
        result = score(findings)
        assert result.finding_counts["HIGH"] == 1
        assert result.finding_counts["MEDIUM"] == 1
        assert result.finding_counts["LOW"] == 1
        assert result.finding_counts["total"] == 3

    def test_unknown_finding_type_uses_default_weight(self):
        result = score([_f("some_future_finding_type", "HIGH")])
        assert result.score > 0.0  # default weight applied
        assert result.score <= 0.20  # default cap

    def test_to_dict_serialisable(self):
        result = score([_f("empty_section", "HIGH")])
        d = result.to_dict()
        assert "score" in d
        assert "priority" in d
        assert "breakdown" in d
        assert "finding_counts" in d


# ===========================================================================
# Pipeline end-to-end integration test
# ===========================================================================

@pytest.mark.skipif(not SAMPLE_AVAILABLE, reason="Sample PDF not available")
class TestPipelineIntegration:
    @pytest.fixture(scope="class")
    def result(self):
        from pipeline import run_pipeline
        return run_pipeline(SAMPLE_PDF)

    def test_result_has_correct_filename(self, result):
        assert result.filename == "020_pika_modul2_DGpraktik.pdf"

    def test_priority_is_high(self, result):
        assert result.priority == "HIGH"

    def test_score_is_in_range(self, result):
        assert 0.0 <= result.score <= 1.0

    def test_score_is_high(self, result):
        assert result.score >= 0.66

    def test_sections_dict_populated(self, result):
        assert isinstance(result.sections, dict)
        assert len(result.sections) >= 4

    def test_findings_list_populated(self, result):
        assert len(result.findings) >= 4

    def test_finding_counts_consistent(self, result):
        counts = result.finding_counts
        assert counts["total"] == len(result.findings)
        assert counts["HIGH"] + counts["MEDIUM"] + counts["LOW"] == counts["total"]

    def test_breakdown_non_empty(self, result):
        assert len(result.score_breakdown) > 0

    def test_to_dict_is_json_serialisable(self, result):
        import json
        d = result.to_dict()
        # Should not raise
        serialised = json.dumps(d, ensure_ascii=False)
        assert len(serialised) > 100

    def test_each_finding_has_required_fields(self, result):
        for f in result.findings:
            assert f.type
            assert f.severity in ("LOW", "MEDIUM", "HIGH")
            assert f.title
            assert f.reason
            assert isinstance(f.evidence, dict)
