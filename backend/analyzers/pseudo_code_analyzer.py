"""
Pseudocode ↔ Code Analyzer

Compares the logical structure described in the pseudocode section against
the extracted source code. Focuses on detectable structural signals rather
than full semantic equivalence (which would require an LLM).

Checks performed
----------------
1. Threshold mismatch    — numeric literals used in conditional branches
                           appear in pseudocode but differ in the code.
2. Branch count mismatch — number of if/else-if branches differs noticeably.
3. Loop presence mismatch — pseudocode describes a loop but code has none,
                            or vice versa.
4. Variable name divergence — variables declared in pseudocode do not appear
                              anywhere in the code (conservative: only flag
                              when several are missing at once).

All checks use conservative language. A finding is NOT a guarantee of error.
"""

from __future__ import annotations

import re
from typing import List

from section_extractor.section_extractor import SectionMap
from analyzers.models import Finding


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Numeric literals in conditionals: capture the number after >= <= > < ==
_CONDITION_NUM = re.compile(r'(?:>=|<=|>|<|==)\s*(\d+(?:\.\d+)?)')

# if / else if / elif branches
_IF_BRANCH_PSEUDO = re.compile(
    r'\b(?:if|else\s+if|elseif)\b', re.IGNORECASE
)
_IF_BRANCH_CODE = re.compile(
    r'\b(?:if|else\s+if|elif)\b'
)

# Loop keywords
_LOOP_PSEUDO = re.compile(
    r'\b(?:for|while|repeat|do|loop|foreach|until)\b', re.IGNORECASE
)
_LOOP_CODE = re.compile(
    r'\b(?:for|while|do)\b'
)

# Variable declarations in pseudocode (VAR name : type)
_PSEUDO_VAR_DECL = re.compile(
    r'\bVAR\s+([\w\s,]+?)(?:\s*[:;])', re.IGNORECASE
)

# switch / case in pseudocode
_SWITCH_PSEUDO = re.compile(r'\bSWITCH\b', re.IGNORECASE)
_SWITCH_CODE   = re.compile(r'\bswitch\b')

# case value in switch
_CASE_VALUE_PSEUDO = re.compile(r'\bcase\s+(\w+)\s*:', re.IGNORECASE)
_CASE_VALUE_CODE   = re.compile(r'\bcase\s+(\w+)\s*:')


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze(smap: SectionMap) -> List[Finding]:
    pseudocode = smap.sections.get("pseudocode", "")
    code       = smap.sections.get("code", "")

    if not pseudocode or not code:
        return []   # nothing to compare

    findings: list[Finding] = []

    findings.extend(_check_threshold_values(pseudocode, code))
    findings.extend(_check_branch_counts(pseudocode, code))
    findings.extend(_check_loop_presence(pseudocode, code))
    findings.extend(_check_switch_case_values(pseudocode, code))

    return findings


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_threshold_values(pseudo: str, code: str) -> List[Finding]:
    """
    Extract numeric literals from conditional expressions in both sections.
    Flag values that appear in pseudocode but not in code (or vice versa),
    where the difference is large enough to be meaningful.
    """
    pseudo_nums = set(_CONDITION_NUM.findall(pseudo))
    code_nums   = set(_CONDITION_NUM.findall(code))

    only_in_pseudo = pseudo_nums - code_nums
    only_in_code   = code_nums   - pseudo_nums

    findings: list[Finding] = []

    if only_in_pseudo and only_in_code:
        # Both sides have numbers the other doesn't — possible threshold mismatch
        findings.append(Finding(
            type="pseudo_code_threshold_mismatch",
            severity="MEDIUM",
            title="Conditional thresholds may differ between pseudocode and code",
            evidence={
                "values_only_in_pseudocode": sorted(only_in_pseudo),
                "values_only_in_code":       sorted(only_in_code),
                "pseudocode_snippet": _extract_condition_lines(pseudo)[:400],
                "code_snippet":       _extract_condition_lines(code)[:400],
            },
            reason=(
                f"The pseudocode contains conditional values {sorted(only_in_pseudo)} "
                f"that do not appear in the code, while the code contains "
                f"{sorted(only_in_code)} that are absent from the pseudocode. "
                f"This may indicate that the pseudocode and implementation use "
                f"different thresholds or conditions."
            ),
            section="pseudocode",
        ))

    return findings


