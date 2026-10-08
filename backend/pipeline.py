"""
LabLens Pipeline — end-to-end entry point.

Takes a PDF source (path or bytes) and returns a ReportResult that contains
everything the API and UI need:

  filename, priority, score, sections, findings, score_breakdown

Usage
-----
    from pipeline import run_pipeline
    result = run_pipeline("reports/student_01.pdf")
    print(result.to_dict())
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import List, Union

from parser.pdf_parser import parse_pdf, ParsedReport
from section_extractor.section_extractor import extract_sections, SectionMap
from analyzers import (
    completeness_analyzer,
    pseudo_code_analyzer,
    analysis_code_analyzer,
    gemini_analyzer,
)
from analyzers.models import Finding
from scorer.anomaly_scorer import score, ScoreResult


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

@dataclass
class ReportResult:
    filename:        str
    priority:        str                   # LOW | MEDIUM | HIGH
    score:           float                 # 0.0 – 1.0
    sections:        dict                  # section_key → text
    missing_sections: List[str]
    findings:        List[Finding]
    score_breakdown: dict
    finding_counts:  dict

    def to_dict(self) -> dict:
        d = asdict(self)
        # findings are already dicts via asdict; keep them clean
        return d


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(source: Union[str, bytes, os.PathLike]) -> ReportResult:
    """
    Run the full LabLens analysis pipeline on a single PDF.

    Args:
        source: file path or raw PDF bytes.

    Returns:
        ReportResult with all fields populated.
    """
    # Stage 1 — Parse
    parsed: ParsedReport = parse_pdf(source)

    # Stage 2 — Extract sections
    smap: SectionMap = extract_sections(parsed)

    # Stage 3 — Analyse (all analyzers)
    findings: list[Finding] = (
    completeness_analyzer.analyze(smap)
    + pseudo_code_analyzer.analyze(smap)
    + analysis_code_analyzer.analyze(smap)
    + gemini_analyzer.analyze(smap)
)

    # Stage 4 — Score
    result: ScoreResult = score(findings)

    return ReportResult(
        filename         = parsed.filename,
        priority         = result.priority,
        score            = result.score,
        sections         = smap.sections,
        missing_sections = smap.missing,
        findings         = findings,
        score_breakdown  = result.breakdown,
        finding_counts   = result.finding_counts,
    )
