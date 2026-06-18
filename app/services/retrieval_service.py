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


_local_embeddings: list[list[float]] | None = None


def get_local_embeddings() -> list[list[float]] | None:
    global _local_embeddings
    if _local_embeddings is None:
        if pgvector_store.is_ready():
            try:
                texts = [f"{p['law']}. {p['provision']}" for p in LAW_PROVISIONS]
                _local_embeddings = pgvector_store.embed_texts(texts)
                logger.info("Successfully pre-embedded %d local laws.", len(_local_embeddings))
            except Exception as e:
                logger.error("Failed to pre-embed local laws: %s", e)
    return _local_embeddings


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = sum(a * a for a in v1) ** 0.5
    mag2 = sum(b * b for b in v2) ** 0.5
    if not mag1 or not mag2:
        return 0.0
    return dot / (mag1 * mag2)


def retrieve(complaint: str) -> Retrieval:
    settings = get_settings()
    
    # 1. Semantically choose 3 laws out of the 12 local laws (LAW_PROVISIONS)
    selected_local_provisions = []
    q_emb = None
    
    if pgvector_store.is_ready():
        try:
            # Embed complaint query once
            q_emb = pgvector_store.embed_texts([complaint])[0]
            
            # Rank the 12 local laws
            local_embs = get_local_embeddings()
            if local_embs and len(local_embs) == len(LAW_PROVISIONS):
                scored_locals = []
                for idx, p in enumerate(LAW_PROVISIONS):
                    sim = cosine_similarity(q_emb, local_embs[idx])
                    scored_locals.append((sim, p))
                # Sort by similarity descending
                scored_locals.sort(key=lambda x: x[0], reverse=True)
                selected_local_provisions = [item[1] for item in scored_locals[:3]]
        except Exception as exc:
            logger.warning("Failed semantic ranking of local laws: %s", exc)
            
    if not selected_local_provisions:
        # Default selection fallback (first 3 laws)
        selected_local_provisions = LAW_PROVISIONS[:3]
        
    # 2. Retrieve 6-10 laws/cases from Supabase vector storage
    supabase_provisions = []
    supabase_score = 0.0
    source = "inclusion"
    
    # Select a value in the 6-10 range based on top_k
    k = max(6, min(10, settings.retrieval_top_k))
    
    if settings.use_vector_store and pgvector_store.is_ready():
        try:
            supabase_provisions, supabase_score = pgvector_store.search(complaint, k, q_emb=q_emb)
            if supabase_provisions and supabase_score >= settings.retrieval_min_score:
                source = "vector"
            else:
                logger.info("Weak supabase vector retrieval (score=%.2f)", supabase_score)
        except Exception as exc:
            logger.warning("Supabase vector retrieval failed: %s", exc)
            
    # Combine the 3 selected local laws and 6-10 supabase laws/cases
    combined_provisions = selected_local_provisions + supabase_provisions
    
    if source == "vector":
        top_score = supabase_score
    else:
        # Inclusion fallback uses all 12 local laws
        combined_provisions = LAW_PROVISIONS
        top_score = 1.0
        source = "inclusion"
        
    return Retrieval(
        context=build_context(combined_provisions),
        source=source,
        top_score=top_score,
        provisions=combined_provisions
    )
