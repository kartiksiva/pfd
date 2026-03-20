from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Process Documentation Agent API", alias="APP_NAME")
    env: str = Field(default="development", alias="ENV")
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    default_provider: str = Field(default="google", alias="DEFAULT_PROVIDER")
    default_processing_profile: str = Field(default="balanced", alias="DEFAULT_PROCESSING_PROFILE")

    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    azure_openai_api_key: Optional[str] = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = Field(default="2024-10-21", alias="AZURE_OPENAI_API_VERSION")
    azure_openai_mode: str = Field(default="auto", alias="AZURE_OPENAI_MODE")
    azure_openai_chat_deployment: Optional[str] = Field(default=None, alias="AZURE_OPENAI_CHAT_DEPLOYMENT")
    azure_openai_transcription_deployment: Optional[str] = Field(
        default=None,
        alias="AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT",
    )
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3-vl:8b", alias="OLLAMA_MODEL")
    llm_enabled: bool = Field(default=True, alias="LLM_ENABLED")

    database_url: str = Field(default="sqlite:///./pfcd.db", alias="DATABASE_URL")
    uploads_dir: str = Field(default="./uploads", alias="UPLOADS_DIR")
    exports_dir: str = Field(default="./exports", alias="EXPORTS_DIR")
    retention_days: int = Field(default=7, alias="RETENTION_DAYS")
    retention_sweep_seconds: int = Field(default=300, alias="RETENTION_SWEEP_SECONDS")
    max_job_duration_seconds: int = Field(default=7200, alias="MAX_JOB_DURATION_SECONDS")
    max_provider_tokens: int = Field(default=1500000, alias="MAX_PROVIDER_TOKENS")
    cost_band_min_usd: float = Field(default=2.0, alias="COST_BAND_MIN_USD")
    cost_band_max_usd: float = Field(default=8.0, alias="COST_BAND_MAX_USD")
    transcript_media_check_enabled: bool = Field(default=True, alias="TRANSCRIPT_MEDIA_CHECK_ENABLED")
    transcript_media_sample_seconds: int = Field(default=60, alias="TRANSCRIPT_MEDIA_SAMPLE_SECONDS")
    transcript_media_min_transcript_chars: int = Field(default=200, alias="TRANSCRIPT_MEDIA_MIN_TRANSCRIPT_CHARS")
    transcript_media_match_threshold: float = Field(default=0.80, alias="TRANSCRIPT_MEDIA_MATCH_THRESHOLD")
    transcript_media_mismatch_threshold: float = Field(default=0.30, alias="TRANSCRIPT_MEDIA_MISMATCH_THRESHOLD")
    task_runner: str = Field(default="inprocess", alias="TASK_RUNNER")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    owner_access_code: str = Field(default="PFCD-OWNER-7429", alias="OWNER_ACCESS_CODE")
    guest_access_code: str = Field(default="PFCD-GUEST-3184", alias="GUEST_ACCESS_CODE")
    guest_access_timeout_minutes: int = Field(default=30, alias="GUEST_ACCESS_TIMEOUT_MINUTES")
    access_session_secret: str = Field(default="change-this-demo-secret", alias="ACCESS_SESSION_SECRET")
    access_cookie_name: str = Field(default="pfcd_access_session", alias="ACCESS_COOKIE_NAME")
    access_cookie_secure: bool = Field(default=False, alias="ACCESS_COOKIE_SECURE")
    allowed_origins: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        alias="ALLOWED_ORIGINS",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
