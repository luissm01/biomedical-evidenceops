from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVIDENCEOPS_",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    database_url: PostgresDsn
    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(default="gemini-3.6-flash", min_length=1)
    gemini_max_output_tokens: int = Field(default=2048, gt=0)
    gemini_timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)

    @field_validator("gemini_model", mode="before")
    @classmethod
    def strip_model(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("gemini_api_key")
    @classmethod
    def normalize_empty_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return value

    @field_validator("database_url")
    @classmethod
    def require_psycopg_driver(cls, database_url: PostgresDsn) -> PostgresDsn:
        if database_url.scheme != "postgresql+psycopg":
            raise ValueError("database URL must use the postgresql+psycopg scheme")
        return database_url
