"""Know Your Rights service."""

import time
import uuid

from app.core.ai_client import generate_structured
from app.core.citation_verifier import enforce
from app.core.config import get_settings
from app.knowledge.prompts import build_rights_prompt
from app.schemas.complaint import ResponseMeta
from app.schemas.rights import RightsAnswer, RightsResponse
from app.services.retrieval_service import retrieve


async def explain_rights(scenario: str) -> RightsResponse:
    settings = get_settings()
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    retrieval = retrieve(scenario)
    answer, model_used = await generate_structured(
        build_rights_prompt(scenario, retrieval.context), RightsAnswer
    )
    answer, citation_verified = enforce(answer)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return RightsResponse(
        **answer.model_dump(),
        meta=ResponseMeta(
            request_id=request_id,
            model_used=model_used,
            processing_ms=elapsed_ms,
            citation_verified=citation_verified,
            retrieval_source=retrieval.source,
            top_score=round(retrieval.top_score, 3),
            db_version=settings.db_version,
            last_legal_review=settings.last_legal_review,
        ),
    )
