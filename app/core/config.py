"""Application configuration loaded from environment / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    primary_model: str = "gemini-3.5-flash"
    fallback_model: str = "gemini-3.1-flash-lite"
    embedding_model: str = "gemini-embedding-001"
    allowed_origins: str = "http://localhost:3000"
    app_name: str = "HaqDar AI"
    api_prefix: str = "/api/v1"
    # Public base URL of THIS server (e.g. https://haqdar-ai.onrender.com).
    # Used to build absolute links to generated PDFs so Twilio can fetch them.
    public_base_url: str = "https://haqdar-ai.onrender.com"
    # Twilio creds — needed to download WhatsApp voice-note media.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""

    # RAG / retrieval
    use_vector_store: bool = True
    retrieval_top_k: int = 3
    retrieval_min_score: float = 0.55  # below this -> low-confidence signal
    chroma_path: str = "./chroma_store"
    reports_db_path: str = "./data/reports.db"
    database_url: str = ""

    # Knowledge provenance (shown on every response)
    db_version: str = "June 2026"
    last_legal_review: str = "2026-06-10"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
