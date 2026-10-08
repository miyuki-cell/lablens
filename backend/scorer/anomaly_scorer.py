"""
Anomaly Scorer — Stage 4 of the LabLens pipeline.

Responsibility:
    Consume a list of Finding objects and produce:
      - A normalised anomaly score  (0.0 – 1.0)
      - A priority label            (LOW | MEDIUM | HIGH)
      - A score breakdown           (which finding types contributed what)

Design
------
Each finding type has a base weight.  The weight is scaled by severity:
    HIGH   × 1.0
    MEDIUM × 0.6
    LOW    × 0.3

Multiple findings of the same type do NOT stack beyond the type's cap —
this prevents a report with 5 minor issues from outranking one with a
single critical structural flaw.

The final score is the sum of capped contributions, clamped to [0, 1].

Priority thresholds (easy to change for demo tuning):
    0.00 – 0.35  →  LOW
    0.36 – 0.65  →  MEDIUM
    0.66 – 1.00  →  HIGH
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List

from analyzers.models import Finding


# ---------------------------------------------------------------------------
# Weight table
# Each entry: finding_type → (base_weight, per_type_cap)
# base_weight : how much one HIGH finding of this type contributes
# per_type_cap: maximum total contribution from this type regardless of count
# ---------------------------------------------------------------------------

_WEIGHTS: dict[str, tuple[float, float]] = {
    # Structural completeness — these directly impede grading
    "missing_section":                      (0.30, 0.30),
    "empty_section":                        (0.25, 0.50),  # up to 2 empties matter
    "thin_section":                         (0.12, 0.24),

    # Pseudocode logic issues
    "pseudo_internal_switch_inconsistency": (0.30, 0.30),
    "pseudo_code_switch_case_mismatch":     (0.25, 0.25),
    "pseudo_code_threshold_mismatch":       (0.20, 0.20),
    "pseudo_code_loop_mismatch":            (0.15, 0.15),
    "pseudo_code_branch_count_mismatch":    (0.08, 0.08),

    # Analysis ↔ Code
    "analysis_missing_construct_mention":   (0.10, 0.20),  # up to 2 unmentioned constructs

    # Fallback for any future finding type not listed
    "_default":                             (0.10, 0.20),
}

_SEVERITY_SCALE: dict[str, float] = {
    "HIGH":   1.0,
    "MEDIUM": 0.6,
    "LOW":    0.3,
}

# Priority thresholds
_THRESHOLDS = [
    (0.66, "HIGH"),
    (0.36, "MEDIUM"),
    (0.00, "LOW"),
]


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    score: float                              # 0.0 – 1.0, rounded to 2 dp
    priority: str                             # LOW | MEDIUM | HIGH
    breakdown: Dict[str, float] = field(default_factory=dict)
    # finding_count by severity for the dashboard summary
    finding_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

def score(findings: List[Finding]) -> ScoreResult:
    """
    Compute an anomaly score and priority from a list of Finding objects.

    Returns a ScoreResult with score, priority, breakdown, and finding_counts.
    """
    # Accumulate contribution per finding type (capped)
    type_totals: dict[str, float] = {}

    for f in findings:
        base_weight, cap = _WEIGHTS.get(f.type, _WEIGHTS["_default"])
        severity_scale   = _SEVERITY_SCALE.get(f.severity, 0.5)
        contribution     = base_weight * severity_scale

        current = type_totals.get(f.type, 0.0)
        type_totals[f.type] = min(current + contribution, cap)

    raw_score    = sum(type_totals.values())
    final_score  = round(min(raw_score, 1.0), 2)

    priority = "LOW"
    for threshold, label in _THRESHOLDS:
        if final_score >= threshold:
            priority = label
            break

    finding_counts = {
        "HIGH":   sum(1 for f in findings if f.severity == "HIGH"),
        "MEDIUM": sum(1 for f in findings if f.severity == "MEDIUM"),
        "LOW":    sum(1 for f in findings if f.severity == "LOW"),
        "total":  len(findings),
    }

    return ScoreResult(
        score          = final_score,
        priority       = priority,
        breakdown      = {k: round(v, 3) for k, v in sorted(type_totals.items())},
        finding_counts = finding_counts,
    )
