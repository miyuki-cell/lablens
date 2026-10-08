"""
Section Extractor — Stage 2 of the LabLens pipeline.

Responsibility:
    Convert a ParsedReport (list of pages with raw text) into a
    SectionMap: a dict of logical section name → extracted text.

Strategy:
    1. Detect the Table of Contents page(s) and exclude them from
       section scanning — this prevents false positives from ToC entries.
    2. Scan page text for numbered heading patterns that are characteristic
       of actual section starts (e.g. "2.2 Pseudocode", "BAB II", "3.4 Kesimpulan").
    3. Accumulate page text into the active section until the next heading
       is detected.
    4. Clean placeholder/template text from each section.

Section vocabulary (Indonesian practical report conventions):
    pendahuluan   → BAB I / 1.x headings
    flowchart     → 2.1 Diagram Flowchart
    pseudocode    → 2.2 Pseudocode
    code          → 2.3 Kode Program
    analysis      → 2.4 Analisis Program
    output        → 3.3 Output Program  (also "Hasil")
    conclusion    → 3.4 Kesimpulan
    references    → DAFTAR PUSTAKA

The extractor does NOT interpret the content — it only segments it.
Downstream analyzers decide what to do with each section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from parser.pdf_parser import ParsedReport, ParsedPage


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

SECTION_KEYS = [
    "pendahuluan",
    "flowchart",
    "pseudocode",
    "code",
    "analysis",
    "output",
    "conclusion",
    "references",
]


@dataclass
class SectionMap:
    filename: str
    sections: Dict[str, str] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)      # expected but not found
    page_map: Dict[str, List[int]] = field(default_factory=dict)  # section → page numbers

    def to_dict(self) -> dict:
        return asdict(self)

    def get(self, key: str, default: str = "") -> str:
        return self.sections.get(key, default)


# ---------------------------------------------------------------------------
# Heading patterns
# ---------------------------------------------------------------------------
# Each entry: (section_key, compiled_regex)
# Regexes match against a single line (stripped).
# They must be specific enough to not match ToC dot-leaders.
# A heading line in a ToC typically looks like:
#   "2.2 Pseudocode ............. 4"
# We reject matches that contain dot-leaders (4+ consecutive dots) or
# are followed immediately by a page-number-only suffix.

_DOT_LEADER = re.compile(r'\.{4,}')          # "........" = ToC line
_PAGE_SUFFIX = re.compile(r'\s+\d{1,3}\s*$') # ends with whitespace + 1-3 digits

_RAW_PATTERNS: list[tuple[str, str]] = [
    # BAB I block
    ("pendahuluan",  r'^(?:BAB\s+I\b|1\.\s*(?:Tujuan|Dasar\s+Teori|Pendahuluan|Latar\s+Belakang))'),
    # Flowchart / Diagram Flowchart
    ("flowchart",    r'^2\.1[\s\.\-–]+(?:Diagram\s+)?(?:Flowchart|Alur)'),
    # Pseudocode
    ("pseudocode",   r'^2\.2[\s\.\-–]+Pseudocode'),
    # Kode Program / Source Code
    ("code",         r'^2\.3[\s\.\-–]+(?:Kode\s+Program|Source\s+Code|Kode\s+Sumber|Program)'),
    # Analisis Program
    ("analysis",     r'^2\.4[\s\.\-–]+Analisis\s+Program'),
    # Output Program / Hasil
    ("output",       r'^3\.(?:1|2|3|4|5)[\s\.\-–]+(?:Output|Hasil(?:\s+dan\s+Kesimpulan)?)'),
    # Kesimpulan
    ("conclusion",   r'^3\.(?:1|2|3|4|5)[\s\.\-–]+Kesimpulan'),
    # Fallbacks — less specific, checked last
    ("pendahuluan",  r'^PENDAHULUAN\s*$'),
    ("pseudocode",   r'^Pseudocode\s*$'),
    ("code",         r'^(?:Kode\s+Program|Source\s+Code)\s*$'),
    ("analysis",     r'^Analisis\s+Program\s*$'),
    ("conclusion",   r'^Kesimpulan\s*$'),
    ("references",   r'^DAFTAR\s+PUSTAKA\s*$'),
    # BAB III block start
    ("output",       r'^BAB\s+III\b'),
]

_PATTERNS: list[tuple[str, re.Pattern]] = [
    (key, re.compile(pat, re.IGNORECASE))
    for key, pat in _RAW_PATTERNS
]

# ToC page detection: a page is considered a ToC if it has 3+ dot-leader lines
_TOC_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Placeholder / template text patterns — strip these from section content
# ---------------------------------------------------------------------------

_PLACEHOLDER_PATTERNS: list[re.Pattern] = [
    re.compile(r'"[^"]{10,200}"'),                    # quoted template instructions (single line)
    re.compile(r'Gambar\s+x\..*', re.IGNORECASE),     # "Gambar x. ..."
    re.compile(r'Program\s+x\..*', re.IGNORECASE),    # "Program x. ..."
    re.compile(r'Pseudocode\s+x\..*', re.IGNORECASE), # "Pseudocode x. ..."
    re.compile(r'Tabel\s+x\..*', re.IGNORECASE),
]

# Whole-line artifacts to drop entirely (page number stubs, lone digits from PDF headers)
_ARTIFACT_LINE_PATTERNS: list[re.Pattern] = [
    re.compile(r'^\d{1,3}$'),                         # lone page numbers (e.g. "4", "10")
    re.compile(r'^HASIL\s+DAN\s+KESIMPULAN\s*$', re.IGNORECASE),  # chapter header bleed
]


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

def extract_sections(report: ParsedReport) -> SectionMap:
    """
    Extract logical sections from a ParsedReport.

    Returns a SectionMap with:
      - sections: dict of section_key → cleaned text
      - missing:  list of expected section keys that were not found
      - page_map: which pages contributed to each section
    """
    toc_pages = _detect_toc_pages(report.pages)

    # Build (page_number, line) pairs, skipping ToC pages
    lines_with_meta: list[tuple[int, str]] = []
    for page in report.pages:
        if page.page_number in toc_pages:
            continue
        for line in page.text.splitlines():
            lines_with_meta.append((page.page_number, line))

    # Walk lines, detect heading transitions, accumulate section text
    section_buffers: dict[str, list[str]] = {k: [] for k in SECTION_KEYS}
    section_pages: dict[str, set[int]] = {k: set() for k in SECTION_KEYS}
    active_section: Optional[str] = None

    for page_num, line in lines_with_meta:
        stripped = line.strip()
        matched_key = _match_heading(stripped)

        if matched_key is not None:
            active_section = matched_key
            # Don't include the heading line itself in the content buffer
            # (it's structural metadata, not content)
            section_pages[active_section].add(page_num)
            continue

        if active_section is not None:
            section_buffers[active_section].append(line)
            section_pages[active_section].add(page_num)

    # Finalize: join, clean, and record
    sections: dict[str, str] = {}
    for key in SECTION_KEYS:
        raw = "\n".join(section_buffers[key])
        cleaned = _clean_section_text(raw)
        if cleaned:
            sections[key] = cleaned

    missing = [k for k in SECTION_KEYS if k not in sections and k != "references"]

    page_map = {
        k: sorted(v)
        for k, v in section_pages.items()
        if v
    }

    return SectionMap(
        filename=report.filename,
        sections=sections,
        missing=missing,
        page_map=page_map,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_toc_pages(pages: list[ParsedPage]) -> set[int]:
    """
    Return the set of page numbers that are Table-of-Contents pages.
    Heuristic: a page with >= TOC_THRESHOLD dot-leader lines.
    """
    toc_pages: set[int] = set()
    for page in pages:
        dot_leader_count = sum(
            1 for line in page.text.splitlines()
            if _DOT_LEADER.search(line)
        )
        if dot_leader_count >= _TOC_THRESHOLD:
            toc_pages.add(page.page_number)
    return toc_pages


def _match_heading(line: str) -> Optional[str]:
    """
    Return the section key if `line` looks like a real section heading,
    or None if it doesn't match or looks like a ToC entry.
    """
    if not line:
        return None

    # Reject ToC dot-leader lines immediately
    if _DOT_LEADER.search(line):
        return None

    # Reject lines that end with a bare page number (ToC ref)
    # e.g. "2.2 Pseudocode  4"  — but allow "2.2 Pseudocode" alone
    # We only apply this if the line also has trailing digits after whitespace
    # and no other content after the number.
    stripped_no_num = re.sub(r'\s+\d{1,3}\s*$', '', line)
    if stripped_no_num != line and len(stripped_no_num) < len(line) - 1:
        # The line ends with " <number>" — likely a ToC reference if the rest is short
        if len(stripped_no_num.strip()) < 40:
            return None

    for key, pattern in _PATTERNS:
        if pattern.search(line):
            return key

    return None


def _clean_section_text(text: str) -> str:
    """
    Remove placeholder/template content and normalize whitespace.

    Two passes:
      1. Remove multi-line quoted template instructions (span "..." across lines).
      2. Per-line: drop artifact lines, strip inline placeholder patterns.
    """
    # Pass 1 — strip multi-line quoted template strings (handles both straight " and curly " " quotes)
    text = re.sub(r'["\u201c][^"\u201c\u201d]{5,500}["\u201d]', '', text, flags=re.DOTALL)

    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()

        # Drop whole-line artifacts
        if any(pat.match(stripped) for pat in _ARTIFACT_LINE_PATTERNS):
            continue

        # Strip inline placeholder patterns
        scrubbed = line
        for pat in _PLACEHOLDER_PATTERNS:
            scrubbed = pat.sub('', scrubbed)
        scrubbed = scrubbed.rstrip()
        cleaned.append(scrubbed)

    # Collapse consecutive blank lines
    result_lines: list[str] = []
    prev_blank = False
    for line in cleaned:
        is_blank = line.strip() == ''
        if is_blank and prev_blank:
            continue
        result_lines.append(line)
        prev_blank = is_blank

    return "\n".join(result_lines).strip()
