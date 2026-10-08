"""
Completeness Analyzer — checks whether required sections exist and have
meaningful content.

This is entirely deterministic — no heuristics, no ML.

Two distinct checks:
  1. Missing section   — the heading was never found in the document.
  2. Empty section     — the heading was found but content is blank after
                         placeholder stripping (template-only content).

These are separate because they carry different implications:
  - A missing section may mean the student skipped it entirely.
  - An empty section means they left the template placeholder in place.
"""

from __future__ import annotations

from typing import List

from section_extractor.section_extractor import SectionMap
from analyzers.models import Finding


# Sections required by the practical report format and their display labels
REQUIRED_SECTIONS: dict[str, str] = {
    "pendahuluan": "Pendahuluan (Introduction)",
    "flowchart":   "Diagram Flowchart",
    "pseudocode":  "Pseudocode",
    "code":        "Kode Program (Source Code)",
    "analysis":    "Analisis Program (Analysis)",
    "output":      "Output Program",
    "conclusion":  "Kesimpulan (Conclusion)",
}

# Minimum character count to consider a section non-trivially filled
# (sub-headings alone, e.g. "2.4.1 Analisis Program A", should not count)
_MIN_CONTENT_CHARS = 80


def analyze(smap: SectionMap) -> List[Finding]:
    """
    Return a list of Finding objects for completeness issues.

    Checks every section in REQUIRED_SECTIONS against the SectionMap.
    """
    findings: list[Finding] = []

    for key, label in REQUIRED_SECTIONS.items():
        section_text = smap.sections.get(key, "")
        was_found_in_toc = key in smap.page_map  # heading was detected

        if not section_text:
            if was_found_in_toc:
                # Heading found, but content is empty after placeholder stripping
                findings.append(Finding(
                    type="empty_section",
                    severity="HIGH",
                    title=f"Section '{label}' appears to contain only placeholder content",
                    evidence={
                        "section": key,
                        "pages": smap.page_map.get(key, []),
                    },
                    reason=(
                        f"The '{label}' section heading was detected on "
                        f"page(s) {smap.page_map.get(key, [])} but after removing "
                        f"template placeholder text, no substantive content remains. "
                        f"This suggests the student did not fill in this section."
                    ),
                    section=key,
                ))
            else:
                # Heading was never found at all
                findings.append(Finding(
                    type="missing_section",
                    severity="HIGH",
                    title=f"Required section '{label}' not found",
                    evidence={"section": key},
                    reason=(
                        f"No heading matching '{label}' was detected in the document. "
                        f"This section is required by the practical report format."
                    ),
                    section=key,
                ))

        elif len(section_text.strip()) < _MIN_CONTENT_CHARS:
            # Section has something but it's suspiciously short
            findings.append(Finding(
                type="thin_section",
                severity="MEDIUM",
                title=f"Section '{label}' has very little content",
                evidence={
                    "section": key,
                    "content_length": len(section_text.strip()),
                    "content_preview": section_text.strip()[:200],
                },
                reason=(
                    f"The '{label}' section contains only {len(section_text.strip())} "
                    f"characters after cleanup. This may indicate the section was not "
                    f"adequately completed."
                ),
                section=key,
            ))

    return findings
