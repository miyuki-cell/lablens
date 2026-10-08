"""
Semantic analyzer for LabLens.

Uses Gemini as the primary provider and Groq as a fallback
to detect semantic inconsistencies between:
- pseudocode and code
- analysis and code
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from groq import Groq

from analyzers.models import Finding


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)


gemini_api_key = os.getenv("GEMINI_API_KEY")

if not gemini_api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. "
        f"Expected it in: {ENV_PATH}"
    )

gemini_client = genai.Client(api_key=gemini_api_key)

GEMINI_MODEL = "gemini-3.8-flash"


# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------

groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    raise RuntimeError(
        "GROQ_API_KEY is not set. "
        f"Expected it in: {ENV_PATH}"
    )

groq_client = Groq(api_key=groq_api_key)

GROQ_MODEL = "openai/gpt-oss-20b"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_findings(text: str) -> list[Finding]:
    """
    Convert provider JSON output into LabLens Finding objects.
    """

    if not text:
        return []

    data = json.loads(text)

    findings: list[Finding] = []

    for item in data.get("findings", []):
        severity = str(item.get("severity", "LOW")).upper()

        if severity not in {"LOW", "MEDIUM", "HIGH"}:
            severity = "LOW"

        findings.append(
            Finding(
                type=item.get(
                    "type",
                    "semantic_issue",
                ),
                severity=severity,
                title=item.get(
                    "title",
                    "Potential semantic inconsistency",
                ),
                evidence=item.get(
                    "evidence",
                    {},
                ),
                reason=item.get(
                    "reason",
                    "",
                ),
                section=item.get(
                    "section",
                ),
            )
        )

    return findings


def _build_prompt(
    pseudocode: str,
    code: str,
    analysis: str,
) -> str:
    """
    Build the semantic-analysis prompt shared by Gemini and Groq.
    """

    return f"""
You are a semantic consistency analyzer for a university programming
practical report.

Your job is NOT to grade the student.

Your job is to identify potential inconsistencies between the student's
pseudocode, source code, and written analysis.

Only report an issue when there is actual evidence.

Important rules:
- Do not invent information.
- Do not assume missing information.
- Do not claim an error with certainty unless the evidence is explicit.
- Prefer "may be inconsistent" over definitive accusations.
- If there is no meaningful inconsistency, return an empty findings list.
- Keep evidence short and quote only the relevant parts.
- Do not analyze writing quality or grammar.
- Focus on logical and semantic consistency.

REPORT SECTIONS

PSEUDOCODE:
{pseudocode or "[No pseudocode section found]"}

SOURCE CODE:
{code}

ANALYSIS:
{analysis or "[No analysis section found]"}

Return ONLY valid JSON in exactly this structure:

{{
  "findings": [
    {{
      "type": "pseudo_code_mismatch",
      "severity": "LOW | MEDIUM | HIGH",
      "title": "Short description",
      "evidence": {{
        "pseudocode": "Relevant pseudocode excerpt",
        "code": "Relevant code excerpt"
      }},
      "reason": "Brief explanation of why they may be inconsistent.",
      "section": "pseudocode"
    }},
    {{
      "type": "analysis_code_mismatch",
      "severity": "LOW | MEDIUM | HIGH",
      "title": "Short description",
      "evidence": {{
        "analysis": "Relevant analysis excerpt",
        "code": "Relevant code excerpt"
      }},
      "reason": "Brief explanation of why they may be inconsistent.",
      "section": "analysis"
    }}
  ]
}}

Only include findings that are actually supported by the provided text.
"""


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

def analyze(smap) -> list[Finding]:
    """
    Analyze semantic consistency between report sections.

    Gemini is the primary provider.
    Groq is used as a fallback if Gemini fails.
    """

    sections = smap.sections

    pseudocode = sections.get("pseudocode", "")
    code = sections.get("code", "")
    analysis = sections.get("analysis", "")

    # No code means there is nothing meaningful to compare.
    if not code:
        return []

    prompt = _build_prompt(
        pseudocode=pseudocode,
        code=code,
        analysis=analysis,
    )

    # -----------------------------------------------------------------------
    # 1. Try Gemini
    # -----------------------------------------------------------------------

    try:
        print("[Semantic Analyzer] Trying Gemini...")

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        findings = _parse_findings(response.text)

        print(
            f"[Semantic Analyzer] Gemini succeeded "
            f"({len(findings)} findings)."
        )

        return findings

    except Exception as exc:
        print(f"[Semantic Analyzer] Gemini failed: {exc}")
        print("[Semantic Analyzer] Falling back to Groq...")


    # -----------------------------------------------------------------------
    # 2. Fallback to Groq
    # -----------------------------------------------------------------------

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content

        findings = _parse_findings(text)

        print(
            f"[Semantic Analyzer] Groq succeeded "
            f"({len(findings)} findings)."
        )

        return findings

    except Exception as exc:
        print(f"[Semantic Analyzer] Groq failed: {exc}")
        print("[Semantic Analyzer] Semantic analysis unavailable.")

        return []