"""Retrieval service: the heart of the RAG-with-fallback design.

Primary path: embed the complaint, vector-search the store, ground in the top-k
provisions. Fallback path: if the store is unavailable or the match is weak,
ground in ALL provisions (inclusion). Either way the model only ever sees
verified law text — retrieval just narrows it.
"""

import logging
from dataclasses import dataclass

from app.core.config import get_settings
from app.core import pgvector_store
from app.knowledge.pakistan_laws import LAW_PROVISIONS, LAWS_CONTEXT, build_context

logger = logging.getLogger("haqdar.retrieval")


@dataclass
class Retrieval:
    context: str          # grounding block injected into the prompt
    source: str           # "vector" | "inclusion"
    top_score: float      # retrieval strength (1.0 for inclusion)
    provisions: list[dict]  # the provisions used


def retrieve(complaint: str) -> Retrieval:
    settings = get_settings()
    if settings.use_vector_store and pgvector_store.is_ready():
        try:
            provisions, score = pgvector_store.search(complaint, settings.retrieval_top_k)
            if provisions and score >= settings.retrieval_min_score:
                return Retrieval(build_context(provisions), "vector", score, provisions)
            logger.info("weak retrieval (score=%.2f) -> inclusion fallback", score)
        except Exception as exc:  # noqa: BLE001
            logger.warning("retrieval failed: %s -> inclusion fallback", exc)

    return Retrieval(LAWS_CONTEXT, "inclusion", 1.0, LAW_PROVISIONS)