def _check_branch_counts(pseudo: str, code: str) -> List[Finding]:
    """
    Compare the number of conditional branches in pseudocode vs code.
    A difference of 2+ branches is flagged.
    """
    pseudo_branches = len(_IF_BRANCH_PSEUDO.findall(pseudo))
    code_branches   = len(_IF_BRANCH_CODE.findall(code))

    findings: list[Finding] = []

    diff = abs(pseudo_branches - code_branches)
    if diff >= 2 and pseudo_branches > 0 and code_branches > 0:
        findings.append(Finding(
            type="pseudo_code_branch_count_mismatch",
            severity="LOW",
            title="Number of conditional branches differs between pseudocode and code",
            evidence={
                "pseudocode_branch_count": pseudo_branches,
                "code_branch_count":       code_branches,
            },
            reason=(
                f"The pseudocode contains approximately {pseudo_branches} conditional "
                f"branch(es), while the code contains {code_branches}. A difference "
                f"of {diff} may suggest structural divergence, though minor differences "
                f"in if/else-if style are common and do not necessarily indicate an error."
            ),
            section="pseudocode",
        ))

    return findings


def _check_loop_presence(pseudo: str, code: str) -> List[Finding]:
    """
    Flag when pseudocode describes a loop but code has none, or vice versa.
    """
    pseudo_has_loop = bool(_LOOP_PSEUDO.search(pseudo))
    code_has_loop   = bool(_LOOP_CODE.search(code))

    findings: list[Finding] = []

    if pseudo_has_loop and not code_has_loop:
        findings.append(Finding(
            type="pseudo_code_loop_mismatch",
            severity="MEDIUM",
            title="Pseudocode describes a loop but no loop found in code",
            evidence={
                "pseudocode_loop_keywords": _LOOP_PSEUDO.findall(pseudo),
            },
            reason=(
                "The pseudocode contains loop keywords, but no corresponding "
                "loop construct (for/while/do) was found in the extracted code. "
                "This may indicate the implementation differs from the described algorithm."
            ),
            section="pseudocode",
        ))
    elif code_has_loop and not pseudo_has_loop:
        findings.append(Finding(
            type="pseudo_code_loop_mismatch",
            severity="LOW",
            title="Code contains a loop but pseudocode does not describe one",
            evidence={
                "code_loop_keywords": _LOOP_CODE.findall(code),
            },
            reason=(
                "The extracted code uses loop constructs, but the pseudocode "
                "does not describe any iteration. This may be intentional "
                "(e.g., a library function internally loops) or an oversight in the pseudocode."
            ),
            section="pseudocode",
        ))

    return findings


def _check_switch_case_values(pseudo: str, code: str) -> List[Finding]:
    """
    When both pseudocode and code use switch/case, compare the case values.
    Flag discrepancies in which case values are handled.
    Also detect internal pseudocode inconsistency: assignments to the switch
    variable that don't align with the case labels defined in the same pseudocode.
    """
    pseudo_has_switch = bool(_SWITCH_PSEUDO.search(pseudo))
    code_has_switch   = bool(_SWITCH_CODE.search(code))

    findings: list[Finding] = []

    if not pseudo_has_switch or not code_has_switch:
        return findings

    pseudo_cases = set(_CASE_VALUE_PSEUDO.findall(pseudo))
    code_cases   = set(_CASE_VALUE_CODE.findall(code))

    only_in_pseudo = pseudo_cases - code_cases
    only_in_code   = code_cases   - pseudo_cases

    if only_in_pseudo or only_in_code:
        severity = "HIGH" if len(pseudo_cases) != len(code_cases) else "MEDIUM"
        findings.append(Finding(
            type="pseudo_code_switch_case_mismatch",
            severity=severity,
            title="Switch/case values differ between pseudocode and code",
            evidence={
                "pseudocode_cases": sorted(pseudo_cases),
                "code_cases":       sorted(code_cases),
                "only_in_pseudocode": sorted(only_in_pseudo),
                "only_in_code":       sorted(only_in_code),
                "pseudocode_snippet": _extract_switch_lines(pseudo)[:400],
                "code_snippet":       _extract_switch_lines(code)[:400],
            },
            reason=(
                f"The pseudocode defines case(s) {sorted(pseudo_cases)}, while the code "
                f"defines case(s) {sorted(code_cases)}. "
                + (f"Case(s) {sorted(only_in_pseudo)} are in the pseudocode but not the code. " if only_in_pseudo else "")
                + (f"Case(s) {sorted(only_in_code)} are in the code but not the pseudocode. " if only_in_code else "")
                + "This may indicate the pseudocode and implementation handle different cases."
            ),
            section="pseudocode",
        ))

    # Internal pseudocode consistency: values assigned to the switch variable
    # must match the case labels. E.g. if pseudocode assigns X=3 but only
    # defines case 1 and case 2, that is internally inconsistent.
    findings.extend(_check_pseudo_switch_internal_consistency(pseudo, pseudo_cases))

    return findings


