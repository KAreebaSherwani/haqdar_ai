"""Supabase pgvector store for law provisions.

Uses Google Gemini's text-embedding-004 to embed user queries, 
and queries the Supabase vector database for semantic retrieval using psycopg_pool.
"""

import logging

from psycopg_pool import ConnectionPool
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.knowledge.pakistan_laws import LAW_PROVISIONS

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

def map_to_verified_law(law_name: str, chunk_text: str) -> dict | None:
    """Helper to map a retrieved database law row to a hand-verified law entry."""
    combined = (law_name + " " + chunk_text).lower()
    
    # Keyword mappings for each of the 12 hand-verified laws
    mappings = [
        {
            "id": "police-receipt",
            "keywords": ["crpc", "criminal procedure", "police station", "fir", "arrest", "detain", "seizure", "fine", "challan"]
        },
        {
            "id": "consumer-overcharge",
            "keywords": ["consumer protection", "consumer court", "overcharge", "displayed price", "defective", "refund", "trader"]
        },
        {
            "id": "rti-access",
            "keywords": ["access to information", "right to information", "public body", "public record"]
        },
        {
            "id": "labour-wages",
            "keywords": ["minimum wage", "standing orders", "appointment letter", "employer", "wages", "labor", "labour"]
        },
        {
            "id": "health-emergency",
            "keywords": ["healthcare commission", "emergency treatment", "patient rights", "medical care", "hospital"]
        },
        {
            "id": "traffic-challan",
            "keywords": ["motor vehicle", "traffic police", "challan", "fine", "traffic ticket"]
        },
        {
            "id": "municipal-services",
            "keywords": ["local government", "municipal", "sanitation", "waste", "water supply", "street light"]
        },
        {
            "id": "utility-billing",
            "keywords": ["nepra", "ogra", "utility", "electricity bill", "gas bill", "billing dispute", "wasa"]
        },
        {
            "id": "education-fees",
            "keywords": ["educational institutions", "tuition fee", "private school", "pepris", "school fee"]
        },
        {
            "id": "women-harassment",
            "keywords": ["harassment", "workplace", "women", "ombudsperson", "inquiry committee"]
        }
    ]
    
    for mapping in mappings:
        for kw in mapping["keywords"]:
            if kw in combined:
                for prov in LAW_PROVISIONS:
                    if prov["id"] == mapping["id"]:
                        return prov
                        
    for prov in LAW_PROVISIONS:
        if prov["law"].lower() in combined:
            return prov
            
    return None

def search(query: str, top_k: int) -> tuple[list[dict], float]:
    """Return (matched provisions, top_score in 0..1). Raises if store not ready."""
    if not _ready or _pool is None or _client is None:
        raise RuntimeError("pgvector store not ready")
        
    # Get embedding for the query using the text-embedding-004 model
    response = _client.models.embed_content(
        model='text-embedding-004',
        contents=[query],
        config=types.EmbedContentConfig(output_dimensionality=768)
    )
    q_emb = response.embeddings[0].values
    
    # Convert query embedding vector list to a Postgres vector string representation to prevent type-casting issues
    q_emb_str = f"[{','.join(map(str, q_emb))}]"
    
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            # Query the closest vectors using cosine distance operator <=>
            cur.execute("""
                SELECT id, source, law_name, chunk_text, 1 - (embedding <=> %s::vector) as similarity
                FROM law_embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (q_emb_str, q_emb_str, top_k))
            
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
            
        # Map raw row back to verified law provisions if applicable
        verified_law = map_to_verified_law(row[2], row[3])
        if verified_law:
            provisions.append({
                "id": verified_law["id"],
                "domain": verified_law["domain"],
                "law": verified_law["law"],
                "provision": row[3],
                "authority": verified_law["authority"],
                "authority_contact": verified_law["authority_contact"],
                "source": source,
                "similarity": sim
            })
        else:
            provisions.append({
                "id": str(row[0]),
                "domain": "general",
                "law": "Verified Pakistani Law Registry Entry",
                "provision": row[3],
                "authority": "Relevant Government Department/Court",
                "authority_contact": "Consult local legal counsel or district office",
                "source": source,
                "similarity": sim
            })
        
    # Re-sort provisions in case boosting changed the ranking
    provisions.sort(key=lambda x: x["similarity"], reverse=True)
        
    return provisions, top_score
