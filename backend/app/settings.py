from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_api_key: str = "lm-studio"
    lmstudio_model: str = "local-model"
    lmstudio_embedding_model: str = "text-embedding-model"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_embedding_model: str = "nomic-embed-text"
    chroma_persist_dir: str = ".chroma"
    it_knowledge_dir: str = "data/it_knowledge"
    frontend_origin: str = "http://localhost:5173"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def knowledge_path(self) -> Path:
        return (self.backend_root / self.it_knowledge_dir).resolve()

    @property
    def chroma_path(self) -> Path:
        return (self.backend_root / self.chroma_persist_dir).resolve()

    @property
    def allowed_frontend_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]
        if self.frontend_origin and self.frontend_origin not in origins:
            origins.append(self.frontend_origin)
        return origins

    @property
    def normalized_llm_provider(self) -> str:
        return self.llm_provider.strip().lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()
