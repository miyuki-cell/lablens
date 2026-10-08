"""
Tests for the FastAPI endpoints.

Run with:
    cd lablens/backend
    python -m pytest tests/test_api.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

SAMPLE_PDF = os.path.join(
    os.path.dirname(__file__), "..", "sample_pdfs", "020_pika_modul2_DGpraktik.pdf"
)
SAMPLE_AVAILABLE = os.path.isfile(SAMPLE_PDF)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /analyze — input validation
# ---------------------------------------------------------------------------

class TestAnalyzeValidation:
    def test_no_files_returns_422(self):
        r = client.post("/analyze")
        assert r.status_code == 422   # FastAPI validation error (missing required field)

    def test_non_pdf_rejected(self):
        r = client.post(
            "/analyze",
            files=[("files", ("report.txt", b"hello", "text/plain"))],
        )
        # All files fail → 422
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /analyze — real PDF
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not SAMPLE_AVAILABLE, reason="Sample PDF not available")
class TestAnalyzeRealPdf:
    @pytest.fixture(scope="class")
    def response(self):
        with open(SAMPLE_PDF, "rb") as f:
            pdf_bytes = f.read()
        r = client.post(
            "/analyze",
            files=[("files", ("020_pika_modul2_DGpraktik.pdf", pdf_bytes, "application/pdf"))],
        )
        return r

    def test_status_200(self, response):
        assert response.status_code == 200

    def test_response_has_reports_and_summary(self, response):
        body = response.json()
        assert "reports" in body
        assert "summary" in body

    def test_one_report_returned(self, response):
        body = response.json()
        assert len(body["reports"]) == 1

    def test_report_fields_present(self, response):
        report = response.json()["reports"][0]
        for key in ["filename", "priority", "score", "sections",
                    "findings", "score_breakdown", "finding_counts"]:
            assert key in report, f"Missing field: {key}"

    def test_priority_is_high(self, response):
        report = response.json()["reports"][0]
        assert report["priority"] == "HIGH"

    def test_score_in_range(self, response):
        report = response.json()["reports"][0]
        assert 0.0 <= report["score"] <= 1.0

    def test_findings_non_empty(self, response):
        report = response.json()["reports"][0]
        assert len(report["findings"]) >= 4

    def test_each_finding_has_required_fields(self, response):
        report = response.json()["reports"][0]
        for f in report["findings"]:
            assert "type" in f
            assert "severity" in f
            assert "title" in f
            assert "evidence" in f
            assert "reason" in f

    def test_summary_counts_match(self, response):
        body    = response.json()
        summary = body["summary"]
        reports = body["reports"]
        assert summary["total"] == len(reports)
        assert summary["HIGH"] + summary["MEDIUM"] + summary["LOW"] == summary["total"]

    def test_filename_preserved_from_upload(self, response):
        report = response.json()["reports"][0]
        assert report["filename"] == "020_pika_modul2_DGpraktik.pdf"


@pytest.mark.skipif(not SAMPLE_AVAILABLE, reason="Sample PDF not available")
class TestAnalyzeMultipleUploads:
    """Upload the same PDF twice to verify multi-file handling and sorting."""

    def test_two_files_both_processed(self):
        with open(SAMPLE_PDF, "rb") as f:
            pdf_bytes = f.read()
        r = client.post(
            "/analyze",
            files=[
                ("files", ("report_a.pdf", pdf_bytes, "application/pdf")),
                ("files", ("report_b.pdf", pdf_bytes, "application/pdf")),
            ],
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["reports"]) == 2
        assert body["summary"]["total"] == 2

    def test_sorted_high_first(self):
        """Results must be sorted HIGH → MEDIUM → LOW."""
        with open(SAMPLE_PDF, "rb") as f:
            pdf_bytes = f.read()
        r = client.post(
            "/analyze",
            files=[
                ("files", ("r1.pdf", pdf_bytes, "application/pdf")),
                ("files", ("r2.pdf", pdf_bytes, "application/pdf")),
            ],
        )
        reports  = r.json()["reports"]
        from api import _PRIORITY_ORDER
        priorities = [rpt["priority"] for rpt in reports]
        orders     = [_PRIORITY_ORDER[p] for p in priorities]
        assert orders == sorted(orders), "Reports not sorted by priority"
