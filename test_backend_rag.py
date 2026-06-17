import os
import sys
from dotenv import load_dotenv

# Load backend environment variables
load_dotenv()

# Add backend directory to sys.path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core import pgvector_store
from app.core.config import get_settings

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
    print(f"\nSearching database for query: '{query}'...")
    try:
        provisions, top_score = pgvector_store.search(query, top_k=3)
        print(f"\nTop Search Score: {top_score:.4f}")
        print(f"Retrieved {len(provisions)} provisions:")
        for idx, p in enumerate(provisions):
            print(f"\n[{idx+1}] Law: {p['law']} (Score/Similarity: {p.get('similarity', 0.0):.4f})")
            print(f"    Authority: {p['authority']}")
            print(f"    Contact: {p.get('authority_contact', '')}")
            print(f"    Provision snippet: {p['provision'][:300].strip()}...")
            print("-" * 60)
    except Exception as e:
        print("❌ Search failed:", e)

if __name__ == "__main__":
    run_test()
