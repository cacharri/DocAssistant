from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="DocAssistant", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    # RAG / Retrieval settings
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL_NAME",
    )
    index_dir: str = Field(default="data/index", alias="INDEX_DIR")
    top_k: int = Field(default=5, alias="TOP_K")

    # NEW: separate thresholds
    min_top_score: float = Field(default=0.80, alias="MIN_TOP_SCORE")
    min_top_score_margin: float = Field(default=0.05, alias="MIN_TOP_SCORE_MARGIN")
    min_row_score: float = Field(default=0.30, alias="MIN_ROW_SCORE")
    min_score_gap: float = Field(default=0.02, alias="MIN_SCORE_GAP")

    debug_rag: bool = Field(default=False, alias="DEBUG_RAG")
    search_candidates_k: int = Field(default=15, alias="SEARCH_CANDIDATES_K")
    max_citations: int = Field(default=5, alias="MAX_CITATIONS")


settings = Settings()