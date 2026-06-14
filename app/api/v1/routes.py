"""API v1 routers: /analyze, /rights, /stats, /health."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core import vector_store
from app.schemas.complaint import AnalyzeResponse, ComplaintRequest, NeedsMoreInfoResponse
from app.schemas.rights import RightsRequest, RightsResponse
from app.services.analysis_service import analyze_complaint
from app.services.pdf_service import build_letter_pdf
from app.services.rights_service import explain_rights

router = APIRouter()

_INJECTION_PATTERNS = ("ignore previous", "ignore all previous", "system prompt", "you are now")


def _guard(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Input cannot be empty")
    lowered = cleaned.lower()
    if any(p in lowered for p in _INJECTION_PATTERNS):
        raise HTTPException(status_code=400, detail="Invalid input")
    return cleaned


@router.post("/analyze", response_model=AnalyzeResponse | NeedsMoreInfoResponse, tags=["core"])
async def analyze(req: ComplaintRequest) -> AnalyzeResponse | NeedsMoreInfoResponse:
    """Citizen complaint -> full legal action package."""
    complaint = _guard(req.complaint)
    try:
        return await analyze_complaint(complaint, req.district, req.name, req.incident_date, req.language, req.letter_language)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="سروس عارضی طور پر دستیاب نہیں۔ براہ کرم دوبارہ کوشش کریں۔",
        ) from None


@router.post("/rights", response_model=RightsResponse, tags=["core"])
async def rights(req: RightsRequest) -> RightsResponse:
    """Scenario -> rights education answer."""
    scenario = _guard(req.scenario)
    try:
        return await explain_rights(scenario, req.language)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="سروس عارضی طور پر دستیاب نہیں۔ براہ کرم دوبارہ کوشش کریں۔",
        ) from None


class LetterPdfRequest(BaseModel):
    reference_id: str = "HQD-2026-0001"
    complaint_letter: str
    law_reference: str = ""
    responsible_authority: str = ""


@router.post("/letter/pdf", tags=["core"])
def letter_pdf(req: LetterPdfRequest) -> Response:
    """Render the complaint letter as a downloadable Urdu PDF."""
    if not req.complaint_letter.strip():
        raise HTTPException(status_code=400, detail="No letter content")
    s = get_settings()
    from datetime import date

    pdf_bytes = build_letter_pdf(
        reference_id=req.reference_id,
        complaint_letter=req.complaint_letter,
        law_reference=req.law_reference,
        authority=req.responsible_authority,
        db_version=s.db_version,
        generated_date=date.today().isoformat(),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{req.reference_id}.pdf"'},
    )


@router.get("/stats", tags=["dashboard"])
def stats() -> dict:
    """REAL civic aggregates — every number is a complaint this system processed.

    Anonymous by design: only domain, district, and date are ever stored.
    """
    from app.services import report_store

    return report_store.stats()


@router.get("/report/{reference_id}", tags=["dashboard"])
def report_lookup(reference_id: str) -> dict:
    """Look up an anonymous report by its reference number (no personal data)."""
    from app.services import report_store

    found = report_store.get_by_reference(reference_id)
    if not found:
        raise HTTPException(status_code=404, detail="Reference not found")
    return found


@router.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness check — also the keep-alive ping target."""
    s = get_settings()
    return {
        "status": "online",
        "service": s.app_name,
        "primary_model": s.primary_model,
        "fallback_model": s.fallback_model,
        "vector_store_ready": vector_store.is_ready(),
        "db_version": s.db_version,
    }
