import os
import sys
from dotenv import load_dotenv

# Load backend environment variables
load_dotenv()

# Add backend directory to sys.path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core import pgvector_store
from app.core.config import get_settings
from app.services.retrieval_service import retrieve

def run_test():
    print("Initializing settings...")
    settings = get_settings()
    if not settings.database_url:
        print("❌ DATABASE_URL not set in .env!")
        return
        
    print(f"DATABASE_URL: {settings.database_url[:35]}... (length: {len(settings.database_url)})")
    
    print("\nInitializing pgvector store...")
    pgvector_store.init_store()
    
    if not pgvector_store.is_ready():
        print("❌ pgvector store failed to initialize!")
        return
        
    print("✅ pgvector store is ready.")
    
    query = "police ny rishwat mangee. mein ny nahi dee to maar parhee."
    print(f"\nCalling retrieve() for query: '{query}'...")
    try:
        retrieval = retrieve(query)
        print(f"\nRetrieval Source: {retrieval.source}")
        print(f"Top Score: {retrieval.top_score:.4f}")
        print(f"Total provisions retrieved: {len(retrieval.provisions)}")
        
        print("\n--- Provisions List ---")
        for idx, p in enumerate(retrieval.provisions):
            print(f"\n[{idx+1}] Law: {p['law']} (Source: {p.get('source', 'unknown')})")
            print(f"    Provision snippet: {p['provision'][:150].strip()}...")
            
    except Exception as e:
        print("❌ Retrieval failed:", e)

if __name__ == "__main__":
    run_test()
