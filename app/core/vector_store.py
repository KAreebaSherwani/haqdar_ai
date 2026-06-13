"""Chroma vector store for law provisions.

Embedded (in-process) — no separate server. Indexes all verified provisions at
startup. Search returns provisions ranked by similarity with a normalized score.

If anything here fails, callers fall back to grounding-by-inclusion, so the
vector store is an enhancement, never a hard dependency.
"""

import logging

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.core.embeddings import embed_one, embed_texts
from app.knowledge.pakistan_laws import LAW_PROVISIONS

logger = logging.getLogger("haqdar.vector")

_collection = None
_ready = False


def is_ready() -> bool:
    return _ready


def init_store() -> None:
    """Build/load the Chroma collection and index provisions. Idempotent."""
    global _collection, _ready
    settings = get_settings()
    if not settings.use_vector_store:
        logger.info("vector store disabled by config")
        return
    try:
        client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        _collection = client.get_or_create_collection(
            name="laws", metadata={"hnsw:space": "cosine"}
        )
        if _collection.count() >= len(LAW_PROVISIONS):
            logger.info("vector store already indexed (%d items)", _collection.count())
            _ready = True
            return

        docs = [f"{p['law']}. {p['provision']}" for p in LAW_PROVISIONS]
        embeddings = embed_texts(docs)
        _collection.upsert(
            ids=[p["id"] for p in LAW_PROVISIONS],
            embeddings=embeddings,
            documents=docs,
            metadatas=[
                {"law": p["law"], "domain": p["domain"], "authority": p["authority"]}
                for p in LAW_PROVISIONS
            ],
        )
        _ready = True
        logger.info("vector store indexed %d provisions", len(LAW_PROVISIONS))
    except Exception as exc:  # noqa: BLE001
        logger.warning("vector store init failed: %s — retrieval will fall back", exc)
        _ready = False


def search(query: str, top_k: int) -> tuple[list[dict], float]:
    """Return (matched provisions, top_score in 0..1). Raises if store not ready."""
    if not _ready or _collection is None:
        raise RuntimeError("vector store not ready")
    q_emb = embed_one(query)
    res = _collection.query(query_embeddings=[q_emb], n_results=top_k)
    ids = res["ids"][0]
    distances = res.get("distances", [[]])[0]
    by_id = {p["id"]: p for p in LAW_PROVISIONS}
    provisions = [by_id[i] for i in ids if i in by_id]
    # cosine distance -> similarity (1 - distance); clamp to [0,1]
    top_score = max(0.0, 1.0 - distances[0]) if distances else 0.0
    return provisions, top_score