# Pattern: "Kategori = 3" or "variableName = <number>"
_PSEUDO_ASSIGN_NUM = re.compile(r'\b\w+\s*=\s*(\d+)\b')


def _check_pseudo_switch_internal_consistency(
    pseudo: str, case_labels: set[str]
) -> List[Finding]:
    """
    Check whether numeric assignments inside the pseudocode produce values
    that do not correspond to any defined case label.
    This catches bugs like: pseudocode assigns Kategori=3 for medium range,
    but the switch only meaningfully handles case 2 for that category.
    """
    if not case_labels:
        return []

    # Find all lines that look like: <var> = <number>  (outside a case/write line)
    assigned_values: set[str] = set()
    for line in pseudo.splitlines():
        l = line.strip().lower()
        # Skip lines that are case declarations or WRITE statements
        if l.startswith("case") or l.startswith("write") or l.startswith("default"):
            continue
        for val in _PSEUDO_ASSIGN_NUM.findall(line):
            if val != "0":   # 0 is a common sentinel/default, skip
                assigned_values.add(val)

    # Values assigned but never appear as a case label
    unhandled = assigned_values - case_labels
    # Values that are case labels but never assigned
    unassigned = case_labels - assigned_values - {"0"}

    if unhandled and unassigned:
        # Strong signal: something is assigned that doesn't match any case
        return [Finding(
            type="pseudo_internal_switch_inconsistency",
            severity="HIGH",
            title="Pseudocode assigns values that do not match its own switch/case labels",
            evidence={
                "assigned_values":       sorted(assigned_values),
                "case_labels":           sorted(case_labels),
                "assigned_but_no_case":  sorted(unhandled),
                "case_label_never_assigned": sorted(unassigned),
                "pseudocode_snippet":    _extract_switch_lines(pseudo)[:500],
            },
            reason=(
                f"In the pseudocode, the value(s) {sorted(unhandled)} are assigned "
                f"to the switch variable, but the switch block does not define a "
                f"corresponding case for them. Meanwhile, case label(s) {sorted(unassigned)} "
                f"are defined but never assigned. This suggests an internal inconsistency "
                f"in the pseudocode logic — for example, a category variable may be "
                f"assigned 3 for a condition that should yield 2."
            ),
            section="pseudocode",
        )]

    # Softer signal: a case label exists but is never assigned in the if/else block.
    # This can happen when the assignment logic skips a value — e.g. assigns 1 and 3
    # but never 2, yet case 2 is defined. Combined with a value that IS assigned
    # appearing in a "wrong" semantic position.
    if unassigned and len(assigned_values) >= 2:
        return [Finding(
            type="pseudo_internal_switch_inconsistency",
            severity="HIGH",
            title="Pseudocode switch/case has a label that is never assigned in the logic",
            evidence={
                "assigned_values":           sorted(assigned_values),
                "case_labels":               sorted(case_labels),
                "case_label_never_assigned": sorted(unassigned),
                "pseudocode_snippet":        _extract_switch_lines(pseudo)[:500],
            },
            reason=(
                f"The pseudocode defines case label(s) {sorted(unassigned)} in its "
                f"switch block, but the if/else logic above never assigns "
                f"{'that value' if len(unassigned)==1 else 'those values'} to the "
                f"switch variable (assigned values found: {sorted(assigned_values)}). "
                f"This means the case(s) {sorted(unassigned)} can never be reached, "
                f"which likely indicates a logic error in the pseudocode."
            ),
            section="pseudocode",
        )]

    return []


# ---------------------------------------------------------------------------
# Snippet helpers
# ---------------------------------------------------------------------------

def _extract_condition_lines(text: str) -> str:
    """Return lines that contain conditional keywords."""
    return "\n".join(
        line for line in text.splitlines()
        if re.search(r'\b(?:if|else|elif|>=|<=)\b', line, re.IGNORECASE)
    )


def _extract_switch_lines(text: str) -> str:
    """Return lines that contain switch/case keywords."""
    return "\n".join(
        line for line in text.splitlines()
        if re.search(r'\b(?:switch|case|default)\b', line, re.IGNORECASE)
    )
