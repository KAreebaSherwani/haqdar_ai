"""Supabase pgvector store for law provisions.

Uses Google Gemini's gemini-embedding-2 (with MRL=768) to embed user queries, 
and queries the Supabase vector database for semantic retrieval using psycopg_pool.
"""

import logging

from psycopg_pool import ConnectionPool
from google import genai
from google.genai import types

from app.core.config import get_settings

logger = logging.getLogger("haqdar.pgvector")

_pool: ConnectionPool | None = None
_client = None
_ready = False

def is_ready() -> bool:
    return _ready

def init_store() -> None:
    """Initialize the connection pool and Vertex AI client."""
    global _pool, _client, _ready
    settings = get_settings()
    if not settings.use_vector_store:
        logger.info("pgvector store disabled by config")
        return
        
    try:
        if not settings.database_url:
            logger.error("database_url not provided, cannot connect to Supabase.")
            return
            
        _pool = ConnectionPool(conninfo=settings.database_url, min_size=1, max_size=5)
        import os
        cred_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "haqdar-ai-499713-595c09d7a539.json")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
        
        _client = genai.Client(vertexai=True, project="haqdar-ai-499713", location="us-central1")
        
        # Test connection
        with _pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                
        _ready = True
        logger.info("Supabase pgvector store connected and ready with Vertex AI client.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("pgvector store init failed: %s — retrieval will fall back", exc)
        _ready = False

def search(query: str, top_k: int) -> tuple[list[dict], float]:
    """Return (matched provisions, top_score in 0..1). Raises if store not ready."""
    if not _ready or _pool is None or _client is None:
        raise RuntimeError("pgvector store not ready")
        
    # Get embedding for the query
    response = _client.models.embed_content(
        model='text-embedding-004',
        contents=[query],
        config=types.EmbedContentConfig(output_dimensionality=768)
    )
    q_emb = response.embeddings[0].values
    
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            # Query the closest vectors using cosine distance operator <=>
            cur.execute("""
                SELECT id, source, law_name, chunk_text, 1 - (embedding <=> %s::vector) as similarity
                FROM law_embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (q_emb, q_emb, top_k))
            
            rows = cur.fetchall()
            
    provisions = []
    top_score = 0.0
    for row in rows:
        sim = float(row[4])
        source = row[1]
        
        # Apply custom weighting logic: boost our hand-verified "gold" laws
        if source == "AI":
            sim = min(1.0, sim + 0.05)
            
        if sim > top_score:
            top_score = sim
            
        provisions.append({
            "id": str(row[0]),
            "domain": "general",
            "law": row[2],
            "provision": row[3],
            "authority": "Relevant Government Department/Court",
            "authority_contact": "Consult local legal counsel or district office",
            "source": source,
            "similarity": sim
        })
        
    # Re-sort provisions in case boosting changed the ranking
    provisions.sort(key=lambda x: x["similarity"], reverse=True)
        
    return provisions, top_score
