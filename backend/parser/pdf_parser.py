"""
PDF Parser — Stage 1 of the LabLens pipeline.

Responsibility:
    Convert a PDF file into a structured dict with per-page plain text.
    Nothing more. Downstream components handle interpretation.

Output schema:
    {
        "filename": str,
        "pages": [
            {"page_number": int, "text": str},
            ...
        ]
    }
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import List

try:
    import pymupdf
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyMuPDF is required. Install it with:  pip install pymupdf"
    ) from exc


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ParsedPage:
    page_number: int   # 1-based
    text: str


@dataclass
class ParsedReport:
    filename: str
    pages: List[ParsedPage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def full_text(self) -> str:
        """Concatenate all page texts, separated by a form-feed character."""
        return "\f".join(p.text for p in self.pages)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_pdf(source: str | bytes | os.PathLike) -> ParsedReport:
    """
    Parse a PDF and return a ParsedReport.

    Args:
        source: A file path (str / Path) or raw PDF bytes.

    Returns:
        ParsedReport with one ParsedPage per non-blank page.

    Raises:
        FileNotFoundError: If a file path is given but does not exist.
        ValueError: If the source is neither a valid path nor bytes.
        fitz.FileDataError: If the PDF is corrupt or unreadable.
    """
    if isinstance(source, (str, os.PathLike)):
        path = str(source)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"PDF not found: {path}")
        filename = os.path.basename(path)
        doc = pymupdf.open(path)
    elif isinstance(source, (bytes, bytearray)):
        filename = "<bytes>"
        doc = pymupdf.open(stream=source, filetype="pdf")
    else:
        raise ValueError(
            f"source must be a file path or bytes, got {type(source).__name__}"
        )

    pages: list[ParsedPage] = []

    with doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")          
            text = _normalize_whitespace(text)
            if text:                              
                pages.append(ParsedPage(page_number=i, text=text))

    return ParsedReport(filename=filename, pages=pages)


def _normalize_whitespace(text: str) -> str:
    """
    Strip leading/trailing whitespace from each line,
    collapse runs of blank lines to a single blank line,
    and strip outer whitespace.
    """
    lines = text.splitlines()
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        stripped = line.rstrip()
        is_blank = stripped == ""
        if is_blank and prev_blank:
            continue  # collapse consecutive blank lines
        cleaned.append(stripped)
        prev_blank = is_blank
    return "\n".join(cleaned).strip()
