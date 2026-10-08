"""
Analysis ↔ Code Analyzer

Checks whether the written analysis section actually mentions the constructs
present in the code. This is a semantic plausibility check, not a proof of error.

Checks performed
----------------
1. Construct mention check — code uses construct X (loop, switch, recursion…)
                             but the analysis never mentions it.
2. Empty/missing analysis  — analysis section is too short to be meaningful
                             (handled by completeness_analyzer; we skip here to
                             avoid duplicate findings).

Conservative by design: only reports when evidence is clear.
"""

from __future__ import annotations

import re
from typing import List

from section_extractor.section_extractor import SectionMap
from analyzers.models import Finding


# ---------------------------------------------------------------------------
# Construct detection patterns for code
# ---------------------------------------------------------------------------

_CODE_CONSTRUCTS: list[tuple[str, re.Pattern, list[str]]] = [
    # (construct_label, code_regex, analysis_keywords_that_count_as_mention)
    (
        "for loop",
        re.compile(r'\bfor\s*\(', re.IGNORECASE),
        ["for", "perulangan", "loop", "iterasi", "repetisi"],
    ),
    (
        "while loop",
        re.compile(r'\bwhile\s*\(', re.IGNORECASE),
        ["while", "perulangan", "loop", "iterasi"],
    ),
    (
        "switch/case",
        re.compile(r'\bswitch\s*\('),
        ["switch", "case", "percabangan", "switch-case"],
    ),
    (
        "recursion",
        re.compile(r'\b(\w+)\s*\([^)]*\)\s*\{[\s\S]{0,400}\b\1\s*\('),
        ["rekursi", "recursion", "memanggil dirinya", "recursive"],
    ),
    (
        "if/else branching",
        re.compile(r'\bif\s*\('),
        ["if", "percabangan", "kondisi", "seleksi", "cabang", "branch"],
    ),
    (
        "array/vector",
        re.compile(r'\b(?:int|double|float|string|char)\s+\w+\s*\['),
        ["array", "larik", "vektor", "vector", "indeks"],
    ),
]


# Minimum analysis length to bother checking
# (very short analysis is caught by completeness_analyzer)
_MIN_ANALYSIS_LEN = 80


def analyze(smap: SectionMap) -> List[Finding]:
    code     = smap.sections.get("code", "")
    analysis = smap.sections.get("analysis", "")

    if not code or not analysis or len(analysis.strip()) < _MIN_ANALYSIS_LEN:
        return []

    analysis_lower = analysis.lower()
    findings: list[Finding] = []

    for label, code_pattern, mention_keywords in _CODE_CONSTRUCTS:
        if not code_pattern.search(code):
            continue  # this construct is not in the code — skip

        # Check whether the analysis mentions it
        mentioned = any(kw in analysis_lower for kw in mention_keywords)
        if not mentioned:
            findings.append(Finding(
                type="analysis_missing_construct_mention",
                severity="MEDIUM",
                title=f"Analysis does not appear to mention the '{label}' used in code",
                evidence={
                    "construct": label,
                    "expected_keywords": mention_keywords,
                    "analysis_preview": analysis.strip()[:300],
                    "code_snippet": _extract_construct_lines(code, code_pattern)[:300],
                },
                reason=(
                    f"The extracted code contains a '{label}' construct, but the "
                    f"analysis section does not appear to mention it "
                    f"(checked for keywords: {mention_keywords}). "
                    f"This may indicate the analysis does not accurately describe "
                    f"the implementation."
                ),
                section="analysis",
            ))

    return findings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_construct_lines(code: str, pattern: re.Pattern) -> str:
    """Return a few lines around each pattern match."""
    lines = code.splitlines()
    result: list[str] = []
    for i, line in enumerate(lines):
        if pattern.search(line):
            start = max(0, i - 1)
            end   = min(len(lines), i + 3)
            result.extend(lines[start:end])
            result.append("...")
    return "\n".join(result)
