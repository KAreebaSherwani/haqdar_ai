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
    # Always include the core baseline hand-verified laws
    provisions = list(LAW_PROVISIONS)
    source = "inclusion"
    score = 1.0

    if settings.use_vector_store and pgvector_store.is_ready():
        try:
            db_provisions, search_score = pgvector_store.search(complaint, settings.retrieval_top_k)
            if db_provisions and search_score >= settings.retrieval_min_score:
                source = "vector"
                score = search_score
                # Deduplicate based on lowercased law name
                seen_laws = {p["law"].lower().strip() for p in provisions}
                for db_p in db_provisions:
                    law_name = db_p["law"].lower().strip()
                    if law_name not in seen_laws:
                        seen_laws.add(law_name)
                        provisions.append(db_p)
            else:
                logger.info("weak retrieval (score=%.2f) -> fallback to core baseline only", search_score)
        except Exception as exc:  # noqa: BLE001
            logger.warning("retrieval failed: %s -> fallback to core baseline only", exc)

    return Retrieval(build_context(provisions), source, score, provisions)
