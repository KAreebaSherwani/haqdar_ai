"""Analysis service: missing-info check -> retrieval -> AI -> verifier -> response."""

import logging
import random
import time
import uuid
from datetime import date

from app.core.ai_client import AIUnavailableError, generate_structured
from app.core.citation_verifier import enforce
from app.core.config import get_settings
from app.knowledge.prompts import build_complaint_prompt
from app.resilience import demo_cache
from app.schemas.complaint import (
    AnalyzeResponse,
    ComplaintAnalysis,
    NeedsMoreInfoResponse,
    RelevantLaw,
    ResponseMeta,
)
from app.services import missing_info, report_store
from app.services.retrieval_service import retrieve

logger = logging.getLogger("haqdar.service")

# Numeric companions to the categorical confidence (judges love measurable confidence)
_CONFIDENCE_VALUE = {"high": 0.9, "medium": 0.65, "needs_verification": 0.35}


def _meta(request_id: str, model: str, start: float, **kw) -> ResponseMeta:
    s = get_settings()
    return ResponseMeta(
        request_id=request_id,
        model_used=model,
        processing_ms=int((time.perf_counter() - start) * 1000),
        db_version=s.db_version,
        last_legal_review=s.last_legal_review,
        **kw,
    )


def _new_reference() -> str:
    return f"HQD-{date.today().year}-{random.randint(0, 9999):04d}"


async def analyze_complaint(
    complaint: str,
    district: str | None = None,
    name: str | None = None,
    incident_date: str | None = None,
    language: str = "Urdu",
    letter_language: str = "Urdu",
) -> AnalyzeResponse | NeedsMoreInfoResponse:
    settings = get_settings()
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    # 1. Missing-information detector: safely unpacks all 4 items from the updated triage module
    needs_more, domain, questions, extracted_district = missing_info.check(complaint)
    if needs_more:
        return NeedsMoreInfoResponse(
            questions=questions,
            detected_domain=domain,
            meta=_meta(request_id, "heuristic", start),
        )

    # Smart Triage Fallback: Auto-fill district using native script extraction if user left dropdown blank
    if not district or district.strip().lower() == "unknown":
        district = extracted_district if extracted_district else None

    # 2. Retrieve grounding context (RAG primary, inclusion fallback)
    retrieval = retrieve(complaint)

    # 3. Generate (model fallback chain), then demo-cache fallback
    reference_id = _new_reference()
    try:
        analysis, model_used = await generate_structured(
            build_complaint_prompt(
                complaint,
                retrieval.context,
                reference_id=reference_id,
                letter_date=date.today().isoformat(),
                district=district,  # Pipes sanitized district info to anchor prompt generation
                name=name,
                incident_date=incident_date,
                response_language=language or "Urdu",
                letter_language=letter_language or "Urdu",
            ),
            ComplaintAnalysis,
        )
        cached = False
    except AIUnavailableError:
        logger.error("all model tiers failed — trying demo cache (req=%s)", request_id)
        fallback = demo_cache.lookup(complaint)
        if fallback is None:
            raise
        analysis, model_used, cached = fallback, "cache", True

    # 4. Deterministic citation verification
    analysis, citation_verified = enforce(analysis)

    # 5. Confidence-from-similarity: weak retrieval lowers confidence
    confidence_key = str(getattr(analysis.confidence_score, "value", analysis.confidence_score))
    if (
        not cached
        and retrieval.source == "vector"
        and retrieval.top_score < settings.retrieval_min_score + 0.1
        and confidence_key == "high"
    ):
        analysis.confidence_score = "medium"
        confidence_key = "medium"

    # 6. Multi-law surfacing with contacts, deduped by law
    seen: set[str] = set()
    relevant: list[RelevantLaw] = []
    for p in retrieval.provisions:
        if p["law"] not in seen:
            seen.add(p["law"])
            relevant.append(RelevantLaw(
                law=p["law"], authority=p["authority"], contact=p.get("authority_contact", ""),
                provision=p.get("provision", ""),
            ))

    primary_domain = missing_info.detect_domain(complaint)
    retrieved_domains = [p["domain"] for p in retrieval.provisions]
    secondary_domain = next(
        (d for d in retrieved_domains if d != primary_domain), None
    ) if retrieval.source == "vector" else None

    # 7. Record the anonymous report (Pipes automated district parsing directly to Supabase table updates!)
    report_store.record(primary_domain, district, reference_id)

    return AnalyzeResponse(
        **analysis.model_dump(),
        reference_id=reference_id,
        primary_domain=primary_domain,
        secondary_domain=secondary_domain,
        relevant_laws=relevant[:3],
        confidence_value=_CONFIDENCE_VALUE.get(confidence_key, 0.5),
        meta=_meta(
            request_id,
            model_used,
            start,
            cached=cached,
            citation_verified=citation_verified,
            retrieval_source=retrieval.source,
            top_score=round(retrieval.top_score, 3),
            used_rag=(retrieval.source == "vector"),
            rag_context=retrieval.context if retrieval.source == "vector" else None,
            grounding_sources_count=len(retrieval.provisions),
        ),
    )