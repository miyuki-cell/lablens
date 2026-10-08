"""
Shared data structures for all LabLens analyzers.

Every analyzer returns a list of Finding objects.
The anomaly scorer consumes these to produce a final score.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


# Severity levels — ordered so that comparison works correctly
SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


@dataclass
class Finding:
    """
    A single detected anomaly or issue in a report section.

    Fields
    ------
    type        : machine-readable key, e.g. "missing_section"
    severity    : LOW | MEDIUM | HIGH
    title       : short human-readable summary
    evidence    : dict of labelled snippets that support the finding
    reason      : one or two sentences explaining the inference
    section     : which section key this finding came from (optional)
    """
    type: str
    severity: str                             # "LOW" | "MEDIUM" | "HIGH"
    title: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    section: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def severity_score(self) -> float:
        """Map severity to a numeric score for aggregation."""
        return {"LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.9}[self.severity]
