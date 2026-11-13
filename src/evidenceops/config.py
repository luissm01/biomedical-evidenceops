from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, SecretStr, TypeAdapter, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_POSTGRES_DSN = TypeAdapter(PostgresDsn)


class GenerationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVIDENCEOPS_",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    llm_provider: Literal["gemini", "deepseek"] = "gemini"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(default="gemini-3.6-flash", min_length=1)
    gemini_max_output_tokens: int = Field(default=2048, gt=0)
    gemini_timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)

    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = Field(default="deepseek-flash", min_length=1)
    deepseek_max_output_tokens: int = Field(default=2048, gt=0)
    deepseek_timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    # Wall-clock budget for one generate() call, SDK retries included (D037).
    # The transport timeout above applies per HTTP operation, not in total.
    llm_total_timeout_seconds: float = Field(default=90.0, gt=0, allow_inf_nan=False)

    @property
    def selected_model(self) -> str:
        return self.gemini_model if self.llm_provider == "gemini" else self.deepseek_model

    @property
    def selected_max_output_tokens(self) -> int:
        return (self.gemini_max_output_tokens if self.llm_provider == "gemini"
                else self.deepseek_max_output_tokens)

    @property
    def selected_timeout_seconds(self) -> float:
        return (self.gemini_timeout_seconds if self.llm_provider == "gemini"
                else self.deepseek_timeout_seconds)

    @field_validator("gemini_model", "deepseek_model", mode="before")
    @classmethod
    def strip_model(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("gemini_api_key", "deepseek_api_key")
    @classmethod
    def normalize_empty_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return value


class Settings(GenerationSettings):
    # Secret: the URL usually embeds the database password (D037).
    database_url: SecretStr
    database_connect_timeout_seconds: int = Field(default=5, ge=2, le=60)
    database_statement_timeout_ms: int = Field(default=30_000, ge=100, le=600_000)
    trace_console: bool = False
    retrieval_mode: Literal["semantic", "hybrid", "reranking"] = "semantic"
    # Comma-separated in the environment; required by the API at startup.
    api_keys: Annotated[tuple[SecretStr, ...], NoDecode] = ()
    rate_limit_capacity: int = Field(default=5, ge=1, le=1000)
    rate_limit_refill_per_second: float = Field(default=0.1, gt=0, le=100, allow_inf_nan=False)

    @field_validator("database_url")
    @classmethod
    def require_psycopg_driver(cls, database_url: SecretStr) -> SecretStr:
        try:
            dsn = _POSTGRES_DSN.validate_python(database_url.get_secret_value())
        except ValidationError:
            # Never chain or echo the original error: it would contain the URL.
            raise ValueError("database URL must be a valid PostgreSQL URL") from None
        if dsn.scheme != "postgresql+psycopg":
            raise ValueError("database URL must use the postgresql+psycopg scheme")
        return database_url

    @field_validator("api_keys", mode="before")
    @classmethod
    def split_api_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(key.strip() for key in value.split(",") if key.strip())
        return value

    @field_validator("api_keys")
    @classmethod
    def require_strong_api_keys(cls, keys: tuple[SecretStr, ...]) -> tuple[SecretStr, ...]:
        if any(len(key.get_secret_value()) < 16 for key in keys):
            raise ValueError("API keys must have at least 16 characters")
        return keys

    @property
    def database_dsn(self) -> str:
        """Plain URL for engine creation only; never log or render it."""
        return self.database_url.get_secret_value()


class PubMedSettings(BaseSettings):
    """Settings for the standalone PubMed adapter; no database is required."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVIDENCEOPS_PUBMED_",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    api_key: SecretStr | None = None
    email: str | None = None
    tool: str = Field(default="EvidenceOps", pattern=r"^[A-Za-z0-9_.-]+$")
    timeout_seconds: float = Field(default=15.0, gt=0, allow_inf_nan=False)

    @field_validator("api_key")
    @classmethod
    def normalize_empty_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if "@" not in value or any(char.isspace() for char in value):
            raise ValueError("PubMed email must be a contact email address")
        return value


class JobSettings(BaseSettings):
    """Queue and worker policy; independent of LLM and PubMed settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVIDENCEOPS_JOBS_",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    # Copied into each job at enqueue time: changing it never alters queued jobs.
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_base_seconds: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    backoff_max_seconds: float = Field(default=300.0, gt=0, allow_inf_nan=False)
    # Must exceed the longest expected job; there is no heartbeat (D036).
    lease_seconds: float = Field(default=300.0, gt=0, allow_inf_nan=False)
    poll_seconds: float = Field(default=2.0, gt=0, allow_inf_nan=False)
    # Cap for the exponential wait after consecutive polling failures (M11.2).
    poll_backoff_max_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)
