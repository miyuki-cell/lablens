"""
Run with:
    cd lablens/backend
    uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import sys
import os
import traceback
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))

from pipeline import run_pipeline, ReportResult


app = FastAPI(
    title="LabLens API",
    description="AI-assisted practical report analyzer for teaching assistants.",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.aspraklablens.me"],   
    allow_methods=["GET", "POST"],
    allow_headers=["Content-type"],
)



class EvidenceModel(BaseModel):
    model_config = {"extra": "allow"}


class FindingModel(BaseModel):
    type:     str
    severity: str
    title:    str
    evidence: dict
    reason:   str
    section:  str | None = None


class ReportModel(BaseModel):
    filename:         str
    priority:         str
    score:            float
    sections:         dict
    missing_sections: List[str]
    findings:         List[FindingModel]
    score_breakdown:  dict
    finding_counts:   dict


class AnalyzeResponse(BaseModel):
    reports:       List[ReportModel]
    summary:       dict  

_PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _sort_key(r: ReportResult) -> tuple:
    return (_PRIORITY_ORDER.get(r.priority, 9), -r.score)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(files: List[UploadFile] = File(...)) -> AnalyzeResponse:
    """
    Accept one or more PDF files, run the full analysis pipeline on each,
    and return results sorted by priority (HIGH first) then score (desc).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    results: list[ReportResult] = []
    errors:  list[dict]         = []

    for upload in files:
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            errors.append({"filename": upload.filename, "error": "Not a PDF file."})
            continue

        try:
            pdf_bytes = await upload.read()
            result    = run_pipeline(pdf_bytes)
            
            result.filename = upload.filename
            results.append(result)
        except Exception as exc:
            errors.append({
                "filename": upload.filename,
                "error":    str(exc),
                "trace":    traceback.format_exc()[-500:],
            })

    if not results and errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "All files failed to process.", "errors": errors},
        )
        
    results.sort(key=_sort_key)

    summary = {
        "total":       len(results),
        "HIGH":        sum(1 for r in results if r.priority == "HIGH"),
        "MEDIUM":      sum(1 for r in results if r.priority == "MEDIUM"),
        "LOW":         sum(1 for r in results if r.priority == "LOW"),
        "errors":      errors,
    }

    report_models = [
        ReportModel(
            filename         = r.filename,
            priority         = r.priority,
            score            = r.score,
            sections         = r.sections,
            missing_sections = r.missing_sections,
            findings         = [FindingModel(**f.to_dict()) for f in r.findings],
            score_breakdown  = r.score_breakdown,
            finding_counts   = r.finding_counts,
        )
        for r in results
    ]

    return AnalyzeResponse(reports=report_models, summary=summary)
