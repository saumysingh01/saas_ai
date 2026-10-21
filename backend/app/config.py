from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_base_url: str = "http://127.0.0.1:5500"

    # Comma-separated origins, parsed into a list
    cors_origins: str = "http://localhost:3000"

    # LLM provider (Groq / Llama)
    groq_api_key: str
    groq_model_name: str = "groq/llama-3.3-70b-versatile"

    # Search tool
    serper_api_key: str

    # Supabase
    supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: str

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
